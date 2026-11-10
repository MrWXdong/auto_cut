from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from app.config import get_settings
from app.core.workflow.context import RunContext
from app.core.workflow.node import Node, RetryPolicy
from app.gateway.asr import CloudASR
from app.gateway.base import ChatMessage
from app.gateway.factory import build_chat_model
from app.nodes.subtitle import build_timed_text
from app.storage_names import (
    FULL_SUBTITLE_TXT,
    SUBTITLES_DIR,
    SYSTEM_DIR,
    TRANSCRIPT_FILE,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a senior short-video editor. Pick the strongest standalone moments "
    "from a transcript. Return JSON only."
)


async def _audio_duration(path: str) -> float:
    settings = get_settings()
    process = await asyncio.create_subprocess_exec(
        settings.ffmpeg_bin,
        "-hide_banner",
        "-i",
        path,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    match = re.search(
        r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)",
        stderr.decode("utf-8", errors="replace"),
    )
    if not match:
        return 0.0
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


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
        job_params = inputs.get("job_params") or {}
        provider = str(job_params.get("asr_provider") or settings.asr_provider)
        model = str(job_params.get("asr_model") or settings.asr_model)
        try:
            if provider.lower() == "local":
                payload = await asyncio.to_thread(
                    _transcribe,
                    audio_path,
                    model or settings.asr_local_model,
                    str(language) if language else None,
                )
            else:
                adapter = CloudASR(
                    base_url=settings.asr_base_url,
                    api_key=settings.asr_api_key,
                    model=model,
                )
                payload = await adapter.transcribe(
                    audio_path,
                    str(language) if language else None,
                )
        except Exception as exc:
            logger.warning("ASR failed; falling back to rule-based clipping", exc_info=True)
            payload = {
                "language": str(language or "zh"),
                "duration": await _audio_duration(audio_path),
                "segments": [],
                "model": model or "asr-unavailable",
                "warning": f"ASR 暂时不可用，已降级为规则切片：{type(exc).__name__}: {exc}",
            }

        system_dir = ctx.work_dir / SYSTEM_DIR
        output = system_dir / TRANSCRIPT_FILE
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        segments = payload.get("segments") or []
        subtitle_dir = ctx.work_dir / SUBTITLES_DIR
        subtitle_dir.mkdir(parents=True, exist_ok=True)
        text_path = subtitle_dir / FULL_SUBTITLE_TXT
        text_path.write_text("\ufeff" + build_timed_text(segments), encoding="utf-8")
        return {
            "path": str(output),
            "text_path": str(text_path),
            **payload,
        }


def _build_prompt(
    segments: list[dict[str, Any]],
    duration: float,
    max_clips: int,
    min_seconds: float,
    max_seconds: float,
    brief: str = "",
) -> str:
    if max_seconds > 0:
        duration_rule = (
            f"单段最长 {max_seconds:.0f} 秒，最短不低于 {min_seconds:.1f} 秒。"
        )
    elif min_seconds > 0:
        duration_rule = (
            f"不设固定单段上限，按内容完整性决定；几秒钟的有效高光也可以保留，"
            f"最短不低于 {min_seconds:.1f} 秒。"
        )
    else:
        duration_rule = "不设固定单段时长，几秒钟到几十秒都可以，按内容完整性决定。"
    lines = [
        f"视频总时长：{duration:.1f} 秒。",
        f"请挑选最多 {max_clips} 个片段。{duration_rule}",
        "不要为了凑固定时长切断句子或镜头；片段必须有完整语义。",
        "片段必须能独立成片，开头有钩子，结尾有落点，避免口误、冷场和未说完的句子。",
        f"用户剪辑要求：{brief.strip() or '无特别要求'}",
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
        if length < min_seconds or (max_seconds > 0 and length > max_seconds):
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


async def _scene_cuts(path: str) -> list[float]:
    settings = get_settings()
    process = await asyncio.create_subprocess_exec(
        settings.ffmpeg_bin,
        "-hide_banner",
        "-i",
        path,
        "-vf",
        "select='gt(scene,0.3)',showinfo",
        "-an",
        "-f",
        "null",
        "-",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    text = stderr.decode("utf-8", errors="replace")
    cuts = sorted(
        {
            round(float(value), 3)
            for value in re.findall(r"pts_time:([0-9]+(?:\.[0-9]+)?)", text)
        }
    )
    return [cut for cut in cuts if cut > 0]


def _units_from_segments(
    segments: list[dict[str, Any]],
    duration: float,
) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    for segment in segments:
        try:
            start = max(0.0, float(segment.get("start") or 0))
            end = min(duration, float(segment.get("end") or 0))
        except (TypeError, ValueError):
            continue
        if end - start < 0.2:
            continue
        units.append(
            {
                "start": round(start, 3),
                "end": round(end, 3),
                "text": str(segment.get("text") or "").strip(),
            }
        )
    units.sort(key=lambda item: (item["start"], item["end"]))
    return units


def _units_from_scene_cuts(
    scene_cuts: list[float] | None,
    duration: float,
) -> list[dict[str, Any]]:
    if not scene_cuts:
        return []
    cuts = sorted(
        {
            round(float(cut), 3)
            for cut in scene_cuts or []
            if 0 < float(cut) < duration
        }
    )
    boundaries = [0.0, *cuts, round(duration, 3)]
    return [
        {
            "start": boundaries[index],
            "end": boundaries[index + 1],
            "text": "",
        }
        for index in range(len(boundaries) - 1)
        if boundaries[index + 1] - boundaries[index] >= 0.2
    ]


def _merge_tiny_units(
    units: list[dict[str, Any]],
    threshold: float = 1.0,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for unit in units:
        tiny = unit["end"] - unit["start"] < threshold
        previous_tiny = bool(merged) and (
            merged[-1]["end"] - merged[-1]["start"] < threshold
        )
        if merged and (tiny or previous_tiny):
            previous = merged[-1]
            previous["end"] = max(previous["end"], unit["end"])
            if unit["text"]:
                previous["text"] = " ".join(
                    part for part in (previous["text"], unit["text"]) if part
                )
            continue
        merged.append(dict(unit))
    return merged


def _partition_units(
    units: list[dict[str, Any]],
    max_clips: int,
) -> list[list[dict[str, Any]]]:
    count = min(max(1, max_clips), len(units))
    if count <= 1:
        return [units]

    durations = [unit["end"] - unit["start"] for unit in units]
    prefix = [0.0]
    for value in durations:
        prefix.append(prefix[-1] + value)
    target = prefix[-1] / count
    infinity = float("inf")
    dp = [[infinity] * (len(units) + 1) for _ in range(count + 1)]
    previous = [[-1] * (len(units) + 1) for _ in range(count + 1)]
    dp[0][0] = 0.0

    for group_index in range(1, count + 1):
        for end in range(group_index, len(units) + 1):
            for begin in range(group_index - 1, end):
                group_duration = prefix[end] - prefix[begin]
                cost = (group_duration - target) ** 2
                candidate = dp[group_index - 1][begin] + cost
                if candidate < dp[group_index][end]:
                    dp[group_index][end] = candidate
                    previous[group_index][end] = begin

    groups: list[list[dict[str, Any]]] = []
    end = len(units)
    for group_index in range(count, 0, -1):
        begin = previous[group_index][end]
        groups.append(units[begin:end])
        end = begin
    groups.reverse()
    return groups


def _split_long_groups(
    groups: list[list[dict[str, Any]]],
    max_seconds: float,
) -> list[list[dict[str, Any]]]:
    if max_seconds <= 0:
        return groups
    result: list[list[dict[str, Any]]] = []
    for group in groups:
        current: list[dict[str, Any]] = []
        for unit in group:
            if current and unit["end"] - current[0]["start"] > max_seconds:
                result.append(current)
                current = []
            if unit["end"] - unit["start"] > max_seconds:
                start = unit["start"]
                while start < unit["end"]:
                    end = min(unit["end"], start + max_seconds)
                    result.append([{**unit, "start": round(start, 3), "end": round(end, 3)}])
                    start = end
                continue
            current.append(unit)
        if current:
            result.append(current)
    return result


def _equal_groups(
    duration: float,
    max_clips: int,
) -> list[list[dict[str, Any]]]:
    slots = max(1, min(max_clips, max(1, int(duration // 0.5))))
    boundaries = [duration * index / slots for index in range(slots + 1)]
    return [
        [
            {
                "start": round(boundaries[index], 3),
                "end": round(boundaries[index + 1], 3),
                "text": "",
            }
        ]
        for index in range(slots)
    ]


def _fallback_segments(
    segments: list[dict[str, Any]],
    duration: float,
    max_clips: int,
    min_seconds: float,
    max_seconds: float,
    scene_cuts: list[float] | None = None,
) -> list[dict[str, Any]]:
    if duration <= 0:
        return []
    if max_clips <= 1:
        text = " ".join(str(item.get("text") or "") for item in segments).strip()
        return [
            {
                "start": 0.0,
                "end": round(duration, 3),
                "title": text[:40] or "完整视频",
                "reason": "只请求一个片段，保留完整视频",
                "score": 0.5,
                "id": "clip-01",
            }
        ]

    units = _units_from_segments(segments, duration)
    reason = "按字幕句段切分"
    if not units:
        units = _units_from_scene_cuts(scene_cuts, duration)
        reason = "按画面场景切分"
    if units:
        units = _merge_tiny_units(units)
        groups = _partition_units(units, max_clips)
    else:
        groups = _equal_groups(duration, max_clips)
        reason = "没有字幕或场景边界，按数量等分兜底"

    groups = _split_long_groups(groups, max_seconds)
    picks: list[dict[str, Any]] = []
    for index, group in enumerate(groups):
        start = group[0]["start"]
        end = group[-1]["end"]
        if end <= start:
            continue
        text = " ".join(
            str(item.get("text") or "").strip()
            for item in group
            if str(item.get("text") or "").strip()
        ).strip()
        picks.append(
            {
                "start": round(start, 3),
                "end": round(end, 3),
                "title": text[:40] or f"片段 {index + 1}",
                "reason": reason,
                "score": 0.5 if units else 0.3,
            }
        )
    return picks


class SelectSegmentsNode(Node):
    type = "llm.select_segments"
    retry = RetryPolicy(max_attempts=3, initial_delay=2.0, max_delay=10.0)

    async def run(self, ctx: RunContext, inputs: dict[str, Any]) -> dict[str, Any]:
        segments = inputs["data"].get("segments") or []
        duration = float(inputs["data"].get("duration") or 0.0)
        max_clips = int(inputs["params"].get("max_clips", 5))
        min_seconds = max(0.0, float(inputs["params"].get("min_seconds") or 1.0))
        max_seconds = max(0.0, float(inputs["params"].get("max_seconds") or 0.0))
        job_params = inputs.get("job_params") or {}
        model_ref = str(job_params.get("model_ref") or "")
        brief = str(job_params.get("brief") or "")

        picks: list[dict[str, Any]] = []
        payload: dict[str, Any] = {}
        model_name = "rule-fallback"
        warning = None if segments else "未识别到可用人声，已自动使用规则选段"
        chat_model = build_chat_model(model_ref or None) if segments else None
        if segments and chat_model is None:
            warning = "所选选段模型未配置，已自动使用规则选段"
        if segments and chat_model is not None:
            prompt = _build_prompt(
                segments,
                duration,
                max_clips,
                min_seconds,
                max_seconds,
                brief,
            )
            try:
                result = await chat_model.chat(
                    [
                        ChatMessage(role="system", content=SYSTEM_PROMPT),
                        ChatMessage(role="user", content=prompt),
                    ],
                    temperature=0.2,
                )
                model_name = result.model or model_ref or "chat-model"
                payload = {"usage": result.usage}
                picks = _parse_segments(
                    result.text,
                    duration,
                    min_seconds,
                    max_seconds,
                )
            except Exception:
                logger.warning("AI segment selection failed; using rule fallback", exc_info=True)
                warning = "AI 选段失败，已自动使用规则选段"
        if not picks:
            if segments and payload:
                warning = "AI 未选出可用片段，已自动使用规则选段"
        scene_cuts: list[float] = []
        video_path = str(
            (inputs.get("upstream") or {}).get("probe", {}).get("path")
            or inputs["data"].get("path")
            or ""
        )
        if not segments and video_path:
            scene_cuts = await _scene_cuts(video_path)
        picks = _fallback_segments(
            segments,
            duration,
            max_clips,
            min_seconds,
            max_seconds,
            scene_cuts,
        )
        if not picks:
            raise ValueError("no usable segments")

        picks.sort(key=lambda item: item["score"], reverse=True)
        picks = picks[:max_clips]
        picks.sort(key=lambda item: item["start"])
        for index, item in enumerate(picks, 1):
            item["id"] = f"clip-{index:02d}"

        return {
            "segments": picks,
            "model": model_name,
            "prompt_version": "v1" if payload else "fallback",
            "usage": payload.get("usage") or {},
            "warning": warning,
        }
