"""
Tests for the cv_rewriter skip optimization.

When items_removed == 0, the rewriter is skipped (no gaps to smooth).
When items_removed > 0, the rewriter is called as before.

R1 — KÜRZEN-only run: _run_rewriter is not called
R2 — Mixed run (removes present): _run_rewriter is called
R3 — Skipped rewriter: tailored_cv reflects the deterministic KÜRZEN edit
R4 — Skipped rewriter: inflation check still runs and returns valid
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models.tailoring import (
    ClassifierItem,
    ClassifierOutput,
    GeneratorItem,
    GeneratorOutput,
)

_JOB = "We need a backend engineer with Python experience"
_TARGET = "Backend Engineer"

# 25 words exactly — meets the enforcer's _SHORTEN_MIN_WORDS threshold so that
# a TRANSFERABEL classification produces a KÜRZEN instruction.
_LONG_ITEM = (
    "Developed scalable distributed backend systems using Python, Redis, and Kafka, "
    "achieving significant latency reductions and major throughput improvements "
    "across the whole microservices platform with Kubernetes"
)

_CV = f"## Experience\n- {_LONG_ITEM}\n\n## Skills\n- Python\n"


# ── helpers ───────────────────────────────────────────────────────────────────

def _mk_classifier(**classifications: str) -> ClassifierOutput:
    return ClassifierOutput(items=[
        ClassifierItem(id=k, classification=v)
        for k, v in classifications.items()
    ])


def _mk_generator(*rows: tuple[str, str, str]) -> GeneratorOutput:
    return GeneratorOutput(items=[
        GeneratorItem(id=item_id, action=action, new_content=content)
        for item_id, action, content in rows
    ])


# ── R1: KÜRZEN-only run skips _run_rewriter ───────────────────────────────────

@pytest.mark.asyncio
async def test_kuerzen_only_skips_rewriter():
    """No items removed → rewriter must not be called."""
    from backend.pipeline.cv_tailoring import run_cv_tailoring

    mock_rewriter = AsyncMock()

    with (
        patch("backend.pipeline.cv_tailoring._run_classifier",
              AsyncMock(return_value=_mk_classifier(item_000="TRANSFERABEL", item_001="KEEP"))),
        patch("backend.pipeline.cv_tailoring._run_generator",
              AsyncMock(return_value=_mk_generator(
                  ("item_000", "KÜRZEN", "Developed distributed systems using Python and Kafka"),
              ))),
        patch("backend.pipeline.cv_tailoring._run_rewriter", mock_rewriter),
    ):
        result = await run_cv_tailoring(
            MagicMock(),
            cv_text=_CV,
            job_posting=_JOB,
            career_target=_TARGET,
        )

    mock_rewriter.assert_not_called()
    assert result.items_removed == 0
    assert result.items_shortened == 1


# ── R2: Mixed run (removes present) still calls _run_rewriter ─────────────────

@pytest.mark.asyncio
async def test_mixed_run_calls_rewriter():
    """items_removed > 0 → rewriter must be called."""
    from backend.pipeline.cv_tailoring import run_cv_tailoring

    # Two items in the same section.
    # item_000 (short, DISTRAKTOR) → ENTFERNEN
    # item_001 (long, TRANSFERABEL) → KÜRZEN
    cv = f"## Experience\n- Short distracting line\n- {_LONG_ITEM}\n"
    classifier = _mk_classifier(item_000="DISTRAKTOR", item_001="TRANSFERABEL")
    generator = _mk_generator(
        ("item_000", "ENTFERNEN", ""),
        ("item_001", "KÜRZEN", "Developed distributed systems using Python and Kafka"),
    )
    # Return the original cv so word-count inflation check passes.
    mock_rewriter = AsyncMock(return_value=cv)

    with (
        patch("backend.pipeline.cv_tailoring._run_classifier", AsyncMock(return_value=classifier)),
        patch("backend.pipeline.cv_tailoring._run_generator", AsyncMock(return_value=generator)),
        patch("backend.pipeline.cv_tailoring._run_rewriter", mock_rewriter),
    ):
        result = await run_cv_tailoring(
            MagicMock(),
            cv_text=cv,
            job_posting=_JOB,
            career_target=_TARGET,
        )

    mock_rewriter.assert_called_once()
    assert result.items_removed == 1


# ── R3: Skipped rewriter → tailored_cv reflects deterministic KÜRZEN edit ────

@pytest.mark.asyncio
async def test_skipped_rewriter_tailored_cv_reflects_kuerzen_edit():
    """
    When the rewriter is skipped, tailored_cv must equal the deterministic
    edited CV: KÜRZEN replacement applied, original long text gone.
    """
    from backend.pipeline.cv_tailoring import run_cv_tailoring

    shortened = "Developed distributed systems using Python and Kafka"

    with (
        patch("backend.pipeline.cv_tailoring._run_classifier",
              AsyncMock(return_value=_mk_classifier(item_000="TRANSFERABEL", item_001="KEEP"))),
        patch("backend.pipeline.cv_tailoring._run_generator",
              AsyncMock(return_value=_mk_generator(
                  ("item_000", "KÜRZEN", shortened),
              ))),
        patch("backend.pipeline.cv_tailoring._run_rewriter", AsyncMock()),
    ):
        result = await run_cv_tailoring(
            MagicMock(),
            cv_text=_CV,
            job_posting=_JOB,
            career_target=_TARGET,
        )

    assert shortened in result.tailored_cv
    assert _LONG_ITEM not in result.tailored_cv  # original text replaced
    assert result.items_removed == 0


# ── R4: Inflation check still runs (and passes) when rewriter is skipped ──────

@pytest.mark.asyncio
async def test_inflation_check_runs_and_passes_when_rewriter_skipped():
    """
    check_cv_word_inflation must still be called even when rewriter is skipped.
    With rewritten_cv == edited_cv the check must return valid=True (no inflation).
    """
    from backend.pipeline.cv_tailoring import run_cv_tailoring
    from backend.pipeline.truthfulness import check_cv_word_inflation as _real

    calls: list[tuple] = []

    def _spy(original: str, edited: str, rewritten: str):
        r = _real(original, edited, rewritten)
        calls.append((original, edited, rewritten, r))
        return r

    mock_rewriter = AsyncMock()

    with (
        patch("backend.pipeline.cv_tailoring._run_classifier",
              AsyncMock(return_value=_mk_classifier(item_000="TRANSFERABEL", item_001="KEEP"))),
        patch("backend.pipeline.cv_tailoring._run_generator",
              AsyncMock(return_value=_mk_generator(
                  ("item_000", "KÜRZEN", "Developed distributed systems using Python"),
              ))),
        patch("backend.pipeline.cv_tailoring._run_rewriter", mock_rewriter),
        patch("backend.pipeline.cv_tailoring.check_cv_word_inflation", _spy),
    ):
        result = await run_cv_tailoring(
            MagicMock(),
            cv_text=_CV,
            job_posting=_JOB,
            career_target=_TARGET,
        )

    mock_rewriter.assert_not_called()
    assert calls, "check_cv_word_inflation was never called"
    *_, check_result = calls[0]
    assert check_result.valid is True
    assert not check_result.issues
    assert isinstance(result.tailored_cv, str) and result.tailored_cv
