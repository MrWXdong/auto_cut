from __future__ import annotations

from app.config import get_settings
from app.gateway.base import Capability, ChatModel, EndpointConfig
from app.gateway.openai_compatible import OpenAICompatibleChat


def build_chat_model() -> ChatModel | None:
    """Return a cloud chat model when a key is configured, otherwise None."""
    settings = get_settings()
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
