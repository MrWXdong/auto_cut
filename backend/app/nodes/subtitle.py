from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.workflow.context import RunContext
from app.core.workflow.node import Node
from app.storage_names import FULL_SUBTITLE_TXT, SUBTITLES_DIR


def format_timestamp(seconds: float) -> str:
    total_ms = max(0, round(seconds * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_short_timestamp(seconds: float) -> str:
    total = max(0, round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def build_timed_text(
    segments: list[dict[str, Any]],
    offset: float = 0.0,
) -> str:
    lines: list[str] = []
    for segment in segments:
        text = str(segment.get("text") or "").strip()
        if not text:
            continue
        start = max(0.0, float(segment.get("start") or 0) - offset)
        end = max(start, float(segment.get("end") or 0) - offset)
        lines.append(
            f"[{format_timestamp(start)} --> {format_timestamp(end)}] {text}"
        )
    return "\n".join(lines)


def build_clip_timed_text(
    clips: list[dict[str, Any]],
    transcript: list[dict[str, Any]],
) -> str:
    lines: list[str] = []
    for clip in clips:
        try:
            start = max(0.0, float(clip.get("start") or 0))
            end = max(start, float(clip.get("end") or 0))
        except (TypeError, ValueError):
            continue
        if end <= start:
            continue
        texts: list[str] = []
        for item in transcript:
            try:
                item_start = float(item.get("start") or 0)
                item_end = float(item.get("end") or 0)
            except (TypeError, ValueError):
                continue
            if item_end <= start or item_start >= end:
                continue
            text = str(item.get("text") or "").strip()
            if text:
                texts.append(text)
        text = " ".join(texts).strip() or str(clip.get("title") or "").strip()
        if not text:
            continue
        lines.append(
            f"[{format_short_timestamp(start)} --> "
            f"{format_short_timestamp(end)}] {text}"
        )
    return "\n".join(lines)


def write_clip_subtitles(
    root: Path,
    clips: list[dict[str, Any]],
    transcript: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    subtitle_dir = root / SUBTITLES_DIR
    subtitle_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    full_content = (
        build_clip_timed_text(clips, transcript)
        if clips
        else build_timed_text(transcript)
    )
    if full_content:
        path = subtitle_dir / FULL_SUBTITLE_TXT
        path.write_text("\ufeff" + full_content, encoding="utf-8")
        records.append(
            {
                "path": str(path),
                "name": path.name,
                "clip": 0,
                "kind": "full",
            }
        )
    for index, clip in enumerate(clips, 1):
        content = build_clip_timed_text([clip], transcript)
        if not content:
            continue
        path = subtitle_dir / f"切片{index:02d}_字幕.txt"
        path.write_text("\ufeff" + content, encoding="utf-8")
        records.append(
            {
                "path": str(path),
                "name": path.name,
                "clip": index,
                "kind": "clip",
            }
        )
    return records


class BuildSubtitleNode(Node):
    type = "subtitle.build"

    async def run(self, ctx: RunContext, inputs: dict[str, Any]) -> dict[str, Any]:
        segments = inputs["params"].get("segments") or inputs["data"].get("segments") or []
        if not segments:
            raise ValueError("no transcript segments to build subtitles from")

        content = build_timed_text(segments)
        output = ctx.work_dir / SUBTITLES_DIR / FULL_SUBTITLE_TXT
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\ufeff" + content, encoding="utf-8")
        return {"path": str(output), "count": len(content.splitlines())}
