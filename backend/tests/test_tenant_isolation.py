from __future__ import annotations

from app.api.deps import get_studio_store
from app.auth.security import issue_token
from app.config import get_settings
from app.domain import Job
from app.platform.store import PlatformStore
from app.storage import JobStore
from app.studio.store import StudioStore
from app.studio.tenant_store import TenantStudioStore


def _token(tenant_id: str, email: str) -> str:
    return issue_token(
        {
            "scope": "tenant",
            "sub": email,
            "tenant_id": tenant_id,
            "role": "owner",
            "email": email,
            "name": email,
        },
        get_settings().auth_secret,
    )


def test_tenant_studio_proxy_filters_projects(tmp_path) -> None:
    store = StudioStore(tmp_path / "studio.db", tmp_path / "work")
    first = store.create_project("tenant-a", tenant_id="tenant-a")
    second = store.create_project("tenant-b", tenant_id="tenant-b")

    tenant_a = TenantStudioStore(store, "tenant-a")
    projects = tenant_a.list_projects()
    assert [item["id"] for item in projects] == [first["id"]]
    assert tenant_a.get_project(second["id"]) is None
    assert tenant_a.get_project(first["id"]) is not None
    assert tenant_a.usage("tenant-a")["projects"] == 1


def test_api_dependency_binds_token_tenant(tmp_path, monkeypatch) -> None:
    database = tmp_path / "platform.db"
    platform = PlatformStore(database)
    platform.seed(get_settings())
    for tenant_id, email in (("tenant-a", "a@example.com"), ("tenant-b", "b@example.com")):
        platform.create_tenant(
            tenant_id,
            "trial",
            owner_email=email,
            owner_password="secret",
            owner_name=email,
        )
    studio = StudioStore(database, tmp_path / "work")
    studio.create_project("tenant-a project", tenant_id="tenant-a")
    studio.create_project("tenant-b project", tenant_id="tenant-b")

    monkeypatch.setattr("app.api.deps._base_studio_store", lambda: studio)
    token_a = _token("tenant-a", "a@example.com")
    token_b = _token("tenant-b", "b@example.com")

    projects_a = get_studio_store(f"Bearer {token_a}").list_projects()
    projects_b = get_studio_store(f"Bearer {token_b}").list_projects()
    assert [item["tenant_id"] for item in projects_a] == ["tenant-a"]
    assert [item["tenant_id"] for item in projects_b] == ["tenant-b"]


def test_workflow_jobs_are_filtered_by_tenant(tmp_path) -> None:
    store = JobStore(tmp_path / "jobs.db")
    first = Job(
        id="job-a",
        tenant_id="tenant-a",
        workflow="quick_cut",
        input_path="a.mp4",
    )
    second = Job(
        id="job-b",
        tenant_id="tenant-b",
        workflow="quick_cut",
        input_path="b.mp4",
    )
    store.create(first)
    store.create(second)

    assert [job.id for job in store.list(tenant_id="tenant-a")] == ["job-a"]
    assert store.get("job-b", "tenant-a") is None
    claimed = store.claim_next("tenant-b")
    assert claimed is not None
    assert claimed.id == "job-b"
