"""
Anschreiben (cover letter) generation pipeline.
Ports the n8n Anschreiben node from the main workflow.
Uses claude-sonnet-4-6 (as per hard constraint).
"""
import logging

import asyncpg

from backend import llm
from backend.models.company import CompanyResearchResult
from backend.prompts.loader import load_prompt

log = logging.getLogger(__name__)

_SONNET = "claude-sonnet-4-6"


async def run_anschreiben(
    conn: asyncpg.Connection,
    *,
    job_posting: str,
    cv_text: str,
    career_target: str,
    candidate_profile: dict,
    company_result: CompanyResearchResult,
    job_language: str = "de",
    profile_id: int | None = None,
) -> str:
    """
    Generate a cover letter for the given job posting and candidate profile.
    Returns the cover letter text (without address block or date).
    """
    system = load_prompt("anschreiben")

    name = candidate_profile.get("name", "")
    core_skills = candidate_profile.get("core_skills", "")
    target_format = candidate_profile.get("target_format", "")
    commute_options = candidate_profile.get("commute_options", "")

    user = (
        f"<job_language>{job_language}</job_language>\n\n"
        f"<job_posting>\n{job_posting}\n</job_posting>\n\n"
        f"<company_name>{company_result.company_name}</company_name>\n\n"
        f"<company_profile>\n{company_result.company_profile}\n</company_profile>\n\n"
        f"<cv_text>\n{cv_text}\n</cv_text>\n\n"
        f"<candidate_summary>\n"
        f"Name: {name}\n"
        f"Core skills: {core_skills}\n"
        f"Career target: {career_target}\n"
        f"Work format preference: {target_format}\n"
        f"Location / commute: {commute_options}\n"
        f"</candidate_summary>"
    )

    log.info("Generating Anschreiben (Sonnet)...")
    text = await llm.call_raw(
        conn,
        model=_SONNET,
        system=system,
        user=user,
        max_tokens=1000,
        temperature=0.3,
        node_name="anschreiben",
        profile_id=profile_id,
    )
    log.info("Anschreiben complete: %d words", len(text.split()))
    return text
