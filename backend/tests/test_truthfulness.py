"""
Tests for the truthfulness validation layer.

Covers:
  - check_cv_word_inflation (pure deterministic function)
  - validate_anschreiben (async LLM call, mocked)
  - main_pipeline truthfulness branch:
      * clean validation skips retry
      * medium/high triggers retry with strict_grounding=True
      * retry result is used even when first attempt fails
      * validator exception does not crash the pipeline (fail open)
      * surviving medium/high issue is surfaced in PipelineResult
"""
import json
from unittest.mock import AsyncMock, call, patch

import pytest

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
from backend.models.tailoring import TailoringResult
from backend.models.validation import TruthfulnessIssue, TruthfulnessResult
from backend.pipeline.truthfulness import check_cv_word_inflation


# ── helpers ───────────────────────────────────────────────────────────────────

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


def _clean_result() -> TruthfulnessResult:
    return TruthfulnessResult(valid=True, issues=[], severity="low")


def _medium_result() -> TruthfulnessResult:
    return TruthfulnessResult(
        valid=False,
        severity="medium",
        issues=[TruthfulnessIssue(
            claim="Kubernetes",
            issue_type="invented_skill",
            detail="'Kubernetes' not present in original CV",
        )],
    )


_FAKE_CONTEXT = {
    "cv_text": "## Skills\n- Python, SQL",
    "candidate_profile": json.dumps({"core_skills": "Python, SQL"}),
    "role_type_scores": json.dumps({}),
    "career_target": "Backend Developer",
    "market_research": "tech sector",
    "cv_language": "de",
}

_FAKE_COMPANY = CompanyResearchResult(company_name="Acme GmbH", search_name="acme", company_profile="")

_FAKE_TAILORING = TailoringResult(
    tailored_cv="Tailored CV text",
    cv_diff="",
    items_removed=0,
    items_shortened=0,
)


# ── check_cv_word_inflation ───────────────────────────────────────────────────

def test_no_inflation_returns_valid():
    result = check_cv_word_inflation("word " * 200, "word " * 180, "word " * 170)
    assert result.valid is True
    assert result.severity == "low"
    assert result.issues == []


def test_rewritten_exceeds_original_by_more_than_5_percent():
    result = check_cv_word_inflation("word " * 200, "word " * 180, "word " * 215)
    assert result.valid is False
    assert result.severity == "medium"
    assert "exceeds original" in result.issues[0].detail


def test_rewritten_at_exactly_5_percent_above_original_is_ok():
    # edited is close to original so the 15%-vs-edited check also doesn't fire
    result = check_cv_word_inflation("word " * 200, "word " * 197, "word " * 210)
    assert result.valid is True


def test_rewriter_inflates_vs_edited_cv_by_more_than_15_percent():
    result = check_cv_word_inflation("word " * 300, "word " * 100, "word " * 120)
    assert result.valid is False
    assert result.severity == "medium"
    assert "inflated" in result.issues[0].detail


def test_empty_original_does_not_crash():
    result = check_cv_word_inflation("", "", "word " * 10)
    assert isinstance(result, TruthfulnessResult)


def test_rewritten_equal_to_original_is_valid():
    cv = "Python Django REST API " * 50
    assert check_cv_word_inflation(cv, cv, cv).valid is True


# ── validate_anschreiben (async, mocked LLM) ─────────────────────────────────

@pytest.mark.asyncio
async def test_validate_anschreiben_clean_returns_valid():
    mock_conn = AsyncMock()
    with patch("backend.pipeline.truthfulness.llm.call_structured", new=AsyncMock(return_value=_clean_result())):
        from backend.pipeline.truthfulness import validate_anschreiben
        result = await validate_anschreiben(
            mock_conn,
            anschreiben_text="Ich bewerbe mich als Python-Entwickler.",
            original_cv="## Erfahrung\n- Python-Entwickler bei Acme GmbH (2019–2024)",
            profile_id=1,
        )
    assert result.valid is True
    assert result.severity == "low"


@pytest.mark.asyncio
async def test_validate_anschreiben_with_invented_skill_returns_invalid():
    mock_conn = AsyncMock()
    with patch("backend.pipeline.truthfulness.llm.call_structured", new=AsyncMock(return_value=_medium_result())):
        from backend.pipeline.truthfulness import validate_anschreiben
        result = await validate_anschreiben(
            mock_conn,
            anschreiben_text="Ich bringe Kubernetes-Erfahrung mit.",
            original_cv="## Skills\n- Python, Django",
            candidate_profile={"core_skills": "Python, Django"},
        )
    assert result.valid is False
    assert result.issues[0].issue_type == "invented_skill"


@pytest.mark.asyncio
async def test_validate_anschreiben_uses_correct_node_name():
    captured: dict = {}

    async def spy(conn, *, model, system, user, response_model, **kwargs):
        captured["node_name"] = kwargs.get("node_name")
        return _clean_result()

    mock_conn = AsyncMock()
    with patch("backend.pipeline.truthfulness.llm.call_structured", new=spy):
        from backend.pipeline.truthfulness import validate_anschreiben
        await validate_anschreiben(mock_conn, anschreiben_text="x", original_cv="y")

    assert captured["node_name"] == "truthfulness_validator"


@pytest.mark.asyncio
async def test_validate_anschreiben_includes_candidate_profile_in_prompt():
    captured: dict = {}

    async def spy(conn, *, model, system, user, response_model, **kwargs):
        captured["user"] = user
        return _clean_result()

    mock_conn = AsyncMock()
    with patch("backend.pipeline.truthfulness.llm.call_structured", new=spy):
        from backend.pipeline.truthfulness import validate_anschreiben
        await validate_anschreiben(
            mock_conn,
            anschreiben_text="letter",
            original_cv="cv",
            candidate_profile={"core_skills": "Python, Docker"},
        )

    assert "Python, Docker" in captured["user"]
    assert "<original_cv>" in captured["user"]
    assert "<candidate_profile>" in captured["user"]


# ── main_pipeline truthfulness branch ────────────────────────────────────────

def _base_patches(*, validate_side_effect=None, validate_return=None, anschreiben_texts=None):
    """
    Returns a dict of patch targets → mocks for the truthfulness branch tests.
    Callers can override validate_anschreiben behavior via side_effect or return_value.
    anschreiben_texts is a list of values returned on successive calls.
    """
    anschreiben_mock = AsyncMock(side_effect=anschreiben_texts or ["First letter", "Retry letter"])
    if validate_side_effect is not None:
        validate_mock = AsyncMock(side_effect=validate_side_effect)
    else:
        validate_mock = AsyncMock(return_value=validate_return or _clean_result())
    return anschreiben_mock, validate_mock


async def _run_pipeline_with_patches(*, validate_mock, anschreiben_mock):
    from backend.pipeline.main_pipeline import run_main_pipeline

    mock_conn = AsyncMock()
    with (
        patch("backend.pipeline.main_pipeline._fetch_profile_context", new=AsyncMock(return_value=_FAKE_CONTEXT)),
        patch("backend.pipeline.main_pipeline.run_company_research", new=AsyncMock(return_value=_FAKE_COMPANY)),
        patch("backend.pipeline.main_pipeline.get_cv_for_language", new=AsyncMock(return_value="CV for analysis")),
        patch("backend.pipeline.main_pipeline.run_analysis_scoring", new=AsyncMock(return_value=(_fake_scoring("pass"), None))),
        patch("backend.pipeline.main_pipeline.run_cv_tailoring", new=AsyncMock(return_value=_FAKE_TAILORING)),
        patch("backend.pipeline.main_pipeline.run_anschreiben", new=anschreiben_mock),
        patch("backend.pipeline.main_pipeline.validate_anschreiben", new=validate_mock),
        patch("backend.pipeline.main_pipeline._store_job_application", new=AsyncMock(return_value=99)),
    ):
        result = await run_main_pipeline(mock_conn, profile_id=1, job_posting="Backend Developer")
    return result, anschreiben_mock, validate_mock


@pytest.mark.asyncio
async def test_clean_validation_skips_retry():
    """When the first validation is clean (low), run_anschreiben is called only once."""
    anschreiben_mock = AsyncMock(return_value="First letter")
    validate_mock = AsyncMock(return_value=_clean_result())

    result, anschreiben_mock, validate_mock = await _run_pipeline_with_patches(
        validate_mock=validate_mock,
        anschreiben_mock=anschreiben_mock,
    )

    assert anschreiben_mock.call_count == 1
    assert validate_mock.call_count == 1
    assert result.anschreiben_truthfulness_warning is None


@pytest.mark.asyncio
async def test_medium_validation_triggers_retry_with_strict_grounding():
    """medium severity → retry call must use strict_grounding=True."""
    anschreiben_mock = AsyncMock(side_effect=["First letter", "Retry letter"])
    validate_mock = AsyncMock(side_effect=[_medium_result(), _clean_result()])

    result, anschreiben_mock, validate_mock = await _run_pipeline_with_patches(
        validate_mock=validate_mock,
        anschreiben_mock=anschreiben_mock,
    )

    assert anschreiben_mock.call_count == 2
    # Second call must have strict_grounding=True
    _, retry_kwargs = anschreiben_mock.call_args_list[1]
    assert retry_kwargs.get("strict_grounding") is True
    assert validate_mock.call_count == 2


@pytest.mark.asyncio
async def test_retry_result_is_used_as_anschreiben_text():
    """The text from the retry call is what ends up in the result, not the first attempt."""
    anschreiben_mock = AsyncMock(side_effect=["First letter", "Retry letter"])
    validate_mock = AsyncMock(side_effect=[_medium_result(), _clean_result()])

    result, _, _ = await _run_pipeline_with_patches(
        validate_mock=validate_mock,
        anschreiben_mock=anschreiben_mock,
    )

    assert result.anschreiben_text == "Retry letter"


@pytest.mark.asyncio
async def test_validator_exception_does_not_crash_pipeline():
    """An API/parse error in validate_anschreiben must not prevent document generation."""
    anschreiben_mock = AsyncMock(return_value="Letter text")
    validate_mock = AsyncMock(side_effect=RuntimeError("Haiku API timeout"))

    result, _, _ = await _run_pipeline_with_patches(
        validate_mock=validate_mock,
        anschreiben_mock=anschreiben_mock,
    )

    # Pipeline completes without raising; no retry was attempted
    assert result.anschreiben_text == "Letter text"
    assert result.anschreiben_truthfulness_warning is None
    assert anschreiben_mock.call_count == 1


@pytest.mark.asyncio
async def test_surviving_medium_issue_surfaced_in_result():
    """If retry still has medium/high issues, PipelineResult carries the warning."""
    anschreiben_mock = AsyncMock(side_effect=["First letter", "Retry letter"])
    validate_mock = AsyncMock(side_effect=[_medium_result(), _medium_result()])

    result, _, _ = await _run_pipeline_with_patches(
        validate_mock=validate_mock,
        anschreiben_mock=anschreiben_mock,
    )

    assert result.anschreiben_truthfulness_warning is not None
    assert len(result.anschreiben_truthfulness_warning) > 0
    assert "Kubernetes" in result.anschreiben_truthfulness_warning[0]


# ── persistence: warning survives store/reload ───────────────────────────────

@pytest.mark.asyncio
async def test_truthfulness_warning_stored_in_scoring_details():
    """
    _store_job_application must embed truthfulness_warning inside the
    scoring_details JSONB column so the history endpoint returns it.
    """
    from backend.pipeline.main_pipeline import _store_job_application

    warning = ["'Kubernetes' not present in original CV"]
    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=42)

    await _store_job_application(
        mock_conn,
        profile_id=1,
        company_name="Acme",
        role_title="Engineer",
        job_posting="Senior Engineer role",
        scoring=_fake_scoring("pass"),
        cv_diff="",
        tailored_cv="CV text",
        anschreiben="Letter text",
        gaps="",
        truthfulness_warning=warning,
    )

    assert mock_conn.fetchval.called
    # scoring_details_json is the last positional argument to fetchval
    call_args = mock_conn.fetchval.call_args
    positional = call_args[0]   # (sql, $1, $2, ..., $11)
    scoring_details_json = positional[-1]
    stored = json.loads(scoring_details_json)

    assert "truthfulness_warning" in stored, (
        "truthfulness_warning must be present in scoring_details JSONB"
    )
    assert stored["truthfulness_warning"] == warning


@pytest.mark.asyncio
async def test_no_truthfulness_warning_omitted_from_scoring_details():
    """When there is no warning, scoring_details must not contain the key."""
    from backend.pipeline.main_pipeline import _store_job_application

    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=42)

    await _store_job_application(
        mock_conn,
        profile_id=1,
        company_name="Acme",
        role_title="Engineer",
        job_posting="role",
        scoring=_fake_scoring("pass"),
        cv_diff="",
        tailored_cv="",
        anschreiben="",
        gaps="",
        truthfulness_warning=None,
    )

    positional = mock_conn.fetchval.call_args[0]
    stored = json.loads(positional[-1])
    assert "truthfulness_warning" not in stored


# ── cv_tailoring integration: inflation triggers pre-rewrite fallback ─────────

@pytest.mark.asyncio
async def test_cv_tailoring_falls_back_to_edited_cv_on_rewriter_inflation():
    """
    When the rewriter returns a CV that's inflated vs the original,
    run_cv_tailoring must use the pre-rewrite edited_cv, not the rewritten one.
    """
    from backend.pipeline.cv_tailoring import run_cv_tailoring
    from backend.models.tailoring import ClassifierOutput, ClassifierItem, GeneratorOutput, GeneratorItem

    original_cv = (
        "## Erfahrung\n"
        "- Python-Entwickler bei Acme (2018–2023)\n"
        "## Ausbildung\n"
        "- B.Sc. Informatik, TU Berlin (2014–2018)\n"
        "## Skills\n"
        "- Python, SQL, Git\n"
    )
    inflated_rewrite = original_cv + ("\nZusätzliche Erfindungen. " * 50)

    classifier_out = ClassifierOutput(items=[
        ClassifierItem(id="item_000", classification="KEEP", reasoning="relevant"),
    ])
    generator_out = GeneratorOutput(items=[
        GeneratorItem(id="item_000", action="KEEP", new_content=""),
    ])

    mock_conn = AsyncMock()
    with (
        patch("backend.pipeline.cv_tailoring._run_classifier", new=AsyncMock(return_value=classifier_out)),
        patch("backend.pipeline.cv_tailoring._run_generator", new=AsyncMock(return_value=generator_out)),
        patch("backend.pipeline.cv_tailoring._run_rewriter", new=AsyncMock(return_value=inflated_rewrite)),
    ):
        result = await run_cv_tailoring(
            mock_conn,
            cv_text=original_cv,
            job_posting="Python Developer role",
            career_target="Software Engineer",
            profile_id=99,
        )

    assert "Zusätzliche Erfindungen" not in result.tailored_cv
