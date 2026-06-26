"""
Deterministic CV section trimmer.

Applied as a post-processing step after the LLM tailoring/rewrite flow and
before compute_diff() and TailoringResult storage. Enforces structural limits
on section content without calling any LLM.

Sections modified:
  PROJEKTE (and known project section aliases):
    - Keep at most MAX_PROJECTS (3) entries by document order.
    - Within each kept entry: keep at most MAX_BULLETS_PER_ENTRY (2) bullets.
    - Preserve at most one Tech-Stack line per kept entry (the first).
    - Entry title lines are always preserved.

  PRAKTISCHE ERFAHRUNG and known aliases (BERUFSERFAHRUNG, ARBEITSERFAHRUNG,
  ERFAHRUNG, PRAKTIKA, PRAKTIKUM):
    - Keep at most MAX_BULLETS_PER_ENTRY (2) bullet lines per work entry.
    - Entries themselves are never removed.

All other sections (PROFIL, AUSBILDUNG, KENNTNISSE, ZERTIFIKATE, SPRACHEN,
and anything not listed above) are passed through entirely unchanged.

Conservative guarantee:
  If an entry's bullet structure cannot be confidently parsed, the section is
  returned unchanged rather than silently broken.

Entry boundary detection (used for PROJEKTE and ERFAHRUNG sections):
  A new entry starts at the first non-bullet, non-tech-stack, non-empty line
  that follows a blank gap which itself came AFTER at least one bullet line in
  the preceding entry. This means:
  - Multi-line entry headers (title + pre-bullet prose) stay in one entry.
  - A tech-stack line is not confused with the next entry title.
  - Leading blank lines before the first entry are discarded.
"""

import re

# ── Constants ──────────────────────────────────────────────────────────────────

MAX_PROJECTS: int = 3
MAX_BULLETS_PER_ENTRY: int = 2

# Section names whose content gets the full project trim (count + bullets).
_PROJEKTE_NAMES: frozenset[str] = frozenset({
    "PROJEKTE", "PROJEKT", "HOCHSCHULPROJEKTE",
})

# Section names that get per-entry bullet trimming only (no entry-count limit).
_EXPERIENCE_NAMES: frozenset[str] = frozenset({
    "PRAKTISCHE ERFAHRUNG", "BERUFSERFAHRUNG", "ARBEITSERFAHRUNG", "ERFAHRUNG",
    "PRAKTIKA", "PRAKTIKUM",
})

# ── Line-type helpers ──────────────────────────────────────────────────────────

_HEADING_RE = re.compile(r'^(#{1,2})\s+')
_BULLET_RE = re.compile(r'^[-–•*]\s')
_TECH_STACK_RE = re.compile(r'^[Tt]ech[-\s][Ss]tack\s*:', re.IGNORECASE)

# Known section names used for auto-detecting which heading level is primary.
_KNOWN_SECTION_NAMES: frozenset[str] = frozenset({
    "PROFIL", "KURZPROFIL", "AUSBILDUNG", "PRAKTISCHE ERFAHRUNG",
    "BERUFSERFAHRUNG", "ARBEITSERFAHRUNG", "ERFAHRUNG", "PRAKTIKA", "PRAKTIKUM",
    "PROJEKTE", "PROJEKT", "HOCHSCHULPROJEKTE", "KENNTNISSE", "TECHNISCHE KENNTNISSE",
    "ZERTIFIKATE", "SPRACHEN", "SPRACHKENNTNISSE",
})


def _heading_name(line: str) -> str | None:
    """
    If `line` is a Markdown # or ## heading, return its normalized
    UPPERCASE section name (bold markers and extra whitespace stripped).
    Returns None for any non-heading line.
    """
    stripped = line.strip()
    m = _HEADING_RE.match(stripped)
    if not m:
        return None
    return stripped[m.end():].replace("**", "").strip().upper()


def _heading_name_at_level(line: str, level: int) -> str | None:
    """Like _heading_name but only matches headings at exactly `level` hashes."""
    stripped = line.strip()
    m = _HEADING_RE.match(stripped)
    if not m or len(m.group(1)) != level:
        return None
    return stripped[m.end():].replace("**", "").strip().upper()


def _detect_section_level(lines: list[str]) -> int:
    """
    Return 1 or 2: the heading depth (#  vs ##) used for major section names.

    Scans lines until it finds a heading whose name matches a known CV section.
    The first match wins. Defaults to 2 (the common double-hash format) if no
    known section heading is found.

    This lets the trimmer handle CVs where project entries are sub-headings:
      level-2 CV:  ## PROJEKTE … **Entry title** | date  (entries = bold text)
      level-1 CV:  # PROJEKTE  … ## Entry title  | date  (entries = ## headings)
    """
    for line in lines:
        stripped = line.strip()
        m = _HEADING_RE.match(stripped)
        if not m:
            continue
        level = len(m.group(1))
        name = stripped[m.end():].replace("**", "").strip().upper()
        if name in _KNOWN_SECTION_NAMES:
            return level
    return 2


def _is_bullet(line: str) -> bool:
    return bool(_BULLET_RE.match(line.strip()))


def _is_tech_stack(line: str) -> bool:
    return bool(_TECH_STACK_RE.match(line.strip()))


# ── Blank-line collapsing ──────────────────────────────────────────────────────

def _collapse_blanks(lines: list[str]) -> list[str]:
    """Collapse two or more consecutive blank lines into one."""
    out: list[str] = []
    prev_blank = False
    for line in lines:
        blank = not line.strip()
        if blank and prev_blank:
            continue
        out.append(line)
        prev_blank = blank
    return out


# ── Entry splitting ────────────────────────────────────────────────────────────

def _split_entries(lines: list[str]) -> list[list[str]]:
    """
    Split a section's lines into separate entries (projects or work experiences).

    Algorithm:
      Walk lines sequentially, accumulating the current entry.
      When a non-bullet, non-tech-stack, non-empty line is encountered after a
      blank gap that followed at least one bullet line in the current entry,
      the current entry is saved and a new one begins.

    Trailing blank lines are stripped from each entry before it is saved.
    Leading blank lines at the start of the section are discarded.

    Returns a list of entries; each entry is a list of raw lines.
    Returns an empty list if no clear entry structure is found.
    """
    entries: list[list[str]] = []
    current: list[str] = []
    current_has_bullet: bool = False
    # True once we have seen a blank line AFTER at least one bullet in current entry.
    after_blank_post_bullet: bool = False

    for line in lines:
        stripped = line.strip()

        if not stripped:
            if current_has_bullet:
                after_blank_post_bullet = True
            if current:
                current.append(line)
            continue

        if _is_bullet(line):
            current.append(line)
            current_has_bullet = True
            after_blank_post_bullet = False
            continue

        if _is_tech_stack(line):
            current.append(line)
            after_blank_post_bullet = False
            continue

        # Non-empty, non-bullet, non-tech-stack line.
        if after_blank_post_bullet:
            # We are past the bullet block of the current entry — save it and
            # start a fresh entry with this line as the new title.
            _save_entry(entries, current)
            current = [line]
            current_has_bullet = False
            after_blank_post_bullet = False
        else:
            # Still in the header area of the current entry.
            current.append(line)
            after_blank_post_bullet = False

    _save_entry(entries, current)
    return entries


def _save_entry(entries: list[list[str]], current: list[str]) -> None:
    """Strip trailing blanks from `current` and append to `entries` if non-empty."""
    if not current:
        return
    while current and not current[-1].strip():
        current.pop()
    if current:
        entries.append(current)


# ── Entry-level bullet trimmer ─────────────────────────────────────────────────

def _trim_entry_bullets(entry_lines: list[str], max_bullets: int) -> list[str]:
    """
    Return the entry's lines with at most `max_bullets` bullet lines kept.
    The first Tech-Stack line is kept; any additional are dropped.
    All non-bullet, non-tech-stack lines (title, prose) are always preserved.
    Leading and trailing blank lines are stripped; internal consecutive blanks
    are collapsed to one.
    """
    result: list[str] = []
    bullet_count = 0
    tech_stack_seen = 0

    for line in entry_lines:
        if _is_bullet(line):
            if bullet_count < max_bullets:
                result.append(line)
                bullet_count += 1
            # Excess bullets dropped silently.
        elif _is_tech_stack(line):
            if tech_stack_seen == 0:
                result.append(line)
            tech_stack_seen += 1
        else:
            result.append(line)

    # Strip leading/trailing blanks.
    while result and not result[0].strip():
        result.pop(0)
    while result and not result[-1].strip():
        result.pop()

    return _collapse_blanks(result)


# ── Section-level trimmers ─────────────────────────────────────────────────────

def _trim_projekte_section(section_lines: list[str]) -> list[str]:
    """
    Enforce project count and bullet limits on a PROJEKTE section body.

    Returns `section_lines` unchanged if no entries are detected (conservative
    fallback to avoid breaking an unexpected structure).
    """
    entries = _split_entries(section_lines)
    if not entries:
        return section_lines

    kept = entries[:MAX_PROJECTS]

    out: list[str] = []
    for entry in kept:
        if out:
            out.append("")  # one blank line between entries
        out.extend(_trim_entry_bullets(entry, MAX_BULLETS_PER_ENTRY))

    # Prepend a single blank to match the standard section body indentation.
    return _collapse_blanks([""] + out)


def _trim_experience_section(section_lines: list[str]) -> list[str]:
    """
    Enforce bullet limits on each entry in a PRAKTISCHE ERFAHRUNG section.
    Entries are never removed, only their bullet counts capped.

    Returns `section_lines` unchanged if no entries are detected.
    """
    entries = _split_entries(section_lines)
    if not entries:
        return section_lines

    out: list[str] = []
    for entry in entries:
        if out:
            out.append("")
        out.extend(_trim_entry_bullets(entry, MAX_BULLETS_PER_ENTRY))

    return _collapse_blanks([""] + out)


# ── Public entry point ─────────────────────────────────────────────────────────

def trim_cv_to_2_pages(cv_text: str) -> str:
    """
    Apply deterministic section-level trimming to a tailored CV markdown string.

    Walks the CV line by line, identifies ## section headings, collects each
    section's body, applies the appropriate trimming rule, and reassembles.
    Sections whose names do not match any known trim target are emitted unchanged.

    Returns the trimmed CV with excessive blank lines collapsed. Suitable for
    German CVs produced by the LLM tailoring pipeline.
    """
    lines = cv_text.splitlines()
    # Detect whether the CV uses # (level 1) or ## (level 2) for major sections.
    # Level-1 CVs embed project entries as ## headings, which must be treated as
    # content rather than new section boundaries during body collection.
    section_level = _detect_section_level(lines)

    out: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        name = _heading_name_at_level(line, section_level)

        if name is None:
            out.append(line)
            i += 1
            continue

        # Heading line — write it and collect the section body.
        out.append(line)
        i += 1

        body: list[str] = []
        while i < len(lines) and _heading_name_at_level(lines[i], section_level) is None:
            body.append(lines[i])
            i += 1

        if name in _PROJEKTE_NAMES:
            body = _trim_projekte_section(body)
        elif name in _EXPERIENCE_NAMES:
            body = _trim_experience_section(body)
        # All other sections: body passes through unchanged.

        out.extend(body)

    # Final cleanup: collapse 3+ consecutive blank lines to 2.
    result = re.sub(r'\n{3,}', '\n\n', "\n".join(out))
    return result.strip()
