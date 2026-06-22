"""
Tests for compute_diff in backend/deterministic/cv_editor.py.

Verifies that the positional unified diff:
  - Preserves line order (changes at their actual position)
  - Handles duplicate lines without conflating them
  - Shows context lines around each changed block
  - Produces separate @@ hunk markers for distinct changed regions
  - Returns an empty string for unchanged CVs
  - Does not crash on empty inputs or old-format diffs in the frontend
"""

import pytest

from backend.deterministic.cv_editor import compute_diff


# ── helpers ───────────────────────────────────────────────────────────────────

def _added(diff: str) -> list[str]:
    """Lines that start with + in the diff (excluding +++ file header)."""
    return [l[1:].strip() for l in diff.splitlines() if l.startswith('+') and not l.startswith('+++')]


def _removed(diff: str) -> list[str]:
    """Lines that start with - in the diff (excluding --- file header)."""
    return [l[1:].strip() for l in diff.splitlines() if l.startswith('-') and not l.startswith('---')]


def _context(diff: str) -> list[str]:
    """Context lines (single leading space)."""
    return [l[1:] for l in diff.splitlines() if l.startswith(' ')]


def _hunks(diff: str) -> list[str]:
    """@@ hunk header lines."""
    return [l for l in diff.splitlines() if l.startswith('@@')]


# ── basic operations ──────────────────────────────────────────────────────────

def test_unchanged_cv_returns_empty_string():
    cv = "## Skills\n\n- Python\n- SQL\n"
    assert compute_diff(cv, cv) == ""


def test_simple_removal():
    original = "Line A\nLine B\nLine C\n"
    modified = "Line A\nLine C\n"
    diff = compute_diff(original, modified)
    assert "Line B" in "".join(_removed(diff))
    assert "Line B" not in "".join(_added(diff))


def test_simple_addition():
    original = "Line A\nLine C\n"
    modified = "Line A\nLine B\nLine C\n"
    diff = compute_diff(original, modified)
    assert "Line B" in "".join(_added(diff))
    assert "Line B" not in "".join(_removed(diff))


def test_replacement_shows_both_old_and_new():
    original = "## Erfahrung\n\nSenior Engineer bei Acme GmbH.\n"
    modified = "## Erfahrung\n\nLead Engineer bei Acme GmbH.\n"
    diff = compute_diff(original, modified)
    removed = "".join(_removed(diff))
    added   = "".join(_added(diff))
    assert "Senior Engineer" in removed
    assert "Lead Engineer"   in added


def test_duplicate_lines_not_conflated():
    """
    The old set-based approach would treat the first and second occurrence of
    a duplicate line as the same token.  The positional diff must distinguish
    which occurrence was removed.
    """
    original = "Python\nPython\nSQL\n"
    modified = "Python\nSQL\n"          # remove the second Python
    diff = compute_diff(original, modified)
    # Exactly one 'Python' line should be removed
    assert _removed(diff).count("Python") == 1
    assert _added(diff).count("Python") == 0


def test_reordered_lines_produce_nonempty_diff():
    """
    Swapping two lines must produce a non-empty diff.
    A positional diff identifies the minimum edit: one of the two swapped lines
    is marked as removed-then-added (its position changed), the other stays as
    context (difflib's SequenceMatcher finds the longest common subsequence).
    We only assert that the diff is non-empty and that every changed line
    comes from the original content — not that both lines appear as changed.
    """
    original = "A\nB\nC\n"
    modified = "B\nA\nC\n"
    diff = compute_diff(original, modified)
    removed = _removed(diff)
    added   = _added(diff)
    assert removed or added, "Reordering two lines must produce a non-empty diff"
    for line in removed + added:
        assert line in ("A", "B"), f"Changed line not from original content: {line!r}"


def test_markdown_headings_preserved_in_diff():
    original = "## Skills\n\n- Python\n- Java\n\n## Erfahrung\n\nSomething.\n"
    modified = "## Skills\n\n- Python\n\n## Erfahrung\n\nSomething.\n"
    diff = compute_diff(original, modified)
    assert _removed(diff)  # Java was removed
    assert "Java" in "".join(_removed(diff))
    # The heading should appear as context near the removed line
    ctx = "".join(_context(diff))
    assert "Skills" in ctx or "##" in ctx


def test_context_lines_shown_around_change():
    """2 lines of context must appear before and after each changed block."""
    original = "A\nB\nC\nD\nE\nF\n"
    modified = "A\nB\nX\nD\nE\nF\n"   # C → X
    diff = compute_diff(original, modified)
    ctx = _context(diff)
    # B and D must appear as context (they are adjacent to the change)
    assert "B" in ctx
    assert "D" in ctx


def test_multiple_sections_produce_separate_hunks():
    """
    Two non-adjacent changed regions must each get their own @@ hunk header
    so the user knows where in the document each change lives.
    """
    original = "\n".join([
        "## Section 1", "Keep 1", "Remove this", "Keep 2",
        "## Section 2", "Keep 3", "Keep 4", "Keep 5", "Keep 6",
        "## Section 3", "Keep 7", "Also remove this", "Keep 8",
    ])
    modified = "\n".join([
        "## Section 1", "Keep 1", "Keep 2",
        "## Section 2", "Keep 3", "Keep 4", "Keep 5", "Keep 6",
        "## Section 3", "Keep 7", "Keep 8",
    ])
    diff = compute_diff(original, modified)
    hunks = _hunks(diff)
    assert len(hunks) >= 2, f"Expected at least 2 @@ hunk headers, got: {hunks}"


def test_empty_original():
    modified = "New content\nAnother line\n"
    diff = compute_diff("", modified)
    assert _added(diff)  # everything should appear as added


def test_empty_modified():
    original = "Old content\nAnother line\n"
    diff = compute_diff(original, "")
    assert _removed(diff)  # everything should appear as removed


def test_diff_format_has_no_file_headers():
    """The ---/+++ file-name header lines must be stripped."""
    original = "A\n"
    modified = "B\n"
    diff = compute_diff(original, modified)
    for line in diff.splitlines():
        assert not line.startswith("---"), f"Found --- header in output: {line!r}"
        assert not line.startswith("+++"), f"Found +++ header in output: {line!r}"


def test_changes_appear_at_correct_position():
    """
    A removal near the start and an addition near the end must appear in
    their actual positions, not clustered together.
    """
    original = "Start\nREMOVE\nMiddle1\nMiddle2\nMiddle3\nEnd\n"
    modified = "Start\nMiddle1\nMiddle2\nMiddle3\nADDED\nEnd\n"
    diff = compute_diff(original, modified)
    lines = diff.splitlines()
    remove_idx = next(i for i, l in enumerate(lines) if "REMOVE" in l)
    add_idx    = next(i for i, l in enumerate(lines) if "ADDED"  in l)
    # REMOVE must appear before ADDED (positional order preserved)
    assert remove_idx < add_idx, (
        "Removal must precede addition in positional diff, "
        f"but got remove at line {remove_idx}, add at line {add_idx}"
    )
