"""
Requirements compliance check.

Uses Haiku to identify explicit mandatory requirements from the job posting
and verify whether the candidate clearly fails to meet any of them.

Runs after the Analyzer (GPT-4.1) as a focused secondary check.
The result is used by apply_requirements_override() in deterministic/scoring.py
to adjust the final threshold without touching the dimension scores.
"""
import json
import logging

import asyncpg

from backend import llm
from backend.models.requirements import RequirementsAnalysis
from backend.prompts.loader import load_prompt

log = logging.getLogger(__name__)

_HAIKU = "claude-haiku-4-5-20251001"

_PROFILE_KEYS = ("core_skills", "secondary_tools", "home_location", "commute_options", "career_target")


async def run_requirements_check(
    conn: asyncpg.Connection,
    *,
    job_posting: str,
    cv_text: str,
    candidate_profile: dict,
    profile_id: int | None = None,
) -> RequirementsAnalysis:
    """
    Extract explicit mandatory requirements from the job posting and compare
    them against the candidate's CV and profile.

    Returns RequirementsAnalysis with structured lists of blockers.
    Never raises — returns an empty (no-blockers) result on error so a failed
    check never prevents document generation.
    """
    system = load_prompt("requirements_extractor")

    profile_summary = json.dumps(
        {k: v for k, v in candidate_profile.items() if k in _PROFILE_KEYS and v},
        ensure_ascii=False,
        indent=2,
    )
    user = (
        f"<job_posting>\n{job_posting}\n</job_posting>\n\n"
        f"<candidate_profile>\n{profile_summary}\n</candidate_profile>\n\n"
        f"<cv_text>\n{cv_text}\n</cv_text>"
    )

    log.info("Running requirements check (Haiku)...")
    result = await llm.call_structured(
        conn,
        model=_HAIKU,
        system=system,
        user=user,
        response_model=RequirementsAnalysis,
        max_tokens=1000,
        temperature=0.0,
        node_name="requirements_check",
        profile_id=profile_id,
    )

    log.info(
        "Requirements check: %d hard missing, %d dealbreakers, %d soft missing",
        len(result.missing_hard_requirements),
        len(result.triggered_dealbreakers),
        len(result.missing_soft_requirements),
    )
    return result
