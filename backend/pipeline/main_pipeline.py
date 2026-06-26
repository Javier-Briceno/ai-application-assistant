"""
Main pipeline orchestrator.
Ports the n8n "Job Application Assistant" main workflow.

Flow (mirrors n8n):
  1. Fetch profile + candidate_context from DB
  2. Detect job posting language
  3. Company Research + CV Translation (parallel)
  4. Analysis & Scoring
  5a. If fail → gap analysis → done
  5b. If pass/caution:
       - CV Tailoring
       - Anschreiben
  6. Compute diff (already done in cv_tailoring)
  7. Format response
  8. Store in job_applications
"""
import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Callable

import asyncpg

from backend.deterministic.language import detect_language
from backend.exceptions import UserVisibleError
from backend.models.analysis import ScoringResult
from backend.models.company import CompanyResearchResult
from backend.models.tailoring import TailoringResult
from backend.models.validation import TruthfulnessResult
from backend.pipeline.analysis_scoring import run_analysis_scoring
from backend.pipeline.anschreiben import run_anschreiben
from backend.pipeline.company_research import run_company_research
from backend.pipeline.cv_tailoring import run_cv_tailoring
from backend.pipeline.translation_cache import get_cv_for_language
from backend.pipeline.truthfulness import validate_anschreiben

log = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    profile_id: int
    company: CompanyResearchResult
    scoring: ScoringResult
    tailoring: TailoringResult | None          # None if threshold == 'fail'
    anschreiben_text: str | None               # None if threshold == 'fail'
    gap_analysis: str | None                   # None if threshold != 'fail'
    job_application_id: int | None             # set after DB insert
    anschreiben_truthfulness_warning: list[str] | None = None  # set if retry still found issues


async def _fetch_profile_context(conn: asyncpg.Connection, profile_id: int) -> dict:
    """Fetch all candidate_context keys into a single dict."""
    rows = await conn.fetch(
        "SELECT key, value FROM job_application_assistant.candidate_context WHERE profile_id = $1",
        profile_id,
    )
    return {r["key"]: r["value"] for r in rows}


async def _store_job_application(
    conn: asyncpg.Connection,
    *,
    profile_id: int,
    company_name: str,
    company_address: str = "",
    contact_person: str = "",
    role_title: str,
    job_posting: str,
    scoring: ScoringResult,
    cv_diff: str,
    tailored_cv: str,
    anschreiben: str,
    gaps: str,
    truthfulness_warning: list[str] | None = None,
) -> int:
    import json
    scoring_details: dict = {
        "technical":    {"score": scoring.dims.technical,    "reasoning": scoring.analyzer_output.technical.reasoning},
        "requirements": {"score": scoring.dims.requirements, "reasoning": scoring.analyzer_output.requirements.reasoning},
        "role_fit":     {"score": scoring.dims.role_fit,     "reasoning": scoring.analyzer_output.role_fit.reasoning},
        "location":     {"score": scoring.dims.location,     "reasoning": scoring.analyzer_output.location.reasoning},
        "strategic":    {"score": scoring.dims.strategic,    "reasoning": scoring.analyzer_output.strategic.reasoning},
    }
    if truthfulness_warning:
        scoring_details["truthfulness_warning"] = truthfulness_warning
    if scoring.requirements_analysis:
        scoring_details["requirements_analysis"] = scoring.requirements_analysis.model_dump()
    scoring_details_json = json.dumps(scoring_details)
    return await conn.fetchval(
        """
        INSERT INTO job_application_assistant.job_applications
            (profile_id, company, company_address, contact_person, role_title, job_posting, score, threshold,
             cv_diff, tailored_cv, anschreiben, gaps, scoring_details)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13::jsonb)
        RETURNING id
        """,
        profile_id,
        company_name,
        company_address,
        contact_person,
        role_title,
        job_posting,
        scoring.total_score,
        scoring.threshold,
        cv_diff,
        tailored_cv,
        anschreiben,
        gaps,
        scoring_details_json,
    )


async def run_main_pipeline(
    conn: asyncpg.Connection,
    *,
    profile_id: int,
    job_posting: str,
    on_step: Callable[[str], None] | None = None,
) -> PipelineResult:
    """
    Full job application pipeline.
    on_step is called with a German status string at each major step.
    """
    from typing import Callable

    def step(msg: str) -> None:
        log.info(msg)
        if on_step:
            on_step(msg)

    # ── 1. Fetch profile context ───────────────────────────────────────────────
    step("Profil wird geladen...")
    context = await _fetch_profile_context(conn, profile_id)

    cv_text = context.get("cv_text", "")
    market_research = context.get("market_research", "")
    career_target = context.get("career_target", "")
    cv_language = context.get("cv_language", "de")
    candidate_profile_raw = context.get("candidate_profile", "{}")

    try:
        candidate_profile = json.loads(candidate_profile_raw)
    except json.JSONDecodeError:
        candidate_profile = {}

    # B1 fix: role_type_scores is stored as a separate context key but the
    # Analyzer prompt expects it inside candidate_profile.  Merge it in here.
    role_type_scores_raw = context.get("role_type_scores", "{}")
    try:
        role_type_scores = json.loads(role_type_scores_raw)
    except json.JSONDecodeError:
        log.warning("profile_id=%d: role_type_scores is not valid JSON; using {}", profile_id)
        role_type_scores = {}
    candidate_profile["role_type_scores"] = role_type_scores

    if not cv_text:
        raise UserVisibleError("Kein Lebenslauf im Profil hinterlegt. Bitte Profil bearbeiten.")

    # ── 2. Detect job language ─────────────────────────────────────────────────
    job_language = detect_language(job_posting)
    log.info("Job posting language: %s (CV language: %s)", job_language, cv_language)

    # ── 3. Company Research + CV Translation (parallel) ────────────────────────
    step("Unternehmen wird recherchiert & Lebenslauf wird vorbereitet...")

    company_task = asyncio.create_task(
        run_company_research(conn, job_posting=job_posting, profile_id=profile_id)
    )
    translation_task = asyncio.create_task(
        get_cv_for_language(
            conn,
            profile_id=profile_id,
            cv_text=cv_text,
            cv_language=cv_language,
            job_language=job_language,
        )
    )
    company_result, cv_for_analysis = await asyncio.gather(company_task, translation_task)

    log.info(
        "Company: %r | CV language for analysis: %s",
        company_result.company_name,
        job_language,
    )

    # ── 4. Analysis & Scoring ──────────────────────────────────────────────────
    step("Stelle wird analysiert & bewertet...")
    scoring, gap_analysis = await run_analysis_scoring(
        conn,
        job_posting=job_posting,
        cv_text=cv_for_analysis,
        candidate_profile=candidate_profile,
        company_result=company_result,
        profile_id=profile_id,
    )

    log.info("Score: %d/100 (%s)", scoring.total_score, scoring.threshold)

    # ── 5a. Fail path ──────────────────────────────────────────────────────────
    if scoring.threshold == "fail":
        step("Keine ausreichende Übereinstimmung — Lückenanalyse wird erstellt...")
        app_id = await _store_job_application(
            conn,
            profile_id=profile_id,
            company_name=company_result.company_name,
            company_address=company_result.company_address,
            contact_person=company_result.contact_person,
            role_title=_extract_role_title(job_posting),
            job_posting=job_posting,
            scoring=scoring,
            cv_diff="",
            tailored_cv="",
            anschreiben="",
            gaps=gap_analysis or "",
        )
        return PipelineResult(
            profile_id=profile_id,
            company=company_result,
            scoring=scoring,
            tailoring=None,
            anschreiben_text=None,
            gap_analysis=gap_analysis,
            job_application_id=app_id,
        )

    # ── 5b. Pass / Caution path ────────────────────────────────────────────────
    step("Lebenslauf wird angepasst...")
    tailoring = await run_cv_tailoring(
        conn,
        cv_text=cv_for_analysis,
        job_posting=job_posting,
        career_target=career_target,
        profile_id=profile_id,
    )

    step("Anschreiben wird verfasst...")
    anschreiben_text = await run_anschreiben(
        conn,
        job_posting=job_posting,
        cv_text=tailoring.tailored_cv,
        career_target=career_target,
        candidate_profile=candidate_profile,
        company_result=company_result,
        job_language=job_language,
        profile_id=profile_id,
    )

    # ── Truthfulness: validate cover letter against the ORIGINAL CV ────────────
    # Anchored on cv_for_analysis (original, language-matched) — NOT the tailored
    # CV, which is also LLM-generated and cannot serve as its own truth source.
    # Wrapped in try/except so a broken safety check never kills document generation.
    _safe_valid = TruthfulnessResult(valid=True, issues=[], severity="low")
    surviving_warning: list[str] | None = None

    try:
        anschreiben_validation = await validate_anschreiben(
            conn,
            anschreiben_text=anschreiben_text,
            original_cv=cv_for_analysis,
            candidate_profile=candidate_profile,
            profile_id=profile_id,
        )
    except Exception as exc:
        log.warning("Anschreiben truthfulness check failed (ignored): %s", exc)
        anschreiben_validation = _safe_valid

    if anschreiben_validation.severity in ("medium", "high"):
        log.warning(
            "Anschreiben truthfulness issues (severity=%s, %d issues) — "
            "retrying with strict grounding: %s",
            anschreiben_validation.severity,
            len(anschreiben_validation.issues),
            [i.detail for i in anschreiben_validation.issues],
        )
        anschreiben_text = await run_anschreiben(
            conn,
            job_posting=job_posting,
            cv_text=tailoring.tailored_cv,
            career_target=career_target,
            candidate_profile=candidate_profile,
            company_result=company_result,
            job_language=job_language,
            profile_id=profile_id,
            strict_grounding=True,
        )
        try:
            anschreiben_validation2 = await validate_anschreiben(
                conn,
                anschreiben_text=anschreiben_text,
                original_cv=cv_for_analysis,
                candidate_profile=candidate_profile,
                profile_id=profile_id,
            )
        except Exception as exc:
            log.warning("Anschreiben truthfulness re-check failed (ignored): %s", exc)
            anschreiben_validation2 = _safe_valid

        if anschreiben_validation2.severity in ("medium", "high"):
            surviving_warning = [i.detail for i in anschreiben_validation2.issues]
            log.warning(
                "Anschreiben retry still has truthfulness issues (severity=%s) — "
                "surfacing warning to user: %s",
                anschreiben_validation2.severity,
                surviving_warning,
            )

    # ── 6. Store result ────────────────────────────────────────────────────────
    step("Ergebnisse werden gespeichert...")
    app_id = await _store_job_application(
        conn,
        profile_id=profile_id,
        company_name=company_result.company_name,
        company_address=company_result.company_address,
        contact_person=company_result.contact_person,
        role_title=_extract_role_title(job_posting),
        job_posting=job_posting,
        scoring=scoring,
        cv_diff=tailoring.cv_diff,
        tailored_cv=tailoring.tailored_cv,
        anschreiben=anschreiben_text,
        gaps="",
        truthfulness_warning=surviving_warning,
    )

    step("Fertig!")
    return PipelineResult(
        profile_id=profile_id,
        company=company_result,
        scoring=scoring,
        tailoring=tailoring,
        anschreiben_text=anschreiben_text,
        gap_analysis=None,
        job_application_id=app_id,
        anschreiben_truthfulness_warning=surviving_warning,
    )


def _extract_role_title(job_posting: str) -> str:
    """Best-effort: return first non-empty line of the posting as role title."""
    for line in job_posting.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:200]
    return "Unbekannte Stelle"
