"""
Server-side DOCX generation using python-docx.
Follows the German reference template specs (Lebenslauf_Muster / Anschreiben_Muster).
"""
import io
import re
from datetime import date

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

# ── Colours ───────────────────────────────────────────────────────────────────
_BODY_COLOR = RGBColor(0x2B, 0x2B, 0x2B)
_HEADING_COLOR = RGBColor(0x1F, 0x4E, 0x79)
_DATE_COLOR = RGBColor(0x6B, 0x6B, 0x6B)

# ── Section alias map: normalise variant section names to canonical ────────────
_SECTION_ALIASES: dict[str, str] = {
    "KURZPROFIL": "PROFIL",
    "PROFIL/ZUSAMMENFASSUNG": "PROFIL",
    "ZUSAMMENFASSUNG": "PROFIL",
    "BERUFSERFAHRUNG": "PRAKTISCHE ERFAHRUNG",
    "ARBEITSERFAHRUNG": "PRAKTISCHE ERFAHRUNG",
    "TECHNISCHE KENNTNISSE": "KENNTNISSE",
    "SPRACHKENNTNISSE": "SPRACHEN",
    "SPRACHKOMPETENZ": "SPRACHEN",
    "FACHKENNTNISSE": "KENNTNISSE",
}

# ── All recognised German CV section names (canonical + variant spellings) ────
# Used as a whitelist to detect plain-text section headings (no ## or **).
_ALL_SECTION_NAMES: frozenset[str] = frozenset({
    "PROFIL", "KURZPROFIL", "PROFIL/ZUSAMMENFASSUNG", "ZUSAMMENFASSUNG",
    "AUSBILDUNG", "STUDIUM",
    "PRAKTISCHE ERFAHRUNG", "BERUFSERFAHRUNG", "ARBEITSERFAHRUNG", "ERFAHRUNG",
    "PRAKTIKA", "PRAKTIKUM",
    "PROJEKTE", "PROJEKT", "HOCHSCHULPROJEKTE",
    "KENNTNISSE", "TECHNISCHE KENNTNISSE", "FACHKENNTNISSE",
    "IT-KENNTNISSE", "EDV-KENNTNISSE", "SOFT SKILLS",
    "SPRACHEN", "SPRACHKENNTNISSE", "SPRACHKOMPETENZ",
    "ZERTIFIKATE", "ZERTIFIZIERUNGEN", "WEITERBILDUNG", "FORTBILDUNG",
    "EHRENAMT", "EHRENAMTLICHES ENGAGEMENT", "ENGAGEMENT",
    "INTERESSEN", "HOBBYS", "HOBBIES",
    "REFERENZEN", "FREIWILLIGENARBEIT",
    "PUBLIKATIONEN", "VERÖFFENTLICHUNGEN",
    "LEISTUNGEN", "AUSZEICHNUNGEN",
})

# ── Regexes used in normalisation ─────────────────────────────────────────────
_HR_RE = re.compile(r'^[-*_]{3,}\s*$')
_MD_LINK_RE = re.compile(r'\[([^\]]*)\]\([^)]*\)')
_HEADING_RE = re.compile(r'^(#{1,2})\s+(.+)$')
# Matches standalone bold-only heading lines: **SECTION NAME** (all uppercase, 3+ chars)
_BOLD_HEADING_RE = re.compile(r'^\*\*([A-ZÄÖÜ][A-ZÄÖÜ\s/]{2,})\*\*\s*$')
# Unescapes Markdown backslash sequences: \+ \- \. \_ etc.
_MD_UNESCAPE_RE = re.compile(r'\\([*_{}\[\]()#+\-.!|\\`>])')


def _is_plain_section_line(line: str) -> bool:
    """Return True if the stripped line is a known plain-text CV section heading."""
    return line.strip().upper() in _ALL_SECTION_NAMES


def _extract_known_section(line: str) -> str | None:
    """Return canonical section name if line is a known CV section heading; else None.

    Supports all heading formats the LLM may produce:
      ## PROFIL       # PROFIL
      ## **Kurzprofil**   # **Kurzprofil**
      **KURZPROFIL**      plain PROFIL

    Will NOT match document-title lines, contact lines, or entry titles such as:
      # **Javier Briceño Ticona**
      # **Adresse**: Siegen...
      ## **Universität Siegen · Informatik B.Sc.** | 04.2024 – heute
    """
    stripped = line.strip()
    # # or ## heading (with or without ** wrapping the name)
    hm = _HEADING_RE.match(stripped)
    if hm:
        name = hm.group(2).strip().replace("**", "").strip().upper()
        if name in _ALL_SECTION_NAMES or name in _SECTION_ALIASES:
            return _SECTION_ALIASES.get(name, name)
        return None
    # **ALL CAPS** bold-only line
    bm = _BOLD_HEADING_RE.match(stripped)
    if bm:
        name = bm.group(1).strip().upper()
        if name in _ALL_SECTION_NAMES or name in _SECTION_ALIASES:
            return _SECTION_ALIASES.get(name, name)
        return None
    # Plain whitelist section name (PROFIL, AUSBILDUNG, etc.)
    if _is_plain_section_line(stripped):
        name = stripped.upper()
        return _SECTION_ALIASES.get(name, name)
    return None


# ── Markdown pre-processing ───────────────────────────────────────────────────

def _normalize_cv_markdown(markdown: str, candidate_name: str = "") -> str:
    """
    Pre-process tailored CV markdown before DOCX rendering.

    Steps:
    1. Strip the pre-sections header block (everything before the first KNOWN section)
       when a deterministic candidate_name is already being rendered.
       Uses _extract_known_section() so only whitelisted section names are accepted as
       anchors — document title, contact lines, and entry titles are never treated as
       section anchors. Line 0 is always skipped (it is the document title/name line).
    2. Strip horizontal rules (---, ***, ___).
    3. Convert [display](url) markdown links to display text only.
    4. Unescape Markdown backslash sequences (\\+, \\-, \\., \\_, etc.).
    5. Convert standalone **ALL CAPS** bold lines that are known sections → ## CANONICAL.
    6. Normalise # / ## headings:
         - Known section name → ## CANONICAL (always double-hash, normalised)
         - Non-section heading (document title, entry title, contact line) → plain body text
    7. Convert plain whitelist section headings (PROFIL, AUSBILDUNG, …) → ## CANONICAL.
    8. Strip any remaining ** markers from body lines.
    """
    lines = markdown.splitlines()

    # Strip pre-sections header block when we have a deterministic header.
    # _extract_known_section() rejects document titles, contact lines, and entry titles,
    # so only a real CV section name can be the cut point.
    #
    # Skip this entirely if line 0 is itself a known section — the CV starts clean
    # with no personal header block to strip.
    # Otherwise, search from i > 0 so the document-title line (# **Name** or the
    # candidate's name in plain text) is never treated as the stripping anchor.
    if candidate_name:
        first_line_is_section = bool(lines) and _extract_known_section(lines[0]) is not None
        if not first_line_is_section:
            first_section_idx: int | None = next(
                (i for i, ln in enumerate(lines)
                 if i > 0 and _extract_known_section(ln) is not None),
                None,
            )
            if first_section_idx is not None:
                lines = lines[first_section_idx:]

    out: list[str] = []
    for line in lines:
        stripped = line.strip()

        # Drop horizontal rules
        if _HR_RE.match(stripped):
            continue

        # Convert markdown links → display text
        line = _MD_LINK_RE.sub(r'\1', line)

        # Unescape Markdown backslash sequences: \+ \- \. \_ etc.
        line = _MD_UNESCAPE_RE.sub(r'\1', line)
        stripped = line.strip()

        # Convert standalone **ALL CAPS** bold heading lines to ## CANONICAL.
        # Only proceeds if the content is a known section name.
        bm = _BOLD_HEADING_RE.match(stripped)
        if bm:
            name = bm.group(1).strip().upper()
            canonical = _SECTION_ALIASES.get(name, name)
            if canonical in _ALL_SECTION_NAMES or name in _ALL_SECTION_NAMES:
                out.append(f"## {canonical}")
            else:
                out.append(bm.group(1).strip())  # not a section — plain body text
            continue

        # Normalise # / ## headings.
        # Known section name → ## CANONICAL.
        # Everything else (document title, entry title, contact line) → plain body text.
        hm = _HEADING_RE.match(stripped)
        if hm:
            name = hm.group(2).strip().replace("**", "").strip().upper()
            canonical = _SECTION_ALIASES.get(name, name)
            if canonical in _ALL_SECTION_NAMES or name in _ALL_SECTION_NAMES:
                out.append(f"## {canonical}")
            else:
                body = hm.group(2).strip().replace("**", "").strip()
                out.append(body)
            continue

        # Convert plain whitelist section headings: PROFIL, AUSBILDUNG, etc. → ## CANONICAL
        if _is_plain_section_line(stripped):
            name = stripped.upper()
            canonical = _SECTION_ALIASES.get(name, name)
            out.append(f"## {canonical}")
            continue

        # Strip any remaining ** markers from body lines
        line = line.replace("**", "")

        out.append(line)

    return "\n".join(out)


# ── URL / city helpers ────────────────────────────────────────────────────────

def _clean_url(url: str) -> str:
    """Strip https:// or http:// prefix so URLs display cleanly."""
    return re.sub(r'^https?://', '', url).rstrip('/')


def _short_city(city: str) -> str:
    """Return only the city portion, dropping any state/Bundesland after a comma.

    'Siegen, Nordrhein-Westfalen' → 'Siegen'
    'Frankfurt am Main' → 'Frankfurt am Main' (no comma, unchanged)
    """
    return city.split(",")[0].strip() if city else ""


# ── Low-level XML helpers ─────────────────────────────────────────────────────

def _set_para_spacing(para, before_pt: float = 0, after_pt: float = 0) -> None:
    pPr = para._p.get_or_add_pPr()
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:before"), str(int(before_pt * 20)))
    spacing.set(qn("w:after"), str(int(after_pt * 20)))
    pPr.append(spacing)


def _set_run_font(run, name: str = "Calibri", size_pt: float | None = None,
                  color: RGBColor | None = None, bold: bool = False,
                  italic: bool = False) -> None:
    run.font.name = name
    if size_pt is not None:
        run.font.size = Pt(size_pt)
    if color is not None:
        run.font.color.rgb = color
    run.font.bold = bold
    run.font.italic = italic


def _add_run(para, text: str, size_pt: float | None = None,
             color: RGBColor | None = None, bold: bool = False,
             italic: bool = False) -> None:
    run = para.add_run(text)
    _set_run_font(run, size_pt=size_pt, color=color or _BODY_COLOR,
                  bold=bold, italic=italic)


def _set_tab_stops(para, right_pos_cm: float) -> None:
    pPr = para._p.get_or_add_pPr()
    tabs = OxmlElement("w:tabs")
    tab = OxmlElement("w:tab")
    tab.set(qn("w:val"), "right")
    tab.set(qn("w:pos"), str(int(right_pos_cm * 720)))
    tabs.append(tab)
    pPr.append(tabs)


# ── Document setup ────────────────────────────────────────────────────────────

def _setup_a4(doc: Document, top_cm=2.0, bottom_cm=2.0,
              left_cm=2.0, right_cm=2.0, header_dist_cm=1.25) -> None:
    for section in doc.sections:
        section.page_height = Cm(29.7)
        section.page_width = Cm(21.0)
        section.top_margin = Cm(top_cm)
        section.bottom_margin = Cm(bottom_cm)
        section.left_margin = Cm(left_cm)
        section.right_margin = Cm(right_cm)
        section.header_distance = Cm(header_dist_cm)
        section.footer_distance = Cm(header_dist_cm)


def _set_doc_default_font(doc: Document, name: str = "Calibri",
                          size_pt: float = 11.0) -> None:
    style = doc.styles["Normal"]
    style.font.name = name
    style.font.size = Pt(size_pt)
    style.font.color.rgb = _BODY_COLOR


# ── Shared paragraph helpers ──────────────────────────────────────────────────

def _add_blank_line(doc: Document, size_pt: float = 4.0) -> None:
    para = doc.add_paragraph()
    _set_para_spacing(para, before_pt=0, after_pt=0)
    para.add_run().font.size = Pt(size_pt)


# ── CV-specific helpers ───────────────────────────────────────────────────────

def _add_cv_section_heading(doc: Document, text: str) -> None:
    para = doc.add_paragraph()
    _set_para_spacing(para, before_pt=11, after_pt=4)
    run = para.add_run(text.upper())
    _set_run_font(run, size_pt=10.5, color=_HEADING_COLOR, bold=True)
    pPr = para._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "4")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "1F4E79")
    pBdr.append(bottom)
    pPr.append(pBdr)


def _add_cv_entry_title(doc: Document, title: str, org: str = "",
                        period: str = "", usable_width_cm: float = 17.0) -> None:
    para = doc.add_paragraph()
    _set_para_spacing(para, before_pt=6, after_pt=2)
    if period:
        _set_tab_stops(para, right_pos_cm=usable_width_cm)
    _add_run(para, title, size_pt=10.5, bold=True)
    if org:
        _add_run(para, f"  |  {org}", size_pt=10.5)
    if period:
        para.add_run("\t")
        _add_run(para, period, size_pt=9.5, color=_DATE_COLOR, italic=True)


def _add_cv_bullet(doc: Document, text: str) -> None:
    para = doc.add_paragraph()
    _set_para_spacing(para, before_pt=1, after_pt=1)
    pPr = para._p.get_or_add_pPr()
    ind = OxmlElement("w:ind")
    ind.set(qn("w:left"), "360")
    ind.set(qn("w:hanging"), "180")
    pPr.append(ind)
    _add_run(para, "–  " + text, size_pt=10.5)


# ── Markdown-inline bold renderer ─────────────────────────────────────────────

def _render_inline(para, text: str, size_pt: float = 10.5,
                   color: RGBColor | None = None) -> None:
    parts = re.split(r"(\*\*.*?\*\*)", text)
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            _add_run(para, part[2:-2], size_pt=size_pt, color=color, bold=True)
        elif part:
            _add_run(para, part, size_pt=size_pt, color=color)


# ── Entry-title heuristics ────────────────────────────────────────────────────

_ENTRY_TITLE_RE = re.compile(
    r"(.+?)\s+(?:bei|at|@)\s+(.+?)\s*[\(\[]([^\)\]]+)[\)\]]$",
    re.IGNORECASE,
)
_TRAILING_DATE_RE = re.compile(
    r"^(.+?)\s*[\(\[]([0-9]{4}[^)\]]{0,20})[\)\]]$"
)


def _looks_like_entry_title(line: str) -> bool:
    return bool(_ENTRY_TITLE_RE.match(line)) or bool(_TRAILING_DATE_RE.match(line))


def _render_entry_line(doc: Document, line: str, usable_width_cm: float) -> None:
    m = _ENTRY_TITLE_RE.match(line)
    if m:
        _add_cv_entry_title(doc, m.group(1).strip(), org=m.group(2).strip(),
                            period=m.group(3).strip(),
                            usable_width_cm=usable_width_cm)
        return
    m2 = _TRAILING_DATE_RE.match(line)
    if m2:
        _add_cv_entry_title(doc, m2.group(1).strip(), period=m2.group(2).strip(),
                            usable_width_cm=usable_width_cm)
        return
    para = doc.add_paragraph()
    _set_para_spacing(para, before_pt=6, after_pt=2)
    _render_inline(para, line, size_pt=10.5)


# ── CV DOCX ───────────────────────────────────────────────────────────────────

def generate_cv_docx(
    cv_markdown: str,
    candidate_name: str = "",
    candidate_role: str = "",
    candidate_city: str = "",
    candidate_email: str = "",
    candidate_phone: str = "",
    candidate_linkedin: str = "",
    candidate_github: str = "",
) -> bytes:
    """
    Convert the tailored CV markdown to a DOCX file.
    Returns bytes suitable for a file download response.
    """
    doc = Document()
    _setup_a4(doc, top_cm=2.0, bottom_cm=2.0, left_cm=2.0, right_cm=2.0)
    _set_doc_default_font(doc, "Calibri", 10.5)

    # ── Deterministic header table ─────────────────────────────────────────────
    # Usable width = 21 - 2 - 2 = 17 cm; right col reserved for photo (TODO: real photo support)
    usable_width_cm = 17.0
    left_col_cm, right_col_cm = 14.5, 2.5

    table = doc.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    tbl = table._tbl
    tblPr = tbl.find(qn("w:tblPr"))
    if tblPr is None:
        tblPr = OxmlElement("w:tblPr")
        tbl.insert(0, tblPr)
    tblBorders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "none")
        tblBorders.append(el)
    tblPr.append(tblBorders)

    table.columns[0].width = Cm(left_col_cm)
    table.columns[1].width = Cm(right_col_cm)

    left_cell = table.cell(0, 0)
    right_cell = table.cell(0, 1)

    for cell in (left_cell, right_cell):
        for para in cell.paragraphs:
            _set_para_spacing(para, before_pt=0, after_pt=0)

    # Name (20 pt, blue, bold)
    name_para = left_cell.paragraphs[0]
    _set_para_spacing(name_para, before_pt=0, after_pt=4)
    if candidate_name:
        run = name_para.add_run(candidate_name)
        _set_run_font(run, size_pt=20, color=_HEADING_COLOR, bold=True)

    # Role line
    if candidate_role:
        rp = left_cell.add_paragraph()
        _set_para_spacing(rp, before_pt=0, after_pt=6)
        _add_run(rp, candidate_role, size_pt=10.5, color=_BODY_COLOR)

    # Contact line: city | phone | email
    city_short = _short_city(candidate_city)
    contact_parts = [x for x in [city_short, candidate_phone, candidate_email] if x]
    if contact_parts:
        cp = left_cell.add_paragraph()
        _set_para_spacing(cp, before_pt=0, after_pt=2)
        _add_run(cp, "  |  ".join(contact_parts), size_pt=9.5, color=_DATE_COLOR)

    # Links line: LinkedIn | GitHub
    link_parts = []
    if candidate_linkedin:
        link_parts.append(_clean_url(candidate_linkedin))
    if candidate_github:
        link_parts.append(_clean_url(candidate_github))
    if link_parts:
        lp = left_cell.add_paragraph()
        _set_para_spacing(lp, before_pt=0, after_pt=2)
        _add_run(lp, "  |  ".join(link_parts), size_pt=9.5, color=_DATE_COLOR)

    # Right cell: empty — TODO: insert real profile photo when available
    right_cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_para_spacing(right_cell.paragraphs[0], before_pt=0, after_pt=0)

    # Gap after header
    gap = doc.add_paragraph()
    _set_para_spacing(gap, before_pt=6, after_pt=0)
    gap.add_run().font.size = Pt(4)

    # ── Normalise and render markdown body ─────────────────────────────────────
    # TODO: exact 2-page enforcement requires a semantic/layout step — not in this patch.
    normalised = _normalize_cv_markdown(cv_markdown, candidate_name)
    seen_sections: set[str] = set()
    in_skip_section = False

    for line in normalised.splitlines():
        stripped = line.strip()

        # Section heading detection
        hm = _HEADING_RE.match(stripped)
        if hm:
            section_name = hm.group(2).strip().upper()
            if section_name in seen_sections:
                # Skip duplicate section and its content
                in_skip_section = True
            else:
                seen_sections.add(section_name)
                in_skip_section = False
                _add_cv_section_heading(doc, section_name)
            continue

        if in_skip_section or not stripped:
            continue

        if stripped.startswith(("- ", "• ", "* ")):
            _add_cv_bullet(doc, stripped[2:].strip())
        elif stripped.startswith("– ") or stripped.startswith("— "):
            _add_cv_bullet(doc, stripped[2:].strip())
        elif _looks_like_entry_title(stripped):
            _render_entry_line(doc, stripped, usable_width_cm)
        else:
            para = doc.add_paragraph()
            _set_para_spacing(para, before_pt=1, after_pt=1)
            _render_inline(para, stripped, size_pt=10.5)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ── Anschreiben DOCX ──────────────────────────────────────────────────────────

_DE_MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni",
               "Juli", "August", "September", "Oktober", "November", "Dezember"]


def generate_anschreiben_docx(
    anschreiben_text: str,
    candidate_name: str = "",
    candidate_city: str = "",
    candidate_phone: str = "",
    candidate_email: str = "",
    candidate_linkedin: str = "",
    candidate_github: str = "",  # kept in signature but not shown in letter header
    company_name: str = "",
    company_address: str = "",
    candidate_address: str = "",  # legacy alias for candidate_city
) -> bytes:
    """
    Convert the Anschreiben to a DOCX following the German reference letter style.
    Returns bytes suitable for a file download response.
    """
    if candidate_address and not candidate_city:
        candidate_city = candidate_address

    doc = Document()
    _setup_a4(doc, top_cm=2.0, bottom_cm=2.0, left_cm=2.5, right_cm=2.0)
    _set_doc_default_font(doc, "Calibri", 11.0)

    # ── 1. Sender block (one field per line) ───────────────────────────────────
    if candidate_name:
        p = doc.add_paragraph()
        _set_para_spacing(p, before_pt=0, after_pt=4)
        _add_run(p, candidate_name, size_pt=11, bold=True)

    city_short = _short_city(candidate_city)
    city_phone_parts = [x for x in [city_short, candidate_phone] if x]
    if city_phone_parts:
        p = doc.add_paragraph()
        _set_para_spacing(p, before_pt=0, after_pt=4)
        _add_run(p, "  |  ".join(city_phone_parts), size_pt=11)

    if candidate_email:
        p = doc.add_paragraph()
        _set_para_spacing(p, before_pt=0, after_pt=4)
        _add_run(p, candidate_email, size_pt=11)

    if candidate_linkedin:
        p = doc.add_paragraph()
        _set_para_spacing(p, before_pt=0, after_pt=4)
        _add_run(p, _clean_url(candidate_linkedin), size_pt=11)
    # Note: GitHub omitted from letter header — relevant for CV, not cover letter

    # ── 2. Blank line ──────────────────────────────────────────────────────────
    _add_blank_line(doc, size_pt=6)

    # ── 3. Recipient block ─────────────────────────────────────────────────────
    if company_name:
        p = doc.add_paragraph()
        _set_para_spacing(p, before_pt=0, after_pt=4)
        _add_run(p, company_name, size_pt=11, bold=True)
    # Company address: render only if explicitly provided — never invent it
    if company_address:
        for addr_line in company_address.splitlines():
            addr_line = addr_line.strip()
            if addr_line:
                p = doc.add_paragraph()
                _set_para_spacing(p, before_pt=0, after_pt=4)
                _add_run(p, addr_line, size_pt=11)

    # ── 4. Blank line ──────────────────────────────────────────────────────────
    _add_blank_line(doc, size_pt=6)

    # ── 5. Date, right-aligned ─────────────────────────────────────────────────
    _today = date.today()
    today_str = f"{_today.day}. {_DE_MONTHS[_today.month - 1]} {_today.year}"
    p = doc.add_paragraph()
    _set_para_spacing(p, before_pt=0, after_pt=8)
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    _add_run(p, today_str, size_pt=11)

    # ── 6–11. Body ─────────────────────────────────────────────────────────────
    _render_anschreiben_body(doc, anschreiben_text)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _render_anschreiben_body(doc: Document, text: str) -> None:
    """
    Render Anschreiben body text into the document.

    Handles:
    - Subject line (bold): line starting with "Betreff:", "Bewerbung", "Ihre Ausschreibung"
    - Greeting: "Sehr geehrte..."
    - Body paragraphs: plain/inline-bold text
    - Closing: "Mit freundlichen Grüßen" — always gets a signature gap below it
    - Candidate name: lines immediately after closing (same or next blank-separated block)

    The closing + name are split even if no blank line separates them in the LLM output.
    """
    # Build blocks: lists of non-blank lines, separated by blank lines
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if s:
            current.append(s)
        else:
            if current:
                blocks.append(current)
                current = []
    if current:
        blocks.append(current)

    post_closing = False

    for block_lines in blocks:
        first = block_lines[0].lower()

        is_subject = (
            first.startswith("betreff:")
            or first.startswith("bewerbung")
            or first.startswith("ihre ausschreibung")
        )
        is_greeting = first.startswith("sehr geehrte")
        is_closing = first.startswith("mit freundlichen")

        if post_closing:
            # Lines after the closing block are the candidate name / signature
            for ln in block_lines:
                p = doc.add_paragraph()
                _set_para_spacing(p, before_pt=0, after_pt=4)
                _add_run(p, ln, size_pt=11)
            continue

        if is_closing:
            post_closing = True
            # Render the closing formula on its own paragraph
            p = doc.add_paragraph()
            _set_para_spacing(p, before_pt=12, after_pt=4)
            _add_run(p, block_lines[0], size_pt=11)
            # Signature gap (space for handwritten signature)
            for _ in range(2):
                _add_blank_line(doc, size_pt=8)
            # Any additional lines in the same block (name merged without blank line)
            for name_line in block_lines[1:]:
                if name_line.strip():
                    p = doc.add_paragraph()
                    _set_para_spacing(p, before_pt=0, after_pt=4)
                    _add_run(p, name_line, size_pt=11)
            continue

        # Join lines within the block for subject / greeting / body
        block_text = " ".join(block_lines)

        if is_subject:
            p = doc.add_paragraph()
            _set_para_spacing(p, before_pt=0, after_pt=8)
            subject_text = re.sub(r"^[Bb]etreff:\s*", "", block_text)
            _add_run(p, subject_text, size_pt=11, bold=True)
        elif is_greeting:
            p = doc.add_paragraph()
            _set_para_spacing(p, before_pt=0, after_pt=6)
            _add_run(p, block_text, size_pt=11)
        else:
            p = doc.add_paragraph()
            _set_para_spacing(p, before_pt=0, after_pt=6)
            _render_inline(p, block_text, size_pt=11)
