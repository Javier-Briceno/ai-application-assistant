"""
Regression tests for the Verlauf history API serialization.

V1 — api_list_applications returns the anschreiben field for every row
V2 — Each row carries its own independent anschreiben value (no shared reference)
V3 — api_list_applications returns all required fields for the detail panel
V4 — Rows are ordered by date_applied DESC (newest first, matching UI auto-select)
"""
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_row(id: int, anschreiben: str, date_applied=None) -> MagicMock:
    """Build a minimal asyncpg-row-like mock for job_applications."""
    row = MagicMock()
    row.__getitem__ = lambda self, k: {
        "id": id,
        "profile_id": 1,
        "company": f"Company {id}",
        "role_title": f"Role {id}",
        "score": 70,
        "threshold": "pass",
        "date_applied": date_applied or datetime(2024, 6, 1, tzinfo=timezone.utc),
        "cv_diff": "",
        "anschreiben": anschreiben,
        "gaps": "",
        "scoring_details": json.dumps({}),
        "has_tailored_cv": True,
    }[k]
    return row


# ── V1: anschreiben field is present in every serialised row ──────────────────

@pytest.mark.asyncio
async def test_list_applications_includes_anschreiben_field():
    from backend.api.applications import api_list_applications

    rows = [
        _make_row(1, "Bewerbung als Python-Entwickler..."),
        _make_row(2, "Bewerbung als Data Scientist..."),
    ]
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=rows)

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_get_conn():
        yield mock_conn

    with patch("backend.api.applications.get_conn", fake_get_conn):
        result = await api_list_applications(profile_id=1)

    assert len(result) == 2
    for item in result:
        assert "anschreiben" in item, "Each application row must expose the 'anschreiben' field"


# ── V2: Each row carries its own distinct anschreiben value ──────────────────

@pytest.mark.asyncio
async def test_list_applications_anschreiben_values_are_per_row():
    from backend.api.applications import api_list_applications

    letter_48 = "Bewerbung als Werkstudent KI & Digitalisierung bei Prange Pharma"
    letter_47 = "Bewerbung als Werkstudent KI – Analyse bei Mercedes-Benz"
    letter_46 = "Bewerbung als Werkstudent KI/NLP bei VDM Metals"

    rows = [
        _make_row(48, letter_48),
        _make_row(47, letter_47),
        _make_row(46, letter_46),
    ]
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=rows)

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_get_conn():
        yield mock_conn

    with patch("backend.api.applications.get_conn", fake_get_conn):
        result = await api_list_applications(profile_id=1)

    by_id = {r["id"]: r for r in result}
    assert by_id[48]["anschreiben"] == letter_48
    assert by_id[47]["anschreiben"] == letter_47
    assert by_id[46]["anschreiben"] == letter_46
    # All three are distinct — no cross-contamination
    assert len({by_id[i]["anschreiben"] for i in (46, 47, 48)}) == 3


# ── V3: All fields required by the Verlauf detail panel are present ───────────

@pytest.mark.asyncio
async def test_list_applications_returns_all_detail_panel_fields():
    from backend.api.applications import api_list_applications

    required_fields = {
        "id", "profile_id", "company", "role_title", "score", "threshold",
        "date_applied", "cv_diff", "anschreiben", "gaps", "scoring_details",
        "has_tailored_cv",
    }
    rows = [_make_row(1, "letter")]
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=rows)

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_get_conn():
        yield mock_conn

    with patch("backend.api.applications.get_conn", fake_get_conn):
        result = await api_list_applications(profile_id=1)

    assert len(result) == 1
    missing = required_fields - result[0].keys()
    assert not missing, f"API response missing fields needed by Verlauf panel: {missing}"


# ── V4: Rows arrive newest-first (matches UI auto-select of apps[0]) ──────────

@pytest.mark.asyncio
async def test_list_applications_returns_rows_in_db_order():
    """The API preserves the DB ORDER BY date_applied DESC ordering.
    VerlaufPage auto-selects apps[0] — so the newest must come first.
    """
    from backend.api.applications import api_list_applications

    newer = _make_row(10, "newer letter", datetime(2024, 6, 1, tzinfo=timezone.utc))
    older = _make_row(9,  "older letter", datetime(2024, 1, 1, tzinfo=timezone.utc))

    # DB already returns them DESC — API must preserve that order
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[newer, older])

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_get_conn():
        yield mock_conn

    with patch("backend.api.applications.get_conn", fake_get_conn):
        result = await api_list_applications(profile_id=1)

    assert result[0]["id"] == 10, "Newest application must be first (apps[0] is auto-selected)"
    assert result[1]["id"] == 9
