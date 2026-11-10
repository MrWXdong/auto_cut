from __future__ import annotations

import json

import pytest

from app.config import get_settings
from app.gateway.factory import build_chat_model, build_image_model
from app.gateway.image import DoubaoImage, DoubaoImageError, _doubao_message
from app.gateway.openai_compatible import OpenAICompatibleChat, _provider_error_message
from app.studio.executors import (
    _image_suffix,
    execute_module,
    execute_module_job,
    execute_pipeline,
)
from app.studio.store import StudioStore


@pytest.fixture
def studio(tmp_path) -> StudioStore:
    return StudioStore(tmp_path / "studio.db", tmp_path / "work")


@pytest.fixture
def project(studio: StudioStore) -> dict:
    return studio.create_project("测试项目")


@pytest.mark.asyncio
async def test_copywriting_creates_script(studio: StudioStore, project: dict) -> None:
    outcome = await execute_module(
        studio,
        "copywriting",
        "script",
        "面膜",
        {},
        project["id"],
    )
    assert outcome["status"] == "succeeded"
    assert len(studio.list_scripts(project["id"])) == 1


@pytest.mark.asyncio
async def test_image_creates_svg_asset(studio: StudioStore, project: dict) -> None:
    outcome = await execute_module(
        studio,
        "image",
        "cover",
        "墨绿色护肤品",
        {},
        project["id"],
    )
    assert outcome["status"] == "needs_config"
    asset = studio.get_asset(outcome["result"]["asset_id"])
    assert asset is not None
    assert asset["kind"] == "image"
    path = studio.work_root / asset["storage_key"]
    assert path.is_file()
    assert path.suffix == ".svg"


@pytest.mark.asyncio
async def test_image_provider_failure_is_reported_as_failed(
    studio: StudioStore,
    project: dict,
    monkeypatch,
) -> None:
    class FailingImageModel:
        model = "fake-image"

        async def generate(self, prompt: str, size: str = "1024x1024") -> dict:
            raise RuntimeError("provider offline")

    monkeypatch.setattr(
        "app.studio.executors.build_image_model",
        lambda _model_ref=None: FailingImageModel(),
    )
    outcome = await execute_module(
        studio,
        "image",
        "cover",
        "失败测试",
        {},
        project["id"],
    )
    assert outcome["status"] == "failed"
    assert "provider offline" in outcome["error"]


def test_doubao_image_model_is_built_from_provider_key(monkeypatch) -> None:
    monkeypatch.setenv("AUTOCUT_DOUBAO_API_KEY", "test-key")
    model = build_image_model("doubao:doubao-seedream-4-0-250828")
    assert isinstance(model, DoubaoImage)
    assert model.model == "doubao-seedream-4-0-250828"


def test_doubao_chat_model_uses_ark_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("AUTOCUT_DOUBAO_API_KEY", "test-key")
    get_settings.cache_clear()
    try:
        model = build_chat_model("doubao:doubao-seed-2-1-pro-260915")
    finally:
        get_settings.cache_clear()
    assert isinstance(model, OpenAICompatibleChat)
    assert model.endpoint.base_url == "https://ark.cn-beijing.volces.com/api/v3"
    assert model.endpoint.model == "doubao-seed-2-1-pro-260915"
    assert model.endpoint.meta["thinking"] == "disabled"


def test_doubao_default_image_model_has_fallbacks(monkeypatch) -> None:
    monkeypatch.setenv("AUTOCUT_DOUBAO_API_KEY", "test-key")
    monkeypatch.setenv(
        "AUTOCUT_DOUBAO_IMAGE_MODEL",
        "doubao-seedream-5-0-flash-260915",
    )
    get_settings.cache_clear()
    try:
        model = build_image_model()
    finally:
        get_settings.cache_clear()
    assert isinstance(model, DoubaoImage)
    assert model.model == "doubao-seedream-5-0-flash-260915"
    assert "doubao-seedream-5-0-pro-260628" in model.fallback_models


@pytest.mark.asyncio
async def test_doubao_image_falls_back_when_model_is_not_open(monkeypatch) -> None:
    model = DoubaoImage(
        api_key="test-key",
        base_url="https://example.invalid/api/v3",
        model="doubao-seedream-not-open",
        fallback_models=["doubao-seedream-working"],
    )
    calls: list[str] = []

    async def fake_generate_once(**kwargs):
        calls.append(kwargs["model"])
        if kwargs["model"] == "doubao-seedream-not-open":
            raise DoubaoImageError(
                "model not open",
                provider_code="ModelNotOpen",
            )
        return {
            "url": "https://example.invalid/image.png",
            "id": "image-1",
            "model": kwargs["model"],
            "watermark": False,
        }

    monkeypatch.setattr(model, "_generate_once", fake_generate_once)
    result = await model.generate("cover")
    assert calls == ["doubao-seedream-not-open", "doubao-seedream-working"]
    assert result["model"] == "doubao-seedream-working"
    assert result["fallback_used"] is True
    assert model.model == "doubao-seedream-working"


def test_doubao_model_not_open_message_is_actionable() -> None:
    message = _doubao_message("ModelNotOpen", "", "doubao-seedream-x", 404)
    assert "尚未开通" in message
    assert "火山方舟控制台" in message


def test_doubao_chat_model_not_open_message_is_actionable() -> None:
    message = _provider_error_message(
        "doubao",
        "doubao-seed-2-1-pro-260915",
        404,
        "ModelNotOpen",
        "",
    )
    assert "尚未开通" in message
    assert "推理接入点" in message


@pytest.mark.asyncio
async def test_project_style_overrides_default(studio: StudioStore) -> None:
    style = studio.create_style(
        {
            "name": "项目专属风格",
            "palette": ["#112233", "#445566"],
        }
    )
    project = studio.create_project("风格项目", style_id=style["id"])
    outcome = await execute_module(
        studio,
        "image",
        "cover",
        "风格测试",
        {},
        project["id"],
    )
    asset = studio.get_asset(outcome["result"]["asset_id"])
    assert asset is not None
    svg = (studio.work_root / asset["storage_key"]).read_text(encoding="utf-8")
    assert "#112233" in svg


def test_project_custom_style_takes_priority(studio: StudioStore) -> None:
    project = studio.create_project(
        "自定义风格项目",
        custom_style="黑白纪录片质感，缓慢推镜",
    )
    style = studio.effective_style(project["id"])
    assert style is not None
    assert style["custom"] is True
    assert style["name"] == "自定义风格"
    assert style["prompt"] == "黑白纪录片质感，缓慢推镜"


def test_image_suffix_uses_magic_bytes() -> None:
    assert _image_suffix(b"\xff\xd8\xff\xe0", "image/png") == ".jpg"
    assert _image_suffix(b"\x89PNG\r\n\x1a\n", "image/jpeg") == ".png"
    assert _image_suffix(b"RIFF0000WEBP", "image/png") == ".webp"


@pytest.mark.asyncio
async def test_storyboard_creates_json(studio: StudioStore, project: dict) -> None:
    outcome = await execute_module(
        studio,
        "storyboard",
        "auto",
        "第一镜。第二镜。第三镜。",
        {},
        project["id"],
    )
    assert outcome["status"] == "succeeded"
    asset = studio.get_asset(outcome["result"]["asset_id"])
    assert asset is not None
    payload = json.loads(
        (studio.work_root / asset["storage_key"]).read_text(encoding="utf-8")
    )
    assert len(payload["scenes"]) == 3


@pytest.mark.asyncio
async def test_tts_creates_wav(studio: StudioStore, project: dict) -> None:
    outcome = await execute_module(
        studio,
        "audio",
        "tts",
        "配音",
        {},
        project["id"],
    )
    assert outcome["status"] == "succeeded"
    asset = studio.get_asset(outcome["result"]["asset_id"])
    assert asset is not None
    assert asset["kind"] == "audio"
    assert (studio.work_root / asset["storage_key"]).is_file()


@pytest.mark.asyncio
async def test_lora_generates_config_and_warns(
    studio: StudioStore,
    project: dict,
) -> None:
    outcome = await execute_module(
        studio,
        "lora",
        "train",
        "风格",
        {},
        project["id"],
    )
    assert outcome["status"] == "needs_config"
    assert outcome["result"]["asset_id"]


@pytest.mark.asyncio
async def test_pipeline_runs_local_steps(
    studio: StudioStore,
    project: dict,
) -> None:
    pipeline = studio.create_pipeline(
        "测试流水线",
        [
            {"module": "copywriting", "mode": "script", "prompt": "面膜"},
            {"module": "image", "mode": "cover", "prompt": "面膜封面"},
        ],
        project_id=project["id"],
    )
    await execute_pipeline(studio, pipeline)
    saved = studio.get_pipeline(pipeline["id"])
    assert saved is not None
    assert saved["status"] == "needs_config"
    assert saved["steps"][0]["status"] == "succeeded"
    assert saved["steps"][1]["status"] == "needs_config"


@pytest.mark.asyncio
async def test_module_job_status_is_updated(
    studio: StudioStore,
    project: dict,
) -> None:
    job = studio.create_job("image", "cover", "封面", {}, project["id"])
    claimed = studio.claim_next_job()
    assert claimed is not None
    await execute_module_job(studio, claimed)

    saved = studio.get_job(job["id"])
    assert saved is not None
    assert saved["status"] == "needs_config"
    assert saved["result"]["asset_id"]


@pytest.mark.asyncio
async def test_copywriting_passes_selected_model(
    studio: StudioStore,
    project: dict,
    monkeypatch,
) -> None:
    captured: dict[str, str | None] = {}

    def fake_build_chat_model(model_ref: str | None = None):
        captured["model_ref"] = model_ref
        return None

    monkeypatch.setattr(
        "app.studio.executors.build_chat_model",
        fake_build_chat_model,
    )
    outcome = await execute_module(
        studio,
        "copywriting",
        "script",
        "产品",
        {"model": "doubao:doubao-seed-2-1-pro-260915"},
        project["id"],
    )
    assert outcome["status"] == "succeeded"
    assert captured["model_ref"] == "doubao:doubao-seed-2-1-pro-260915"
