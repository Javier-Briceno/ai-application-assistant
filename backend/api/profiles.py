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
    def _phone(p) -> str:
        code = (p.phone_country_code or "").strip()
        number = (p.phone_number or "").strip()
        if code and number:
            return f"{code} {number}"
        return number or code

    return [
        {
            "id": p.id,
            "display_name": p.display_name,
            "first_name": p.first_name,
            "last_name": p.last_name,
            "avatar_data_url": p.avatar_url,
            "home_location": p.city,
            "street_address": p.street_address,
            "postal_code": p.postal_code,
            "email": p.email or "",
            "phone": _phone(p),
            "linkedin_url": p.linkedin_url or "",
            "github_url": p.github_url or "",
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
        "phone_country_code": row.phone_country_code,
        "phone_number": row.phone_number,
        "street_address": row.street_address,
        "postal_code": row.postal_code,
        "home_location": row.city,
        "linkedin_url": row.linkedin_url,
        "github_url": row.github_url,
        "website_url": row.website_url,
        "avatar_data_url": row.avatar_url,
        "notes": row.notes,
        "cv_text": row.cv_text,
        "market_research": row.market_research,
        "career_target": row.career_target,
    }


async def _handle_profile_form(
    profile_id: int | None,
    first_name: str,
    last_name: str,
    email: str,
    phone_country_code: str,
    phone_number: str,
    street_address: str,
    postal_code: str,
    home_location: str,
    linkedin_url: str,
    github_url: str,
    website_url: str,
    notes: str,
    career_target: str,
    market_research: str,
    cv_text: str,
    avatar: UploadFile | None,
    existing_avatar_url: str | None = None,
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
                phone_country_code=phone_country_code or "+49",
                phone_number=phone_number or None,
                street_address=street_address or None,
                postal_code=postal_code or None,
                city=home_location or None,
                linkedin_url=linkedin_url or None,
                github_url=github_url or None,
                website_url=website_url or None,
                avatar_url=avatar_data_url or existing_avatar_url,
                notes=notes or None,
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
    phone_country_code: str = Form("+49"),
    phone_number: str = Form(""),
    street_address: str = Form(""),
    postal_code: str = Form(""),
    home_location: str = Form(""),
    linkedin_url: str = Form(""),
    github_url: str = Form(""),
    website_url: str = Form(""),
    notes: str = Form(""),
    career_target: str = Form(""),
    market_research: str = Form(""),
    cv_text: str = Form(""),
    avatar: UploadFile | None = None,
):
    return await _handle_profile_form(
        None, first_name, last_name, email, phone_country_code, phone_number,
        street_address, postal_code, home_location, linkedin_url, github_url,
        website_url, notes, career_target, market_research, cv_text, avatar,
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
    phone_country_code: str = Form("+49"),
    phone_number: str = Form(""),
    street_address: str = Form(""),
    postal_code: str = Form(""),
    home_location: str = Form(""),
    linkedin_url: str = Form(""),
    github_url: str = Form(""),
    website_url: str = Form(""),
    notes: str = Form(""),
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
        profile_id, first_name, last_name, email, phone_country_code, phone_number,
        street_address, postal_code, home_location, linkedin_url, github_url,
        website_url, notes, career_target, market_research, cv_text, avatar,
        existing_avatar_url=existing.avatar_url,
    )
