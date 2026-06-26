import io
import json
import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

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
                SELECT id, profile_id, company, company_address, role_title, score, threshold,
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
                SELECT id, profile_id, company, company_address, role_title, score, threshold,
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
            SELECT ja.id, ja.profile_id, ja.company, ja.company_address, ja.role_title,
                   ja.tailored_cv, ja.anschreiben,
                   p.first_name, p.last_name,
                   p.city, p.email,
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


@router.get("/{application_id}/anschreiben.docx")
async def download_anschreiben_docx(application_id: int):
    row = await _fetch_application(application_id)
    text = row.get("anschreiben") or ""
    if not text:
        raise HTTPException(404, "Kein Anschreiben vorhanden")

    candidate_name = f"{row.get('first_name', '') or ''} {row.get('last_name', '') or ''}".strip()
    data = generate_anschreiben_docx(
        text,
        candidate_name=candidate_name,
        candidate_city=row.get("city") or "",
        candidate_phone=_build_phone(row),
        candidate_email=row.get("email") or "",
        candidate_linkedin=row.get("linkedin_url") or "",
        candidate_github=row.get("github_url") or "",
        company_name=row.get("company") or "",
        company_address=row.get("company_address") or "",
    )
    buf = io.BytesIO(data)

    safe_name = candidate_name.replace(" ", "_") if candidate_name else "Anschreiben"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}_Anschreiben.docx"'},
    )
