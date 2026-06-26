"""
Profile extraction pipeline.
Ports the n8n "Utility: Extract Profile" workflow to Python.
Handles both CREATE and UPDATE modes. All LLM calls go through llm.py.
"""
import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Callable, Literal

import asyncpg

from backend import llm
from backend.deterministic.cv_utils import compute_content_hash, hash_cv, normalize_cv
from backend.deterministic.language import detect_language
from backend.models.profile import (
    BinaryClassifierOutput,
    CandidateProfileOutput,
    CoreSkillsOutput,
    MarketResearchOutput,
    ProfileRow,
    ProfileSummary,
)
from backend.prompts.loader import load_prompt

log = logging.getLogger(__name__)

_HAIKU = "claude-haiku-4-5-20251001"
_SONNET = "claude-sonnet-4-6"
_CORE_SKILLS_MIN_COUNT = 2


# ── Public result type ────────────────────────────────────────────────────────

@dataclass
class ProfileSetupResult:
    profile_id: int
    action: Literal["created", "updated"]
    llm_ran: bool


# ── DB helpers ────────────────────────────────────────────────────────────────

async def list_profiles(conn: asyncpg.Connection) -> list[ProfileSummary]:
    rows = await conn.fetch(
        """
        SELECT id, first_name, last_name, avatar_url,
               street_address, postal_code, city,
               email, phone_country_code, phone_number,
               linkedin_url, github_url
        FROM job_application_assistant.profiles
        ORDER BY last_name, first_name
        """
    )
    return [ProfileSummary(**dict(r)) for r in rows]


async def get_profile(conn: asyncpg.Connection, profile_id: int) -> ProfileRow | None:
    row = await conn.fetchrow(
        """
        SELECT
            p.id, p.first_name, p.last_name, p.email,
            p.phone_country_code, p.phone_number,
            p.street_address, p.postal_code, p.city,
            p.linkedin_url, p.github_url, p.avatar_url,
            MAX(CASE WHEN cc.key = 'cv_text'          THEN cc.value END) AS cv_text,
            MAX(CASE WHEN cc.key = 'market_research'   THEN cc.value END) AS market_research,
            MAX(CASE WHEN cc.key = 'career_target'     THEN cc.value END) AS career_target
        FROM job_application_assistant.profiles p
        LEFT JOIN job_application_assistant.candidate_context cc
               ON cc.profile_id = p.id
              AND cc.key IN ('cv_text', 'market_research', 'career_target')
        WHERE p.id = $1
        GROUP BY p.id
        """,
        profile_id,
    )
    if not row:
        return None
    return ProfileRow(**dict(row))


# ── Candidate context helpers ─────────────────────────────────────────────────

async def _upsert_context(conn: asyncpg.Connection, profile_id: int, key: str, value: str) -> None:
    await conn.execute(
        """
        INSERT INTO job_application_assistant.candidate_context (profile_id, key, value)
        VALUES ($1, $2, $3)
        ON CONFLICT (profile_id, key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
        """,
        profile_id,
        key,
        value,
    )


async def _delete_translation_cache(conn: asyncpg.Connection, profile_id: int) -> None:
    """Remove translation cache entries when CV changes."""
    await conn.execute(
        """
        DELETE FROM job_application_assistant.candidate_context
        WHERE profile_id = $1 AND key LIKE 'translated_cv_text_%'
        """,
        profile_id,
    )


# ── LLM extraction steps ──────────────────────────────────────────────────────

async def _extract_market_research(
    conn: asyncpg.Connection, market_research: str, profile_id: int
) -> MarketResearchOutput:
    system = load_prompt("market_research_extractor")
    user = f"<market_research>\n{market_research}\n</market_research>"
    return await llm.call_structured(
        conn,
        model=_HAIKU,
        system=system,
        user=user,
        response_model=MarketResearchOutput,
        max_tokens=2048,
        node_name="market_research_extractor",
        profile_id=profile_id,
    )


async def _classify_technologies(
    conn: asyncpg.Connection, candidates: list[str], profile_id: int
) -> BinaryClassifierOutput:
    system = load_prompt("binary_classifier")
    user = f"Classify each item in this list:\n{json.dumps(candidates, ensure_ascii=False)}"
    return await llm.call_structured(
        conn,
        model=_HAIKU,
        system=system,
        user=user,
        response_model=BinaryClassifierOutput,
        max_tokens=4096,
        node_name="binary_classifier",
        profile_id=profile_id,
    )


async def _extract_core_skills(
    conn: asyncpg.Connection, cv_text: str, profile_id: int
) -> CoreSkillsOutput:
    system = load_prompt("core_skills_extractor")
    user = f"<cv_text>\n{cv_text}\n</cv_text>"
    return await llm.call_structured(
        conn,
        model=_HAIKU,
        system=system,
        user=user,
        response_model=CoreSkillsOutput,
        max_tokens=2048,
        node_name="core_skills_extractor",
        profile_id=profile_id,
    )


def _dynamic_filter(
    market: MarketResearchOutput,
    classifier: BinaryClassifierOutput,
    core_skills: CoreSkillsOutput,
) -> tuple[list[str], list[str], list[dict], list[str]]:
    """
    Mirrors the n8n Dynamic Filter Code Node.
    Returns (technology_list, city_list, role_list_dicts, core_skills_list).
    """
    valid_items = {d.item for d in classifier.decisions if d.valid}
    technology_list = [c for c in market.candidates if c in valid_items]

    city_list = market.city_list

    role_list_dicts = [
        {"label": r.label, "frequency": r.frequency, "bridge_quality": r.bridge_quality}
        for r in market.role_list
    ]

    # Technologies appearing in >= CORE_SKILLS_MIN_COUNT projects, ordered by count desc
    core_skills_list = [
        s.technology
        for s in sorted(core_skills.skill_counts, key=lambda x: -x.count)
        if s.count >= _CORE_SKILLS_MIN_COUNT
    ]

    return technology_list, city_list, role_list_dicts, core_skills_list


async def _extract_candidate_profile(
    conn: asyncpg.Connection,
    *,
    cv_text: str,
    career_target: str,
    market_research: str,
    technology_list: list[str],
    city_list: list[str],
    role_list: list[dict],
    core_skills_list: list[str],
    profile_id: int,
) -> CandidateProfileOutput:
    system = load_prompt("candidate_profile")
    user = (
        f"<cv_text>\n{cv_text}\n</cv_text>\n\n"
        f"<technology_list>\n{json.dumps(technology_list, ensure_ascii=False)}\n</technology_list>\n\n"
        f"<city_list>\n{json.dumps(city_list, ensure_ascii=False)}\n</city_list>\n\n"
        f"<role_list>\n{json.dumps(role_list, ensure_ascii=False, indent=2)}\n</role_list>\n\n"
        f"<core_skills_list>\n{json.dumps(core_skills_list, ensure_ascii=False)}\n</core_skills_list>\n\n"
        f"<career_target>\n{career_target}\n</career_target>\n\n"
        f"<market_research>\n{market_research}\n</market_research>"
    )
    return await llm.call_structured(
        conn,
        model=_SONNET,
        system=system,
        user=user,
        response_model=CandidateProfileOutput,
        max_tokens=6000,
        temperature=0.0,
        node_name="candidate_profile_extractor",
        profile_id=profile_id,
    )


def _finalize_output(
    output: CandidateProfileOutput, market_research: str
) -> CandidateProfileOutput:
    """
    Mirrors the n8n Finalize Output Code Node.
    Ensures home city appears in commute_options if market_research mentions it.
    """
    import re

    profile = output.candidate_profile
    home_city = profile.home_location.split(",")[0].strip()
    if not home_city:
        return output

    if home_city.lower() not in profile.commute_options.lower():
        if re.search(rf"\b{re.escape(home_city)}\b", market_research, re.IGNORECASE):
            updated = output.model_copy(
                update={
                    "candidate_profile": profile.model_copy(
                        update={
                            "commute_options": (
                                f"{home_city} (~0h, Heimatstadt) | {profile.commute_options}"
                            )
                        }
                    )
                }
            )
            return updated

    return output


# ── Main entry point ──────────────────────────────────────────────────────────

async def run_profile_setup(
    conn: asyncpg.Connection,
    *,
    # Profile fields
    first_name: str,
    last_name: str,
    email: str | None = None,
    phone_country_code: str = "+49",
    phone_number: str | None = None,
    street_address: str | None = None,
    postal_code: str | None = None,
    city: str | None = None,
    linkedin_url: str | None = None,
    github_url: str | None = None,
    avatar_url: str | None = None,
    # Content fields
    cv_text: str,
    market_research: str,
    career_target: str,
    # Optional: if set → UPDATE mode; else → CREATE mode
    profile_id: int | None = None,
    # Progress callback for UI updates
    on_step: Callable[[str], None] | None = None,
) -> ProfileSetupResult:
    """
    Full profile setup pipeline.
    Creates or updates the profile and runs LLM extraction if needed.
    """

    def step(msg: str) -> None:
        log.info(msg)
        if on_step:
            on_step(msg)

    is_update = profile_id is not None
    cv_normalized = normalize_cv(cv_text)
    cv_hash = hash_cv(cv_normalized)
    cv_lang = detect_language(cv_normalized)
    # Hash covering all three LLM-input fields; drives whether re-extraction runs.
    content_hash = compute_content_hash(cv_normalized, career_target, market_research)

    async with conn.transaction():
        if is_update:
            # ── UPDATE ────────────────────────────────────────────────────────
            step("Profil wird aktualisiert...")
            await conn.execute(
                """
                UPDATE job_application_assistant.profiles
                SET first_name=$1, last_name=$2, email=$3, phone_country_code=$4,
                    phone_number=$5, street_address=$6, postal_code=$7, city=$8,
                    linkedin_url=$9, github_url=$10, avatar_url=$11, updated_at=NOW()
                WHERE id=$12
                """,
                first_name, last_name, email, phone_country_code,
                phone_number, street_address, postal_code, city,
                linkedin_url, github_url, avatar_url, profile_id,
            )
            action: Literal["created", "updated"] = "updated"

            # cv_changed → invalidate translation cache (CV language may differ)
            old_cv_hash = await conn.fetchval(
                "SELECT value FROM job_application_assistant.candidate_context WHERE profile_id=$1 AND key='cv_hash'",
                profile_id,
            )
            cv_changed = (old_cv_hash != cv_hash)
            if cv_changed:
                step("Lebenslauf geändert — Übersetzungs-Cache wird gelöscht...")
                await _delete_translation_cache(conn, profile_id)

            # B2 fix: also re-extract when career_target or market_research change.
            # content_hash covers all three LLM-input fields; None means first run
            # after this fix was deployed, which safely triggers one re-extraction.
            old_content_hash = await conn.fetchval(
                "SELECT value FROM job_application_assistant.candidate_context WHERE profile_id=$1 AND key='content_hash'",
                profile_id,
            )
            content_changed = (old_content_hash != content_hash)

        else:
            # ── CREATE ────────────────────────────────────────────────────────
            step("Neues Profil wird erstellt...")
            profile_id = await conn.fetchval(
                """
                INSERT INTO job_application_assistant.profiles
                    (first_name, last_name, email, phone_country_code, phone_number,
                     street_address, postal_code, city, linkedin_url, github_url, avatar_url)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                RETURNING id
                """,
                first_name, last_name, email, phone_country_code, phone_number,
                street_address, postal_code, city, linkedin_url, github_url, avatar_url,
            )
            action = "created"
            cv_changed = True
            content_changed = True  # Always run LLM for new profiles

        # ── Upsert content into candidate_context ─────────────────────────────
        for key, value in [
            ("cv_text", cv_normalized),
            ("market_research", market_research),
            ("career_target", career_target),
            ("cv_hash", cv_hash),
            ("cv_language", cv_lang),
            ("content_hash", content_hash),
        ]:
            await _upsert_context(conn, profile_id, key, value)

    # ── LLM extraction (outside transaction — can be slow) ────────────────────
    # B2 fix: was `cv_changed`; now covers career_target + market_research too.
    llm_needed = not is_update or content_changed
    if llm_needed:
        step("Marktrecherche wird analysiert...")

        # Run market_research and core_skills extractions in parallel
        mr_task = asyncio.create_task(
            _extract_market_research(conn, market_research, profile_id)
        )
        cs_task = asyncio.create_task(
            _extract_core_skills(conn, cv_normalized, profile_id)
        )
        market_output, core_skills_output = await asyncio.gather(mr_task, cs_task)

        step("Technologien werden klassifiziert...")
        classifier_output = await _classify_technologies(
            conn, market_output.candidates, profile_id
        )

        technology_list, city_list, role_list_dicts, core_skills_list = _dynamic_filter(
            market_output, classifier_output, core_skills_output
        )

        step("Kandidatenprofil wird extrahiert...")
        profile_output = await _extract_candidate_profile(
            conn,
            cv_text=cv_normalized,
            career_target=career_target,
            market_research=market_research,
            technology_list=technology_list,
            city_list=city_list,
            role_list=role_list_dicts,
            core_skills_list=core_skills_list,
            profile_id=profile_id,
        )
        profile_output = _finalize_output(profile_output, market_research)

        step("Ergebnisse werden gespeichert...")
        async with conn.transaction():
            await _upsert_context(
                conn,
                profile_id,
                "candidate_profile",
                json.dumps(profile_output.candidate_profile.model_dump(), ensure_ascii=False),
            )
            await _upsert_context(
                conn,
                profile_id,
                "role_type_scores",
                json.dumps(profile_output.role_type_scores, ensure_ascii=False),
            )

        step("Profil vollständig gespeichert.")
    else:
        step("Kein LLM-Durchlauf nötig (kein CV-Wechsel).")

    return ProfileSetupResult(
        profile_id=profile_id,
        action=action,
        llm_ran=llm_needed,
    )
