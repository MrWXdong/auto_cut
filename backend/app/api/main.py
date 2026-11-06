from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routers import (
    auth,
    billing,
    chat,
    jobs,
    knowledge,
    settings,
    skills,
    system,
    workflows,
)

app = FastAPI(title="AutoCut API", version="0.1.0")

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")

for router in (
    system.router,
    workflows.router,
    jobs.router,
    auth.router,
    chat.router,
    skills.router,
    knowledge.router,
    billing.router,
    settings.router,
):
    app.include_router(router)


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")
