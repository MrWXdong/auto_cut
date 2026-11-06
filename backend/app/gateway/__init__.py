"""Model gateway: capability protocols, adapters and registry."""

from .asr import CloudASR
from .base import (
    Capability,
    ChatMessage,
    ChatModel,
    ChatResult,
    EndpointConfig,
    ModelRegistry,
    VideoModel,
)
from .catalog import MODEL_CATALOG
from .openai_compatible import OpenAICompatibleChat
from .seedance import SeedanceVideo

__all__ = [
    "MODEL_CATALOG",
    "Capability",
    "ChatMessage",
    "ChatModel",
    "ChatResult",
    "CloudASR",
    "EndpointConfig",
    "ModelRegistry",
    "OpenAICompatibleChat",
    "SeedanceVideo",
    "VideoModel",
]
