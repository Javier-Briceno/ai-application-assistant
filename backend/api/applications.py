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
                SELECT id, profile_id, company, role_title, score, threshold,
                       date_applied, cv_diff, anschreiben, gaps, scoring_details
                FROM job_application_assistant.job_applications
                WHERE profile_id = $1
                ORDER BY date_applied DESC
                """,
                profile_id,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, profile_id, company, role_title, score, threshold,
                       date_applied, cv_diff, anschreiben, gaps, scoring_details
                FROM job_application_assistant.job_applications
                ORDER BY date_applied DESC
                """
            )
    return [
        {
            "id": r["id"],
            "profile_id": r["profile_id"],
            "company": r["company"],
            "role_title": r["role_title"],
            "score": r["score"],
            "threshold": r["threshold"],
            "date_applied": r["date_applied"].isoformat() if r["date_applied"] else None,
            "cv_diff": r["cv_diff"],
            "anschreiben": r["anschreiben"],
            "gaps": r["gaps"],
            "scoring_details": json.loads(r["scoring_details"]) if isinstance(r["scoring_details"], str) else r["scoring_details"],
        }
        for r in rows
    ]


async def _fetch_application(application_id: int) -> dict:
    async with get_conn() as conn:
        row = await conn.fetchrow(
            """
            SELECT ja.id, ja.profile_id, ja.company, ja.role_title,
                   ja.tailored_cv, ja.anschreiben,
                   p.first_name, p.last_name, p.city
            FROM job_application_assistant.job_applications ja
            JOIN job_application_assistant.profiles p ON p.id = ja.profile_id
            WHERE ja.id = $1
            """,
            application_id,
        )
    if not row:
        raise HTTPException(404, "Bewerbung nicht gefunden")
    return dict(row)


@router.get("/{application_id}/cv.docx")
async def download_cv_docx(application_id: int):
    row = await _fetch_application(application_id)
    cv_text = row.get("tailored_cv") or ""
    if not cv_text:
        raise HTTPException(404, "Kein angepasster Lebenslauf vorhanden")

    candidate_name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()
    data = generate_cv_docx(cv_text, candidate_name=candidate_name)
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

    candidate_name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()
    company = row.get("company", "")
    candidate_address = row.get("city") or ""
    data = generate_anschreiben_docx(
        text,
        candidate_name=candidate_name,
        company_name=company,
        candidate_address=candidate_address,
    )
    buf = io.BytesIO(data)

    safe_name = candidate_name.replace(" ", "_") if candidate_name else "Anschreiben"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}_Anschreiben.docx"'},
    )
