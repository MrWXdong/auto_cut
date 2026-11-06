from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class Capability(str, Enum):
    CHAT = "chat"
    EMBEDDING = "embedding"
    RERANK = "rerank"
    ASR = "asr"
    TTS = "tts"
    IMAGE = "image.generate"
    VIDEO = "video.generate"


@dataclass
class ChatMessage:
    role: str
    content: str


@dataclass
class ChatResult:
    text: str
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)


@dataclass
class EndpointConfig:
    provider: str
    capability: Capability
    base_url: str
    model: str
    api_key: str = ""
    timeout_s: float = 60.0
    meta: dict[str, Any] = field(default_factory=dict)


class ChatModel(Protocol):
    async def chat(self, messages: list[ChatMessage], **options: Any) -> ChatResult: ...


class EmbeddingModel(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class RerankModel(Protocol):
    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 5,
    ) -> list[dict[str, Any]]: ...


class ASRModel(Protocol):
    async def transcribe(self, audio_path: str, language: str | None = None) -> dict[str, Any]: ...


class ImageModel(Protocol):
    async def generate(self, prompt: str, **options: Any) -> dict[str, Any]: ...


class VideoModel(Protocol):
    async def submit(self, prompt: str, **options: Any) -> str: ...

    async def poll(self, task_id: str) -> dict[str, Any]: ...


class ModelRegistry:
    """Capability-first registry. Adapters register under a capability and a name."""

    def __init__(self) -> None:
        self._models: dict[Capability, dict[str, Any]] = {}

    def register(self, capability: Capability, name: str, model: Any) -> None:
        if not name:
            raise ValueError("model name is required")
        bucket = self._models.setdefault(capability, {})
        if name in bucket:
            raise ValueError(f"duplicate model: {capability.value}/{name}")
        bucket[name] = model

    def get(self, capability: Capability, name: str | None = None) -> Any:
        bucket = self._models.get(capability) or {}
        if not bucket:
            raise KeyError(f"no model registered for capability: {capability.value}")
        if name is None:
            return next(iter(bucket.values()))
        if name not in bucket:
            raise KeyError(f"model not found: {capability.value}/{name}")
        return bucket[name]

    def names(self, capability: Capability) -> list[str]:
        return sorted(self._models.get(capability, {}))

    def capabilities(self) -> list[str]:
        return sorted(item.value for item in self._models)
