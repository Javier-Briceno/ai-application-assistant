import logging

from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from backend.db import get_conn
from backend.pipeline.profile_extraction import (
    get_profile,
    list_profiles,
    run_profile_setup,
)
from backend.ui.components.avatar import process_avatar

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/profiles", tags=["profiles"])


@router.get("")
async def api_list_profiles():
    async with get_conn() as conn:
        profiles = await list_profiles(conn)
    return [
        {
            "id": p.id,
            "display_name": p.display_name,
            "first_name": p.first_name,
            "last_name": p.last_name,
            "avatar_data_url": p.avatar_url,
            "home_location": p.city,
        }
        for p in profiles
    ]


@router.get("/{profile_id}")
async def api_get_profile(profile_id: int):
    async with get_conn() as conn:
        row = await get_profile(conn, profile_id)
    if not row:
        raise HTTPException(404, "Profil nicht gefunden")
    display_name = f"{row.first_name or ''} {row.last_name or ''}".strip() or f"Profil #{row.id}"
    return {
        "id": row.id,
        "display_name": display_name,
        "first_name": row.first_name,
        "last_name": row.last_name,
        "email": row.email,
        "phone": row.phone_number,
        "linkedin_url": row.linkedin_url,
        "avatar_data_url": row.avatar_url,
        "cv_text": row.cv_text,
        "market_research": row.market_research,
        "career_target": row.career_target,
        "home_location": row.city,
    }


async def _handle_profile_form(
    profile_id: int | None,
    first_name: str,
    last_name: str,
    email: str,
    phone: str,
    linkedin_url: str,
    home_location: str,
    career_target: str,
    market_research: str,
    cv_text: str,
    avatar: UploadFile | None,
) -> JSONResponse:
    avatar_data_url: str | None = None
    if avatar and avatar.filename:
        raw = await avatar.read()
        if raw:
            try:
                avatar_data_url = process_avatar(raw)
            except ValueError as exc:
                raise HTTPException(400, str(exc))

    import asyncio

    async def _run():
        async with get_conn() as conn:
            result = await run_profile_setup(
                conn,
                profile_id=profile_id,
                first_name=first_name,
                last_name=last_name,
                email=email or None,
                phone_number=phone or None,
                city=home_location or None,
                linkedin_url=linkedin_url or None,
                avatar_url=avatar_data_url,
                cv_text=cv_text,
                market_research=market_research or "",
                career_target=career_target or "",
            )
        return result.profile_id

    pid = await asyncio.create_task(_run())
    return JSONResponse({"id": pid})


@router.post("")
async def api_create_profile(
    first_name: str = Form(""),
    last_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    linkedin_url: str = Form(""),
    home_location: str = Form(""),
    career_target: str = Form(""),
    market_research: str = Form(""),
    cv_text: str = Form(""),
    avatar: UploadFile | None = None,
):
    return await _handle_profile_form(
        None, first_name, last_name, email, phone, linkedin_url,
        home_location, career_target, market_research, cv_text, avatar,
    )


@router.delete("/{profile_id}", status_code=204)
async def api_delete_profile(profile_id: int):
    async with get_conn() as conn:
        await conn.execute(
            "DELETE FROM job_application_assistant.profiles WHERE id = $1",
            profile_id,
        )


@router.put("/{profile_id}")
async def api_update_profile(
    profile_id: int,
    first_name: str = Form(""),
    last_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    linkedin_url: str = Form(""),
    home_location: str = Form(""),
    career_target: str = Form(""),
    market_research: str = Form(""),
    cv_text: str = Form(""),
    avatar: UploadFile | None = None,
):
    async with get_conn() as conn:
        existing = await get_profile(conn, profile_id)
    if not existing:
        raise HTTPException(404, "Profil nicht gefunden")
    return await _handle_profile_form(
        profile_id, first_name, last_name, email, phone, linkedin_url,
        home_location, career_target, market_research, cv_text, avatar,
    )
