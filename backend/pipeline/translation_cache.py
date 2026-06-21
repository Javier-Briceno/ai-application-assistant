"""
CV Translation Cache pipeline.
Ports the n8n "Utility: CV Translation Cache" sub-workflow to Python.

Flow:
  1. If cv_language == job_language → return original cv_text (no translation needed)
  2. Fetch cache state from candidate_context:
       translated_cv_text_{lang}         — the cached translation
       translated_cv_text_{lang}_source_hash — the cv_hash when it was cached
  3. Cache hit: translation exists AND source_hash matches current cv_hash → return cached text
  4. Cache miss: call LLM translator (Sonnet)
  5. Save new translation + source_hash to candidate_context
  6. Return translated text
"""
import logging

import asyncpg

from backend import llm
from backend.deterministic.cv_utils import hash_cv
from backend.prompts.loader import load_prompt

log = logging.getLogger(__name__)

_SONNET = "claude-sonnet-4-6"


async def _fetch_cache(
    conn: asyncpg.Connection, profile_id: int, lang: str
) -> tuple[str | None, str | None]:
    """Return (cached_translation, source_hash) for the given language."""
    rows = await conn.fetch(
        """
        SELECT key, value
        FROM job_application_assistant.candidate_context
        WHERE profile_id = $1
          AND key IN ($2, $3)
        """,
        profile_id,
        f"translated_cv_text_{lang}",
        f"translated_cv_text_{lang}_source_hash",
    )
    data = {r["key"]: r["value"] for r in rows}
    cached_text = data.get(f"translated_cv_text_{lang}")
    source_hash = data.get(f"translated_cv_text_{lang}_source_hash")
    return cached_text, source_hash


async def _save_cache(
    conn: asyncpg.Connection, profile_id: int, lang: str, translated_text: str, cv_hash: str
) -> None:
    for key, value in [
        (f"translated_cv_text_{lang}", translated_text),
        (f"translated_cv_text_{lang}_source_hash", cv_hash),
    ]:
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


async def _translate_cv(
    conn: asyncpg.Connection,
    *,
    cv_text: str,
    target_language: str,
    profile_id: int | None,
) -> str:
    system = load_prompt("cv_translator")
    user = (
        f"<target_language>{target_language}</target_language>\n\n"
        f"<cv_text>\n{cv_text}\n</cv_text>"
    )
    return await llm.call_raw(
        conn,
        model=_SONNET,
        system=system,
        user=user,
        max_tokens=3000,
        temperature=0.2,
        node_name="cv_translator",
        profile_id=profile_id,
    )


async def get_cv_for_language(
    conn: asyncpg.Connection,
    *,
    profile_id: int,
    cv_text: str,
    cv_language: str,
    job_language: str,
) -> str:
    """
    Return the CV text in job_language.
    Uses cached translation if available and cv_hash matches.
    Falls back to original if translation fails.
    """
    if cv_language == job_language:
        log.info("CV language matches job language (%s) — no translation needed", cv_language)
        return cv_text

    current_hash = hash_cv(cv_text)
    cached_text, source_hash = await _fetch_cache(conn, profile_id, job_language)

    if cached_text and source_hash == current_hash:
        log.info("Translation cache hit for profile %d → %s", profile_id, job_language)
        return cached_text

    log.info(
        "Translation cache miss for profile %d → %s (cv_changed=%s) — calling LLM",
        profile_id,
        job_language,
        source_hash != current_hash,
    )

    try:
        translated = await _translate_cv(
            conn,
            cv_text=cv_text,
            target_language=job_language,
            profile_id=profile_id,
        )
    except Exception:
        log.exception("CV translation failed — using original cv_text as fallback")
        return cv_text

    await _save_cache(conn, profile_id, job_language, translated, current_hash)
    log.info("Translation saved to cache for profile %d → %s", profile_id, job_language)

    return translated
