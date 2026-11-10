from __future__ import annotations

import pytest

from app.config import get_settings
from app.gateway.factory import build_chat_model, build_image_model
from app.gateway.image import ZhipuImage
from app.gateway.openai_compatible import OpenAICompatibleChat
from app.gateway.routing import cheapest_model_ref


@pytest.fixture
def zhipu_only(monkeypatch):
    monkeypatch.setenv("AUTOCUT_LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    monkeypatch.setenv("AUTOCUT_LLM_API_KEY", "test-zhipu-key")
    monkeypatch.setenv("AUTOCUT_LLM_MODEL", "glm-4.5-air")
    monkeypatch.setenv("AUTOCUT_IMAGE_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    monkeypatch.setenv("AUTOCUT_IMAGE_API_KEY", "")
    monkeypatch.setenv("AUTOCUT_IMAGE_MODEL", "cogview-4")
    for key in (
        "AUTOCUT_DEEPSEEK_API_KEY",
        "AUTOCUT_QWEN_API_KEY",
        "AUTOCUT_DOUBAO_API_KEY",
        "AUTOCUT_ZHIPU_API_KEY",
        "AUTOCUT_MOONSHOT_API_KEY",
    ):
        monkeypatch.setenv(key, "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_auto_chooses_cheapest_configured_models(zhipu_only) -> None:
    assert cheapest_model_ref("chat") == "zhipu:glm-4-flash"
    assert cheapest_model_ref("image.generate") == "zhipu:cogview-3-flash"

    chat = build_chat_model()
    assert isinstance(chat, OpenAICompatibleChat)
    assert chat.endpoint.model == "glm-4-flash"

    image = build_image_model()
    assert isinstance(image, ZhipuImage)
    assert image.model == "cogview-3-flash"


def test_explicit_model_still_overrides_auto(zhipu_only) -> None:
    chat = build_chat_model("zhipu:glm-4.5-air")
    assert isinstance(chat, OpenAICompatibleChat)
    assert chat.endpoint.model == "glm-4.5-air"
