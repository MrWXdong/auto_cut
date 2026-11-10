from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_credit_service, get_rag_store, get_studio_store
from app.api.main import app
from app.billing.credits import CreditService
from app.rag.store import RagStore
from app.studio.modules import MODULES
from app.studio.store import StudioStore


@pytest.fixture
def client(tmp_path):
    studio = StudioStore(tmp_path / "studio.db", tmp_path / "work")
    rag = RagStore(tmp_path / "rag.db")
    credits = CreditService(tmp_path / "credits.db")
    credits.grant("demo", 100_000, "test grant")
    app.dependency_overrides[get_studio_store] = lambda: studio
    app.dependency_overrides[get_rag_store] = lambda: rag
    app.dependency_overrides[get_credit_service] = lambda: credits
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def create_project(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/projects",
        json={"name": "双十一 campaign", "aspect_ratio": "9:16"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_project_crud(client: TestClient) -> None:
    project = create_project(client)
    assert project["name"] == "双十一 campaign"
    assert project["aspect_ratio"] == "9:16"

    listed = client.get("/api/v1/projects")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [project["id"]]

    updated = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"status": "archived"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "archived"


def test_project_binds_style(client: TestClient) -> None:
    style = client.post(
        "/api/v1/styles",
        json={
            "name": "电商蓝",
            "prompt": "冷色调，干净背景",
            "palette": ["#123456", "#abcdef"],
        },
    )
    assert style.status_code == 201, style.text
    style_id = style.json()["id"]

    project = client.post(
        "/api/v1/projects",
        json={"name": "品牌项目", "aspect_ratio": "9:16", "style_id": style_id},
    )
    assert project.status_code == 201, project.text
    assert project.json()["style_id"] == style_id
    assert project.json()["style_name"] == "电商蓝"

    listed = client.get("/api/v1/projects").json()["items"]
    assert listed[0]["style_id"] == style_id
    assert listed[0]["style_name"] == "电商蓝"

    invalid = client.post(
        "/api/v1/projects",
        json={"name": "错误项目", "style_id": "missing"},
    )
    assert invalid.status_code == 422


def test_project_accepts_custom_style(client: TestClient) -> None:
    project = client.post(
        "/api/v1/projects",
        json={
            "name": "自定义风格项目",
            "custom_style": "黑白胶片质感，克制运镜",
        },
    )
    assert project.status_code == 201, project.text
    payload = project.json()
    assert payload["style_id"] == ""
    assert payload["custom_style"] == "黑白胶片质感，克制运镜"

    listed = client.get("/api/v1/projects").json()["items"]
    assert listed[0]["custom_style"] == "黑白胶片质感，克制运镜"

    updated = client.patch(
        f"/api/v1/projects/{payload['id']}",
        json={"custom_style": "高反差黑白，快速卡点"},
    )
    assert updated.status_code == 200
    assert updated.json()["custom_style"] == "高反差黑白，快速卡点"


def test_asset_upload_and_download(client: TestClient, tmp_path) -> None:
    project = create_project(client)
    response = client.post(
        f"/api/v1/projects/{project['id']}/assets",
        files={"file": ("cover.png", b"fake-png-bytes", "image/png")},
    )
    assert response.status_code == 201, response.text
    asset = response.json()
    assert asset["kind"] == "image"
    assert asset["size_bytes"] == len(b"fake-png-bytes")

    downloaded = client.get(
        f"/api/v1/projects/{project['id']}/assets/{asset['id']}/file"
    )
    assert downloaded.status_code == 200
    assert downloaded.content == b"fake-png-bytes"


def test_delete_project_removes_asset_files(client: TestClient) -> None:
    store = app.dependency_overrides[get_studio_store]()
    project = create_project(client)
    storage_key = f"projects/{project['id']}/assets/cover.txt"
    path = store.work_root / storage_key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("asset", encoding="utf-8")
    store.add_asset(project["id"], "cover.txt", storage_key, 5)

    response = client.delete(f"/api/v1/projects/{project['id']}")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "deleted"
    assert not path.exists()
    assert client.get(f"/api/v1/projects/{project['id']}").status_code == 404


def test_script_create_and_generate(client: TestClient) -> None:
    project = create_project(client)
    created = client.post(
        "/api/v1/scripts",
        json={
            "title": "口播稿",
            "body": "这是第一版脚本。",
            "project_id": project["id"],
            "tags": ["抖音"],
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["tags"] == ["抖音"]

    generated = client.post(
        "/api/v1/scripts/generate",
        json={
            "product": "面膜",
            "platform": "小红书",
            "style": "测评",
            "project_id": project["id"],
        },
    )
    assert generated.status_code == 201, generated.text
    payload = generated.json()
    assert payload["shell"] is True
    assert payload["script"]["project_id"] == project["id"]


def test_script_topic_suggestions_without_model(client: TestClient) -> None:
    response = client.post(
        "/api/v1/scripts/topics",
        json={
            "product": "燕云十六声",
            "platform": "抖音",
            "style": "热血燃向",
            "brief": "面向新玩家，讲具体玩法",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["shell"] is True
    assert len(payload["items"]) >= 6
    assert any("燕云十六声" in item["title"] for item in payload["items"])


def test_script_generates_structured_storyboard(client: TestClient) -> None:
    project = create_project(client)
    script = client.post(
        "/api/v1/scripts",
        json={
            "title": "口播稿",
            "body": "第一镜开场。第二镜介绍产品。第三镜给出行动指令。",
            "project_id": project["id"],
        },
    ).json()

    response = client.post(f"/api/v1/scripts/{script['id']}/storyboard")
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["script_id"] == script["id"]
    assert payload["asset_id"]
    assert len(payload["scenes"]) >= 3
    assert payload["scenes"][0]["visual_prompt"]

    assets = client.get(f"/api/v1/projects/{project['id']}/assets").json()["items"]
    assert any(item["filename"].startswith("storyboard-") for item in assets)


def test_module_job_lifecycle(client: TestClient) -> None:
    project = create_project(client)
    created = client.post(
        "/api/v1/modules/image/jobs",
        json={
            "mode": "text2img",
            "prompt": "墨绿色护肤品海报",
            "project_id": project["id"],
            "params": {"size": "1024x1536"},
        },
    )
    assert created.status_code == 201, created.text
    job = created.json()
    assert job["status"] == "queued"
    assert job["module"] == "image"

    listed = client.get("/api/v1/modules/image/jobs")
    assert [item["id"] for item in listed.json()["items"]] == [job["id"]]

    assert client.post(f"/api/v1/module-jobs/{job['id']}/cancel").status_code == 200
    assert client.post(f"/api/v1/module-jobs/{job['id']}/cancel").status_code == 409


@pytest.mark.parametrize(
    ("module_id", "mode"),
    [(str(module["id"]), str(module["modes"][0])) for module in MODULES],
)
def test_delete_queued_job_for_every_module(
    client: TestClient,
    module_id: str,
    mode: str,
) -> None:
    credits = app.dependency_overrides[get_credit_service]()
    balance_before = credits.balance("demo")
    project = create_project(client)

    created = client.post(
        f"/api/v1/modules/{module_id}/jobs",
        json={
            "mode": mode,
            "prompt": f"delete test for {module_id}",
            "project_id": project["id"],
        },
    )
    assert created.status_code == 201, created.text
    job = created.json()
    assert credits.balance("demo") < balance_before

    deleted = client.delete(f"/api/v1/module-jobs/{job['id']}")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["status"] == "deleted"
    assert credits.balance("demo") == balance_before

    listed = client.get(f"/api/v1/modules/{module_id}/jobs")
    assert job["id"] not in {item["id"] for item in listed.json()["items"]}
    assert client.get(f"/api/v1/module-jobs/{job['id']}").status_code == 404


def test_delete_running_job_is_rejected(client: TestClient) -> None:
    project = create_project(client)
    job = client.post(
        "/api/v1/modules/render/jobs",
        json={
            "mode": "render",
            "prompt": "running render",
            "project_id": project["id"],
        },
    ).json()
    store = app.dependency_overrides[get_studio_store]()
    store.update_job(job["id"], "running")

    response = client.delete(f"/api/v1/module-jobs/{job['id']}")
    assert response.status_code == 409
    assert client.get(f"/api/v1/module-jobs/{job['id']}").status_code == 200


def test_delete_finished_job_keeps_charged_credits(client: TestClient) -> None:
    credits = app.dependency_overrides[get_credit_service]()
    project = create_project(client)
    job = client.post(
        "/api/v1/modules/copywriting/jobs",
        json={
            "mode": "script",
            "prompt": "finished script",
            "project_id": project["id"],
        },
    ).json()
    store = app.dependency_overrides[get_studio_store]()
    store.update_job(job["id"], "succeeded", result={"note": "done"})
    balance_before_delete = credits.balance("demo")

    deleted = client.delete(f"/api/v1/module-jobs/{job['id']}")
    assert deleted.status_code == 200
    assert credits.balance("demo") == balance_before_delete
    assert client.get(f"/api/v1/module-jobs/{job['id']}").status_code == 404


def test_delete_missing_job_returns_404(client: TestClient) -> None:
    assert client.delete("/api/v1/module-jobs/not-found").status_code == 404


def test_admin_overview_and_quotas(client: TestClient) -> None:
    create_project(client)
    overview = client.get("/api/v1/admin/overview")
    assert overview.status_code == 200
    assert overview.json()["usage"]["projects"] == 1

    quotas = client.get("/api/v1/quotas")
    assert quotas.status_code == 200
    kinds = {item["kind"] for item in quotas.json()["items"]}
    assert {"projects", "assets", "scripts", "jobs"} <= kinds
