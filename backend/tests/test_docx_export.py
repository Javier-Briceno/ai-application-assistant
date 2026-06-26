"""
Tests for DOCX export (CV and Anschreiben).

Patch 1 — basic formatting:
  - Generation does not crash and produces valid DOCX
  - Expected section headings are present (ALL CAPS)
  - Deterministic profile fields appear in output
  - Company name and subject appear in Anschreiben
  - No obvious unresolved placeholders
  - Page margins and default font per spec
  - LLM-generated fake personal fields not inserted by DOCX layer

Patch 2 — regression fixes:
  - CV: pre-sections markdown header stripped when deterministic name is provided
  - CV: no --- horizontal rules in output
  - CV: no raw ** markers in output
  - CV: no markdown link syntax in output
  - CV: KURZPROFIL aliased to PROFIL, duplicate section suppressed
  - CV: no literal 'Foto' text when no photo exists
  - Anschreiben: date paragraph is right-aligned
  - Anschreiben: closing and candidate name on separate paragraphs
  - Anschreiben: email and LinkedIn on separate lines (not concatenated)
  - Anschreiben: missing company address not invented
  - Anschreiben: city shortened to first part before comma
"""
import io
import re

import pytest
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm

from backend.ui.docx_export import generate_anschreiben_docx, generate_cv_docx

# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_CV = """\
## PROFIL
Erfahrene Controllerin mit Schwerpunkt auf Budgetplanung und Power BI.

## AUSBILDUNG
Bachelor BWL, Universität Siegen (2021–heute)
Schwerpunkt: Controlling, Note: 1.8

## PRAKTISCHE ERFAHRUNG
Werkstudentin Controlling bei ACME GmbH (2023–heute)
- Budgetplanung und Soll-Ist-Abgleiche mit Excel
- Erstellung von Power BI Dashboards

## KENNTNISSE
Microsoft Excel, Power BI, DAX, Power Query, SAP
"""

# CV whose markdown starts with a header block before the first ## section
CV_WITH_HEADER = (
    "**SARA MUSTERMANN**\n"
    "Werkstudentin Controlling | Siegen, NRW | sara@example.com | +49 123 456789\n\n"
    "---\n\n"
    "## PROFIL\n"
    "Erfahrene Controllerin.\n\n"
    "## AUSBILDUNG\n"
    "Bachelor BWL (2021–heute)\n"
)

# CV with KURZPROFIL that should be deduped against PROFIL
CV_WITH_KURZPROFIL = (
    "## PROFIL\n"
    "Erfahrene Controllerin.\n\n"
    "## KURZPROFIL\n"
    "Noch mehr über Controlling.\n\n"
    "## AUSBILDUNG\n"
    "Bachelor BWL (2021–heute)\n"
)

# CV with markdown links and --- separators
CV_WITH_ARTIFACTS = (
    "## PROFIL\n"
    "Siehe [github.com/sara](https://github.com/sara) für Projekte.\n\n"
    "---\n\n"
    "## KENNTNISSE\n"
    "Python, Docker\n"
)

# CV with a raw old personal header block using plain uppercase section headings (no ## or **)
# Mimics the real regression: LLM tailored CV still contains the old personal header.
CV_WITH_PLAIN_HEADER = (
    "JAVIER BRICEÑO TICONA\n"
    "Informatik B.Sc. Student\n"
    "Adresse: Siegen, Nordrhein-Westfalen · Telefonnummer: +49 123 456789\n"
    "Email: javier@example.com\n"
    "LinkedIn: linkedin.com/in/javier\n"
    "\n"
    "PROFIL\n"
    "Erfahrener Entwickler mit Fokus auf KI.\n"
    "\n"
    "AUSBILDUNG\n"
    "Bachelor CS bei Universität Siegen (2020–2024)\n"
    "\n"
    "PRAKTISCHE ERFAHRUNG\n"
    "Werkstudent bei ACME GmbH (2023–heute)\n"
    "- Entwicklung von KI-Modellen\n"
    "\n"
    "KENNTNISSE\n"
    "Python, TypeScript, Docker\n"
    "\n"
    "SPRACHEN\n"
    "Deutsch: C1, Englisch: B2\n"
)

# CV where LLM used **HEADING** instead of ## HEADING throughout
CV_WITH_BOLD_HEADINGS = (
    "Javier Briceño\n"
    "Software Engineer | Siegen\n\n"
    "**KURZPROFIL**\n"
    "Erfahrener Entwickler.\n\n"
    "**AUSBILDUNG**\n"
    "Bachelor CS (2020–2024)\n\n"
    "**TECHNISCHE KENNTNISSE**\n"
    "Python, TypeScript, Docker\n\n"
    "**SPRACHKENNTNISSE**\n"
    "Deutsch: C1, Englisch: B2\n\n"
    "**PROJEKTE**\n"
    "Open-Source-Beitrag bei [repo](https://github.com/repo)\n"
)

SAMPLE_ANSCHREIBEN = """\
Bewerbung als Junior Controller

Sehr geehrte Damen und Herren,

Ich bewerbe mich für die ausgeschriebene Stelle als Junior Controller. Meine Erfahrungen aus dem Werkstudium passen sehr gut zu Ihren Anforderungen.

Mit freundlichen Grüßen

Sara Mustermann
"""

# Closing WITHOUT a blank line between formula and name (LLM sometimes omits it)
ANSCHREIBEN_CLOSING_MERGED = """\
Bewerbung als Junior Controller

Sehr geehrte Damen und Herren,

Ich bewerbe mich für die ausgeschriebene Stelle.

Mit freundlichen Grüßen
Sara Mustermann
"""

PROFILE = dict(
    candidate_name="Sara Mustermann",
    candidate_city="Siegen",
    candidate_phone="+49 123 456789",
    candidate_email="sara@example.com",
    candidate_linkedin="linkedin.com/in/sara",
    candidate_github="github.com/sara",
)

COMPANY = dict(company_name="TechCorp GmbH")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _open_cv(**kw) -> Document:
    return Document(io.BytesIO(generate_cv_docx(SAMPLE_CV, **kw)))


def _open_anschreiben(**kw) -> Document:
    return Document(io.BytesIO(generate_anschreiben_docx(SAMPLE_ANSCHREIBEN, **kw)))


def _all_text(doc: Document) -> list[str]:
    """Collect paragraph text from body AND table cells."""
    texts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    if para.text.strip():
                        texts.append(para.text)
    return texts


def _body_text(doc: Document) -> str:
    """Full text of body paragraphs only (not table cells), joined."""
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


# ══════════════════════════════════════════════════════════════════════════════
# CV — patch 1: basic generation
# ══════════════════════════════════════════════════════════════════════════════

def test_cv_generation_does_not_crash():
    data = generate_cv_docx(SAMPLE_CV, **PROFILE)
    assert len(data) > 1000


def test_cv_is_valid_docx():
    doc = _open_cv(**PROFILE)
    assert len(doc.paragraphs) > 0


def test_cv_contains_profil_heading():
    texts = _all_text(_open_cv(**PROFILE))
    assert any("PROFIL" in t for t in texts), f"Expected PROFIL heading, got: {texts}"


def test_cv_contains_ausbildung_heading():
    texts = _all_text(_open_cv(**PROFILE))
    assert any("AUSBILDUNG" in t for t in texts), f"Expected AUSBILDUNG heading, got: {texts}"


def test_cv_contains_kenntnisse_heading():
    texts = _all_text(_open_cv(**PROFILE))
    assert any("KENNTNISSE" in t for t in texts), f"Expected KENNTNISSE heading, got: {texts}"


def test_cv_section_headings_are_uppercased():
    doc = Document(io.BytesIO(generate_cv_docx(
        "## erfahrung\n- etwas gemacht\n## ausbildung\nStudium"
    )))
    texts = _all_text(doc)
    assert any(t == "ERFAHRUNG" for t in texts), f"Expected ERFAHRUNG, got: {texts}"
    assert any(t == "AUSBILDUNG" for t in texts), f"Expected AUSBILDUNG, got: {texts}"


def test_cv_contains_candidate_name():
    texts = _all_text(_open_cv(**PROFILE))
    assert any("Sara Mustermann" in t for t in texts), (
        f"Candidate name should appear in header. Got: {texts}"
    )


def test_cv_margins_are_2cm():
    doc = _open_cv(**PROFILE)
    tol = Cm(0.05)
    assert abs(doc.sections[0].top_margin - Cm(2.0)) < tol
    assert abs(doc.sections[0].left_margin - Cm(2.0)) < tol


def test_cv_page_is_a4():
    doc = _open_cv(**PROFILE)
    tol = Cm(0.1)
    assert abs(doc.sections[0].page_width - Cm(21.0)) < tol
    assert abs(doc.sections[0].page_height - Cm(29.7)) < tol


def test_cv_no_fake_data_when_fields_empty():
    doc = Document(io.BytesIO(generate_cv_docx(SAMPLE_CV, candidate_name="Max Muster")))
    full = _body_text(doc)
    assert "+49" not in full, "Phone must not be invented"


# ══════════════════════════════════════════════════════════════════════════════
# CV — patch 2: regression fixes
# ══════════════════════════════════════════════════════════════════════════════

def test_cv_pre_sections_header_stripped():
    """Markdown header block before first ## must be stripped when deterministic name is set."""
    doc = Document(io.BytesIO(generate_cv_docx(CV_WITH_HEADER, candidate_name="Sara Mustermann")))
    body = _body_text(doc)
    assert "SARA MUSTERMANN" not in body, (
        "Name from markdown pre-sections block must not appear in body paragraphs"
    )
    assert "sara@example.com" not in body, (
        "Email from markdown pre-sections block must not appear in body paragraphs"
    )


def test_cv_no_horizontal_rules():
    doc = Document(io.BytesIO(generate_cv_docx(CV_WITH_ARTIFACTS)))
    full = "\n".join(_all_text(doc))
    assert "---" not in full, "Horizontal rules (---) must be stripped from DOCX output"


def test_cv_no_raw_bold_markers():
    """** markers must not appear literally — inline bold must be rendered, not leaked."""
    cv = "## PROFIL\n**Erfahrene** Controllerin mit **Power BI**."
    doc = Document(io.BytesIO(generate_cv_docx(cv)))
    full = "\n".join(_all_text(doc))
    assert "**" not in full, f"Raw ** markers must not appear in DOCX. Got: {full!r}"


def test_cv_no_markdown_links():
    """[text](url) links must be converted to display text only."""
    doc = Document(io.BytesIO(generate_cv_docx(CV_WITH_ARTIFACTS)))
    full = "\n".join(_all_text(doc))
    assert "](https://" not in full and "](http://" not in full, (
        "Markdown link syntax must be stripped"
    )
    assert "github.com/sara" in full, "Link display text should remain in output"


def test_cv_kurzprofil_aliased_to_profil():
    """KURZPROFIL must be aliased to PROFIL and not appear as a separate heading."""
    doc = Document(io.BytesIO(generate_cv_docx(CV_WITH_KURZPROFIL)))
    texts = _all_text(doc)
    assert not any("KURZPROFIL" in t for t in texts), (
        "KURZPROFIL heading must not appear; it should be aliased to PROFIL"
    )


def test_cv_no_duplicate_profil_section():
    """When KURZPROFIL is present, only one PROFIL heading should appear."""
    doc = Document(io.BytesIO(generate_cv_docx(CV_WITH_KURZPROFIL)))
    texts = _all_text(doc)
    profil_count = sum(1 for t in texts if t.strip() == "PROFIL")
    assert profil_count <= 1, (
        f"PROFIL must appear at most once, got {profil_count} times. Texts: {texts}"
    )


def test_cv_no_literal_foto():
    """No literal 'Foto' text when no real profile photo is available."""
    doc = _open_cv(**PROFILE)
    full = "\n".join(_all_text(doc))
    assert "Foto" not in full, (
        "Literal 'Foto' must not be rendered; photo cell should be empty until real photo support"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Anschreiben — patch 1: basic generation
# ══════════════════════════════════════════════════════════════════════════════

def test_anschreiben_generation_does_not_crash():
    assert len(generate_anschreiben_docx(SAMPLE_ANSCHREIBEN, **PROFILE, **COMPANY)) > 1000


def test_anschreiben_is_valid_docx():
    assert len(_open_anschreiben(**PROFILE, **COMPANY).paragraphs) > 0


def test_anschreiben_contains_candidate_name():
    texts = _all_text(_open_anschreiben(**PROFILE, **COMPANY))
    assert any("Sara Mustermann" in t for t in texts)


def test_anschreiben_contains_email():
    texts = _all_text(_open_anschreiben(**PROFILE, **COMPANY))
    assert any("sara@example.com" in t for t in texts)


def test_anschreiben_contains_company_name():
    texts = _all_text(_open_anschreiben(**PROFILE, **COMPANY))
    assert any("TechCorp GmbH" in t for t in texts)


def test_anschreiben_contains_subject():
    texts = _all_text(_open_anschreiben(**PROFILE, **COMPANY))
    assert any("Junior Controller" in t for t in texts)


def test_anschreiben_contains_greeting():
    texts = _all_text(_open_anschreiben(**PROFILE, **COMPANY))
    assert any("Sehr geehrte" in t for t in texts)


def test_anschreiben_contains_closing():
    texts = _all_text(_open_anschreiben(**PROFILE, **COMPANY))
    assert any("Mit freundlichen" in t for t in texts)


def test_anschreiben_no_unresolved_placeholders():
    doc = _open_anschreiben(**PROFILE, **COMPANY)
    full = _body_text(doc)
    for ph in ("{name}", "{email}", "[Name]", "[Email]", "{{", "}}", "INSERT"):
        assert ph not in full, f"Unresolved placeholder {ph!r} found"


def test_anschreiben_no_fake_data_when_fields_empty():
    doc = Document(io.BytesIO(generate_anschreiben_docx(
        SAMPLE_ANSCHREIBEN, candidate_name="Max Muster", company_name="Firma GmbH"
    )))
    full = _body_text(doc)
    assert "+49" not in full
    assert "@example" not in full
    assert "linkedin" not in full.lower()


def test_anschreiben_left_margin_is_2_5cm():
    doc = _open_anschreiben(**PROFILE, **COMPANY)
    tol = Cm(0.05)
    assert abs(doc.sections[0].left_margin - Cm(2.5)) < tol


def test_anschreiben_page_is_a4():
    doc = _open_anschreiben(**PROFILE, **COMPANY)
    tol = Cm(0.1)
    assert abs(doc.sections[0].page_width - Cm(21.0)) < tol
    assert abs(doc.sections[0].page_height - Cm(29.7)) < tol


def test_anschreiben_contains_german_date():
    texts = _all_text(_open_anschreiben(**PROFILE, **COMPANY))
    months = ["Januar","Februar","März","April","Mai","Juni",
              "Juli","August","September","Oktober","November","Dezember"]
    assert any(any(m in t for m in months) for t in texts)


def test_anschreiben_candidate_address_alias():
    doc = Document(io.BytesIO(generate_anschreiben_docx(
        SAMPLE_ANSCHREIBEN,
        candidate_name="Max Muster",
        candidate_address="München",
        company_name="Firma GmbH",
    )))
    assert any("München" in t for t in _all_text(doc))


# ══════════════════════════════════════════════════════════════════════════════
# Anschreiben — patch 2: regression fixes
# ══════════════════════════════════════════════════════════════════════════════

def test_anschreiben_date_is_right_aligned():
    """The date paragraph must be right-aligned."""
    doc = _open_anschreiben(**PROFILE, **COMPANY)
    months = ["Januar","Februar","März","April","Mai","Juni",
              "Juli","August","September","Oktober","November","Dezember"]
    date_para = next(
        (p for p in doc.paragraphs if any(m in p.text for m in months)),
        None,
    )
    assert date_para is not None, "Date paragraph not found"
    assert date_para.alignment == WD_ALIGN_PARAGRAPH.RIGHT, (
        f"Date must be right-aligned, got: {date_para.alignment}"
    )


def test_anschreiben_closing_on_separate_line_from_name():
    """Closing formula and name must be on separate paragraphs even without blank line between them."""
    data = generate_anschreiben_docx(
        ANSCHREIBEN_CLOSING_MERGED,
        candidate_name="Sara Mustermann",
        company_name="Firma GmbH",
    )
    doc = Document(io.BytesIO(data))
    texts = [p.text for p in doc.paragraphs if p.text.strip()]

    closing_idx = next((i for i, t in enumerate(texts) if "Mit freundlichen" in t), None)
    assert closing_idx is not None, "Closing must appear"

    # Name must be on a different paragraph from the closing
    closing_text = texts[closing_idx]
    assert "Sara Mustermann" not in closing_text, (
        f"Candidate name must not be concatenated onto the closing line: {closing_text!r}"
    )

    # Name must appear somewhere after the closing
    name_after = any(
        "Sara Mustermann" in t for t in texts[closing_idx + 1:]
    )
    assert name_after, (
        f"Candidate name must appear after the closing. Texts after closing: {texts[closing_idx:]}"
    )


def test_anschreiben_closing_with_blank_line_still_separate():
    """Normal case: blank line between closing and name — both on separate paragraphs."""
    doc = _open_anschreiben(**PROFILE, **COMPANY)
    texts = [p.text for p in doc.paragraphs if p.text.strip()]

    closing_idx = next((i for i, t in enumerate(texts) if "Mit freundlichen" in t), None)
    assert closing_idx is not None
    assert "Sara Mustermann" not in texts[closing_idx], (
        "Closing line must not contain the candidate name"
    )


def test_anschreiben_email_on_separate_line_from_linkedin():
    """Email and LinkedIn must not be on the same line."""
    doc = _open_anschreiben(**PROFILE, **COMPANY)
    texts = [p.text for p in doc.paragraphs if p.text.strip()]

    email_line = next((t for t in texts if "sara@example.com" in t), None)
    linkedin_line = next((t for t in texts if "linkedin.com" in t), None)

    assert email_line is not None, "Email must appear in contact block"
    if linkedin_line is not None:
        assert email_line != linkedin_line, (
            f"Email and LinkedIn must be on separate lines. Got: {email_line!r}"
        )


def test_anschreiben_no_invented_company_address():
    """When no company_address is provided, no street/postal address should appear."""
    doc = Document(io.BytesIO(generate_anschreiben_docx(
        SAMPLE_ANSCHREIBEN,
        candidate_name="Max Muster",
        company_name="Firma GmbH",
        # no company_address
    )))
    texts = [p.text for p in doc.paragraphs if p.text.strip()]
    company_idx = next((i for i, t in enumerate(texts) if "Firma GmbH" in t), None)
    assert company_idx is not None

    # Lines after the company name should not look like invented addresses
    for t in texts[company_idx + 1:]:
        assert not re.match(r'^\d{5}', t), f"PLZ-style address must not be invented: {t!r}"
        assert not re.search(r'\b(str\.|straße|weg|gasse|platz)\b', t, re.I), (
            f"Street address must not be invented: {t!r}"
        )


def test_anschreiben_city_shortened_before_comma():
    """City 'Siegen, Nordrhein-Westfalen' must appear as just 'Siegen' in the letter."""
    data = generate_anschreiben_docx(
        SAMPLE_ANSCHREIBEN,
        candidate_name="Max Muster",
        candidate_city="Siegen, Nordrhein-Westfalen",
        company_name="Firma GmbH",
    )
    doc = Document(io.BytesIO(data))
    full = _body_text(doc)
    assert "Nordrhein-Westfalen" not in full, (
        "Bundesland should be stripped from city in letter contact block"
    )
    assert "Siegen" in full, "City name should still appear"


def test_anschreiben_github_not_in_letter_header():
    """GitHub URL must not appear in the Anschreiben contact block."""
    doc = _open_anschreiben(**PROFILE, **COMPANY)
    texts = [p.text for p in doc.paragraphs if p.text.strip()]
    # Only check header area (first few paragraphs before date)
    months = ["Januar","Februar","März","April","Mai","Juni",
              "Juli","August","September","Oktober","November","Dezember"]
    date_idx = next(
        (i for i, t in enumerate(texts) if any(m in t for m in months)), len(texts)
    )
    header_texts = "\n".join(texts[:date_idx])
    assert "github.com" not in header_texts.lower(), (
        "GitHub must not appear in the Anschreiben letter header/contact block"
    )


# ══════════════════════════════════════════════════════════════════════════════
# CV — patch 3: bold heading lines (**SECTION**) fix
# ══════════════════════════════════════════════════════════════════════════════

def test_cv_bold_kurzprofil_becomes_profil_heading():
    """**KURZPROFIL** standalone line must be aliased to PROFIL section heading."""
    doc = Document(io.BytesIO(generate_cv_docx(
        CV_WITH_BOLD_HEADINGS, candidate_name="Javier Briceño"
    )))
    texts = _all_text(doc)
    assert any(t.strip() == "PROFIL" for t in texts), (
        f"**KURZPROFIL** must become a PROFIL heading. Got: {texts}"
    )
    assert not any("KURZPROFIL" in t for t in texts), (
        "KURZPROFIL must not appear after aliasing"
    )


def test_cv_bold_ausbildung_no_asterisks():
    """**AUSBILDUNG** must render as a section heading without literal ** in output."""
    doc = Document(io.BytesIO(generate_cv_docx(
        CV_WITH_BOLD_HEADINGS, candidate_name="Javier Briceño"
    )))
    full = "\n".join(_all_text(doc))
    assert "**" not in full, f"No ** markers must remain in CV output. Got: {full!r}"
    texts = _all_text(doc)
    assert any(t.strip() == "AUSBILDUNG" for t in texts), (
        "AUSBILDUNG must appear as a proper section heading"
    )


def test_cv_technische_kenntnisse_aliased_to_kenntnisse():
    """**TECHNISCHE KENNTNISSE** must be aliased to KENNTNISSE."""
    doc = Document(io.BytesIO(generate_cv_docx(
        CV_WITH_BOLD_HEADINGS, candidate_name="Javier Briceño"
    )))
    texts = _all_text(doc)
    assert any(t.strip() == "KENNTNISSE" for t in texts), (
        f"**TECHNISCHE KENNTNISSE** must become KENNTNISSE. Got: {texts}"
    )
    assert not any("TECHNISCHE KENNTNISSE" in t for t in texts), (
        "TECHNISCHE KENNTNISSE must not appear literally"
    )


def test_cv_sprachkenntnisse_aliased_to_sprachen():
    """**SPRACHKENNTNISSE** must be aliased to SPRACHEN."""
    doc = Document(io.BytesIO(generate_cv_docx(
        CV_WITH_BOLD_HEADINGS, candidate_name="Javier Briceño"
    )))
    texts = _all_text(doc)
    assert any(t.strip() == "SPRACHEN" for t in texts), (
        f"**SPRACHKENNTNISSE** must become SPRACHEN. Got: {texts}"
    )
    assert not any("SPRACHKENNTNISSE" in t for t in texts), (
        "SPRACHKENNTNISSE must not appear literally"
    )


def test_cv_bold_heading_header_block_stripped():
    """Name/contact lines before first **HEADING** must be stripped when candidate_name is set."""
    doc = Document(io.BytesIO(generate_cv_docx(
        CV_WITH_BOLD_HEADINGS, candidate_name="Javier Briceño"
    )))
    body = _body_text(doc)
    assert "Software Engineer | Siegen" not in body, (
        "Pre-sections contact line must be stripped from body"
    )


# ══════════════════════════════════════════════════════════════════════════════
# CV — patch 4: plain uppercase section heading detection + raw old header strip
# ══════════════════════════════════════════════════════════════════════════════

def test_cv_plain_header_block_stripped():
    """Old raw personal header block before first plain section must be stripped."""
    doc = Document(io.BytesIO(generate_cv_docx(
        CV_WITH_PLAIN_HEADER, candidate_name="Javier Briceño"
    )))
    body = _body_text(doc)
    all_t = "\n".join(_all_text(doc))
    assert "BRICEÑO TICONA" not in body, (
        "Full name from old raw header must not appear in body paragraphs"
    )
    assert "Adresse:" not in all_t, "Old header 'Adresse:' label must be stripped"
    assert "Telefonnummer:" not in all_t, "Old header 'Telefonnummer:' must be stripped"
    assert "Informatik B.Sc. Student" not in all_t, (
        "Role line from old header must be stripped"
    )


def test_cv_plain_profil_is_section_heading():
    """Plain uppercase 'PROFIL' must become a blue section heading, not body text."""
    doc = Document(io.BytesIO(generate_cv_docx(
        CV_WITH_PLAIN_HEADER, candidate_name="Javier Briceño"
    )))
    texts = _all_text(doc)
    assert any(t.strip() == "PROFIL" for t in texts), (
        f"Plain 'PROFIL' must become a section heading. Got: {texts}"
    )


def test_cv_plain_section_headings_all_recognized():
    """AUSBILDUNG, PRAKTISCHE ERFAHRUNG, KENNTNISSE, SPRACHEN must all become headings."""
    doc = Document(io.BytesIO(generate_cv_docx(
        CV_WITH_PLAIN_HEADER, candidate_name="Javier Briceño"
    )))
    texts = _all_text(doc)
    for expected in ("AUSBILDUNG", "PRAKTISCHE ERFAHRUNG", "KENNTNISSE", "SPRACHEN"):
        assert any(t.strip() == expected for t in texts), (
            f"Plain '{expected}' must be recognized as a section heading. Got: {texts}"
        )


def test_cv_candidate_name_in_caps_not_a_section():
    """All-caps candidate name (e.g. 'JAVIER BRICEÑO TICONA') must not become a section heading."""
    doc = Document(io.BytesIO(generate_cv_docx(
        CV_WITH_PLAIN_HEADER, candidate_name="Javier Briceño"
    )))
    texts = _all_text(doc)
    assert not any(t.strip() == "JAVIER BRICEÑO TICONA" for t in texts), (
        "All-caps candidate name must not be treated as a CV section heading"
    )


def test_cv_candidate_name_appears_only_in_header():
    """Candidate name must appear exactly in the DOCX header table, not again as body text."""
    doc = Document(io.BytesIO(generate_cv_docx(
        CV_WITH_PLAIN_HEADER, candidate_name="Javier Briceño"
    )))
    # Header name lives in a table cell, not in doc.paragraphs
    body = _body_text(doc)
    assert "Javier Briceño" not in body, (
        "Candidate name must not appear as a second time in body paragraphs"
    )
    all_t = _all_text(doc)
    assert any("Briceño" in t for t in all_t), (
        "Candidate name must still appear somewhere (in header table)"
    )


def test_cv_no_adresse_or_telefonnummer_in_output():
    """Old raw header contact labels 'Adresse:' and 'Telefonnummer:' must not appear."""
    for cv in (CV_WITH_PLAIN_HEADER,):
        doc = Document(io.BytesIO(generate_cv_docx(cv, candidate_name="Javier Briceño")))
        full = "\n".join(_all_text(doc))
        assert "Adresse:" not in full, f"'Adresse:' label must not appear in DOCX: {full[:200]}"
        assert "Telefonnummer:" not in full, f"'Telefonnummer:' must not appear in DOCX"


def test_cv_no_raw_asterisks_across_all_fixtures():
    """No ** should appear in any CV output regardless of input format."""
    for label, cv in [
        ("SAMPLE_CV", SAMPLE_CV),
        ("CV_WITH_HEADER", CV_WITH_HEADER),
        ("CV_WITH_KURZPROFIL", CV_WITH_KURZPROFIL),
        ("CV_WITH_ARTIFACTS", CV_WITH_ARTIFACTS),
        ("CV_WITH_BOLD_HEADINGS", CV_WITH_BOLD_HEADINGS),
        ("CV_WITH_PLAIN_HEADER", CV_WITH_PLAIN_HEADER),
    ]:
        doc = Document(io.BytesIO(generate_cv_docx(cv, candidate_name="Test Person")))
        full = "\n".join(_all_text(doc))
        assert "**" not in full, (
            f"Found ** in CV output for fixture {label!r}. "
            f"First occurrence near: {full[max(0,full.index('**')-20):full.index('**')+30]!r}"
        )


def test_anschreiben_linkedin_url_has_no_https_prefix():
    """LinkedIn URL displayed in Anschreiben must not start with https://."""
    data = generate_anschreiben_docx(
        SAMPLE_ANSCHREIBEN,
        candidate_name="Max Muster",
        candidate_linkedin="https://linkedin.com/in/max",
        company_name="Firma GmbH",
    )
    doc = Document(io.BytesIO(data))
    full = _body_text(doc)
    assert "https://linkedin.com" not in full, (
        "LinkedIn URL must have https:// stripped for clean display"
    )
    assert "linkedin.com/in/max" in full, "LinkedIn display URL must still appear"


# ══════════════════════════════════════════════════════════════════════════════
# CV — patch 8: layout / readability improvements
# ══════════════════════════════════════════════════════════════════════════════

# CV fixture with German date periods, Tech-Stack lines, and a KENNTNISSE section.
CV_WITH_GERMAN_DATES = """\
## PROFIL
Erfahrener Entwickler.

## AUSBILDUNG
Universität Siegen · Informatik B.Sc. | 04.2024 – heute
Notendurchschnitt: 1,8 (sehr gut)

## PRAKTISCHE ERFAHRUNG
Werkstudent Backend-Entwicklung | 09.2023 – 03.2024
- Entwicklung von REST-APIs mit Python
- Deployment mit Docker

Tech-Stack: Python, Docker, AWS

## PROJEKTE
KI-Bewerbungsassistent | 03.2026 – 04.2026
- Automatisierungspipeline mit n8n und Claude API
- Hash-basiertes Caching-System

Tech-Stack: n8n, Anthropic Claude API, PostgreSQL

## KENNTNISSE
Python, TypeScript, Docker, PostgreSQL, n8n
"""


def _make_test_photo_data_url() -> str:
    """Create a minimal 4×5 pixel JPEG data URL for testing photo rendering."""
    from PIL import Image
    import base64
    img = Image.new("RGB", (4, 5), color=(200, 150, 100))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=50)
    encoded = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/jpeg;base64,{encoded}"


def test_cv_header_structure_without_role_line():
    """CV header left cell must have exactly 3 paragraphs: name, contact, links — no role line."""
    doc = Document(io.BytesIO(generate_cv_docx(SAMPLE_CV, **PROFILE)))
    header_table = doc.tables[0]
    left_cell = header_table.cell(0, 0)
    cell_paras = [p for p in left_cell.paragraphs if p.text.strip()]
    assert len(cell_paras) == 3, (
        f"Header must have exactly 3 lines (name, contact, links), got {len(cell_paras)}: "
        f"{[p.text for p in cell_paras]}"
    )
    assert "Sara Mustermann" in cell_paras[0].text
    assert "sara@example.com" in cell_paras[1].text
    assert "linkedin.com" in cell_paras[2].text or "github.com" in cell_paras[2].text


def test_cv_header_no_job_title_line():
    """Calling generate_cv_docx does not accept candidate_role — no job-title in output."""
    import inspect
    from backend.ui.docx_export import generate_cv_docx as _gcv
    sig = inspect.signature(_gcv)
    assert "candidate_role" not in sig.parameters, (
        "candidate_role parameter must have been removed from generate_cv_docx"
    )


def test_cv_entry_date_rendered_in_document():
    """German date period must appear somewhere in the DOCX (in entry title table cells)."""
    doc = Document(io.BytesIO(generate_cv_docx(CV_WITH_GERMAN_DATES)))
    all_t = _all_text(doc)  # includes table cells
    assert any("Universität Siegen" in t for t in all_t), "Ausbildung entry must appear in DOCX"
    assert any("04.2024" in t for t in all_t), "Date 04.2024 must appear in DOCX"
    assert any("heute" in t for t in all_t), "'heute' must appear in DOCX"


def test_cv_entry_date_in_paragraph():
    """Entry dates must appear in the body paragraphs (tab-stop approach, no extra tables)."""
    doc = Document(io.BytesIO(generate_cv_docx(CV_WITH_GERMAN_DATES)))
    all_t = _all_text(doc)
    assert any("04.2024" in t for t in all_t), "Date 04.2024 must appear in a paragraph"
    assert any("03.2026" in t for t in all_t), "Date 03.2026 must appear in a paragraph"
    assert any("09.2023" in t for t in all_t), "Date 09.2023 must appear in a paragraph"
    # Entry titles must NOT be in extra tables beyond the single header table
    assert len(doc.tables) == 1, (
        f"Only the header table should exist; got {len(doc.tables)} tables"
    )


def test_cv_entry_title_is_bold():
    """Entry title must be rendered bold in a body paragraph."""
    doc = Document(io.BytesIO(generate_cv_docx(CV_WITH_GERMAN_DATES)))
    for para in doc.paragraphs:
        if "KI-Bewerbungsassistent" in para.text:
            assert para.runs and para.runs[0].bold, (
                "Project entry title run must be bold"
            )
            return
    pytest.fail("Project entry title not found in any paragraph")


def test_cv_tech_stack_lines_omitted():
    """Tech-Stack: lines must not appear in DOCX output."""
    doc = Document(io.BytesIO(generate_cv_docx(CV_WITH_GERMAN_DATES)))
    full = "\n".join(_all_text(doc))
    assert "Tech-Stack:" not in full, (
        "Tech-Stack lines must be omitted from DOCX; technologies are listed in KENNTNISSE"
    )


def test_cv_tech_stack_omitted_various_formats():
    """Tech-Stack omission must work for both 'Tech-Stack:' and 'Tech Stack:' spelling."""
    for line_fmt in ("Tech-Stack: Python, Docker", "Tech Stack: Python, Docker"):
        cv = f"## KENNTNISSE\n{line_fmt}\nPython, Docker\n"
        doc = Document(io.BytesIO(generate_cv_docx(cv)))
        full = "\n".join(_all_text(doc))
        assert "Tech-Stack:" not in full and "Tech Stack:" not in full, (
            f"Format {line_fmt!r} must be omitted from DOCX"
        )


def test_cv_kenntnisse_section_preserved():
    """Technologies in KENNTNISSE must still appear even though Tech-Stack lines are omitted."""
    doc = Document(io.BytesIO(generate_cv_docx(CV_WITH_GERMAN_DATES)))
    full = "\n".join(_all_text(doc))
    assert "KENNTNISSE" in full, "KENNTNISSE section heading must appear"
    assert "Python" in full, "Python must appear in KENNTNISSE"
    assert "TypeScript" in full, "TypeScript must appear in KENNTNISSE"
    assert "Docker" in full, "Docker must appear in KENNTNISSE"


def test_cv_photo_rendered_when_provided():
    """Profile photo from a valid data URL must be embedded as an image in the DOCX."""
    data_url = _make_test_photo_data_url()
    doc = Document(io.BytesIO(generate_cv_docx(
        SAMPLE_CV,
        candidate_name="Sara Mustermann",
        candidate_photo_url=data_url,
    )))
    assert len(doc.inline_shapes) > 0, (
        "DOCX must contain at least one inline image when candidate_photo_url is provided"
    )


def test_cv_photo_absent_when_no_url():
    """No inline image when no photo URL is provided."""
    doc = Document(io.BytesIO(generate_cv_docx(SAMPLE_CV, candidate_name="Sara Mustermann")))
    assert len(doc.inline_shapes) == 0, (
        "DOCX must not contain inline images when no photo URL is provided"
    )


def test_cv_invalid_photo_no_crash():
    """Invalid photo data URL must not crash DOCX generation."""
    data = generate_cv_docx(
        SAMPLE_CV,
        candidate_name="Sara Mustermann",
        candidate_photo_url="data:image/jpeg;base64,NOT_VALID_BASE64!!!",
    )
    assert len(data) > 1000, "DOCX must still be generated even with an invalid photo URL"


def test_cv_photo_right_column_wider():
    """When a photo is present, the right header column must be wider than the default 2.5 cm."""
    data_url = _make_test_photo_data_url()
    doc = Document(io.BytesIO(generate_cv_docx(
        SAMPLE_CV,
        candidate_name="Sara Mustermann",
        candidate_photo_url=data_url,
    )))
    right_col_width_cm = doc.tables[0].columns[1].width.cm
    assert right_col_width_cm > 2.5, (
        f"Right column must be > 2.5 cm when photo present, got {right_col_width_cm:.1f} cm"
    )


def test_cv_entry_date_tab_stop_present():
    """Entry title paragraph with a date must contain a right-aligned tab stop."""
    from lxml import etree
    doc = Document(io.BytesIO(generate_cv_docx(CV_WITH_GERMAN_DATES)))
    for para in doc.paragraphs:
        if "04.2024" in para.text or "03.2026" in para.text:
            xml = para._p.xml
            assert 'w:val="right"' in xml, (
                f"Entry title paragraph must have a right-aligned tab stop; got: {xml[:300]}"
            )
            return
    pytest.fail("No entry title paragraph with a date found")


# ══════════════════════════════════════════════════════════════════════════════
# Additional fixtures for patch 5 root-cause regressions
# ══════════════════════════════════════════════════════════════════════════════

# Mimics apps 52/51: LLM uses # **Name** for the document title and ## **Section**
# for real CV sections. Contact lines are plain body text between the title and the
# first section. Pre-section stripping must remove lines 0–N.
CV_WITH_HASH_TITLE_HEADER = (
    "# **Javier Briceño Ticona**\n"
    "\n"
    "Informatik B.Sc. Student\n"
    "\n"
    "**Adresse**: Siegen · **Telefonnummer**: +49 157 12345678\n"
    "\n"
    "**Email**: javier@example.com · **GitHub**: github.com/Javier\n"
    "\n"
    "---\n"
    "\n"
    "## **Kurzprofil**\n"
    "\n"
    "Erfahrener Entwickler im 5. Semester.\n"
    "\n"
    "## **Ausbildung**\n"
    "\n"
    "Universität Siegen | 04.2024 – heute\n"
    "\n"
    "## **Technische Kenntnisse**\n"
    "\n"
    "Python, TypeScript, Docker\n"
)

# Mimics app 50: LLM uses single # for EVERY heading — document title, contact
# lines, AND real sections. Section detection must still find the first KNOWN section.
CV_WITH_SINGLE_HASH_SECTIONS = (
    "# **Javier Briceño Ticona**\n"
    "\n"
    "# Informatik B.Sc. Student\n"
    "\n"
    "# **Adresse**: Siegen · **Telefonnummer**: +49 123 456789\n"
    "\n"
    "---\n"
    "\n"
    "# **Kurzprofil**\n"
    "\n"
    "Erfahrener Entwickler.\n"
    "\n"
    "# **Ausbildung**\n"
    "\n"
    "Bachelor CS bei Universität Siegen (2020–2024)\n"
    "\n"
    "# **Kenntnisse**\n"
    "\n"
    "Python, TypeScript, Docker\n"
)

# Mimics app 50: LLM uses ## for entry titles (not just section names).
# Those must be rendered as body text, NOT as blue section headings.
CV_WITH_ENTRY_TITLE_HEADINGS = (
    "# **Javier Briceño Ticona**\n"
    "\n"
    "## **Kurzprofil**\n"
    "\n"
    "Erfahrener Entwickler.\n"
    "\n"
    "## **Ausbildung**\n"
    "\n"
    "## **Universität Siegen · Informatik B.Sc.**\t04.2024 – heute\n"
    "\n"
    "Notendurchschnitt: 1,8\n"
    "\n"
    "## **Kenntnisse**\n"
    "\n"
    "Python, TypeScript, Docker\n"
)

# CV with Markdown backslash escape sequences, as stored by LLM in app 50.
CV_WITH_ESCAPED_MARKDOWN = (
    "## PROFIL\n"
    "Student im 5\\. Semester mit Erfahrung.\n"
    "\n"
    "## AUSBILDUNG\n"
    "Universität Siegen | 04.2024 \\- heute\n"
    "\n"
    "## KENNTNISSE\n"
    "Tech\\-Stack: Python, Haiku \\+ Sonnet\n"
    "Metadaten: file\\_hash, file\\_size\n"
    "Kontakt: \\+49 157 12345678\n"
)


# ══════════════════════════════════════════════════════════════════════════════
# CV — patch 5: # **Name** title / # section / ## entry-title / escape fixes
# ══════════════════════════════════════════════════════════════════════════════

def test_cv_hash_title_header_stripped():
    """# **Name** at line 0 plus contact lines must be stripped; PROFIL must be first section."""
    doc = Document(io.BytesIO(generate_cv_docx(
        CV_WITH_HASH_TITLE_HEADER, candidate_name="Javier Briceño"
    )))
    body = _body_text(doc)
    all_t = "\n".join(_all_text(doc))
    assert "Informatik B.Sc. Student" not in all_t, (
        "Role line from # heading must be stripped (it is part of the pre-section block)"
    )
    assert "Adresse:" not in all_t, "Contact 'Adresse:' must be stripped"
    assert "Telefonnummer:" not in all_t, "Contact 'Telefonnummer:' must be stripped"
    assert "javier@example.com" not in body, "Email must not appear in body paragraphs"


def test_cv_hash_title_name_not_in_body():
    """Candidate name from # **Name** line must appear only in the header table, not body."""
    doc = Document(io.BytesIO(generate_cv_docx(
        CV_WITH_HASH_TITLE_HEADER, candidate_name="Javier Briceño"
    )))
    body = _body_text(doc)
    assert "Javier Briceño" not in body, (
        "Candidate name must not appear a second time in body paragraphs"
    )
    assert any("Briceño" in t for t in _all_text(doc)), (
        "Candidate name must still appear in the header table"
    )


def test_cv_hash_title_sections_rendered():
    """## **Kurzprofil** / ## **Ausbildung** / ## **Technische Kenntnisse** must become proper sections."""
    doc = Document(io.BytesIO(generate_cv_docx(
        CV_WITH_HASH_TITLE_HEADER, candidate_name="Javier Briceño"
    )))
    texts = _all_text(doc)
    assert any(t.strip() == "PROFIL" for t in texts), "Kurzprofil must become PROFIL"
    assert any(t.strip() == "AUSBILDUNG" for t in texts), "Ausbildung must become AUSBILDUNG"
    assert any(t.strip() == "KENNTNISSE" for t in texts), (
        "Technische Kenntnisse must become KENNTNISSE"
    )


def test_cv_single_hash_title_stripped():
    """# **Name** with all # headings (app-50 format) — pre-section block stripped."""
    doc = Document(io.BytesIO(generate_cv_docx(
        CV_WITH_SINGLE_HASH_SECTIONS, candidate_name="Javier Briceño"
    )))
    all_t = "\n".join(_all_text(doc))
    body = _body_text(doc)
    assert "Informatik B.Sc. Student" not in all_t, (
        "Role line from # heading in app-50 format must be stripped"
    )
    assert "Adresse:" not in all_t
    assert "Javier Briceño" not in body, (
        "Candidate name must not appear in body when all headings use #"
    )


def test_cv_single_hash_sections_rendered():
    """# **Kurzprofil** / # **Ausbildung** etc. must be promoted to ## SECTION headings."""
    doc = Document(io.BytesIO(generate_cv_docx(
        CV_WITH_SINGLE_HASH_SECTIONS, candidate_name="Javier Briceño"
    )))
    texts = _all_text(doc)
    assert any(t.strip() == "PROFIL" for t in texts), (
        "# **Kurzprofil** must become PROFIL heading"
    )
    assert any(t.strip() == "AUSBILDUNG" for t in texts), (
        "# **Ausbildung** must become AUSBILDUNG heading"
    )
    assert any(t.strip() == "KENNTNISSE" for t in texts), (
        "# **Kenntnisse** must become KENNTNISSE heading"
    )


def test_cv_single_hash_non_section_not_a_heading():
    """# Informatik B.Sc. Student and # **Adresse**: ... must become body text, not section headings."""
    from backend.ui.docx_export import _normalize_cv_markdown
    normalised = _normalize_cv_markdown(CV_WITH_SINGLE_HASH_SECTIONS, "Javier Briceño")
    # After pre-section stripping, these lines must not appear at all
    assert "INFORMATIK B.SC. STUDENT" not in normalised.upper(), (
        "Role line with # must not appear as uppercase section heading in normalized text"
    )
    assert "ADRESSE:" not in normalised.upper(), (
        "Contact line with # must not appear as uppercase heading in normalized text"
    )


def test_cv_entry_title_not_a_section_heading():
    """## **Universität Siegen · Informatik B.Sc.** entry title must be body text, not a section."""
    doc = Document(io.BytesIO(generate_cv_docx(
        CV_WITH_ENTRY_TITLE_HEADINGS, candidate_name="Javier Briceño"
    )))
    texts = _all_text(doc)
    # The entry title must appear as body text
    entry_in_output = any("Universität Siegen" in t for t in texts)
    assert entry_in_output, "Entry title text must still be present in DOCX"
    # It must NOT appear ALL-UPPERCASED as a section heading
    assert not any(
        t.strip() == "UNIVERSITÄT SIEGEN · INFORMATIK B.SC." for t in texts
    ), "Entry title must not be rendered as an all-caps section heading"


def test_cv_entry_title_does_not_displace_real_sections():
    """Real ## **Kurzprofil** and ## **Kenntnisse** sections must still render after entry title fix."""
    doc = Document(io.BytesIO(generate_cv_docx(
        CV_WITH_ENTRY_TITLE_HEADINGS, candidate_name="Javier Briceño"
    )))
    texts = _all_text(doc)
    assert any(t.strip() == "PROFIL" for t in texts), "PROFIL section must still appear"
    assert any(t.strip() == "AUSBILDUNG" for t in texts), "AUSBILDUNG section must still appear"
    assert any(t.strip() == "KENNTNISSE" for t in texts), "KENNTNISSE section must still appear"


def test_cv_escaped_markdown_unescaped_in_body():
    """Backslash escape sequences must be removed from DOCX output."""
    doc = Document(io.BytesIO(generate_cv_docx(CV_WITH_ESCAPED_MARKDOWN)))
    full = "\n".join(_all_text(doc))
    assert "5\\." not in full, r"5\. must be unescaped to 5."
    assert "\\-" not in full, r"\- must be unescaped to -"
    assert "\\+" not in full, r"\+ must be unescaped to +"
    assert "\\_" not in full, r"\_ must be unescaped to _"


def test_cv_escaped_markdown_content_correct():
    """After unescaping, the actual content must be present correctly."""
    doc = Document(io.BytesIO(generate_cv_docx(CV_WITH_ESCAPED_MARKDOWN)))
    full = "\n".join(_all_text(doc))
    assert "5. Semester" in full, "5. Semester must appear after unescaping 5\\."
    assert "04.2024 - heute" in full, "Date range must appear after unescaping \\-"
    # Tech-Stack lines are intentionally omitted from DOCX output; \+ is verified via phone:
    assert "+49 157 12345678" in full, "Phone must appear after unescaping \\+"
    assert "file_hash" in full, "Metadata field must appear after unescaping \\_"


def test_cv_no_backslash_artifacts_across_fixtures():
    """No raw Markdown backslash artifacts in any CV fixture output."""
    _escape_re = re.compile(r'\\[+\-.*_{}\[\]()#!|>\\]')
    for label, cv in [
        ("CV_WITH_ESCAPED_MARKDOWN", CV_WITH_ESCAPED_MARKDOWN),
        ("CV_WITH_HASH_TITLE_HEADER", CV_WITH_HASH_TITLE_HEADER),
        ("CV_WITH_SINGLE_HASH_SECTIONS", CV_WITH_SINGLE_HASH_SECTIONS),
    ]:
        doc = Document(io.BytesIO(generate_cv_docx(cv, candidate_name="Javier Briceño")))
        full = "\n".join(_all_text(doc))
        m = _escape_re.search(full)
        assert m is None, (
            f"Escaped Markdown artifact {m.group()!r} found in {label} DOCX output"
        )


# ══════════════════════════════════════════════════════════════════════════════
# CV — patch 9: portrait photo crop + borderless entry title tables
# ══════════════════════════════════════════════════════════════════════════════

def _make_test_landscape_photo_data_url() -> str:
    """Create a landscape 80×50 pixel JPEG data URL for portrait-crop tests."""
    from PIL import Image
    import base64
    img = Image.new("RGB", (80, 50), color=(180, 120, 80))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=50)
    encoded = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/jpeg;base64,{encoded}"


def test_cv_photo_portrait_ratio():
    """Landscape source photo must be cropped to portrait orientation in the DOCX."""
    data_url = _make_test_landscape_photo_data_url()
    doc = Document(io.BytesIO(generate_cv_docx(
        SAMPLE_CV, candidate_name="Sara Mustermann", candidate_photo_url=data_url,
    )))
    assert len(doc.inline_shapes) > 0, "Photo must be embedded in DOCX"
    shape = doc.inline_shapes[0]
    assert shape.height >= shape.width, (
        f"Photo must be portrait (height >= width). "
        f"Got width={shape.width.cm:.2f}cm, height={shape.height.cm:.2f}cm"
    )


def test_cv_landscape_photo_cropped_to_portrait():
    """_crop_portrait must return a 3:4 portrait image from a landscape input."""
    from backend.ui.docx_export import _crop_portrait
    from PIL import Image
    img = Image.new("RGB", (200, 100), color=(180, 120, 80))  # landscape 2:1
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    result = _crop_portrait(buf.getvalue())
    assert result is not None, "_crop_portrait must not return None for a valid image"
    cropped = Image.open(io.BytesIO(result))
    w, h = cropped.size
    assert h > w, f"Cropped image must be portrait (h > w). Got {w}×{h}"
    ratio = w / h
    assert abs(ratio - 0.75) < 0.05, (
        f"Cropped image must have ~3:4 ratio. Got w/h={ratio:.3f}"
    )
