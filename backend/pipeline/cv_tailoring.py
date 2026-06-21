"""
CV Tailoring pipeline.
Ports the n8n "Utility: CV Tailoring Planner" sub-workflow + CV Deterministic Editor + CV Rewriter.

Flow:
  1. compute_word_budget()          — how many words the tailored CV should have
  2. Parse CV into numbered items   — deterministic
  3. Classifier (GPT-4.1)           — KEEP / DISTRAKTOR / TRANSFERABEL per item
  4. enforcer()                     — converts classifications → Generator instructions
  5. Generator (Haiku)              — produces ENTFERNEN / KÜRZEN actions with new content
  6. validator()                    — checks no-ops, TRANSFERABEL+REMOVE, cluster guard
  7a. If errors → Retry (Sonnet)    — regenerate with error context
  7b. If valid → CV Deterministic Editor (deterministic removes by exact string)
  8. CV Rewriter (Haiku)            — polish the edited CV
  9. compute_diff()                 — line-level diff for the UI
"""
import json
import logging
import re

import asyncpg

from backend import llm
from backend.deterministic.cv_editor import apply_removes_by_content, compute_diff, validate_generator_output
from backend.deterministic.word_budget import compute_word_budget, enforcer
from backend.models.tailoring import (
    ClassifierOutput,
    GeneratorItem,
    GeneratorOutput,
    TailoringResult,
    ValidationResult,
)
from backend.prompts.loader import load_prompt

log = logging.getLogger(__name__)

_GPT41 = "gpt-4.1"
_HAIKU = "claude-haiku-4-5-20251001"
_SONNET = "claude-sonnet-4-6"


# ── CV item parsing ───────────────────────────────────────────────────────────

def _parse_cv_items(cv_text: str) -> tuple[dict[str, str], dict[str, str]]:
    """
    Split CV into numbered items for classification.
    Returns:
      cv_items: {item_id → content}
      section_membership: {item_id → section_header}
    """
    cv_items: dict[str, str] = {}
    section_membership: dict[str, str] = {}
    current_section = "__root__"
    counter = 0

    for line in cv_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("##"):
            current_section = stripped.lstrip("#").strip()
            continue
        # Each non-empty, non-header line becomes an item
        item_id = f"item_{counter:03d}"
        content = stripped.lstrip("-•* ").strip()
        if content:
            cv_items[item_id] = content
            section_membership[item_id] = current_section
            counter += 1

    return cv_items, section_membership


def _rebuild_cv(cv_text: str, generator_output: GeneratorOutput, cv_items: dict[str, str]) -> tuple[str, list[str]]:
    """
    Apply generator output to cv_text.
    - ENTFERNEN: collect original content strings for exact-match removal
    - KÜRZEN: replace original line with new_content in-place
    Returns (modified_cv_text, list_of_content_strings_to_remove).
    """
    gen_map = {item.id: item for item in generator_output.items}
    # Build reverse map: content → item_id
    content_to_id = {v: k for k, v in cv_items.items()}

    to_remove: list[str] = []
    modifications: dict[str, str] = {}  # original content → new content

    for item_id, gen_item in gen_map.items():
        original_content = cv_items.get(item_id, "")
        if gen_item.action == "ENTFERNEN":
            to_remove.append(original_content)
        elif gen_item.action == "KÜRZEN" and gen_item.new_content.strip():
            modifications[original_content] = gen_item.new_content.strip()

    # Apply KÜRZEN in-place (replace text in cv_text)
    result = cv_text
    for original, replacement in modifications.items():
        result = result.replace(original, replacement, 1)

    # Apply ENTFERNEN by exact string match
    result = apply_removes_by_content(result, to_remove)

    return result, to_remove


# ── LLM steps ─────────────────────────────────────────────────────────────────

async def _run_classifier(
    conn: asyncpg.Connection,
    *,
    cv_items: dict[str, str],
    job_posting: str,
    career_target: str,
    word_budget: int,
    profile_id: int | None,
) -> ClassifierOutput:
    system = load_prompt("cv_classifier")
    items_json = json.dumps(
        [{"id": k, "content": v} for k, v in cv_items.items()],
        ensure_ascii=False,
        indent=2,
    )
    user = (
        f"<word_budget>{word_budget}</word_budget>\n\n"
        f"<career_target>{career_target}</career_target>\n\n"
        f"<job_posting>\n{job_posting}\n</job_posting>\n\n"
        f"<cv_items>\n{items_json}\n</cv_items>"
    )
    return await llm.call_structured(
        conn,
        model=_GPT41,
        system=system,
        user=user,
        response_model=ClassifierOutput,
        max_tokens=8192,
        temperature=0.1,
        node_name="cv_classifier",
        profile_id=profile_id,
    )


async def _run_generator(
    conn: asyncpg.Connection,
    *,
    enforcer_items: list[GeneratorItem],
    cv_items: dict[str, str],
    job_posting: str,
    career_target: str,
    node_name: str,
    profile_id: int | None,
    model: str = _HAIKU,
    error_context: str = "",
) -> GeneratorOutput:
    system = load_prompt("cv_generator")
    items_json = json.dumps(
        [{"id": item.id, "action": item.action, "content": cv_items.get(item.id, "")}
         for item in enforcer_items],
        ensure_ascii=False,
        indent=2,
    )
    user = (
        f"<job_posting>\n{job_posting}\n</job_posting>\n\n"
        f"<career_target>{career_target}</career_target>\n\n"
        f"<items_to_process>\n{items_json}\n</items_to_process>"
    )
    if error_context:
        user += f"\n\n<validation_errors>{error_context}</validation_errors>"

    return await llm.call_structured(
        conn,
        model=model,
        system=system,
        user=user,
        response_model=GeneratorOutput,
        max_tokens=8192,
        temperature=0.1,
        node_name=node_name,
        profile_id=profile_id,
    )


async def _run_rewriter(
    conn: asyncpg.Connection,
    *,
    cv_text: str,
    job_posting: str,
    profile_id: int | None,
) -> str:
    system = load_prompt("cv_rewriter")
    user = (
        f"<job_posting>\n{job_posting}\n</job_posting>\n\n"
        f"<edited_cv>\n{cv_text}\n</edited_cv>"
    )
    return await llm.call_raw(
        conn,
        model=_HAIKU,
        system=system,
        user=user,
        max_tokens=8192,
        temperature=0.1,
        node_name="cv_rewriter",
        profile_id=profile_id,
    )


# ── Main entry point ──────────────────────────────────────────────────────────

async def run_cv_tailoring(
    conn: asyncpg.Connection,
    *,
    cv_text: str,
    job_posting: str,
    career_target: str,
    profile_id: int | None = None,
) -> TailoringResult:
    """
    Full CV tailoring pipeline. Returns TailoringResult with tailored CV + diff.
    """
    word_budget = compute_word_budget(cv_text)
    log.info("CV tailoring: word_budget=%d (original=%d words)", word_budget, len(cv_text.split()))

    cv_items, section_membership = _parse_cv_items(cv_text)
    log.info("Parsed %d CV items across %d sections", len(cv_items), len(set(section_membership.values())))

    # Step 1: Classify
    log.info("Running CV Classifier (GPT-4.1)...")
    classifier_output = await _run_classifier(
        conn,
        cv_items=cv_items,
        job_posting=job_posting,
        career_target=career_target,
        word_budget=word_budget,
        profile_id=profile_id,
    )

    keep_count = sum(1 for i in classifier_output.items if i.classification == "KEEP")
    dist_count = sum(1 for i in classifier_output.items if i.classification == "DISTRAKTOR")
    trans_count = sum(1 for i in classifier_output.items if i.classification == "TRANSFERABEL")
    log.info("Classifier: KEEP=%d DISTRAKTOR=%d TRANSFERABEL=%d", keep_count, dist_count, trans_count)

    # Step 2: Enforcer → generator instructions
    enforcer_items = enforcer(classifier_output, cv_items)
    log.info("Enforcer produced %d instructions for Generator", len(enforcer_items))

    if not enforcer_items:
        log.info("No changes needed — returning original CV")
        return TailoringResult(
            tailored_cv=cv_text,
            cv_diff="",
            items_removed=0,
            items_shortened=0,
        )

    # Step 3: Generate
    log.info("Running CV Generator (Haiku)...")
    generator_output = await _run_generator(
        conn,
        enforcer_items=enforcer_items,
        cv_items=cv_items,
        job_posting=job_posting,
        career_target=career_target,
        node_name="cv_generator",
        profile_id=profile_id,
    )

    # Step 4: Validate
    validation = validate_generator_output(
        generator_output, classifier_output, cv_items, section_membership
    )
    retry_used = False

    if not validation.valid:
        error_context = "\n".join(f"- {e.error_type}: {e.detail}" for e in validation.errors)
        log.warning("Validation failed (%d errors) — retrying with Sonnet:\n%s", len(validation.errors), error_context)
        generator_output = await _run_generator(
            conn,
            enforcer_items=enforcer_items,
            cv_items=cv_items,
            job_posting=job_posting,
            career_target=career_target,
            node_name="cv_generator_retry",
            profile_id=profile_id,
            model=_SONNET,
            error_context=error_context,
        )
        retry_used = True
        # Re-validate (log only — proceed regardless)
        validation2 = validate_generator_output(
            generator_output, classifier_output, cv_items, section_membership
        )
        if not validation2.valid:
            log.warning("Retry still has validation errors — proceeding anyway: %s", validation2.errors)

    # Step 5: Apply edits (deterministic removes + in-place KÜRZEN)
    edited_cv, removed_contents = _rebuild_cv(cv_text, generator_output, cv_items)

    items_removed = sum(1 for i in generator_output.items if i.action == "ENTFERNEN")
    items_shortened = sum(1 for i in generator_output.items if i.action == "KÜRZEN")
    log.info("Applied edits: %d removed, %d shortened", items_removed, items_shortened)

    # Step 6: Rewrite (polish)
    log.info("Running CV Rewriter (Haiku)...")
    rewritten_cv = await _run_rewriter(
        conn,
        cv_text=edited_cv,
        job_posting=job_posting,
        profile_id=profile_id,
    )

    # Step 7: Compute diff
    cv_diff = compute_diff(cv_text, rewritten_cv)

    return TailoringResult(
        tailored_cv=rewritten_cv,
        cv_diff=cv_diff,
        items_removed=items_removed,
        items_shortened=items_shortened,
        retry_used=retry_used,
    )
