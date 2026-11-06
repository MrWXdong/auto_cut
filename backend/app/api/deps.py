from __future__ import annotations

from functools import lru_cache

from app.bootstrap import build_registry
from app.config import get_settings
from app.service import JobService
from app.storage import JobStore


@lru_cache
def get_service() -> JobService:
    settings = get_settings()
    store = JobStore(settings.database_path)
    return JobService(
        store,
        settings.work_root,
        build_registry(),
        settings.max_concurrency,
    )
