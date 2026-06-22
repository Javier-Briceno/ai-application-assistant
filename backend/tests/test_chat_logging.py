"""
Tests for LLM observability patch — chat logging.

C1 — _stream_chat yields all deltas AND calls log_call with exact token counts
C2 — _stream_chat yields all deltas even when the DB logging step raises
"""
import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Fake Anthropic streaming helpers ─────────────────────────────────────────

class _FakeUsage:
    def __init__(self, inp: int, out: int) -> None:
        self.input_tokens = inp
        self.output_tokens = out


class _FakeFinalMessage:
    def __init__(self, inp: int, out: int) -> None:
        self.usage = _FakeUsage(inp, out)


class _FakeTextStream:
    def __init__(self, texts: list[str]) -> None:
        self._iter = iter(texts)

    def __aiter__(self):
        return self

    async def __anext__(self) -> str:
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class _FakeStream:
    """Minimal stand-in for the object returned by _anthropic.messages.stream()."""

    def __init__(self, texts: list[str], in_tok: int = 100, out_tok: int = 50) -> None:
        self.text_stream = _FakeTextStream(texts)
        self._msg = _FakeFinalMessage(in_tok, out_tok)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get_final_message(self):
        return self._msg


async def _drain(gen) -> list[str]:
    chunks: list[str] = []
    async for chunk in gen:
        chunks.append(chunk)
    return chunks


# ── C1: yields deltas and logs with correct token counts ─────────────────────

@pytest.mark.asyncio
async def test_chat_stream_yields_deltas_and_logs_usage():
    """_stream_chat must yield all SSE chunks and call log_call with the right kwargs."""
    from backend.api.chat import _stream_chat

    fake_conn = MagicMock()

    @asynccontextmanager
    async def fake_get_conn():
        yield fake_conn

    fake_stream = _FakeStream(["Hello", " world"], in_tok=120, out_tok=60)
    mock_log = AsyncMock()

    with (
        patch("backend.api.chat._anthropic") as mock_client,
        patch("backend.api.chat.get_conn", fake_get_conn),
        patch("backend.api.chat.log_call", mock_log),
    ):
        mock_client.messages.stream.return_value = fake_stream
        chunks = await _drain(_stream_chat([{"role": "user", "content": "hi"}], "system"))

    assert len(chunks) == 2
    assert json.loads(chunks[0].removeprefix("data: ").strip()) == {"delta": "Hello"}
    assert json.loads(chunks[1].removeprefix("data: ").strip()) == {"delta": " world"}

    mock_log.assert_awaited_once()
    kwargs = mock_log.call_args.kwargs
    assert kwargs["node_name"] == "chat"
    assert kwargs["model"] == "claude-haiku-4-5-20251001"
    assert kwargs["input_tokens"] == 120
    assert kwargs["output_tokens"] == 60
    assert kwargs["profile_id"] is None


# ── C2: logging failure must not break the stream ────────────────────────────

@pytest.mark.asyncio
async def test_chat_stream_continues_when_logging_fails():
    """If DB logging raises, _stream_chat must still yield all deltas to the caller."""
    from backend.api.chat import _stream_chat

    fake_stream = _FakeStream(["Hallo", " Welt"], in_tok=80, out_tok=30)

    @asynccontextmanager
    async def broken_get_conn():
        raise Exception("DB unreachable")
        yield  # noqa: unreachable — required for @asynccontextmanager

    with (
        patch("backend.api.chat._anthropic") as mock_client,
        patch("backend.api.chat.get_conn", broken_get_conn),
    ):
        mock_client.messages.stream.return_value = fake_stream
        chunks = await _drain(_stream_chat([{"role": "user", "content": "hi"}], "system"))

    assert len(chunks) == 2
    assert '"delta": "Hallo"' in chunks[0]
    assert '"delta": " Welt"' in chunks[1]
