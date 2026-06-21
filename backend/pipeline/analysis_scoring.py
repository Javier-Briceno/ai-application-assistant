"""
Analysis & Scoring pipeline.
Ports the n8n "Utility: Analysis Scoring" sub-workflow to Python.

Flow:
  1. Analyzer (GPT-4.1) — structured 5-dimension JSON assessment
  2. calculate_dimensions() — clamp scores (deterministic)
  3. calculate_threshold() — pass / caution / fail (deterministic)
  4. If fail → gap_analysis (Sonnet) — concise explanation why
"""
import json
import logging

import asyncpg

from backend import llm
from backend.deterministic.scoring import calculate_dimensions, calculate_threshold
from backend.models.analysis import AnalyzerOutput, ScoringResult
from backend.models.company import CompanyResearchResult
from backend.prompts.loader import load_prompt

log = logging.getLogger(__name__)

_GPT41 = "gpt-4.1"
_SONNET = "claude-sonnet-4-6"


async def _run_analyzer(
    conn: asyncpg.Connection,
    *,
    job_posting: str,
    cv_text: str,
    candidate_profile_json: str,
    company_profile: str,
    profile_id: int | None,
) -> AnalyzerOutput:
    system = load_prompt("analyzer_system")
    user = (
        f"<job_posting>\n{job_posting}\n</job_posting>\n\n"
        f"<candidate_profile>\n{candidate_profile_json}\n</candidate_profile>\n\n"
        f"<company_profile>\n{company_profile}\n</company_profile>\n\n"
        f"<cv_text>\n{cv_text}\n</cv_text>"
    )
    return await llm.call_structured(
        conn,
        model=_GPT41,
        system=system,
        user=user,
        response_model=AnalyzerOutput,
        max_tokens=2000,
        temperature=0.0,
        node_name="analyzer",
        profile_id=profile_id,
    )


async def _run_gap_analysis(
    conn: asyncpg.Connection,
    *,
    job_posting: str,
    scoring_result: ScoringResult,
    profile_id: int | None,
) -> str:
    system = load_prompt("gap_analysis")
    dims = scoring_result.dims
    user = (
        f"<job_posting>\n{job_posting}\n</job_posting>\n\n"
        f"<score_summary>\n"
        f"Total: {scoring_result.total_score}/100 ({scoring_result.threshold})\n"
        f"Technical: {dims.technical}/40\n"
        f"Requirements: {dims.requirements}/25\n"
        f"Role Fit: {dims.role_fit}/20\n"
        f"Location: {dims.location}/10\n"
        f"Strategic: {dims.strategic}/5\n"
        f"</score_summary>\n\n"
        f"<dimension_reasoning>\n"
        f"Technical: {scoring_result.analyzer_output.technical.reasoning}\n"
        f"Missing skills: {', '.join(scoring_result.analyzer_output.technical.missing_skills)}\n"
        f"Requirements: {scoring_result.analyzer_output.requirements.reasoning}\n"
        f"Role Fit: {scoring_result.analyzer_output.role_fit.reasoning}\n"
        f"Location: {scoring_result.analyzer_output.location.reasoning}\n"
        f"</dimension_reasoning>"
    )
    return await llm.call_raw(
        conn,
        model=_SONNET,
        system=system,
        user=user,
        max_tokens=600,
        temperature=0.3,
        node_name="gap_analysis",
        profile_id=profile_id,
    )


async def run_analysis_scoring(
    conn: asyncpg.Connection,
    *,
    job_posting: str,
    cv_text: str,
    candidate_profile: dict,
    company_result: CompanyResearchResult,
    profile_id: int | None = None,
) -> tuple[ScoringResult, str | None]:
    """
    Run the full analysis & scoring pipeline.

    Returns (ScoringResult, gap_analysis_text | None).
    gap_analysis_text is non-None only when threshold == 'fail'.
    """
    candidate_profile_json = json.dumps(candidate_profile, ensure_ascii=False, indent=2)

    log.info("Running analyzer (GPT-4.1)...")
    analyzer_output = await _run_analyzer(
        conn,
        job_posting=job_posting,
        cv_text=cv_text,
        candidate_profile_json=candidate_profile_json,
        company_profile=company_result.company_profile,
        profile_id=profile_id,
    )

    dims = calculate_dimensions(analyzer_output)
    threshold = calculate_threshold(dims)

    result = ScoringResult(
        dims=dims,
        total_score=dims.total,
        threshold=threshold,
        analyzer_output=analyzer_output,
    )

    log.info(
        "Scoring complete: %d/100 (%s) — T:%d R:%d RF:%d L:%d S:%d",
        result.total_score,
        threshold,
        dims.technical,
        dims.requirements,
        dims.role_fit,
        dims.location,
        dims.strategic,
    )

    gap_text: str | None = None
    if threshold == "fail":
        log.info("Threshold = fail — running gap analysis...")
        gap_text = await _run_gap_analysis(
            conn, job_posting=job_posting, scoring_result=result, profile_id=profile_id
        )

    return result, gap_text
