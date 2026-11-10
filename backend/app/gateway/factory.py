from __future__ import annotations

import os

from app.config import get_settings
from app.gateway.base import Capability, ChatModel, EndpointConfig
from app.gateway.catalog import MODEL_CATALOG
from app.gateway.image import DoubaoImage, ZhipuImage
from app.gateway.openai_compatible import OpenAICompatibleChat
from app.gateway.routing import cheapest_model_ref


def _doubao_image_fallbacks(model: str) -> list[str]:
    config = next(
        (item for item in MODEL_CATALOG if item["provider"] == "doubao"),
        None,
    )
    if config is None:
        return []
    return [
        str(item)
        for item in config.get("image_models", [])
        if str(item) and str(item) != model
    ]


def _doubao_api_key(settings: object) -> str:
    api_key = settings.provider_api_key("doubao") or os.getenv(
        "AUTOCUT_DOUBAO_API_KEY",
        "",
    )
    if not api_key and settings.llm_base_url.startswith(
        settings.doubao_image_base_url.rstrip("/")
    ):
        api_key = settings.llm_api_key
    return api_key


def _build_doubao_image(
    settings: object,
    model: str,
    *,
    allow_fallback: bool,
) -> DoubaoImage | None:
    api_key = _doubao_api_key(settings)
    if not api_key:
        return None
    return DoubaoImage(
        api_key=api_key,
        base_url=settings.doubao_image_base_url,
        model=model,
        fallback_models=_doubao_image_fallbacks(model) if allow_fallback else None,
    )


def build_chat_model(model_ref: str | None = None) -> ChatModel | None:
    """Return a cloud chat model when a key is configured, otherwise None."""
    settings = get_settings()
    model_ref = (model_ref or "").strip()
    if model_ref in {"auto", "auto:cheapest", "cheapest"}:
        model_ref = ""
    if not model_ref:
        model_ref = cheapest_model_ref("chat") or ""
    provider, separator, model = (model_ref or "").partition(":")
    if separator and provider:
        config = next(
            (item for item in MODEL_CATALOG if item["provider"] == provider),
            None,
        )
        if config is None:
            return None
        base_url = str(config.get("base_url") or settings.llm_base_url)
        api_key = settings.provider_api_key(provider) or os.getenv(
            f"AUTOCUT_{provider.upper()}_API_KEY",
            "",
        )
        if not api_key:
            current_base = settings.llm_base_url.rstrip("/")
            catalog_base = base_url.rstrip("/")
            if current_base.startswith(catalog_base) or catalog_base.startswith(current_base):
                api_key = settings.llm_api_key
        if not api_key:
            return None
        return OpenAICompatibleChat(
            EndpointConfig(
                provider=provider,
                capability=Capability.CHAT,
                base_url=base_url,
                model=model or settings.llm_model,
                api_key=api_key,
                meta={
                    "thinking": (
                        "enabled" if settings.doubao_thinking else "disabled"
                    )
                }
                if provider == "doubao"
                else {},
            )
        )
    if not settings.llm_api_key:
        return None
    return OpenAICompatibleChat(
        EndpointConfig(
            provider="openai-compatible",
            capability=Capability.CHAT,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
        )
    )


def build_image_model(model_ref: str | None = None) -> ZhipuImage | DoubaoImage | None:
    settings = get_settings()
    model_ref = (model_ref or "").strip()
    if model_ref in {"auto", "auto:cheapest", "cheapest"}:
        model_ref = ""
    if not model_ref:
        auto_ref = cheapest_model_ref("image.generate")
        if auto_ref:
            provider, _, auto_model = auto_ref.partition(":")
            if provider == "doubao":
                return _build_doubao_image(
                    settings,
                    auto_model,
                    allow_fallback=True,
                )
            return build_image_model(auto_ref)
    provider, separator, model = (model_ref or "").partition(":")
    if separator and provider == "doubao":
        return _build_doubao_image(
            settings,
            model=model or settings.doubao_image_model,
            allow_fallback=not bool(model),
        )
    if separator and provider != "zhipu":
        return None

    base_url = settings.image_base_url or settings.llm_base_url
    api_key = settings.image_api_key
    if "bigmodel.cn" not in base_url:
        zhipu_config = next(
            (item for item in MODEL_CATALOG if item["provider"] == "zhipu"),
            None,
        )
        base_url = str(zhipu_config.get("base_url") or base_url) if zhipu_config else base_url
    if not api_key:
        api_key = settings.provider_api_key("zhipu") or os.getenv(
            "AUTOCUT_ZHIPU_API_KEY",
            "",
        )
    api_key = api_key or settings.llm_api_key
    if api_key and "bigmodel.cn" in base_url:
        return ZhipuImage(
            api_key=api_key,
            base_url=base_url,
            model=model or settings.image_model,
        )

    if not model_ref:
        return _build_doubao_image(
            settings,
            settings.doubao_image_model,
            allow_fallback=True,
        )
    return None
