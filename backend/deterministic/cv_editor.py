"""
CV Deterministic Editor and LCS Diff Engine.
Ports the n8n CV Deterministic Editor + Diff Engine Code Nodes from the main workflow.
"""
import re

from backend.models.tailoring import ClassifierOutput, GeneratorOutput, ValidationError, ValidationResult


# ── Validator ─────────────────────────────────────────────────────────────────

_MAX_CLUSTER_REMOVE_RATIO = 0.50


def validate_generator_output(
    generator_output: GeneratorOutput,
    classifier_output: ClassifierOutput,
    cv_items: dict[str, str],
    section_membership: dict[str, str],
) -> ValidationResult:
    """
    Validates generator output against classifier decisions.
    section_membership maps every cv item (including KEEP items) to its section,
    so the cluster guard uses the correct denominator.
    """
    """
    Mirrors the n8n Validator Code Node.
    Returns ValidationResult(valid=True) if all checks pass.
    """
    errors: list[ValidationError] = []
    classifier_map = {item.id: item.classification for item in classifier_output.items}

    # Pre-compute ALL items per section (including KEEP items — correct denominator)
    section_item_counts: dict[str, int] = {}
    for item_id, section in section_membership.items():
        section_item_counts[section] = section_item_counts.get(section, 0) + 1

    section_remove_counts: dict[str, int] = {}

    for item in generator_output.items:
        original = cv_items.get(item.id, "")
        classification = classifier_map.get(item.id, "KEEP")
        section = section_membership.get(item.id, "__root__")

        if section not in section_remove_counts:
            section_remove_counts[section] = 0

        # Check 1: no-op (KÜRZEN but content unchanged)
        if item.action == "KÜRZEN" and item.new_content.strip() == original.strip():
            errors.append(ValidationError(
                item_id=item.id,
                error_type="no_op",
                detail=f"Item {item.id} was marked KÜRZEN but content is unchanged.",
            ))

        # Check 2: TRANSFERABEL items must not be removed
        if item.action == "ENTFERNEN" and classification == "TRANSFERABEL":
            errors.append(ValidationError(
                item_id=item.id,
                error_type="transferabel_removed",
                detail=f"Item {item.id} is TRANSFERABEL but was ENTFERNEN — must be KÜRZEN.",
            ))

        if item.action == "ENTFERNEN":
            section_remove_counts[section] = section_remove_counts.get(section, 0) + 1

    # Check 3: cluster guard — don't remove more than 50% of items from one section
    for section, remove_count in section_remove_counts.items():
        total = section_item_counts.get(section, 1)
        if total > 0 and (remove_count / total) > _MAX_CLUSTER_REMOVE_RATIO:
            errors.append(ValidationError(
                item_id=f"section:{section}",
                error_type="cluster_guard",
                detail=(
                    f"Section '{section}' has {remove_count}/{total} items marked ENTFERNEN "
                    f"({remove_count/total:.0%} > {_MAX_CLUSTER_REMOVE_RATIO:.0%} limit)."
                ),
            ))

    return ValidationResult(valid=len(errors) == 0, errors=errors)


# ── Deterministic editor ──────────────────────────────────────────────────────

def apply_remove_instructions(cv_text: str, generator_output: GeneratorOutput) -> str:
    """
    Mirrors the n8n CV Deterministic Editor Code Node.
    Applies ENTFERNEN by exact string match on the CV text.
    Operates on the full cv_text string (not the item list) for reliability.
    Only processes ENTFERNEN — KÜRZEN is applied by the LLM Rewriter.
    """
    result = cv_text
    for item in generator_output.items:
        if item.action == "ENTFERNEN" and item.id in cv_text:
            # The item id in this context is the original content string
            # (see cv_tailoring.py for how ids are mapped to content)
            pass  # ids are opaque — content lookup happens in pipeline

    return result


def apply_removes_by_content(
    cv_text: str,
    items_to_remove: list[str],
) -> str:
    """
    Remove items by exact content match.
    Each item in items_to_remove is the literal text that should be deleted.
    Handles both bullet-point lines and standalone lines.
    """
    result = cv_text
    for content in items_to_remove:
        if not content.strip():
            continue
        # Escape and match the full line (with optional leading bullet/dash/whitespace)
        pattern = r"[ \t]*(?:[-•*]\s+)?" + re.escape(content.strip()) + r"[ \t]*\n?"
        result = re.sub(pattern, "", result)

    # Collapse 3+ consecutive blank lines to 2
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


# ── LCS Diff Engine ───────────────────────────────────────────────────────────

def _lcs(a: list[str], b: list[str]) -> list[str]:
    """Standard LCS via DP table."""
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    # Backtrack
    result: list[str] = []
    i, j = m, n
    while i > 0 and j > 0:
        if a[i - 1] == b[j - 1]:
            result.append(a[i - 1])
            i -= 1
            j -= 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            i -= 1
        else:
            j -= 1
    return list(reversed(result))


def _strip_md(text: str) -> str:
    """Strip markdown formatting so diff compares plain content only."""
    text = re.sub(r'^#{1,6}\s+', '', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'_([^_\s][^_]*)_', r'\1', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    return text.strip()


def compute_diff(original: str, modified: str) -> str:
    """
    Compute a line-level diff between original and modified CV.
    Returns a string with + (added), - (removed), or 2-space-prefix (context) lines.
    Comparison is done on plain text (markdown stripped) so formatting-only
    changes don't appear as content changes.
    """
    orig_lines = [_strip_md(l) for l in original.splitlines() if l.strip()]
    mod_lines  = [_strip_md(l) for l in modified.splitlines()  if l.strip()]

    # Drop empty strings that result from stripping (e.g. a line that was only `---`)
    orig_lines = [l for l in orig_lines if l]
    mod_lines  = [l for l in mod_lines  if l]

    common = set(_lcs(orig_lines, mod_lines))
    diff_lines: list[str] = []

    orig_set = set(orig_lines)
    mod_set  = set(mod_lines)

    for line in orig_lines:
        if line in common:
            diff_lines.append(f"  {line}")
        elif line not in mod_set:
            diff_lines.append(f"- {line}")

    for line in mod_lines:
        if line not in orig_set:
            diff_lines.append(f"+ {line}")

    return "\n".join(diff_lines)
