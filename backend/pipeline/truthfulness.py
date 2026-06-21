"""
Truthfulness validation for generated documents.

Two-tier approach:
  1. Deterministic word-inflation check for the tailored CV (free, instant).
     NOTE: This is a weak first guard — it only catches verbatim expansion
     by the rewriter, not word-neutral fabrications (swapped skills, inflated
     tenure, etc.).  No semantic CV validation is performed yet.
  2. LLM (Haiku) structured check for the cover letter (cheapest model, ~$0.001/call).
     Anchored on the ORIGINAL cv_text (+ structured candidate_profile), not on the
     tailored CV — the tailored CV is also LLM-generated and cannot be a truth source.

Chosen safe behaviors:
  - CV inflation → fall back to pre-rewrite edited CV (caller's responsibility).
  - Cover letter issues → caller retries run_anschreiben with strict_grounding=True.
    If the retry still has issues, the result is used but a warning is surfaced.
  - Validator errors (API failures, JSON parse errors) → fail open: log + return
    a safe "valid/low" result so a broken safety check never kills generation.
"""
import logging

import asyncpg

from backend import llm
from backend.models.validation import TruthfulnessIssue, TruthfulnessResult
from backend.prompts.loader import load_prompt

log = logging.getLogger(__name__)

_HAIKU = "claude-haiku-4-5-20251001"


def check_cv_word_inflation(
    original_cv: str,
    edited_cv: str,
    rewritten_cv: str,
) -> TruthfulnessResult:
    """
    Deterministic check that the rewriter did not inflate the tailored CV.

    The tailoring pipeline is purely subtractive (removes + shortens items),
    so the final word count must not exceed the original.  The rewriter step
    also polishes — not expands — so it should not add significant new words
    vs the pre-rewrite edited CV.

    Thresholds:
      > 5% above original   → medium severity (pipeline is subtractive)
      > 15% above edited_cv → medium severity (rewriter over-expanded)
    """
    original_count = len(original_cv.split())
    edited_count = len(edited_cv.split())
    rewritten_count = len(rewritten_cv.split())

    issues: list[TruthfulnessIssue] = []

    if original_count > 0 and rewritten_count > original_count * 1.05:
        issues.append(TruthfulnessIssue(
            claim=f"{rewritten_count} words vs {original_count} original",
            issue_type="unsupported_claim",
            detail=(
                f"Tailored CV ({rewritten_count} words) exceeds original "
                f"({original_count} words) by more than 5%. "
                "The pipeline is subtractive — new content may have been introduced."
            ),
        ))
    elif edited_count > 0 and rewritten_count > edited_count * 1.15:
        issues.append(TruthfulnessIssue(
            claim=f"{rewritten_count} words vs {edited_count} pre-rewrite",
            issue_type="unsupported_claim",
            detail=(
                f"Rewriter inflated word count by more than 15%: "
                f"{rewritten_count} words vs {edited_count} pre-rewrite."
            ),
        ))

    if not issues:
        return TruthfulnessResult(valid=True, issues=[], severity="low")
    return TruthfulnessResult(valid=False, issues=issues, severity="medium")


def _format_candidate_profile(profile: dict) -> str:
    """Format structured profile fields for the validator prompt."""
    parts = []
    for key, label in [
        ("name", "Name"),
        ("core_skills", "Core skills"),
        ("secondary_tools", "Secondary tools"),
    ]:
        val = str(profile.get(key, "")).strip()
        if val:
            parts.append(f"{label}: {val}")
    return "\n".join(parts)


async def validate_anschreiben(
    conn: asyncpg.Connection,
    *,
    anschreiben_text: str,
    original_cv: str,
    candidate_profile: dict | None = None,
    profile_id: int | None = None,
) -> TruthfulnessResult:
    """
    LLM (Haiku) check: does the cover letter contain claims unsupported by the CV?

    Anchored on `original_cv` — the candidate's actual CV before any LLM tailoring —
    so a hallucination in the tailored CV cannot launder into the cover letter
    undetected.  The structured `candidate_profile` (core skills, secondary tools)
    is included as additional structured context.

    Returns a TruthfulnessResult so the caller can retry or warn without crashing.
    """
    system = load_prompt("truthfulness_validator")

    profile_block = ""
    if candidate_profile:
        summary = _format_candidate_profile(candidate_profile)
        if summary:
            profile_block = f"<candidate_profile>\n{summary}\n</candidate_profile>\n\n"

    user = (
        f"<original_cv>\n{original_cv}\n</original_cv>\n\n"
        f"{profile_block}"
        f"<cover_letter>\n{anschreiben_text}\n</cover_letter>\n\n"
        "Check every specific factual claim in the cover letter against the original CV "
        "and candidate profile. Return structured JSON."
    )

    log.info("Running Anschreiben truthfulness check (Haiku)...")
    result = await llm.call_structured(
        conn,
        model=_HAIKU,
        system=system,
        user=user,
        response_model=TruthfulnessResult,
        max_tokens=800,
        temperature=0.0,
        node_name="truthfulness_validator",
        profile_id=profile_id,
    )
    log.info(
        "Anschreiben truthfulness: valid=%s severity=%s issues=%d",
        result.valid,
        result.severity,
        len(result.issues),
    )
    return result
