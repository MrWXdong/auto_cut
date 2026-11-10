from __future__ import annotations

import wave

import pytest

from app.core.workflow.context import RunContext
from app.nodes.ai import TranscribeNode


@pytest.mark.asyncio
async def test_asr_failure_falls_back_to_empty_transcript(tmp_path, monkeypatch) -> None:
    audio = tmp_path / "audio.wav"
    with wave.open(str(audio), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(b"\x00\x00" * 16000)

    class FailingASR:
        async def transcribe(self, path: str, language: str | None = None):
            raise ConnectionError("offline")

    monkeypatch.setattr("app.nodes.ai.CloudASR", lambda **kwargs: FailingASR())
    context = RunContext(job_id="asr-fallback", work_dir=tmp_path / "work")
    result = await TranscribeNode().run(
        context,
        {"params": {}, "data": {"path": str(audio)}},
    )
    assert result["segments"] == []
    assert result["duration"] >= 1.0
    assert "规则切片" in result["warning"]
