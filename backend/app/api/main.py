from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.deps import get_platform_store, get_trend_service
from app.api.routers import (
    admin,
    auth,
    billing,
    brand,
    calendar,
    chat,
    clips,
    compliance,
    jobs,
    knowledge,
    modules,
    pipelines,
    platform,
    projects,
    public,
    publishing,
    quality,
    scripts,
    settings,
    skills,
    styles,
    system,
    trends,
    workflows,
)
from app.config import get_settings
from app.studio.trends import trend_refresh_loop


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_platform_store()
    settings = get_settings()
    refresh_task = None
    if settings.trend_auto_refresh:
        refresh_task = asyncio.create_task(
            trend_refresh_loop(
                get_trend_service(),
                settings.trend_refresh_interval_seconds,
            )
        )
    try:
        yield
    finally:
        if refresh_task is not None:
            refresh_task.cancel()
            with suppress(asyncio.CancelledError):
                await refresh_task


app = FastAPI(
    title="云流影 API",
    version="0.1.0",
    docs_url=None,
    lifespan=lifespan,
)


@app.middleware("http")
async def disable_demo_web_cache(request: Request, call_next):
    response = await call_next(request)
    settings = get_settings()
    page_paths = {"/", "/platform", "/signup", "/docs", "/swagger"}
    disable_cache = settings.demo_mode or settings.environment.lower() in {"dev", "local"}
    if disable_cache and (
        request.url.path.startswith("/assets/") or request.url.path in page_paths
    ):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


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
    projects.router,
    public.router,
    scripts.router,
    modules.router,
    pipelines.router,
    platform.router,
    quality.router,
    admin.router,
    brand.router,
    styles.router,
    trends.router,
    calendar.router,
    compliance.router,
    clips.router,
    publishing.router,
):
    app.include_router(router)


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/platform", include_in_schema=False)
async def platform_page() -> FileResponse:
    return FileResponse(WEB_DIR / "platform.html")


@app.get("/signup", include_in_schema=False)
async def signup_page() -> FileResponse:
    return FileResponse(WEB_DIR / "signup.html")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> RedirectResponse:
    return RedirectResponse("/assets/logo-mark.png")


@app.get("/docs", include_in_schema=False)
async def api_docs() -> FileResponse:
    return FileResponse(WEB_DIR / "docs.html")


@app.get("/swagger", include_in_schema=False)
async def swagger_ui():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url or "/openapi.json",
        title=f"{app.title} - Swagger UI",
        swagger_js_url=(
            "https://cdn.bootcdn.net/ajax/libs/swagger-ui/4.15.5/"
            "swagger-ui-bundle.js"
        ),
        swagger_css_url=(
            "https://cdn.bootcdn.net/ajax/libs/swagger-ui/4.15.5/"
            "swagger-ui.css"
        ),
        swagger_favicon_url="/assets/logo-mark.png",
    )
