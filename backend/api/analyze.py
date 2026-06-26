import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.db import get_conn
from backend.exceptions import UserVisibleError
from backend.pipeline.main_pipeline import run_main_pipeline

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["analyze"])

_GENERIC_ERROR = "Analyse fehlgeschlagen. Bitte versuchen Sie es erneut."


def _user_safe_error(exc: Exception) -> str:
    """Return a user-facing German error message.

    UserVisibleError is raised by the pipeline for conditions the user can act
    on (e.g. missing CV).  All other exceptions hide internal details to avoid
    leaking DB errors, API keys, stack traces, or model names.
    """
    if isinstance(exc, UserVisibleError):
        return str(exc)
    return _GENERIC_ERROR


_MAX_POSTING_LEN = 50_000


class AnalyzeRequest(BaseModel):
    profile_id: int
    job_posting: str


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/analyze")
async def api_analyze(req: AnalyzeRequest):
    async def generate_with_steps():
        if len(req.job_posting) > _MAX_POSTING_LEN:
            yield _sse({
                "type": "error",
                "message": (
                    f"Die Stellenausschreibung ist zu lang "
                    f"(max. {_MAX_POSTING_LEN:,} Zeichen).".replace(",", ".")
                ),
            })
            return

        steps: list[str] = []

        async def on_step(msg: str):
            steps.append(msg)

        # We can't easily interleave steps with the pipeline mid-execution
        # via a simple generator. Use a queue approach:
        import asyncio
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        def step_cb(msg: str):
            queue.put_nowait(msg)

        async def run_pipeline():
            try:
                async with get_conn() as conn:
                    result = await run_main_pipeline(
                        conn,
                        profile_id=req.profile_id,
                        job_posting=req.job_posting,
                        on_step=step_cb,
                    )
                queue.put_nowait(None)  # sentinel
                return result
            except Exception as exc:
                queue.put_nowait(None)
                raise exc

        pipeline_task = asyncio.create_task(run_pipeline())

        # Drain step events while pipeline runs
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                if pipeline_task.done():
                    break
                continue
            if msg is None:
                break
            yield _sse({"type": "step", "message": msg})

        # Drain any remaining steps
        while not queue.empty():
            msg = queue.get_nowait()
            if msg:
                yield _sse({"type": "step", "message": msg})

        # Get result or exception
        try:
            result = await pipeline_task
        except Exception as exc:
            log.exception("Pipeline error")
            yield _sse({"type": "error", "message": _user_safe_error(exc)})
            return

        dims = result.scoring.dims
        ao = result.scoring.analyzer_output
        payload = {
            "profile_id": result.profile_id,
            "company": {
                "company_name": result.company.company_name,
                "search_name": result.company.search_name,
                "research_text": result.company.company_profile or "",
                "company_address": result.company.company_address,
                "contact_person": result.company.contact_person,
            },
            "scoring": {
                "total_score": result.scoring.total_score,
                "threshold": result.scoring.threshold,
                "technical":    {"score": dims.technical,    "reasoning": ao.technical.reasoning},
                "requirements": {"score": dims.requirements, "reasoning": ao.requirements.reasoning},
                "role_fit":     {"score": dims.role_fit,     "reasoning": ao.role_fit.reasoning},
                "location":     {"score": dims.location,     "reasoning": ao.location.reasoning},
                "strategic":    {"score": dims.strategic,    "reasoning": ao.strategic.reasoning},
                "requirements_analysis": result.scoring.requirements_analysis.model_dump() if result.scoring.requirements_analysis else None,
            },
            "tailoring": {
                "items_removed": result.tailoring.items_removed,
                "items_shortened": result.tailoring.items_shortened,
                "cv_diff": result.tailoring.cv_diff,
                "tailored_cv": result.tailoring.tailored_cv,
            } if result.tailoring else None,
            "anschreiben_text": result.anschreiben_text,
            "gap_analysis": result.gap_analysis,
            "job_application_id": result.job_application_id,
            "anschreiben_truthfulness_warning": result.anschreiben_truthfulness_warning,
        }
        yield _sse({"type": "result", "data": payload})

    return StreamingResponse(
        generate_with_steps(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
