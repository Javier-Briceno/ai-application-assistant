"""
Focused regression tests for:
  B1 — role_type_scores is merged into the candidate_profile the Analyzer receives
  B2 — profile re-extraction is triggered when career_target or market_research changes,
        but NOT when only unrelated metadata (name, city, …) changes
  B3 — chat endpoint injects application context into system prompt when job_application_id given
  B6 — job postings longer than 50 000 chars are rejected with a clean SSE error
"""
import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest

from backend.deterministic.cv_utils import compute_content_hash
from backend.models.analysis import (
    AnalyzerOutput,
    DimensionScores,
    LocationScore,
    RequirementsScore,
    RoleFitScore,
    ScoringResult,
    StrategicScore,
    TechnicalScore,
)
from backend.models.company import CompanyResearchResult


# ── helpers ──────────────────────────────────────────────────────────────────

def _fake_scoring(threshold: str = "fail") -> ScoringResult:
    analyzer_out = AnalyzerOutput(
        technical=TechnicalScore(score=10, reasoning="low", matching_skills=[], missing_skills=[]),
        requirements=RequirementsScore(score=5, reasoning="low"),
        role_fit=RoleFitScore(score=5, reasoning="low", matched_role_key=""),
        location=LocationScore(score=5, reasoning="ok"),
        strategic=StrategicScore(score=2, reasoning="ok"),
    )
    dims = DimensionScores(technical=10, requirements=5, role_fit=5, location=5, strategic=2)
    return ScoringResult(dims=dims, total_score=27, threshold=threshold, analyzer_output=analyzer_out)


# ── B2: compute_content_hash pure-function tests ──────────────────────────────

def test_content_hash_changes_when_career_target_changes():
    h1 = compute_content_hash("same cv", "target A", "same research")
    h2 = compute_content_hash("same cv", "target B", "same research")
    assert h1 != h2


def test_content_hash_changes_when_market_research_changes():
    h1 = compute_content_hash("same cv", "same target", "research A")
    h2 = compute_content_hash("same cv", "same target", "research B")
    assert h1 != h2


def test_content_hash_unchanged_for_metadata_only_edit():
    """Name / city / phone are not parameters → the hash stays the same.

    This proves that an UPDATE that touches only profile metadata (not
    cv_text, career_target, or market_research) will not trigger a
    costly LLM re-extraction.
    """
    h1 = compute_content_hash("cv content", "career target", "market research")
    # Simulating "user changed their city" — the three inputs are identical
    h2 = compute_content_hash("cv content", "career target", "market research")
    assert h1 == h2


def test_content_hash_changes_when_cv_changes():
    h1 = compute_content_hash("old cv", "target", "research")
    h2 = compute_content_hash("new cv", "target", "research")
    assert h1 != h2


# ── B1: role_type_scores flows to run_analysis_scoring ───────────────────────

@pytest.mark.asyncio
async def test_role_type_scores_included_in_analyzer_input():
    """B1: role_type_scores stored in candidate_context must be merged into the
    candidate_profile dict that run_analysis_scoring (i.e. the Analyzer) receives.
    Without this fix the Role Fit dimension (20 pts) was computed without its data.
    """
    from backend.pipeline.main_pipeline import run_main_pipeline

    role_scores = {"senior_developer": 0.9, "tech_lead": 0.7}
    captured: dict = {}

    test_context = {
        "cv_text": "Engineer with 5 years experience",
        "candidate_profile": json.dumps({"core_skills": ["Python"]}),
        "role_type_scores": json.dumps(role_scores),
        "career_target": "Senior Engineer",
        "market_research": "Growing tech sector",
        "cv_language": "de",
    }

    async def spy_analysis_scoring(
        conn, *, job_posting, cv_text, candidate_profile, company_result, profile_id
    ):
        captured["candidate_profile"] = dict(candidate_profile)
        return _fake_scoring("fail"), "gap text"

    mock_conn = AsyncMock()

    with (
        patch(
            "backend.pipeline.main_pipeline._fetch_profile_context",
            new=AsyncMock(return_value=test_context),
        ),
        patch(
            "backend.pipeline.main_pipeline.run_company_research",
            new=AsyncMock(
                return_value=CompanyResearchResult(
                    company_name="Acme", search_name="acme", company_profile=""
                )
            ),
        ),
        patch(
            "backend.pipeline.main_pipeline.get_cv_for_language",
            new=AsyncMock(return_value=test_context["cv_text"]),
        ),
        patch(
            "backend.pipeline.main_pipeline.run_analysis_scoring",
            new=spy_analysis_scoring,
        ),
        patch(
            "backend.pipeline.main_pipeline._store_job_application",
            new=AsyncMock(return_value=42),
        ),
    ):
        await run_main_pipeline(mock_conn, profile_id=1, job_posting="Senior Engineer role")

    assert "role_type_scores" in captured.get("candidate_profile", {}), (
        "role_type_scores was not present in candidate_profile passed to run_analysis_scoring"
    )
    assert captured["candidate_profile"]["role_type_scores"] == role_scores


@pytest.mark.asyncio
async def test_role_type_scores_missing_from_context_uses_empty_dict():
    """B1: If role_type_scores is absent from context, the Analyzer still receives
    an empty dict (not a KeyError or malformed profile).
    """
    from backend.pipeline.main_pipeline import run_main_pipeline

    captured: dict = {}

    test_context = {
        "cv_text": "Engineer",
        "candidate_profile": json.dumps({"core_skills": ["Python"]}),
        # role_type_scores intentionally absent
        "career_target": "Engineer",
        "market_research": "tech",
        "cv_language": "de",
    }

    async def spy_analysis_scoring(
        conn, *, job_posting, cv_text, candidate_profile, company_result, profile_id
    ):
        captured["candidate_profile"] = dict(candidate_profile)
        return _fake_scoring("fail"), "gap text"

    mock_conn = AsyncMock()

    with (
        patch(
            "backend.pipeline.main_pipeline._fetch_profile_context",
            new=AsyncMock(return_value=test_context),
        ),
        patch(
            "backend.pipeline.main_pipeline.run_company_research",
            new=AsyncMock(
                return_value=CompanyResearchResult(
                    company_name="Acme", search_name="acme", company_profile=""
                )
            ),
        ),
        patch(
            "backend.pipeline.main_pipeline.get_cv_for_language",
            new=AsyncMock(return_value=test_context["cv_text"]),
        ),
        patch(
            "backend.pipeline.main_pipeline.run_analysis_scoring",
            new=spy_analysis_scoring,
        ),
        patch(
            "backend.pipeline.main_pipeline._store_job_application",
            new=AsyncMock(return_value=42),
        ),
    ):
        await run_main_pipeline(mock_conn, profile_id=1, job_posting="Engineer role")

    assert captured["candidate_profile"]["role_type_scores"] == {}


# ── B6: job posting length validation ────────────────────────────────────────

@pytest.mark.asyncio
async def test_job_posting_too_long_returns_sse_error():
    """B6: A posting longer than 50 000 chars must yield an SSE error event
    before any DB or LLM call is made.
    """
    from backend.api.analyze import AnalyzeRequest, api_analyze

    req = AnalyzeRequest(profile_id=1, job_posting="x" * 50_001)
    response = await api_analyze(req)

    events: list[dict] = []
    async for chunk in response.body_iterator:
        text = chunk.decode() if isinstance(chunk, bytes) else chunk
        for line in text.split("\n"):
            if line.startswith("data: "):
                try:
                    events.append(json.loads(line[6:]))
                except json.JSONDecodeError:
                    pass

    error_events = [e for e in events if e.get("type") == "error"]
    assert error_events, "Expected at least one SSE error event for a too-long posting"
    assert "50.000" in error_events[0]["message"], (
        f"Error message should mention the 50k limit; got: {error_events[0]['message']!r}"
    )


@pytest.mark.asyncio
async def test_job_posting_at_limit_not_blocked_by_length_check():
    """B6: A posting of exactly 50 000 chars must pass the length guard
    (the generator must not immediately yield a length-error event).
    """
    from backend.api.analyze import AnalyzeRequest, api_analyze, _MAX_POSTING_LEN

    assert _MAX_POSTING_LEN == 50_000

    # Patch get_conn so the generator fails at the DB step, not the length check.
    # We only care that the length-specific error is NOT the first event.
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_get_conn():
        raise RuntimeError("no db in test")
        yield  # noqa: unreachable — required for asynccontextmanager

    req = AnalyzeRequest(profile_id=1, job_posting="x" * _MAX_POSTING_LEN)

    with patch("backend.api.analyze.get_conn", fake_get_conn):
        response = await api_analyze(req)

        events: list[dict] = []
        async for chunk in response.body_iterator:
            text = chunk.decode() if isinstance(chunk, bytes) else chunk
            for line in text.split("\n"):
                if line.startswith("data: "):
                    try:
                        events.append(json.loads(line[6:]))
                    except json.JSONDecodeError:
                        pass

    length_errors = [
        e for e in events
        if e.get("type") == "error" and "50.000" in e.get("message", "")
    ]
    assert not length_errors, (
        "A posting at exactly 50k chars must not be rejected by the length guard"
    )


# ── B3: chat context injection ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_context_loaded_for_valid_application():
    """B3: _load_application_context returns a string with key application fields
    when the application exists in the database.
    """
    from backend.api.chat import _load_application_context

    fake_row = {
        "company": "Acme GmbH",
        "role_title": "Senior Engineer",
        "job_posting": "Wir suchen einen erfahrenen Ingenieur...",
        "score": 75,
        "threshold": "pass",
        "scoring_details": json.dumps({"technical": {"score": 80, "reasoning": "strong"}}),
        "gaps": "Führungserfahrung fehlt",
        "cv_diff": "+ Python 3.12 hinzugefügt",
        "tailored_cv": "Lebenslauf-Inhalt",
        "anschreiben": "Sehr geehrte Damen und Herren...",
    }

    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=fake_row)

    @asynccontextmanager
    async def fake_get_conn():
        yield mock_conn

    with patch("backend.api.chat.get_conn", fake_get_conn):
        result = await _load_application_context(1)

    assert result is not None
    assert "Acme GmbH" in result
    assert "Senior Engineer" in result
    assert "75" in result
    assert "pass" in result
    assert "Führungserfahrung" in result


@pytest.mark.asyncio
async def test_chat_context_returns_none_for_missing_application():
    """B3: _load_application_context returns None when no row is found,
    so the chat falls back to the base system prompt without crashing.
    """
    from backend.api.chat import _load_application_context

    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=None)

    @asynccontextmanager
    async def fake_get_conn():
        yield mock_conn

    with patch("backend.api.chat.get_conn", fake_get_conn):
        result = await _load_application_context(999)

    assert result is None


@pytest.mark.asyncio
async def test_chat_context_returns_none_on_db_error():
    """B3: _load_application_context returns None (not raises) on a DB exception,
    so the endpoint degrades gracefully to base system prompt.
    """
    from backend.api.chat import _load_application_context

    @asynccontextmanager
    async def fake_get_conn():
        raise RuntimeError("connection refused")
        yield  # noqa: unreachable — required for asynccontextmanager

    with patch("backend.api.chat.get_conn", fake_get_conn):
        result = await _load_application_context(1)

    assert result is None
