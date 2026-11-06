"""Model gateway: capability protocols, adapters and registry."""

from .base import (
    Capability,
    ChatMessage,
    ChatModel,
    ChatResult,
    EndpointConfig,
    ModelRegistry,
    VideoModel,
)
from .asr import CloudASR
from .catalog import MODEL_CATALOG
from .openai_compatible import OpenAICompatibleChat
from .seedance import SeedanceVideo

__all__ = [
    "Capability",
    "CloudASR",
    "ChatMessage",
    "ChatModel",
    "ChatResult",
    "EndpointConfig",
    "MODEL_CATALOG",
    "ModelRegistry",
    "OpenAICompatibleChat",
    "SeedanceVideo",
    "VideoModel",
]
