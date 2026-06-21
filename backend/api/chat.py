import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.db import get_conn
from backend.llm import _anthropic

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])

CHAT_MODEL = "claude-haiku-4-5-20251001"
SYSTEM = (
    "Du bist ein hilfreicher Bewerbungsassistent. "
    "Du hilfst dem Nutzer, seine Bewerbung für eine konkrete Stelle zu optimieren. "
    "Antworte präzise und auf Deutsch, es sei denn, der Nutzer fragt auf Englisch."
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    job_application_id: int | None = None
    company_name: str = ""
    messages: list[ChatMessage]


async def _load_application_context(application_id: int) -> str | None:
    try:
        async with get_conn() as conn:
            row = await conn.fetchrow(
                """
                SELECT company, role_title, job_posting, score, threshold,
                       scoring_details, gaps, cv_diff, tailored_cv, anschreiben
                FROM job_application_assistant.job_applications
                WHERE id = $1
                """,
                application_id,
            )
        if not row:
            return None

        parts = ["## Bewerbungskontext"]
        parts.append(f"Unternehmen: {row['company']}")
        if row["role_title"]:
            parts.append(f"Stelle: {row['role_title']}")
        parts.append(f"Score: {row['score']} (Empfehlung: {row['threshold']})")

        if row["scoring_details"]:
            details = row["scoring_details"]
            if isinstance(details, str):
                details = json.loads(details)
            parts.append(f"Scoring-Details: {json.dumps(details, ensure_ascii=False)[:400]}")

        if row["gaps"]:
            parts.append(f"Lücken/Anforderungen: {str(row['gaps'])[:500]}")

        if row["job_posting"]:
            parts.append(f"Stellenausschreibung (Auszug):\n{row['job_posting'][:1000]}")

        if row["cv_diff"]:
            parts.append(f"Lebenslauf-Änderungen:\n{str(row['cv_diff'])[:600]}")

        if row["tailored_cv"]:
            parts.append(f"Angepasster Lebenslauf (Auszug):\n{str(row['tailored_cv'])[:800]}")

        if row["anschreiben"]:
            parts.append(f"Anschreiben (Auszug):\n{str(row['anschreiben'])[:600]}")

        return "\n\n".join(parts)
    except Exception:
        log.exception("Failed to load application context for chat (id=%s)", application_id)
        return None


async def _stream_chat(messages: list[dict], system: str) -> AsyncGenerator[str, None]:
    async with _anthropic.messages.stream(
        model=CHAT_MODEL,
        system=system,
        max_tokens=1024,
        messages=messages,
    ) as stream:
        async for delta in stream.text_stream:
            yield f"data: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n"


@router.post("/chat")
async def api_chat(req: ChatRequest):
    system = SYSTEM
    if req.job_application_id is not None:
        context = await _load_application_context(req.job_application_id)
        if context:
            system = f"{SYSTEM}\n\n{context}"

    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    # Filter to valid roles only
    messages = [m for m in messages if m["role"] in ("user", "assistant") and m["content"].strip()]
    if not messages:
        return StreamingResponse(iter([]), media_type="text/event-stream")

    return StreamingResponse(
        _stream_chat(messages, system),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
