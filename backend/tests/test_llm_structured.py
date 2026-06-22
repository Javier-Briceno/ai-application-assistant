"""
Tests for the Analyzer retry fix: call_structured() now uses OpenAI's native
structured-output parse API for non-Claude models.

S1 — OpenAI models call chat.completions.parse, not call_raw
S2 — Claude models use manual schema-in-prompt (call_raw), not parse
S3 — OpenAI native path logs model/node/profile/tokens/cost/latency correctly
S4 — OpenAI native parse failure falls back to manual path (call_raw)
S5 — Parse failure warning does not contain prompt or raw-response content
S6 — OpenAI native path passes the original user message unchanged (no schema appended)
"""
import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel, Field


class _Simple(BaseModel):
    value: int = Field(ge=0, le=10)
    label: str


def _parse_resp(parsed_obj, in_tok: int = 100, out_tok: int = 50) -> MagicMock:
    """Minimal stand-in for a ParsedChatCompletion object."""
    resp = MagicMock()
    resp.choices[0].message.parsed = parsed_obj
    resp.usage.prompt_tokens = in_tok
    resp.usage.completion_tokens = out_tok
    return resp


# ── S1: OpenAI path calls parse, not call_raw ─────────────────────────────────

@pytest.mark.asyncio
async def test_openai_uses_native_parse_not_call_raw():
    from backend.llm import call_structured

    expected = _Simple(value=5, label="native")

    with (
        patch("backend.llm._openai") as mock_client,
        patch("backend.llm.call_raw") as mock_call_raw,
        patch("backend.llm._log", AsyncMock()),
        patch("backend.llm._compute_cost", AsyncMock(return_value=0.001)),
    ):
        mock_client.chat.completions.parse = AsyncMock(
            return_value=_parse_resp(expected)
        )

        result = await call_structured(
            MagicMock(),
            model="gpt-4.1",
            system="system prompt",
            user="user message",
            response_model=_Simple,
            node_name="test_node",
        )

    assert result == expected
    mock_client.chat.completions.parse.assert_awaited_once()
    mock_call_raw.assert_not_called()


# ── S2: Claude path uses manual schema, not native parse ─────────────────────

@pytest.mark.asyncio
async def test_claude_uses_manual_schema_not_native_parse():
    from backend.llm import call_structured

    valid_json = json.dumps({"value": 3, "label": "manual"})

    with (
        patch("backend.llm._openai") as mock_client,
        patch("backend.llm.call_raw", AsyncMock(return_value=valid_json)) as mock_call_raw,
        patch("backend.llm._compute_cost", AsyncMock(return_value=0.0)),
        patch("backend.llm._log", AsyncMock()),
    ):
        result = await call_structured(
            MagicMock(),
            model="claude-sonnet-4-6",
            system="system prompt",
            user="user message",
            response_model=_Simple,
            node_name="test_node",
        )

    assert result.value == 3
    assert result.label == "manual"
    mock_client.chat.completions.parse.assert_not_called()
    # Schema instruction must be appended to the user message
    actual_user = mock_call_raw.call_args.kwargs["user"]
    assert "Respond with ONLY a valid JSON object" in actual_user
    assert "user message" in actual_user  # original content preserved


# ── S3: OpenAI native path logs all required fields ──────────────────────────

@pytest.mark.asyncio
async def test_openai_native_logs_model_node_profile_tokens_cost_latency():
    from backend.llm import call_structured

    expected = _Simple(value=7, label="logged")
    mock_log = AsyncMock()
    mock_cost = AsyncMock(return_value=0.0025)

    with (
        patch("backend.llm._openai") as mock_client,
        patch("backend.llm._log", mock_log),
        patch("backend.llm._compute_cost", mock_cost),
    ):
        mock_client.chat.completions.parse = AsyncMock(
            return_value=_parse_resp(expected, in_tok=200, out_tok=80)
        )

        await call_structured(
            MagicMock(),
            model="gpt-4.1",
            system="system",
            user="user",
            response_model=_Simple,
            node_name="analyzer",
            profile_id=99,
        )

    mock_log.assert_awaited_once()
    kw = mock_log.call_args.kwargs
    assert kw["model"] == "gpt-4.1"
    assert kw["node_name"] == "analyzer"
    assert kw["profile_id"] == 99
    assert kw["input_tokens"] == 200
    assert kw["output_tokens"] == 80
    assert kw["cost_usd"] == 0.0025
    assert kw["latency_ms"] >= 0


# ── S4: OpenAI native failure falls back to manual path ──────────────────────

@pytest.mark.asyncio
async def test_openai_native_failure_falls_back_to_manual_path():
    from backend.llm import call_structured

    valid_json = json.dumps({"value": 2, "label": "fallback"})

    with (
        patch("backend.llm._openai") as mock_client,
        patch("backend.llm.call_raw", AsyncMock(return_value=valid_json)) as mock_call_raw,
        patch("backend.llm._compute_cost", AsyncMock(return_value=0.0)),
        patch("backend.llm._log", AsyncMock()),
    ):
        mock_client.chat.completions.parse = AsyncMock(
            side_effect=Exception("openai rate limited")
        )

        result = await call_structured(
            MagicMock(),
            model="gpt-4.1",
            system="system",
            user="user",
            response_model=_Simple,
            node_name="test_node",
        )

    assert result.value == 2
    assert result.label == "fallback"
    mock_call_raw.assert_called_once()


# ── S5: Parse failure warnings must not leak prompt or response content ───────

@pytest.mark.asyncio
async def test_parse_failure_warning_does_not_log_prompt_content():
    from backend.llm import call_structured

    secret = "SEKRIT_PROMPT_XYZ_DO_NOT_LOG"
    bad_json = "not json at all"

    captured: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record.getMessage())

    handler = _Capture()
    import backend.llm as _llm_mod
    llm_logger = logging.getLogger(_llm_mod.__name__)
    llm_logger.addHandler(handler)
    original_level = llm_logger.level
    llm_logger.setLevel(logging.WARNING)

    try:
        with (
            patch("backend.llm._openai") as mock_client,
            patch("backend.llm.call_raw", AsyncMock(return_value=bad_json)),
            patch("backend.llm._compute_cost", AsyncMock(return_value=0.0)),
            patch("backend.llm._log", AsyncMock()),
        ):
            # Native parse fails → manual path → bad JSON fails → raises
            mock_client.chat.completions.parse = AsyncMock(
                side_effect=Exception("native api error")
            )
            with pytest.raises(ValueError):
                await call_structured(
                    MagicMock(),
                    model="gpt-4.1",
                    system=secret,
                    user=secret,
                    response_model=_Simple,
                    node_name="test_node",
                    max_retries=0,
                )
    finally:
        llm_logger.setLevel(original_level)
        llm_logger.removeHandler(handler)

    assert captured, "Expected at least one warning to be logged"
    for msg in captured:
        assert secret not in msg, f"Prompt content leaked in log message: {msg!r}"


# ── S6: OpenAI native path passes user message unchanged ─────────────────────

@pytest.mark.asyncio
async def test_openai_native_does_not_append_schema_to_user_message():
    from backend.llm import call_structured

    expected = _Simple(value=1, label="clean")
    original_user = "original user message — no schema please"
    received_messages: list[list] = []

    async def _spy_parse(**kwargs):
        received_messages.append(list(kwargs.get("messages", [])))
        return _parse_resp(expected)

    with (
        patch("backend.llm._openai") as mock_client,
        patch("backend.llm._log", AsyncMock()),
        patch("backend.llm._compute_cost", AsyncMock(return_value=0.001)),
    ):
        mock_client.chat.completions.parse = _spy_parse

        await call_structured(
            MagicMock(),
            model="gpt-4.1",
            system="system",
            user=original_user,
            response_model=_Simple,
            node_name="test_node",
        )

    assert received_messages, "parse() was never called"
    user_msgs = [m for m in received_messages[0] if m.get("role") == "user"]
    assert user_msgs, "No user message found in parse() call"
    assert user_msgs[0]["content"] == original_user
    assert "Respond with ONLY a valid JSON object" not in user_msgs[0]["content"]
