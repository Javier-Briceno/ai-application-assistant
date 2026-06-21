"""
Word budget and item-level enforcement logic.
Ports the n8n Compute Word Budget + Enforcer Code Nodes.
"""
from backend.models.tailoring import ClassifierItem, ClassifierOutput, GeneratorItem


# ── Word budget ───────────────────────────────────────────────────────────────

_BUDGET_MIN = 700
_BUDGET_MAX = 950
_BUDGET_RATIO = 0.80
_SHORTEN_MIN_WORDS = 25


def compute_word_budget(cv_text: str) -> int:
    """
    Mirrors the n8n Compute Word Budget Code Node.
    Returns the target word count for the tailored CV.
    """
    word_count = len(cv_text.split())
    if word_count <= _BUDGET_MIN:
        return word_count  # already short — no budget pressure
    target = int(word_count * _BUDGET_RATIO)
    return max(_BUDGET_MIN, min(target, _BUDGET_MAX))


# ── Enforcer ──────────────────────────────────────────────────────────────────

def enforcer(
    classifier_output: ClassifierOutput,
    cv_items: dict[str, str],
) -> list[GeneratorItem]:
    """
    Mirrors the n8n Enforcer Code Node.
    Converts DISTRAKTOR / TRANSFERABEL / KEEP classifications into generator instructions.

    DISTRAKTOR → ENTFERNEN (remove)
    TRANSFERABEL → KÜRZEN if item has ≥ SHORTEN_MIN_WORDS words, else KEEP (can't shorten further)
    KEEP → skipped (not passed to Generator)
    """
    result: list[GeneratorItem] = []

    for item in classifier_output.items:
        content = cv_items.get(item.id, "")

        if item.classification == "DISTRAKTOR":
            result.append(GeneratorItem(id=item.id, action="ENTFERNEN", new_content=""))

        elif item.classification == "TRANSFERABEL":
            word_count = len(content.split())
            if word_count >= _SHORTEN_MIN_WORDS:
                result.append(GeneratorItem(id=item.id, action="KÜRZEN", new_content=content))
            # else: item is already short — KEEP it implicitly (no instruction needed)

        # KEEP items are skipped entirely (Generator sees nothing for them)

    return result
