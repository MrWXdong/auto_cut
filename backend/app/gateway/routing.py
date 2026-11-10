from __future__ import annotations

import os
from typing import Any

from app.config import get_settings
from app.gateway.catalog import MODEL_CATALOG

MODEL_LIST_KEYS: dict[str, str] = {
    "chat": "chat_models",
    "image.generate": "image_models",
    "asr": "asr_models",
    "tts": "tts_models",
    "video.generate": "video_models",
    "embedding": "embedding_models",
}

MODEL_COST_OVERRIDES: dict[str, int] = {
    "zhipu:glm-4-flash": 0,
    "zhipu:cogview-3-flash": 5,
}


def _same_base(left: str, right: str) -> bool:
    left = left.rstrip("/")
    right = right.rstrip("/")
    return bool(left and right and (left.startswith(right) or right.startswith(left)))


def _provider_config(provider: str) -> dict[str, Any] | None:
    return next(
        (item for item in MODEL_CATALOG if item.get("provider") == provider),
        None,
    )


def provider_configured(provider: str, capability: str) -> bool:
    settings = get_settings()
    if settings.provider_api_key(provider) or os.getenv(
        f"AUTOCUT_{provider.upper()}_API_KEY",
        "",
    ):
        return True

    config = _provider_config(provider)
    base_url = str(config.get("base_url") or "") if config else ""
    if not base_url:
        return False

    if capability == "image.generate":
        current_base = settings.image_base_url or settings.llm_base_url
        current_key = settings.image_api_key or settings.llm_api_key
    else:
        current_base = settings.llm_base_url
        current_key = settings.llm_api_key
    return bool(current_key and _same_base(current_base, base_url))


def _is_free_model(provider: str, model: str) -> bool:
    config = _provider_config(provider)
    free_models = config.get("free_models", []) if config else []
    return model in {str(item) for item in free_models}


def model_cost_rank(ref: str) -> int:
    """Relative routing cost. Lower is cheaper; this is not a billing rate."""
    if ref in MODEL_COST_OVERRIDES:
        return MODEL_COST_OVERRIDES[ref]
    provider, _, model = ref.partition(":")
    if _is_free_model(provider, model):
        return 0
    name = model.lower()
    if "flash" in name:
        return 10
    if "mini" in name or "lite" in name:
        return 20
    if "air" in name:
        return 30
    if "turbo" in name:
        return 40
    if "chat" in name or "plus" in name:
        return 50
    if "pro" in name or "max" in name or "reasoner" in name:
        return 60
    return 70


def available_model_refs(capability: str) -> list[str]:
    list_key = MODEL_LIST_KEYS.get(capability)
    if not list_key:
        return []
    refs: list[str] = []
    for item in MODEL_CATALOG:
        provider = str(item.get("provider") or "")
        if capability not in (item.get("wired_capabilities") or []):
            continue
        if not provider_configured(provider, capability):
            continue
        for model in item.get(list_key, []) or []:
            ref = f"{provider}:{model}"
            if ref not in refs:
                refs.append(ref)
    return refs


def cheapest_model_ref(capability: str) -> str | None:
    refs = available_model_refs(capability)
    if not refs:
        return None
    return min(refs, key=model_cost_rank)


def auto_model_refs() -> dict[str, str]:
    refs: dict[str, str] = {}
    for capability in MODEL_LIST_KEYS:
        ref = cheapest_model_ref(capability)
        if ref:
            refs[capability] = ref
    return refs
