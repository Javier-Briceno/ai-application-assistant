"""
Entry point: FastAPI on port 8000.
NiceGUI has been replaced by a React frontend (frontend/).
"""
import json
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api.profiles import router as profiles_router
from backend.api.analyze import router as analyze_router
from backend.api.applications import router as applications_router
from backend.api.chat import router as chat_router
from backend.config import settings
from backend.db import close_pool, get_pool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Startup — initialising DB pool...")
    await get_pool()
    log.info("DB pool ready.")
    yield
    log.info("Shutdown — closing DB pool...")
    await close_pool()


app = FastAPI(title="CV Assistant API", lifespan=lifespan)

# Allow Vite dev server in development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API routes ────────────────────────────────────────────────────────────────
app.include_router(profiles_router)
app.include_router(analyze_router)
app.include_router(applications_router)
app.include_router(chat_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# ── Design interview ───────────────────────────────────────────────────────────
_di_html = os.path.join(os.path.dirname(__file__), "design_interview.html")
_di2_html = os.path.join(os.path.dirname(__file__), "design_interview_2.html")
_di3_html = os.path.join(os.path.dirname(__file__), "design_interview_3.html")
_di4_html = os.path.join(os.path.dirname(__file__), "design_interview_4.html")
_di5_html = os.path.join(os.path.dirname(__file__), "design_interview_5.html")
_di6_html = os.path.join(os.path.dirname(__file__), "design_interview_6.html")
_di7_html = os.path.join(os.path.dirname(__file__), "design_interview_7.html")
_di8_html = os.path.join(os.path.dirname(__file__), "design_interview_8.html")
_di9_html = os.path.join(os.path.dirname(__file__), "design_interview_9.html")
_di10_html = os.path.join(os.path.dirname(__file__), "design_interview_10.html")
_di11_html = os.path.join(os.path.dirname(__file__), "design_interview_11.html")

@app.get("/design-interview", include_in_schema=False)
async def design_interview():
    return FileResponse(_di_html, media_type="text/html")

@app.get("/design-interview-2", include_in_schema=False)
async def design_interview_2():
    return FileResponse(_di2_html, media_type="text/html")

@app.get("/design-interview-3", include_in_schema=False)
async def design_interview_3():
    return FileResponse(_di3_html, media_type="text/html")

@app.get("/design-interview-4", include_in_schema=False)
async def design_interview_4():
    return FileResponse(_di4_html, media_type="text/html")

@app.get("/design-interview-5", include_in_schema=False)
async def design_interview_5():
    return FileResponse(_di5_html, media_type="text/html")

@app.get("/design-interview-6", include_in_schema=False)
async def design_interview_6():
    return FileResponse(_di6_html, media_type="text/html")

@app.get("/design-interview-7", include_in_schema=False)
async def design_interview_7():
    return FileResponse(_di7_html, media_type="text/html")

@app.get("/design-interview-8", include_in_schema=False)
async def design_interview_8():
    return FileResponse(_di8_html, media_type="text/html")

@app.get("/design-interview-9", include_in_schema=False)
async def design_interview_9():
    return FileResponse(_di9_html, media_type="text/html")

@app.get("/design-interview-10", include_in_schema=False)
async def design_interview_10():
    return FileResponse(_di10_html, media_type="text/html")

@app.get("/design-interview-11", include_in_schema=False)
async def design_interview_11():
    return FileResponse(_di11_html, media_type="text/html")

@app.post("/api/design-answers")
async def save_design_answers(request: Request):
    body = await request.json()
    out = os.path.join(os.path.dirname(__file__), "..", "design_answers.json")
    with open(out, "w") as f:
        json.dump(body, f, indent=2)
    log.info("Design answers saved: %s", body)
    return JSONResponse({"saved": True})

@app.post("/api/design-answers-2")
async def save_design_answers_2(request: Request):
    body = await request.json()
    out = os.path.join(os.path.dirname(__file__), "..", "design_answers_2.json")
    with open(out, "w") as f:
        json.dump(body, f, indent=2)
    log.info("Design answers round 2 saved: %s", body)
    return JSONResponse({"saved": True})

@app.post("/api/design-answers-3")
async def save_design_answers_3(request: Request):
    body = await request.json()
    out = os.path.join(os.path.dirname(__file__), "..", "design_answers_3.json")
    with open(out, "w") as f:
        json.dump(body, f, indent=2)
    log.info("Design answers round 3 saved: %s", body)
    return JSONResponse({"saved": True})

@app.post("/api/design-answers-4")
async def save_design_answers_4(request: Request):
    body = await request.json()
    out = os.path.join(os.path.dirname(__file__), "..", "design_answers_4.json")
    with open(out, "w") as f:
        json.dump(body, f, indent=2)
    log.info("Design answers round 4 saved: %s", body)
    return JSONResponse({"saved": True})

@app.post("/api/design-answers-5")
async def save_design_answers_5(request: Request):
    body = await request.json()
    out = os.path.join(os.path.dirname(__file__), "..", "design_answers_5.json")
    with open(out, "w") as f:
        json.dump(body, f, indent=2)
    log.info("Design answers round 5 saved: %s", body)
    return JSONResponse({"saved": True})

@app.post("/api/design-answers-6")
async def save_design_answers_6(request: Request):
    body = await request.json()
    out = os.path.join(os.path.dirname(__file__), "..", "design_answers_6.json")
    with open(out, "w") as f:
        json.dump(body, f, indent=2)
    log.info("Design answers round 6 saved: %s", body)
    return JSONResponse({"saved": True})

@app.post("/api/design-answers-7")
async def save_design_answers_7(request: Request):
    body = await request.json()
    out = os.path.join(os.path.dirname(__file__), "..", "design_answers_7.json")
    with open(out, "w") as f:
        json.dump(body, f, indent=2)
    log.info("Design answers round 7 saved: %s", body)
    return JSONResponse({"saved": True})

@app.post("/api/design-answers-8")
async def save_design_answers_8(request: Request):
    body = await request.json()
    out = os.path.join(os.path.dirname(__file__), "..", "design_answers_8.json")
    with open(out, "w") as f:
        json.dump(body, f, indent=2)
    log.info("Design answers round 8 saved: %s", body)
    return JSONResponse({"saved": True})

@app.post("/api/design-answers-9")
async def save_design_answers_9(request: Request):
    body = await request.json()
    out = os.path.join(os.path.dirname(__file__), "..", "design_answers_9.json")
    with open(out, "w") as f:
        json.dump(body, f, indent=2)
    log.info("Design answers round 9 saved: %s", body)
    return JSONResponse({"saved": True})

@app.post("/api/design-answers-10")
async def save_design_answers_10(request: Request):
    body = await request.json()
    out = os.path.join(os.path.dirname(__file__), "..", "design_answers_10.json")
    with open(out, "w") as f:
        json.dump(body, f, indent=2)
    log.info("Design answers round 10 saved: %s", body)
    return JSONResponse({"saved": True})

@app.post("/api/design-answers-11")
async def save_design_answers_11(request: Request):
    body = await request.json()
    out = os.path.join(os.path.dirname(__file__), "..", "design_answers_11.json")
    with open(out, "w") as f:
        json.dump(body, f, indent=2)
    log.info("Design answers round 11 saved: %s", body)
    return JSONResponse({"saved": True})


# ── Serve built React frontend ────────────────────────────────────────────────
_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_dist):
    # Serve compiled assets (JS, CSS, images) — must come before the catch-all
    app.mount("/assets", StaticFiles(directory=os.path.join(_dist, "assets")), name="assets")

    # SPA fallback: every non-asset, non-API path returns index.html
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        return FileResponse(os.path.join(_dist, "index.html"))


# ── Run with uvicorn when invoked as a module ─────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
    )
