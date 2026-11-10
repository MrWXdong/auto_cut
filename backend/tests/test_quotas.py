from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.deps import get_platform_store, get_studio_store
from app.api.main import app
from app.config import get_settings
from app.platform.store import PlatformStore
from app.studio.store import StudioStore


def test_project_limit_is_enforced(tmp_path) -> None:
    database = tmp_path / "platform.db"
    platform = PlatformStore(database)
    platform.seed(get_settings())
    studio = StudioStore(database, tmp_path / "work")
    app.dependency_overrides[get_platform_store] = lambda: platform
    app.dependency_overrides[get_studio_store] = lambda: studio
    try:
        with TestClient(app) as client:
            for index in range(3):
                response = client.post(
                    "/api/v1/projects",
                    json={"name": f"project-{index}"},
                )
                assert response.status_code == 201, response.text
            blocked = client.post(
                "/api/v1/projects",
                json={"name": "project-over-limit"},
            )
            assert blocked.status_code == 402
            assert "套餐上限" in blocked.json()["detail"]
    finally:
        app.dependency_overrides.clear()
