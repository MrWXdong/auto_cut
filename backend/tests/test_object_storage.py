from __future__ import annotations

from pathlib import Path

from app.bootstrap import build_registry
from app.object_storage import S3Config, S3ObjectStorage
from app.service import JobService
from app.storage import JobStore


class FakeObjectStorage:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.deleted: list[str] = []

    async def put_file(self, path: Path, key: str) -> None:
        self.files[key] = path.read_bytes()

    async def delete_key(self, key: str) -> None:
        self.deleted.append(key)
        self.files.pop(key, None)

    async def delete_prefix(self, prefix: str) -> None:
        for key in list(self.files):
            if key.startswith(prefix):
                await self.delete_key(key)

    def presigned_url(self, key: str) -> str:
        return f"https://storage.example/{key}"


async def test_job_artifacts_are_uploaded_and_deleted(tmp_path) -> None:
    storage = FakeObjectStorage()
    service = JobService(
        JobStore(tmp_path / "jobs.db"),
        tmp_path / "work",
        build_registry(),
        object_storage=storage,
    )
    input_path = tmp_path / "input.mp4"
    input_path.write_bytes(b"input")
    job = service.create_job(workflow="quick_cut", input_path=input_path)
    work_dir = service.work_dir(job.id)
    (work_dir / "exports").mkdir(parents=True)
    (work_dir / "exports" / "clip.mp4").write_bytes(b"video")
    (work_dir / "asr").mkdir()
    (work_dir / "asr" / "transcript.json").write_text("{}", encoding="utf-8")

    records = await service.upload_artifacts(job.id, work_dir)
    assert len(records) == 2
    assert len(storage.files) == 2
    assert len(service.store.list_artifacts(job.id)) == 2
    assert not service.store.list_artifacts(job.id)[0]["object_key"].startswith("/")

    assert await service.delete_job(job.id) is True
    assert len(storage.deleted) == 2
    assert service.store.list_artifacts(job.id) == []


def test_s3_presigned_url_contains_signature() -> None:
    storage = S3ObjectStorage(
        S3Config(
            endpoint_url="https://s3.example.com",
            bucket="media",
            access_key="key",
            secret_key="secret",
            region="auto",
            prefix="autocut",
        )
    )
    url = storage.presigned_url("tenants/demo/jobs/j1/clip.mp4")
    assert "X-Amz-Signature=" in url
    assert "/media/autocut/tenants/demo/jobs/j1/clip.mp4" in url
