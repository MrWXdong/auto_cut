from __future__ import annotations

import asyncio
import re
import tempfile
import wave
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings
from app.core.commands import run_command


class CloudASR:
    """Cloud speech-to-text adapter with long-audio chunking."""

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

    @staticmethod
    def _wav_duration(path: Path) -> float:
        try:
            with wave.open(str(path), "rb") as handle:
                return handle.getnframes() / float(handle.getframerate())
        except (OSError, wave.Error, ZeroDivisionError):
            return 0.0

    @staticmethod
    def _split_sentences(text: str, start: float, end: float) -> list[dict[str, Any]]:
        sentences = [
            item.strip()
            for item in re.split(r"(?<=[。！？!?；;])\s*|(?<=\.)\s+|\n+", text)
            if item.strip()
        ]
        if not sentences:
            return []
        total_chars = sum(max(1, len(item)) for item in sentences)
        cursor = start
        segments: list[dict[str, Any]] = []
        for index, sentence in enumerate(sentences):
            if index == len(sentences) - 1:
                segment_end = end
            else:
                ratio = max(1, len(sentence)) / total_chars
                segment_end = cursor + (end - start) * ratio
            segments.append(
                {
                    "start": round(cursor, 3),
                    "end": round(max(cursor, segment_end), 3),
                    "text": sentence,
                }
            )
            cursor = segment_end
        return segments

    async def _transcribe_chunk(
        self,
        client: httpx.AsyncClient,
        path: Path,
        start: float,
        end: float,
        language: str | None,
        semaphore: asyncio.Semaphore,
        api_key: str,
        model: str,
    ) -> list[dict[str, Any]]:
        async with semaphore:
            content = path.read_bytes()
            response = await client.post(
                "/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                data={"model": model, "response_format": "json"},
                files={"file": (path.name, content, "audio/wav")},
            )
            response.raise_for_status()
            payload = response.json()
        text = str(payload.get("text") or "").strip()
        if not text:
            return []
        return self._split_sentences(text, start, end)

    async def transcribe(
        self,
        audio_path: str,
        language: str | None = None,
    ) -> dict[str, Any]:
        settings = get_settings()
        base_url = self.base_url or settings.llm_base_url
        api_key = self.api_key or settings.llm_api_key
        model = self.model or "glm-asr-2512"
        if not base_url or not api_key:
            raise RuntimeError("ASR 未配置：请填写 AUTOCUT_ASR_BASE_URL / API_KEY 或复用 LLM 配置")

        source = Path(audio_path)
        if not source.is_file():
            raise FileNotFoundError(audio_path)

        with tempfile.TemporaryDirectory(prefix="autocut-asr-") as directory:
            chunk_dir = Path(directory)
            await run_command(
                [
                    settings.ffmpeg_bin,
                    "-y",
                    "-i",
                    str(source),
                    "-f",
                    "segment",
                    "-segment_time",
                    "20",
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    "-c:a",
                    "pcm_s16le",
                    str(chunk_dir / "chunk_%04d.wav"),
                ],
                timeout=3600,
            )
            chunks = sorted(chunk_dir.glob("chunk_*.wav"))
            if not chunks:
                raise ValueError("音频分段失败")

            ranges: list[tuple[float, float]] = []
            cursor = 0.0
            for chunk in chunks:
                duration = self._wav_duration(chunk)
                ranges.append((cursor, cursor + duration))
                cursor += duration

            semaphore = asyncio.Semaphore(2)
            async with httpx.AsyncClient(
                base_url=base_url.rstrip("/"),
                timeout=180.0,
            ) as client:
                results = await asyncio.gather(
                    *[
                        self._transcribe_chunk(
                            client,
                            chunk,
                            ranges[index][0],
                            ranges[index][1],
                            language,
                            semaphore,
                            api_key,
                            model,
                        )
                        for index, chunk in enumerate(chunks)
                    ]
                )
            segments = [segment for batch in results for segment in batch]
        return {
            "language": language or "zh",
            "duration": cursor,
            "segments": segments,
            "model": model,
        }
