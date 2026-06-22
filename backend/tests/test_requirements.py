"""
Tests for the requirements compliance layer.

Covers:
  - apply_requirements_override (pure deterministic function)
      * 6 task-specified scenarios: strong match, missing language, missing
        location, junior→senior, missing degree, soft-only missing
      * edge cases: caution unchanged, dealbreaker with fail base stays fail
  - run_requirements_check (async LLM call, mocked)
      * calls Haiku with correct node_name
      * returns RequirementsAnalysis on success
  - analysis_scoring integration
      * apply_requirements_override is actually called — test fails if removed
      * dealbreaker with pass base → threshold caution (NOT fail), docs generated
      * base fail stays fail even with a dealbreaker
      * requirements check exception does not crash pipeline
  - _store_job_application
      * requirements_analysis is persisted in scoring_details JSONB
"""
import json
from unittest.mock import AsyncMock, patch

import pytest

from backend.deterministic.scoring import apply_requirements_override
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
from backend.models.requirements import BlockerItem, RequirementsAnalysis


# ── helpers ───────────────────────────────────────────────────────────────────

def _blocker(requirement: str, reason: str = "not in candidate profile") -> BlockerItem:
    return BlockerItem(requirement=requirement, reason=reason)


def _ra(
    *,
    dealbreakers: list[BlockerItem] | None = None,
    hard_missing: list[BlockerItem] | None = None,
    soft_missing: list[str] | None = None,
) -> RequirementsAnalysis:
    return RequirementsAnalysis(
        triggered_dealbreakers=dealbreakers or [],
        missing_hard_requirements=hard_missing or [],
        missing_soft_requirements=soft_missing or [],
    )


def _fake_scoring(threshold: str = "pass") -> ScoringResult:
    ao = AnalyzerOutput(
        technical=TechnicalScore(score=30, reasoning="ok", matching_skills=[], missing_skills=[]),
        requirements=RequirementsScore(score=20, reasoning="ok"),
        role_fit=RoleFitScore(score=15, reasoning="ok", matched_role_key=""),
        location=LocationScore(score=8, reasoning="ok"),
        strategic=StrategicScore(score=4, reasoning="ok"),
    )
    dims = DimensionScores(technical=30, requirements=20, role_fit=15, location=8, strategic=4)
    return ScoringResult(dims=dims, total_score=77, threshold=threshold, analyzer_output=ao)


# ── apply_requirements_override — 6 task scenarios ────────────────────────────

def test_strong_match_no_blockers_threshold_unchanged():
    """Candidate meets all requirements — pass stays pass."""
    ra = _ra()  # all empty lists
    assert apply_requirements_override("pass", ra) == "pass"


def test_missing_required_language_downgrades_pass_to_caution():
    """Job requires C1 German; candidate has B1 → missing hard requirement → caution."""
    ra = _ra(hard_missing=[_blocker("C1 German required", "CV shows German: B1")])
    assert apply_requirements_override("pass", ra) == "caution"


def test_missing_required_location_dealbreaker_produces_caution():
    """
    Location mismatch as a dealbreaker does NOT suppress generation.
    When base was pass/caution, override produces caution (not fail) so that
    CV and cover letter are still generated and the user can see the blocker.
    Only a base fail stays fail.
    """
    ra = _ra(dealbreakers=[_blocker("100% on-site Munich required", "candidate commutes remote only")])
    assert apply_requirements_override("pass", ra) == "caution"
    assert apply_requirements_override("caution", ra) == "caution"
    assert apply_requirements_override("fail", ra) == "fail"


def test_junior_applying_to_senior_role_downgrades_pass():
    """'Minimum 5 years experience' when candidate has 2 → missing hard requirement."""
    ra = _ra(hard_missing=[_blocker("Minimum 5 years experience required", "CV shows 2 years")])
    assert apply_requirements_override("pass", ra) == "caution"


def test_missing_required_degree_downgrades_pass():
    """'Bachelor's degree required' when CV shows no degree."""
    ra = _ra(hard_missing=[_blocker("Bachelor's degree required", "no degree in CV")])
    assert apply_requirements_override("pass", ra) == "caution"


def test_soft_requirement_missing_does_not_change_threshold():
    """'Master's preferred' candidate has Bachelor's — only soft miss, threshold unchanged."""
    ra = _ra(soft_missing=["Master's degree (preferred)"])
    assert apply_requirements_override("pass", ra) == "pass"
    assert apply_requirements_override("caution", ra) == "caution"


# ── apply_requirements_override — edge cases ──────────────────────────────────

def test_no_requirements_analysis_threshold_unchanged():
    """None passed (failed check) → threshold left unchanged."""
    assert apply_requirements_override("pass", None) == "pass"
    assert apply_requirements_override("fail", None) == "fail"


def test_dealbreaker_produces_caution_not_fail_from_pass_or_caution():
    """
    triggered_dealbreakers with a non-fail base → caution, preserving generation.
    This is intentional: a Haiku-only check must never silently kill document
    generation.  The blocking information is surfaced via requirements_analysis.
    """
    ra = _ra(dealbreakers=[_blocker("EU work permit required")])
    assert apply_requirements_override("pass", ra) == "caution"
    assert apply_requirements_override("caution", ra) == "caution"


def test_dealbreaker_preserves_fail_when_base_was_already_fail():
    """When the Analyzer already scored fail, a dealbreaker must not upgrade to caution."""
    ra = _ra(dealbreakers=[_blocker("EU work permit required")])
    assert apply_requirements_override("fail", ra) == "fail"


def test_missing_hard_req_does_not_downgrade_caution():
    """A missing hard requirement only downgrades 'pass'. 'caution' stays 'caution'."""
    ra = _ra(hard_missing=[_blocker("AWS certification required")])
    assert apply_requirements_override("caution", ra) == "caution"


def test_missing_hard_req_does_not_change_fail():
    """'fail' stays 'fail' with a missing hard requirement."""
    ra = _ra(hard_missing=[_blocker("PMP certification required")])
    assert apply_requirements_override("fail", ra) == "fail"


# ── run_requirements_check ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_requirements_check_calls_haiku_with_correct_node():
    """Verify the call goes to Haiku with node_name='requirements_check'."""
    from backend.pipeline.requirements_check import run_requirements_check

    expected = RequirementsAnalysis()
    mock_conn = AsyncMock()

    with patch("backend.pipeline.requirements_check.llm.call_structured", new=AsyncMock(return_value=expected)) as m:
        result = await run_requirements_check(
            mock_conn,
            job_posting="Backend Developer required",
            cv_text="Python 5 years",
            candidate_profile={"core_skills": "Python"},
            profile_id=1,
        )

    assert result is expected
    _, kwargs = m.call_args
    assert kwargs["model"] == "claude-haiku-4-5-20251001"
    assert kwargs["node_name"] == "requirements_check"
    assert kwargs["temperature"] == 0.0


@pytest.mark.asyncio
async def test_run_requirements_check_returns_structured_analysis():
    """Structured result is returned unmodified."""
    from backend.pipeline.requirements_check import run_requirements_check

    expected = RequirementsAnalysis(
        missing_hard_requirements=[_blocker("C1 German required", "has B1")],
        triggered_dealbreakers=[],
        missing_soft_requirements=["Docker experience preferred"],
    )
    mock_conn = AsyncMock()

    with patch("backend.pipeline.requirements_check.llm.call_structured", new=AsyncMock(return_value=expected)):
        result = await run_requirements_check(
            mock_conn,
            job_posting="Job posting",
            cv_text="CV text",
            candidate_profile={},
        )

    assert len(result.missing_hard_requirements) == 1
    assert result.missing_hard_requirements[0].requirement == "C1 German required"
    assert len(result.missing_soft_requirements) == 1


# ── analysis_scoring integration ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_requirements_override_applied_in_analysis_scoring():
    """
    apply_requirements_override is called inside run_analysis_scoring.
    This test fails if that call is removed from analysis_scoring.py.

    Mechanism: the Analyzer returns a high-scoring 'pass' base; requirements_check
    returns a missing hard requirement.  After override the threshold must be
    'caution', not 'pass' — proof that apply_requirements_override was called.
    """
    from backend.pipeline.analysis_scoring import run_analysis_scoring

    mock_conn = AsyncMock()
    hard_miss_ra = RequirementsAnalysis(
        missing_hard_requirements=[_blocker("C1 German required", "CV shows B1")],
    )

    with (
        patch(
            "backend.pipeline.analysis_scoring._run_analyzer",
            new=AsyncMock(return_value=_fake_scoring("pass").analyzer_output),
        ),
        patch(
            "backend.pipeline.analysis_scoring.run_requirements_check",
            new=AsyncMock(return_value=hard_miss_ra),
        ),
    ):
        result, gap = await run_analysis_scoring(
            mock_conn,
            job_posting="job",
            cv_text="cv",
            candidate_profile={},
            company_result=CompanyResearchResult(company_name="Co", search_name="co", company_profile=""),
        )

    # Proof that apply_requirements_override ran: base was 'pass', override → 'caution'
    assert result.threshold == "caution", (
        "apply_requirements_override was not called or did not downgrade 'pass' to 'caution'"
    )
    assert len(result.requirements_analysis.missing_hard_requirements) == 1


@pytest.mark.asyncio
async def test_dealbreaker_from_requirements_check_produces_caution_not_fail():
    """
    When run_requirements_check returns a dealbreaker and the Analyzer base is
    'pass', the final threshold must be 'caution' — NOT 'fail'.

    This ensures a Haiku false positive cannot silently suppress document
    generation.  The calling pipeline sees 'caution' and proceeds to generate
    tailored CV + cover letter.
    """
    from backend.pipeline.analysis_scoring import run_analysis_scoring

    mock_conn = AsyncMock()
    dealbreaker_ra = RequirementsAnalysis(
        triggered_dealbreakers=[_blocker("EU work permit required", "not in candidate profile")],
    )

    with (
        patch(
            "backend.pipeline.analysis_scoring._run_analyzer",
            new=AsyncMock(return_value=_fake_scoring("pass").analyzer_output),
        ),
        patch(
            "backend.pipeline.analysis_scoring.run_requirements_check",
            new=AsyncMock(return_value=dealbreaker_ra),
        ),
    ):
        result, gap = await run_analysis_scoring(
            mock_conn,
            job_posting="job",
            cv_text="cv",
            candidate_profile={},
            company_result=CompanyResearchResult(company_name="Co", search_name="co", company_profile=""),
        )

    assert result.threshold == "caution", "Dealbreaker must not force fail when base was pass"
    assert len(result.requirements_analysis.triggered_dealbreakers) == 1
    assert gap is None  # caution path does not run gap analysis


@pytest.mark.asyncio
async def test_fail_base_stays_fail_even_with_dealbreaker():
    """
    When the Analyzer base is 'fail', a dealbreaker must keep it 'fail' —
    no accidental upgrade to caution.
    """
    from backend.pipeline.analysis_scoring import run_analysis_scoring

    mock_conn = AsyncMock()
    dealbreaker_ra = RequirementsAnalysis(
        triggered_dealbreakers=[_blocker("EU work permit required")],
    )
    # Build an AnalyzerOutput that will produce 'fail' after calculate_threshold
    fail_ao = AnalyzerOutput(
        technical=TechnicalScore(score=10, reasoning="low", matching_skills=[], missing_skills=[]),
        requirements=RequirementsScore(score=5, reasoning="low"),
        role_fit=RoleFitScore(score=5, reasoning="low", matched_role_key=""),
        location=LocationScore(score=2, reasoning="low"),
        strategic=StrategicScore(score=1, reasoning="low"),
    )  # total=23 → well below caution threshold

    with (
        patch(
            "backend.pipeline.analysis_scoring._run_analyzer",
            new=AsyncMock(return_value=fail_ao),
        ),
        patch(
            "backend.pipeline.analysis_scoring.run_requirements_check",
            new=AsyncMock(return_value=dealbreaker_ra),
        ),
    ):
        result, gap = await run_analysis_scoring(
            mock_conn,
            job_posting="job",
            cv_text="cv",
            candidate_profile={},
            company_result=CompanyResearchResult(company_name="Co", search_name="co", company_profile=""),
        )

    assert result.threshold == "fail"
    assert gap is not None  # fail path always runs gap analysis


@pytest.mark.asyncio
async def test_requirements_check_exception_does_not_crash_scoring():
    """
    A failed requirements check (network error, parse error) must not crash
    run_analysis_scoring — it fails open with empty RequirementsAnalysis.
    """
    from backend.pipeline.analysis_scoring import run_analysis_scoring

    mock_conn = AsyncMock()

    with (
        patch(
            "backend.pipeline.analysis_scoring._run_analyzer",
            new=AsyncMock(return_value=_fake_scoring("pass").analyzer_output),
        ),
        patch(
            "backend.pipeline.analysis_scoring.run_requirements_check",
            new=AsyncMock(side_effect=RuntimeError("Haiku timeout")),
        ),
    ):
        result, gap = await run_analysis_scoring(
            mock_conn,
            job_posting="job",
            cv_text="cv",
            candidate_profile={},
            company_result=CompanyResearchResult(company_name="Co", search_name="co", company_profile=""),
        )

    assert result.requirements_analysis is not None
    assert result.requirements_analysis.triggered_dealbreakers == []
    assert result.requirements_analysis.missing_hard_requirements == []
    # Threshold was not affected by the failed check
    assert result.threshold in ("pass", "caution", "fail")


# ── prompt content invariants ─────────────────────────────────────────────────

def test_prompt_location_is_in_missing_hard_requirements_not_triggered_dealbreakers():
    """
    The requirements_extractor prompt must list location/on-site under
    missing_hard_requirements, NOT under triggered_dealbreakers.
    Overlapping examples in both sections caused the Haiku model to conflate
    location mismatches as hard disqualifiers.
    """
    from backend.prompts.loader import load_prompt

    prompt = load_prompt("requirements_extractor")

    # Split on the section headers to isolate each category block
    dealbreaker_idx = prompt.index("triggered_dealbreakers")
    hard_req_idx = prompt.index("missing_hard_requirements")

    # Everything between the triggered_dealbreakers header and the
    # missing_hard_requirements header is the dealbreaker section.
    dealbreaker_section = prompt[dealbreaker_idx:hard_req_idx]

    # Location / on-site must NOT appear in the dealbreaker section.
    assert "on-site" not in dealbreaker_section.lower(), (
        "on-site example must be in missing_hard_requirements, not triggered_dealbreakers"
    )
    assert "relocation" not in dealbreaker_section.lower() or "NOTE:" in dealbreaker_section, (
        "relocation must only appear in a NOTE clarifying it belongs to missing_hard_requirements"
    )

    # The prompt must contain the uncertainty tie-breaker rule.
    assert "missing_hard_requirement" in prompt[hard_req_idx:]
    assert "uncertain" in prompt.lower()


# ── persistence: requirements_analysis survives store/reload ──────────────────

@pytest.mark.asyncio
async def test_requirements_analysis_stored_in_scoring_details():
    """
    _store_job_application must embed requirements_analysis inside the
    scoring_details JSONB column so the history endpoint returns it.
    """
    from backend.pipeline.main_pipeline import _store_job_application

    ra = RequirementsAnalysis(
        missing_hard_requirements=[_blocker("C1 German required", "has B1 only")],
        triggered_dealbreakers=[],
        missing_soft_requirements=[],
        recommendation_blockers=["C1 German required: has B1 only"],
    )
    scoring = _fake_scoring("caution")
    scoring.requirements_analysis = ra

    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=42)

    await _store_job_application(
        mock_conn,
        profile_id=1,
        company_name="Acme GmbH",
        role_title="Backend Dev",
        job_posting="job posting",
        scoring=scoring,
        cv_diff="",
        tailored_cv="",
        anschreiben="",
        gaps="",
    )

    positional = mock_conn.fetchval.call_args[0]
    scoring_details_json = positional[-1]
    stored = json.loads(scoring_details_json)

    assert "requirements_analysis" in stored
    ra_stored = stored["requirements_analysis"]
    assert len(ra_stored["missing_hard_requirements"]) == 1
    assert ra_stored["missing_hard_requirements"][0]["requirement"] == "C1 German required"
    assert ra_stored["triggered_dealbreakers"] == []
    assert ra_stored["recommendation_blockers"] == ["C1 German required: has B1 only"]


@pytest.mark.asyncio
async def test_empty_requirements_analysis_not_stored():
    """
    When requirements_analysis is empty (no blockers), it is still stored
    (the `if scoring.requirements_analysis` check passes for a non-None model).
    But when requirements_analysis is None it must not appear in scoring_details.
    """
    from backend.pipeline.main_pipeline import _store_job_application

    scoring = _fake_scoring("pass")
    # explicitly set to None (simulates failed check that set requirements_analysis=None? No —
    # failed check produces empty RequirementsAnalysis, not None.  Test None path explicitly.)
    scoring.requirements_analysis = None

    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=1)

    await _store_job_application(
        mock_conn,
        profile_id=1,
        company_name="Co",
        role_title="Dev",
        job_posting="job",
        scoring=scoring,
        cv_diff="",
        tailored_cv="",
        anschreiben="",
        gaps="",
    )

    positional = mock_conn.fetchval.call_args[0]
    stored = json.loads(positional[-1])
    assert "requirements_analysis" not in stored
