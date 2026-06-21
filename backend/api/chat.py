import json
import logging
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


async def _stream_chat(messages: list[dict]) -> AsyncGenerator[str, None]:
    async with _anthropic.messages.stream(
        model=CHAT_MODEL,
        system=SYSTEM,
        max_tokens=1024,
        messages=messages,
    ) as stream:
        async for delta in stream.text_stream:
            yield f"data: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n"


@router.post("/chat")
async def api_chat(req: ChatRequest):
    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    # Filter to valid roles only
    messages = [m for m in messages if m["role"] in ("user", "assistant") and m["content"].strip()]
    if not messages:
        return StreamingResponse(iter([]), media_type="text/event-stream")

    return StreamingResponse(
        _stream_chat(messages),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
