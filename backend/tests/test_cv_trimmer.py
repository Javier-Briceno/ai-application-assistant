"""
Tests for backend/deterministic/cv_trimmer.py and the accompanying
word-budget / cluster-guard constant changes.

Coverage:
  B1–B3  Word budget constants
  G1     Cluster guard allows 70 % removal
  T1–T18 cv_trimmer: entry detection, bullet limits, section passthrough,
         safety / edge-case behaviour
  I1     Integration: trimmer is called from run_cv_tailoring
  D1     Generated DOCX from a trimmed CV does not crash
"""
import io

import pytest

# ── Test fixtures ──────────────────────────────────────────────────────────────

# 5 projects, 3 bullets each, 1 tech-stack line each.
# After trimming: 3 projects, 2 bullets each, 1 tech-stack line each.
CV_MANY_PROJECTS = """\
## PROFIL
Erfahrener Entwickler.

## AUSBILDUNG
Bachelor CS, Universität Siegen (2020–2024)
Note: 1,8

## PRAKTISCHE ERFAHRUNG

Werkstudent bei ACME GmbH | 2023–heute

- Entwicklung von REST-APIs mit Python und FastAPI
- Aufbau einer ETL-Pipeline zur Datenverarbeitung
- Implementierung von Unit- und Integrationstests

## PROJEKTE

Alpha-Projekt | 01.2026–03.2026

- Alpha-Bullet-1-lang genug um wichtig zu sein und zu zaehlen als inhalt
- Alpha-Bullet-2-lang genug um wichtig zu sein und zu zaehlen als inhalt
- Alpha-Bullet-3-lang genug um wichtig zu sein DIESER SOLL WEG

Tech-Stack: Python, Docker, PostgreSQL

Beta-Projekt | 11.2025–01.2026

- Beta-Bullet-1-relevant für die Stelle
- Beta-Bullet-2-relevant für die Stelle
- Beta-Bullet-3-nicht so relevant DIESER SOLL WEG

Gamma-Projekt | 09.2025–11.2025

- Gamma-Bullet-1-wichtige Leistung
- Gamma-Bullet-2-weitere wichtige Leistung
- Gamma-Bullet-3-dritte weniger wichtige DIESER SOLL WEG

Tech-Stack: Node.js, React

Delta-Projekt | 06.2025–09.2025

- Delta-Bullet-1 dieser kommt weg weil nur 3 projekte bleiben
- Delta-Bullet-2 ebenfalls weg

Epsilon-Projekt | 02.2025–06.2025

- Epsilon-Bullet-1 auch weg
- Epsilon-Bullet-2 auch weg

## KENNTNISSE
Python, TypeScript, Docker, PostgreSQL

## ZERTIFIKATE
- CS50 Python (Harvard, 2025)
- AWS Cloud Practitioner (2024)

## SPRACHEN
Deutsch: C1, Englisch: B2
"""

# CV where PROJEKTE already has ≤ 3 projects and ≤ 2 bullets each → unchanged.
CV_SHORT_ALREADY = """\
## PROFIL
Kurzes Profil.

## PROJEKTE

Projekt A | 2026

- Bullet 1
- Bullet 2

Projekt B | 2025

- Bullet 1
- Bullet 2

## KENNTNISSE
Python, SQL
"""

# CV with a PRAKTISCHE ERFAHRUNG section that has 3 bullets per entry.
CV_EXPERIENCE_TOO_MANY_BULLETS = """\
## PROFIL
Profil hier.

## PRAKTISCHE ERFAHRUNG

Werkstudent bei Firma A | 2024–heute

- Erste wichtige Aufgabe lang genug für zählen
- Zweite wichtige Aufgabe lang genug für zählen
- Dritte Aufgabe SOLL WEG da zu viele Bullets

Praktikant bei Firma B | 2023–2024

- Erstaufgabe bei Firma B lang genug
- Zweitaufgabe bei Firma B lang genug
- Drittaufgabe bei Firma B SOLL WEG

## KENNTNISSE
Python, SQL
"""

# CV with no PROJEKTE or ERFAHRUNG sections — should be entirely unchanged.
CV_NO_TRIM_SECTIONS = """\
## PROFIL
Profil.

## AUSBILDUNG
Bachelor BWL (2020–2024)

## KENNTNISSE
Excel, SAP

## SPRACHEN
Deutsch: Muttersprache
"""

# CV without ANY markdown headings (edge case).
CV_NO_HEADINGS = "Ich bin ein Entwickler mit Erfahrung in Python und Docker."


# ── B1–B3: Word budget constants ───────────────────────────────────────────────

def test_budget_max_for_long_cv_is_550():
    from backend.deterministic.word_budget import compute_word_budget
    # 1 200-word CV → max target = 550
    cv = "word " * 1200
    assert compute_word_budget(cv) == 550


def test_budget_max_for_medium_cv_is_capped():
    from backend.deterministic.word_budget import compute_word_budget
    # 700-word CV → 700 × 0.80 = 560, capped to 550
    cv = "word " * 700
    assert compute_word_budget(cv) == 550


def test_budget_short_cv_below_min_is_unchanged():
    from backend.deterministic.word_budget import compute_word_budget
    # CVs at or below _BUDGET_MIN (400) are returned as-is (no budget pressure)
    cv = "word " * 300
    assert compute_word_budget(cv) == 300


def test_budget_cv_at_min_boundary_is_unchanged():
    from backend.deterministic.word_budget import compute_word_budget
    cv = "word " * 400
    assert compute_word_budget(cv) == 400


def test_budget_medium_cv_in_range():
    from backend.deterministic.word_budget import compute_word_budget
    # 500-word CV → 500 × 0.80 = 400 → max(400, 400) = 400 → min(400, 550) = 400
    cv = "word " * 500
    assert compute_word_budget(cv) == 400


# ── G1: Cluster guard allows 70 % removal ─────────────────────────────────────

def test_cluster_guard_allows_70_pct_removal():
    """Removing 7/10 items from one section must pass (70 % == allowed limit)."""
    from backend.deterministic.cv_editor import validate_generator_output
    from backend.models.tailoring import (
        ClassifierItem,
        ClassifierOutput,
        GeneratorItem,
        GeneratorOutput,
    )

    n = 10
    cv_items = {f"item_{i:03d}": f"Content {i}" for i in range(n)}
    section_membership = {k: "PROJEKTE" for k in cv_items}
    classifier_output = ClassifierOutput(items=[
        ClassifierItem(id=k, classification="DISTRAKTOR") for k in cv_items
    ])
    # Remove exactly 7 of 10 items (70 %).
    generator_output = GeneratorOutput(items=[
        GeneratorItem(id=f"item_{i:03d}", action="ENTFERNEN", new_content="")
        for i in range(7)
    ])
    result = validate_generator_output(
        generator_output, classifier_output, cv_items, section_membership
    )
    cluster_errors = [e for e in result.errors if e.error_type == "cluster_guard"]
    assert not cluster_errors, (
        f"70 % removal must not trigger cluster_guard, got: {cluster_errors}"
    )


def test_cluster_guard_blocks_above_70_pct():
    """Removing 8/10 items (80 %) must still trigger the cluster guard."""
    from backend.deterministic.cv_editor import validate_generator_output
    from backend.models.tailoring import (
        ClassifierItem,
        ClassifierOutput,
        GeneratorItem,
        GeneratorOutput,
    )

    n = 10
    cv_items = {f"item_{i:03d}": f"Content {i}" for i in range(n)}
    section_membership = {k: "PROJEKTE" for k in cv_items}
    classifier_output = ClassifierOutput(items=[
        ClassifierItem(id=k, classification="DISTRAKTOR") for k in cv_items
    ])
    generator_output = GeneratorOutput(items=[
        GeneratorItem(id=f"item_{i:03d}", action="ENTFERNEN", new_content="")
        for i in range(8)  # 80 %
    ])
    result = validate_generator_output(
        generator_output, classifier_output, cv_items, section_membership
    )
    cluster_errors = [e for e in result.errors if e.error_type == "cluster_guard"]
    assert cluster_errors, "80 % removal must trigger cluster_guard"


# ── T1–T6: PROJEKTE trimming ───────────────────────────────────────────────────

def test_trim_keeps_max_3_projects():
    from backend.deterministic.cv_trimmer import trim_cv_to_2_pages

    result = trim_cv_to_2_pages(CV_MANY_PROJECTS)
    # Count project entries by counting their distinguishable title lines.
    assert "Alpha-Projekt" in result
    assert "Beta-Projekt" in result
    assert "Gamma-Projekt" in result
    assert "Delta-Projekt" not in result
    assert "Epsilon-Projekt" not in result


def test_trim_keeps_first_3_projects_in_order():
    from backend.deterministic.cv_trimmer import trim_cv_to_2_pages

    result = trim_cv_to_2_pages(CV_MANY_PROJECTS)
    alpha_pos = result.index("Alpha-Projekt")
    beta_pos = result.index("Beta-Projekt")
    gamma_pos = result.index("Gamma-Projekt")
    assert alpha_pos < beta_pos < gamma_pos, "Projects must appear in original order"


def test_trim_keeps_max_2_bullets_per_project():
    from backend.deterministic.cv_trimmer import trim_cv_to_2_pages

    result = trim_cv_to_2_pages(CV_MANY_PROJECTS)
    assert "Alpha-Bullet-3" not in result, "3rd Alpha bullet must be removed"
    assert "Beta-Bullet-3" not in result, "3rd Beta bullet must be removed"
    assert "Gamma-Bullet-3" not in result, "3rd Gamma bullet must be removed"

    assert "Alpha-Bullet-1" in result
    assert "Alpha-Bullet-2" in result
    assert "Beta-Bullet-1" in result
    assert "Beta-Bullet-2" in result


def test_trim_preserves_project_title_lines():
    from backend.deterministic.cv_trimmer import trim_cv_to_2_pages

    result = trim_cv_to_2_pages(CV_MANY_PROJECTS)
    assert "Alpha-Projekt | 01.2026–03.2026" in result
    assert "Beta-Projekt | 11.2025–01.2026" in result
    assert "Gamma-Projekt | 09.2025–11.2025" in result


def test_trim_preserves_one_tech_stack_per_project():
    from backend.deterministic.cv_trimmer import trim_cv_to_2_pages

    result = trim_cv_to_2_pages(CV_MANY_PROJECTS)
    # Alpha has a tech-stack line; it must still be present.
    assert "Tech-Stack: Python, Docker, PostgreSQL" in result
    # Gamma also has one; it must still be present.
    assert "Tech-Stack: Node.js, React" in result


def test_trim_does_not_produce_empty_projekte_section():
    from backend.deterministic.cv_trimmer import trim_cv_to_2_pages

    cv = "## PROJEKTE\n\nEinziges Projekt | 2026\n\n- Bullet\n"
    result = trim_cv_to_2_pages(cv)
    assert "## PROJEKTE" in result
    assert "Einziges Projekt" in result
    assert "Bullet" in result


# ── T7–T8: PRAKTISCHE ERFAHRUNG trimming ──────────────────────────────────────

def test_trim_experience_bullets_to_max_2():
    from backend.deterministic.cv_trimmer import trim_cv_to_2_pages

    result = trim_cv_to_2_pages(CV_EXPERIENCE_TOO_MANY_BULLETS)
    assert "Dritte Aufgabe SOLL WEG" not in result
    assert "Drittaufgabe bei Firma B SOLL WEG" not in result
    assert "Erste wichtige Aufgabe" in result
    assert "Zweite wichtige Aufgabe" in result


def test_trim_experience_preserves_entry_titles():
    from backend.deterministic.cv_trimmer import trim_cv_to_2_pages

    result = trim_cv_to_2_pages(CV_EXPERIENCE_TOO_MANY_BULLETS)
    assert "Werkstudent bei Firma A | 2024–heute" in result
    assert "Praktikant bei Firma B | 2023–2024" in result


def test_trim_experience_keeps_both_entries():
    from backend.deterministic.cv_trimmer import trim_cv_to_2_pages

    # Both work entries must remain — only their bullets are trimmed, not the entries.
    result = trim_cv_to_2_pages(CV_EXPERIENCE_TOO_MANY_BULLETS)
    assert "Firma A" in result
    assert "Firma B" in result


# ── T9–T13: Passthrough sections are untouched ────────────────────────────────

def _extract_section(cv_text: str, heading: str) -> str:
    """Return the content of a named section from the CV text."""
    lines = cv_text.splitlines()
    out: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("##"):
            name = stripped.lstrip("#").replace("**", "").strip().upper()
            in_section = name == heading.upper()
            if in_section:
                continue
        elif in_section:
            out.append(line)
    return "\n".join(out).strip()


def test_profil_section_unchanged():
    from backend.deterministic.cv_trimmer import trim_cv_to_2_pages

    original = _extract_section(CV_MANY_PROJECTS, "PROFIL")
    result = trim_cv_to_2_pages(CV_MANY_PROJECTS)
    trimmed = _extract_section(result, "PROFIL")
    assert original == trimmed, "PROFIL must not be modified"


def test_ausbildung_section_unchanged():
    from backend.deterministic.cv_trimmer import trim_cv_to_2_pages

    original = _extract_section(CV_MANY_PROJECTS, "AUSBILDUNG")
    result = trim_cv_to_2_pages(CV_MANY_PROJECTS)
    trimmed = _extract_section(result, "AUSBILDUNG")
    assert original == trimmed, "AUSBILDUNG must not be modified"


def test_kenntnisse_section_unchanged():
    from backend.deterministic.cv_trimmer import trim_cv_to_2_pages

    original = _extract_section(CV_MANY_PROJECTS, "KENNTNISSE")
    result = trim_cv_to_2_pages(CV_MANY_PROJECTS)
    trimmed = _extract_section(result, "KENNTNISSE")
    assert original == trimmed, "KENNTNISSE must not be modified"


def test_zertifikate_section_unchanged():
    from backend.deterministic.cv_trimmer import trim_cv_to_2_pages

    original = _extract_section(CV_MANY_PROJECTS, "ZERTIFIKATE")
    result = trim_cv_to_2_pages(CV_MANY_PROJECTS)
    trimmed = _extract_section(result, "ZERTIFIKATE")
    assert original == trimmed, "ZERTIFIKATE must not be modified"


def test_sprachen_section_unchanged():
    from backend.deterministic.cv_trimmer import trim_cv_to_2_pages

    original = _extract_section(CV_MANY_PROJECTS, "SPRACHEN")
    result = trim_cv_to_2_pages(CV_MANY_PROJECTS)
    trimmed = _extract_section(result, "SPRACHEN")
    assert original == trimmed, "SPRACHEN must not be modified"


# ── T14–T16: Already-short CVs and edge cases ─────────────────────────────────

def test_already_short_cv_is_unchanged():
    from backend.deterministic.cv_trimmer import trim_cv_to_2_pages

    result = trim_cv_to_2_pages(CV_SHORT_ALREADY)
    # All content must still be present.
    assert "Projekt A" in result
    assert "Projekt B" in result
    for line in ["Bullet 1", "Bullet 2"]:
        assert result.count(line) == 2, f"'{line}' should appear twice (once per project)"


def test_cv_without_trim_sections_unchanged():
    from backend.deterministic.cv_trimmer import trim_cv_to_2_pages

    result = trim_cv_to_2_pages(CV_NO_TRIM_SECTIONS)
    # No projects or experience sections → the whole CV passes through.
    assert "PROFIL" in result
    assert "AUSBILDUNG" in result
    assert "Bachelor BWL" in result
    assert "Excel, SAP" in result


def test_cv_without_headings_unchanged():
    from backend.deterministic.cv_trimmer import trim_cv_to_2_pages

    result = trim_cv_to_2_pages(CV_NO_HEADINGS)
    assert result == CV_NO_HEADINGS


# ── T17: Output is valid markdown ─────────────────────────────────────────────

def test_output_preserves_markdown_headings():
    from backend.deterministic.cv_trimmer import trim_cv_to_2_pages

    result = trim_cv_to_2_pages(CV_MANY_PROJECTS)
    assert "## PROFIL" in result
    assert "## AUSBILDUNG" in result
    assert "## PRAKTISCHE ERFAHRUNG" in result
    assert "## PROJEKTE" in result
    assert "## KENNTNISSE" in result
    assert "## ZERTIFIKATE" in result
    assert "## SPRACHEN" in result


def test_output_has_no_triple_blank_lines():
    from backend.deterministic.cv_trimmer import trim_cv_to_2_pages

    result = trim_cv_to_2_pages(CV_MANY_PROJECTS)
    assert "\n\n\n" not in result, "Output must have no triple blank lines"


# ── T18: Word count proxy for 2-page fit ──────────────────────────────────────

def test_trimmed_long_cv_word_count_under_600():
    from backend.deterministic.cv_trimmer import trim_cv_to_2_pages

    result = trim_cv_to_2_pages(CV_MANY_PROJECTS)
    word_count = len(result.split())
    assert word_count < 600, (
        f"Trimmed CV should be under 600 words (2-page proxy), got {word_count}"
    )


# ── D1: Generated DOCX from trimmed CV does not crash ─────────────────────────

def test_trimmed_cv_generates_valid_docx():
    from docx import Document
    from backend.deterministic.cv_trimmer import trim_cv_to_2_pages
    from backend.ui.docx_export import generate_cv_docx

    trimmed = trim_cv_to_2_pages(CV_MANY_PROJECTS)
    docx_bytes = generate_cv_docx(
        trimmed,
        candidate_name="Test Kandidat",
        candidate_city="Berlin",
        candidate_email="test@example.com",
    )
    doc = Document(io.BytesIO(docx_bytes))
    texts = [p.text for p in doc.paragraphs if p.text.strip()]
    # Must have at least the section headings.
    all_text = "\n".join(texts)
    assert "PROFIL" in all_text
    assert len(docx_bytes) > 1000


# ── I1: Trimmer is wired into run_cv_tailoring ────────────────────────────────

def test_trimmer_called_from_pipeline():
    """
    Verify that trim_cv_to_2_pages is imported and called in cv_tailoring.
    Inspects the source rather than running the full async pipeline.
    """
    import inspect
    from backend.pipeline import cv_tailoring

    source = inspect.getsource(cv_tailoring)
    assert "trim_cv_to_2_pages" in source, (
        "trim_cv_to_2_pages must be imported and called in cv_tailoring.py"
    )


# ── Level-1 sections with level-2 entry headings (app 50 format) ─────────────

def test_level1_section_with_level2_entry_headings():
    """
    App-50 format: # for section headings, ## for project-entry headings within
    the PROJEKTE section. The trimmer must detect # as the section level and
    treat ## lines inside the body as content (entry titles), not new sections.
    """
    from backend.deterministic.cv_trimmer import trim_cv_to_2_pages

    cv = (
        "# **Profil**\nProfil hier.\n\n"
        "# **Projekte**\n\n"
        "## **KI-Assistent (n8n)**\t03.2026 – 04.2026\n\n"
        "- KI-Bullet-1-wichtig\n"
        "- KI-Bullet-2-wichtig\n"
        "- KI-Bullet-3-SOLL-WEG\n\n"
        "Tech-Stack: Python, Docker\n\n"
        "## **Agent Projekt**\t02.2026 – 03.2026\n\n"
        "- Agent-Bullet-1\n"
        "- Agent-Bullet-2\n"
        "- Agent-Bullet-3-SOLL-WEG\n\n"
        "## **SEACE Microservice**\t12.2025 – 02.2026\n\n"
        "- SEACE-Bullet-1\n"
        "- SEACE-Bullet-2\n\n"
        "## **PDF ETL Pipeline**\t01.2026 – 02.2026\n\n"
        "- ETL-Bullet-1-SOLL-WEG\n"
        "- ETL-Bullet-2-SOLL-WEG\n\n"
        "# **Kenntnisse**\nPython, Docker\n"
    )
    result = trim_cv_to_2_pages(cv)
    # 4th project must be removed
    assert "PDF ETL Pipeline" not in result, "4th project must be removed"
    # First 3 projects must be present
    assert "KI-Assistent" in result
    assert "Agent Projekt" in result
    assert "SEACE Microservice" in result
    # Bullet 3 of each kept project must be removed
    assert "KI-Bullet-3-SOLL-WEG" not in result
    assert "Agent-Bullet-3-SOLL-WEG" not in result
    # First 2 bullets of each kept project must be present
    assert "KI-Bullet-1-wichtig" in result
    assert "KI-Bullet-2-wichtig" in result
    # Passthrough section must be intact
    assert "Kenntnisse" in result
    assert "Python, Docker" in result


def test_level1_detect_correct_level():
    """_detect_section_level must return 1 for a level-1 CV format."""
    from backend.deterministic.cv_trimmer import _detect_section_level

    lines = [
        "# **Javier Briceño Ticona**",
        "",
        "# **Profil**",
        "Erfahrener Entwickler.",
        "",
        "# **Projekte**",
        "",
        "## **Projekt A**\t2026",
    ]
    assert _detect_section_level(lines) == 1


def test_level2_detect_correct_level():
    """_detect_section_level must return 2 for a level-2 CV format."""
    from backend.deterministic.cv_trimmer import _detect_section_level

    lines = [
        "## **Javier Briceño Ticona**",
        "",
        "## **Profil**",
        "Erfahrener Entwickler.",
        "",
        "## **Projekte**",
    ]
    assert _detect_section_level(lines) == 2


# ── Single-hash heading support (raw LLM output variant) ──────────────────────

def test_single_hash_projekte_heading_detected():
    """
    Some LLM outputs use # **Projekte** (single hash + bold) instead of ## PROJEKTE.
    The trimmer must still detect and trim the section.
    """
    from backend.deterministic.cv_trimmer import trim_cv_to_2_pages

    cv = (
        "# **Profil**\nErfahrener Entwickler.\n\n"
        "# **Projekte**\n\n"
        "Projekt A | 2026\n\n- A-Bullet-1\n- A-Bullet-2\n- A-Bullet-3-WEG\n\n"
        "Tech-Stack: Python\n\n"
        "Projekt B | 2025\n\n- B-Bullet-1\n- B-Bullet-2\n- B-Bullet-3-WEG\n\n"
        "Projekt C | 2024\n\n- C-Bullet-1\n- C-Bullet-2\n\n"
        "Projekt D | 2023\n\n- D-Bullet-1-WEG\n- D-Bullet-2-WEG\n"
    )
    result = trim_cv_to_2_pages(cv)
    assert "A-Bullet-3-WEG" not in result
    assert "B-Bullet-3-WEG" not in result
    assert "Projekt D" not in result, "4th project must be removed"
    assert "Projekt A" in result
    assert "Projekt B" in result
    assert "Projekt C" in result
