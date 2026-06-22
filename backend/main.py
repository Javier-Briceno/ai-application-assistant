"""
Entry point: FastAPI on port 8000.
NiceGUI has been replaced by a React frontend (frontend/).
"""
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api.profiles import router as profiles_router
from backend.api.analyze import router as analyze_router
from backend.api.applications import router as applications_router
from backend.api.chat import router as chat_router
from backend.config import settings
from backend.db import close_pool, get_pool, ping_db

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
    db_ok = await ping_db()
    if db_ok:
        return {"status": "ok", "db": "connected"}
    return JSONResponse(
        status_code=503,
        content={"status": "degraded", "db": "unreachable"},
    )


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
