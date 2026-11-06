from __future__ import annotations

from typing import Any


class CloudASR:
    """Cloud speech-to-text adapter.

    Expected output shape matches the local transcriber:
    ``{"language": str, "duration": float, "segments": [...]}``.

    Wire Qwen ASR / Doubao ASR / SenseNova here. The host machine only has an
    integrated GPU, so local inference is a fallback, not the default.
    """

    def __init__(
        self,
        *,
        base_url: str = "",
        api_key: str = "",
        model: str = "",
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model

    async def transcribe(
        self,
        audio_path: str,
        language: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError(
            "Cloud ASR adapter is a shell. Wire Qwen/Doubao/SenseNova transcription next."
        )
