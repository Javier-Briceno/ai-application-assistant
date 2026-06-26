import io
import json
import logging
import re

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.db import get_conn
from backend.ui.docx_export import generate_anschreiben_docx, generate_cv_docx

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/applications", tags=["applications"])


@router.get("")
async def api_list_applications(profile_id: int | None = Query(None)):
    async with get_conn() as conn:
        if profile_id is not None:
            rows = await conn.fetch(
                """
                SELECT id, profile_id, company, company_address, contact_person, role_title, score, threshold,
                       date_applied, cv_diff, anschreiben, gaps, scoring_details,
                       (tailored_cv IS NOT NULL AND tailored_cv <> '') AS has_tailored_cv
                FROM job_application_assistant.job_applications
                WHERE profile_id = $1
                ORDER BY date_applied DESC
                """,
                profile_id,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, profile_id, company, company_address, contact_person, role_title, score, threshold,
                       date_applied, cv_diff, anschreiben, gaps, scoring_details,
                       (tailored_cv IS NOT NULL AND tailored_cv <> '') AS has_tailored_cv
                FROM job_application_assistant.job_applications
                ORDER BY date_applied DESC
                """
            )
    return [
        {
            "id": r["id"],
            "profile_id": r["profile_id"],
            "company": r["company"],
            "company_address": r["company_address"] or "",
            "contact_person": r["contact_person"] or "",
            "role_title": r["role_title"],
            "score": r["score"],
            "threshold": r["threshold"],
            "date_applied": r["date_applied"].isoformat() if r["date_applied"] else None,
            "cv_diff": r["cv_diff"],
            "anschreiben": r["anschreiben"],
            "gaps": r["gaps"],
            "scoring_details": json.loads(r["scoring_details"]) if isinstance(r["scoring_details"], str) else r["scoring_details"],
            "has_tailored_cv": bool(r["has_tailored_cv"]),
        }
        for r in rows
    ]


async def _fetch_application(application_id: int) -> dict:
    async with get_conn() as conn:
        row = await conn.fetchrow(
            """
            SELECT ja.id, ja.profile_id, ja.company, ja.company_address, ja.contact_person, ja.role_title,
                   ja.tailored_cv, ja.anschreiben,
                   p.first_name, p.last_name,
                   p.street_address, p.postal_code, p.city, p.email,
                   p.phone_country_code, p.phone_number,
                   p.linkedin_url, p.github_url, p.avatar_url
            FROM job_application_assistant.job_applications ja
            JOIN job_application_assistant.profiles p ON p.id = ja.profile_id
            WHERE ja.id = $1
            """,
            application_id,
        )
    if not row:
        raise HTTPException(404, "Bewerbung nicht gefunden")
    return dict(row)


def _build_phone(row: dict) -> str:
    """Combine country code + number if both are available."""
    code = (row.get("phone_country_code") or "").strip()
    number = (row.get("phone_number") or "").strip()
    if code and number:
        return f"{code} {number}"
    return number or code


class _AnschreibenPatch(BaseModel):
    anschreiben: str


@router.patch("/{application_id}/anschreiben", status_code=204)
async def patch_anschreiben(application_id: int, body: _AnschreibenPatch):
    async with get_conn() as conn:
        result = await conn.execute(
            "UPDATE job_application_assistant.job_applications SET anschreiben = $1 WHERE id = $2",
            body.anschreiben,
            application_id,
        )
    if result == "UPDATE 0":
        raise HTTPException(404, "Bewerbung nicht gefunden")


@router.get("/{application_id}/cv.docx")
async def download_cv_docx(application_id: int):
    row = await _fetch_application(application_id)
    cv_text = row.get("tailored_cv") or ""
    if not cv_text:
        raise HTTPException(404, "Kein angepasster Lebenslauf vorhanden")

    candidate_name = f"{row.get('first_name', '') or ''} {row.get('last_name', '') or ''}".strip()
    data = generate_cv_docx(
        cv_text,
        candidate_name=candidate_name,
        candidate_city=row.get("city") or "",
        candidate_email=row.get("email") or "",
        candidate_phone=_build_phone(row),
        candidate_linkedin=row.get("linkedin_url") or "",
        candidate_github=row.get("github_url") or "",
        candidate_photo_url=row.get("avatar_url") or "",
    )
    buf = io.BytesIO(data)

    safe_name = candidate_name.replace(" ", "_") if candidate_name else "Lebenslauf"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}_Lebenslauf.docx"'},
    )


_DATE_RE = re.compile(r"^\d{1,2}\. \w+ \d{4}$")
_BODY_STARTERS = ("sehr geehrte", "bewerbung", "mit freundlichen", "ich bewerbe", "hochachtungsvoll", "betreff")
_PLZ_RE = re.compile(r"^(.*?),?\s*(\d{5}\s+\S.*)$")


def _split_address_at_plz(address: str) -> str:
    """Split 'Musterstraße 1, 12345 Stadt' into 'Musterstraße 1\n12345 Stadt'."""
    m = _PLZ_RE.match(address)
    if m and m.group(1).strip():
        return f"{m.group(1).strip()}\n{m.group(2).strip()}"
    return address


def _parse_company_from_text(text: str) -> tuple[str, str, str]:
    """Parse a saved anschreiben that may start with the company block.

    Returns (company_name, company_address, body_text).
    If no company block is detected the first two values are empty strings.
    """
    lines = text.split("\n")
    first = lines[0].strip() if lines else ""
    if not first or any(first.lower().startswith(s) for s in _BODY_STARTERS):
        return "", "", text

    company_lines: list[str] = []
    i = 0
    while i < len(lines) and lines[i].strip():
        stripped = lines[i].strip()
        if not _DATE_RE.match(stripped):
            company_lines.append(stripped)
        i += 1

    if not company_lines:
        return "", "", text

    while i < len(lines) and not lines[i].strip():
        i += 1

    company_name = company_lines[0]
    company_address = "\n".join(company_lines[1:])
    body = "\n".join(lines[i:])
    return company_name, company_address, body


@router.get("/{application_id}/anschreiben.docx")
async def download_anschreiben_docx(application_id: int):
    row = await _fetch_application(application_id)
    text = row.get("anschreiben") or ""
    if not text:
        raise HTTPException(404, "Kein Anschreiben vorhanden")

    # Parse company block if the user saved an edited version that starts with it.
    # Falls back to the DB company fields when the text starts directly with letter body.
    parsed_company, parsed_address, body_text = _parse_company_from_text(text)
    company_name = parsed_company or (row.get("company") or "")
    db_contact = row.get("contact_person") or ""
    if parsed_company:
        # Already split by the user's editable block — apply PLZ split on each raw line
        company_address = "\n".join(
            _split_address_at_plz(l) for l in parsed_address.splitlines() if l.strip()
        )
    else:
        # Fallback to DB fields; prepend contact person, then split address at PLZ
        db_address = _split_address_at_plz(row.get("company_address") or "")
        company_address = "\n".join(x for x in [db_contact, db_address] if x)

    candidate_name = f"{row.get('first_name', '') or ''} {row.get('last_name', '') or ''}".strip()
    data = generate_anschreiben_docx(
        body_text,
        candidate_name=candidate_name,
        candidate_street=row.get("street_address") or "",
        candidate_postal_code=row.get("postal_code") or "",
        candidate_city=row.get("city") or "",
        candidate_phone=_build_phone(row),
        candidate_email=row.get("email") or "",
        company_name=company_name,
        company_address=company_address,
    )
    buf = io.BytesIO(data)

    safe_name = candidate_name.replace(" ", "_") if candidate_name else "Anschreiben"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}_Anschreiben.docx"'},
    )
