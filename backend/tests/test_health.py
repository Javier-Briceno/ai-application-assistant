"""
Tests for production-readiness patch:
  H1 — /api/health returns 200 {"status": "ok", "db": "connected"} when DB reachable
  H2 — /api/health returns 503 {"status": "degraded", "db": "unreachable"} when DB down
  H3a — ping_db() returns False (never raises) when get_pool() fails
  H3b — ping_db() returns False (never raises) when conn.execute() fails
  H4 — SSE error path hides internal exception text (asyncpg/API details)
  H5 — SSE error path passes UserVisibleError message through unchanged
"""
import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


async def _drain_sse(response) -> list[dict]:
    """Collect all SSE events from a StreamingResponse body iterator."""
    events: list[dict] = []
    async for chunk in response.body_iterator:
        text = chunk.decode() if isinstance(chunk, bytes) else chunk
        for line in text.split("\n"):
            if line.startswith("data: "):
                try:
                    events.append(json.loads(line[6:]))
                except json.JSONDecodeError:
                    pass
    return events


# ── H1: health ok ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_ok_when_db_reachable():
    from backend.main import health

    with patch("backend.main.ping_db", new=AsyncMock(return_value=True)):
        response = await health()

    assert response == {"status": "ok", "db": "connected"}


# ── H2: health degraded ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_degraded_when_db_unreachable():
    from fastapi.responses import JSONResponse
    from backend.main import health

    with patch("backend.main.ping_db", new=AsyncMock(return_value=False)):
        response = await health()

    assert isinstance(response, JSONResponse)
    assert response.status_code == 503
    body = json.loads(response.body)
    assert body["status"] == "degraded"
    assert body["db"] == "unreachable"


# ── H3a: ping_db does not raise on pool failure ───────────────────────────────

@pytest.mark.asyncio
async def test_ping_db_returns_false_not_raises_on_pool_error():
    """ping_db must return False (never raise) when get_pool() itself fails."""
    from backend.db import ping_db

    with patch("backend.db.get_pool", new=AsyncMock(side_effect=Exception("cannot connect to DB"))):
        result = await ping_db()

    assert result is False


# ── H3b: ping_db does not raise on execute failure ────────────────────────────

@pytest.mark.asyncio
async def test_ping_db_returns_false_not_raises_on_execute_error():
    """ping_db must return False (never raise) when conn.execute('SELECT 1') fails."""
    from backend.db import ping_db

    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock(side_effect=Exception("SSL connection has been closed unexpectedly"))

    class FakeAcquire:
        async def __aenter__(self):
            return mock_conn
        async def __aexit__(self, *args):
            return False

    mock_pool = MagicMock()
    mock_pool.acquire.return_value = FakeAcquire()

    with patch("backend.db.get_pool", new=AsyncMock(return_value=mock_pool)):
        result = await ping_db()

    assert result is False


# ── H4: SSE error hides internal details ─────────────────────────────────────

@pytest.mark.asyncio
async def test_sse_error_hides_internal_exception_text():
    """Raw exception text from asyncpg or other internal errors must not reach the frontend."""
    from backend.api.analyze import AnalyzeRequest, api_analyze

    @asynccontextmanager
    async def failing_get_conn():
        raise RuntimeError("asyncpg: password authentication failed for user admin DB=projects")
        yield  # noqa: unreachable — required for asynccontextmanager

    req = AnalyzeRequest(profile_id=1, job_posting="some job posting text")
    with patch("backend.api.analyze.get_conn", failing_get_conn):
        response = await api_analyze(req)
        events = await _drain_sse(response)

    error_events = [e for e in events if e.get("type") == "error"]
    assert error_events, "Expected at least one SSE error event"
    msg = error_events[0]["message"]
    assert "asyncpg" not in msg, f"Internal detail leaked in message: {msg!r}"
    assert "password" not in msg, f"Internal detail leaked in message: {msg!r}"
    assert "admin" not in msg, f"Internal detail leaked in message: {msg!r}"
    assert "DB=projects" not in msg, f"Internal detail leaked in message: {msg!r}"


# ── H5: UserVisibleError passes through SSE ──────────────────────────────────

@pytest.mark.asyncio
async def test_sse_error_passes_through_user_visible_error():
    """UserVisibleError messages (pipeline user-fixable conditions) must reach the frontend."""
    from backend.api.analyze import AnalyzeRequest, api_analyze
    from backend.exceptions import UserVisibleError

    @asynccontextmanager
    async def failing_get_conn():
        raise UserVisibleError("Kein Lebenslauf im Profil hinterlegt. Bitte Profil bearbeiten.")
        yield  # noqa: unreachable — required for asynccontextmanager

    req = AnalyzeRequest(profile_id=1, job_posting="some job posting text")
    with patch("backend.api.analyze.get_conn", failing_get_conn):
        response = await api_analyze(req)
        events = await _drain_sse(response)

    error_events = [e for e in events if e.get("type") == "error"]
    assert error_events, "Expected at least one SSE error event"
    msg = error_events[0]["message"]
    assert "Kein Lebenslauf" in msg, f"UserVisibleError message was not passed through: {msg!r}"
    assert "Bitte Profil bearbeiten" in msg
