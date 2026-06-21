"""
Server-side DOCX generation using python-docx.
Replaces the client-side docx@8 ESM generation from the JS frontend.
"""
import io
import re

from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH


def _add_markdown_paragraph(doc: Document, text: str) -> None:
    """Add a paragraph with basic markdown bold support."""
    para = doc.add_paragraph()
    parts = re.split(r"(\*\*.*?\*\*)", text)
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            run = para.add_run(part[2:-2])
            run.bold = True
        elif part:
            para.add_run(part)


def generate_cv_docx(cv_markdown: str, candidate_name: str = "") -> bytes:
    """
    Convert the tailored CV markdown to a DOCX file.
    Returns bytes suitable for a file download response.
    """
    doc = Document()

    # Margins
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1.2)
        section.right_margin = Inches(1.2)

    if candidate_name:
        title = doc.add_heading(candidate_name, level=0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    for line in cv_markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            doc.add_paragraph()
            continue

        if stripped.startswith("## "):
            doc.add_heading(stripped[3:], level=2)
        elif stripped.startswith("# "):
            doc.add_heading(stripped[2:], level=1)
        elif stripped.startswith(("- ", "• ", "* ")):
            para = doc.add_paragraph(style="List Bullet")
            _add_markdown_paragraph_to(para, stripped[2:].strip())
        else:
            _add_markdown_paragraph(doc, stripped)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _add_markdown_paragraph_to(para, text: str) -> None:
    """Add runs with bold support to an existing paragraph."""
    parts = re.split(r"(\*\*.*?\*\*)", text)
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            run = para.add_run(part[2:-2])
            run.bold = True
        elif part:
            para.add_run(part)


def generate_anschreiben_docx(
    anschreiben_text: str,
    candidate_name: str = "",
    candidate_address: str = "",
    company_name: str = "",
) -> bytes:
    """
    Convert the Anschreiben to a DOCX file with basic letter formatting.
    Returns bytes suitable for a file download response.
    """
    doc = Document()

    for section in doc.sections:
        section.top_margin = Inches(1.2)
        section.bottom_margin = Inches(1.2)
        section.left_margin = Inches(1.2)
        section.right_margin = Inches(1.2)

    # Sender block (top right)
    if candidate_name or candidate_address:
        sender = doc.add_paragraph()
        sender.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        sender.add_run(candidate_name).bold = True
        if candidate_address:
            sender.add_run(f"\n{candidate_address}")

    doc.add_paragraph()  # spacing

    # Recipient block
    if company_name:
        recipient = doc.add_paragraph()
        recipient.add_run(company_name).bold = True

    doc.add_paragraph()  # spacing

    # Body
    for line in anschreiben_text.splitlines():
        stripped = line.strip()
        if not stripped:
            doc.add_paragraph()
        else:
            _add_markdown_paragraph(doc, stripped)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
