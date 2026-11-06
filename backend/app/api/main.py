from __future__ import annotations

from fastapi import FastAPI

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
