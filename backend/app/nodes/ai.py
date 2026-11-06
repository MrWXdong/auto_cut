from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx

from app.config import get_settings
from app.core.workflow.context import RunContext
from app.core.workflow.node import Node, RetryPolicy
from app.gateway.asr import CloudASR

SYSTEM_PROMPT = (
    "You are a senior short-video editor. Pick the strongest standalone moments "
    "from a transcript. Return JSON only."
)


def _transcribe(path: str, model_name: str, language: str | None) -> dict[str, Any]:
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device="auto", compute_type="int8")
    segments, info = model.transcribe(path, language=language, vad_filter=True)
    items = [
        {
            "start": round(float(segment.start), 3),
            "end": round(float(segment.end), 3),
            "text": segment.text.strip(),
        }
        for segment in segments
    ]
    return {
        "language": info.language,
        "duration": float(info.duration),
        "segments": items,
    }


class TranscribeNode(Node):
    type = "asr.transcribe"
    retry = RetryPolicy(max_attempts=2, initial_delay=3.0, max_delay=10.0)

    async def run(self, ctx: RunContext, inputs: dict[str, Any]) -> dict[str, Any]:
        settings = get_settings()
        raw_path = inputs["params"].get("path") or inputs["data"].get("path")
        if not raw_path:
            raise ValueError("missing audio path for transcription")

        language = inputs["params"].get("language") or None
        audio_path = str(ctx.resolve_path(str(raw_path)))
        if settings.asr_provider.lower() == "local":
            payload = await asyncio.to_thread(
                _transcribe,
                audio_path,
                settings.asr_local_model,
                str(language) if language else None,
            )
        else:
            adapter = CloudASR(
                base_url=settings.asr_base_url,
                api_key=settings.asr_api_key,
                model=settings.asr_model,
            )
            payload = await adapter.transcribe(
                audio_path,
                str(language) if language else None,
            )

        output = ctx.work_dir / "asr" / "transcript.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return {"path": str(output), **payload}


def _build_prompt(
    segments: list[dict[str, Any]],
    duration: float,
    max_clips: int,
    min_seconds: float,
    max_seconds: float,
) -> str:
    lines = [
        f"视频总时长：{duration:.1f} 秒。",
        (
            f"请挑选最多 {max_clips} 个片段，"
            f"每段时长在 {min_seconds:.0f} 到 {max_seconds:.0f} 秒之间。"
        ),
        "片段必须能独立成片，开头有钩子，结尾有落点，避免口误、冷场和未说完的句子。",
        "只返回 JSON 数组，不要解释。每个元素包含：",
        '{"start": 秒, "end": 秒, "title": "片段标题", "reason": "推荐理由", "score": 0到1}',
        "",
        "字幕如下：",
    ]
    for segment in segments:
        lines.append(
            f"[{float(segment['start']):.1f}-{float(segment['end']):.1f}] "
            f"{str(segment.get('text') or '').strip()}"
        )
    return "\n".join(lines)


def _extract_json(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    match = re.search(r"[\[{][\s\S]*[\]}]", cleaned)
    if match is None:
        raise ValueError("no JSON object found in model output")
    return json.loads(match.group(0))


def _parse_segments(
    text: str,
    duration: float,
    min_seconds: float,
    max_seconds: float,
) -> list[dict[str, Any]]:
    payload = _extract_json(text)
    if isinstance(payload, dict):
        payload = payload.get("segments") or payload.get("clips") or []
    if not isinstance(payload, list):
        raise ValueError("model output is not a JSON array")

    picks: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        try:
            start = float(item["start"])
            end = float(item["end"])
        except (KeyError, TypeError, ValueError):
            continue
        start = max(0.0, start)
        if duration > 0:
            end = min(duration, end)
        length = end - start
        if length < min_seconds or length > max_seconds:
            continue
        try:
            score = float(item.get("score", 0.0))
        except (TypeError, ValueError):
            score = 0.0
        picks.append(
            {
                "start": round(start, 3),
                "end": round(end, 3),
                "title": str(item.get("title") or "").strip(),
                "reason": str(item.get("reason") or "").strip(),
                "score": max(0.0, min(1.0, score)),
            }
        )
    return picks


class SelectSegmentsNode(Node):
    type = "llm.select_segments"
    retry = RetryPolicy(max_attempts=3, initial_delay=2.0, max_delay=10.0)

    async def run(self, ctx: RunContext, inputs: dict[str, Any]) -> dict[str, Any]:
        settings = get_settings()
        if not settings.llm_api_key:
            raise RuntimeError("AUTOCUT_LLM_API_KEY is not configured")

        segments = inputs["data"].get("segments") or []
        if not segments:
            raise ValueError("transcript has no segments")
        duration = float(inputs["data"].get("duration") or 0.0)
        max_clips = int(inputs["params"].get("max_clips", 5))
        min_seconds = float(inputs["params"].get("min_seconds", 15))
        max_seconds = float(inputs["params"].get("max_seconds", 60))

        prompt = _build_prompt(segments, duration, max_clips, min_seconds, max_seconds)
        async with httpx.AsyncClient(
            base_url=settings.llm_base_url.rstrip("/"),
            timeout=120.0,
        ) as client:
            response = await client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={
                    "model": settings.llm_model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                },
            )
            response.raise_for_status()
            payload = response.json()

        content = payload["choices"][0]["message"]["content"]
        picks = _parse_segments(content, duration, min_seconds, max_seconds)
        if not picks:
            raise ValueError("model returned no usable segments")

        picks.sort(key=lambda item: item["score"], reverse=True)
        picks = picks[:max_clips]
        picks.sort(key=lambda item: item["start"])
        for index, item in enumerate(picks, 1):
            item["id"] = f"clip-{index:02d}"

        return {
            "segments": picks,
            "model": settings.llm_model,
            "prompt_version": "v1",
            "usage": payload.get("usage") or {},
        }
