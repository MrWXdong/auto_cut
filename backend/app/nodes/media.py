from __future__ import annotations

import asyncio
import json
import math
import re
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.core.commands import CommandError, run_command
from app.core.workflow.context import RunContext
from app.core.workflow.node import Node
from app.storage_names import AUDIO_DIR, AUDIO_FILE, CLIPS_DIR, EXPORTS_DIR

ASPECT_SIZES: dict[str, tuple[int, int]] = {
    "9:16": (1080, 1920),
    "4:5": (1080, 1350),
    "1:1": (1080, 1080),
    "16:9": (1920, 1080),
}

INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _safe_filename_stem(value: str, fallback: str = "素材") -> str:
    name = Path(str(value or "")).stem or str(value or "")
    name = INVALID_FILENAME_CHARS.sub("_", name).strip(" .")
    return name[:80] or fallback


def _source_display_name(source: Path, inputs: dict[str, Any]) -> str:
    job_params = inputs.get("job_params") or {}
    params = inputs.get("params") or {}
    value = (
        params.get("source_name")
        or job_params.get("source_name")
        or source.name
    )
    return _safe_filename_stem(str(value))


def _format_seconds(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".") + "s"


def _parse_fps(value: str | None) -> float:
    if not value or value == "0/0":
        return 0.0
    if "/" in value:
        numerator, _, denominator = value.partition("/")
        try:
            return round(float(numerator) / float(denominator), 3) if float(denominator) else 0.0
        except ValueError:
            return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def _input_path(ctx: RunContext, inputs: dict[str, Any], key: str = "path") -> Path:
    value = inputs["params"].get(key) or inputs["data"].get(key)
    if not value:
        raise ValueError(f"missing input path: {key}")
    return ctx.resolve_path(str(value))


def _escape_filter_path(path: Path) -> str:
    value = str(path.resolve()).replace("\\", "/")
    value = value.replace(":", "\\:")
    return value.replace("'", "\\'")


async def _probe_with_ffmpeg(ffmpeg_bin: str, path: Path) -> dict[str, Any]:
    process = await asyncio.create_subprocess_exec(
        ffmpeg_bin,
        "-hide_banner",
        "-i",
        str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
    text = stderr.decode("utf-8", errors="replace")

    duration = 0.0
    duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if duration_match:
        hours, minutes, seconds = duration_match.groups()
        duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)

    video_line = next((line for line in text.splitlines() if "Video:" in line), "")
    size_match = re.search(r"(\d{2,5})x(\d{2,5})", video_line)
    if not size_match:
        raise ValueError(f"no video stream found in {path}")
    width, height = size_match.groups()
    fps_match = re.search(r"([\d.]+)\s+fps", video_line)
    codec_match = re.search(r"Video:\s*([^\s,]+)", video_line)
    return {
        "path": str(path),
        "duration": duration,
        "width": int(width),
        "height": int(height),
        "fps": float(fps_match.group(1)) if fps_match else 0.0,
        "video_codec": codec_match.group(1) if codec_match else "",
        "size_bytes": path.stat().st_size,
    }


class ProbeMediaNode(Node):
    type = "media.probe"

    async def run(self, ctx: RunContext, inputs: dict[str, Any]) -> dict[str, Any]:
        settings = get_settings()
        path = _input_path(ctx, inputs)
        if not path.exists():
            raise FileNotFoundError(f"input not found: {path}")

        try:
            raw = await run_command(
                [
                    settings.ffprobe_bin,
                    "-v",
                    "error",
                    "-print_format",
                    "json",
                    "-show_format",
                    "-show_streams",
                    str(path),
                ],
                timeout=60,
            )
        except (OSError, CommandError):
            return await _probe_with_ffmpeg(settings.ffmpeg_bin, path)
        payload = json.loads(raw)
        streams = payload.get("streams") or []
        video = next(
            (stream for stream in streams if stream.get("codec_type") == "video"),
            None,
        )
        if video is None:
            raise ValueError(f"no video stream found in {path}")

        container = payload.get("format") or {}
        return {
            "path": str(path),
            "duration": float(container.get("duration") or 0.0),
            "width": int(video.get("width") or 0),
            "height": int(video.get("height") or 0),
            "fps": _parse_fps(video.get("avg_frame_rate") or video.get("r_frame_rate")),
            "video_codec": str(video.get("codec_name") or ""),
            "size_bytes": int(container.get("size") or 0),
        }


class ExtractAudioNode(Node):
    type = "audio.extract"

    async def run(self, ctx: RunContext, inputs: dict[str, Any]) -> dict[str, Any]:
        settings = get_settings()
        path = _input_path(ctx, inputs)
        output_dir = ctx.work_dir / AUDIO_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        output = output_dir / AUDIO_FILE

        await run_command(
            [
                settings.ffmpeg_bin,
                "-y",
                "-i",
                str(path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(output),
            ],
            timeout=1800,
        )
        return {"path": str(output), "sample_rate": 16000}


async def _cut_video(source: Path, start: float, end: float, output: Path) -> None:
    settings = get_settings()
    if end - start < 0.05:
        raise ValueError(f"invalid range: {start} -> {end}")
    output.parent.mkdir(parents=True, exist_ok=True)
    clip_duration = end - start
    fade = min(0.18, max(0.05, clip_duration / 5))
    video_filter = (
        f"fade=t=in:st=0:d={fade:.3f},"
        f"fade=t=out:st={max(0.0, clip_duration - fade):.3f}:d={fade:.3f}"
    )
    await run_command(
        [
            settings.ffmpeg_bin,
            "-y",
            "-ss",
            f"{start:.3f}",
            "-i",
            str(source),
            "-t",
            f"{clip_duration:.3f}",
            "-vf",
            video_filter,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-movflags",
            "+faststart",
            str(output),
        ],
        timeout=3600,
    )


class CutClipNode(Node):
    type = "video.cut"

    async def run(self, ctx: RunContext, inputs: dict[str, Any]) -> dict[str, Any]:
        source = _input_path(ctx, inputs)
        start = float(inputs["params"]["start"])
        end = float(inputs["params"]["end"])
        name = _source_display_name(source, inputs)
        output = (
            ctx.work_dir
            / CLIPS_DIR
            / f"{name}_切片01_{_format_seconds(end - start)}.mp4"
        )
        await _cut_video(source, start, end, output)
        return {"path": str(output), "start": start, "end": end}


class CutClipsNode(Node):
    type = "video.cut_many"

    async def run(self, ctx: RunContext, inputs: dict[str, Any]) -> dict[str, Any]:
        source = _input_path(ctx, inputs)
        segments = inputs["params"].get("segments") or inputs["data"].get("segments") or []
        if not segments:
            raise ValueError("no segments to cut")

        name = _source_display_name(source, inputs)
        clips: list[dict[str, Any]] = []
        for segment in segments:
            try:
                start = float(segment["start"])
                end = float(segment["end"])
            except (KeyError, TypeError, ValueError):
                continue
            if end - start < 0.05:
                continue
            sequence = len(clips) + 1
            output = (
                ctx.work_dir
                / CLIPS_DIR
                / f"{name}_切片{sequence:02d}_{_format_seconds(end - start)}.mp4"
            )
            await _cut_video(source, start, end, output)
            clips.append(
                {
                    "path": str(output),
                    "start": start,
                    "end": end,
                    "index": sequence - 1,
                    "title": segment.get("title", ""),
                }
            )
        if not clips:
            raise ValueError("no valid segments to cut")
        return {"clips": clips}


class SplitEvenNode(Node):
    type = "clip.split_even"

    async def run(self, ctx: RunContext, inputs: dict[str, Any]) -> dict[str, Any]:
        duration = float(inputs["data"].get("duration") or 0.0)
        if duration <= 0:
            raise ValueError("source duration is required")

        count = int(inputs["params"].get("count", 3))
        min_seconds = float(inputs["params"].get("min_seconds", 5))
        max_seconds = float(inputs["params"].get("max_seconds", 60))
        count = max(1, min(count, 20))

        if duration < min_seconds:
            count = 1
        else:
            count = min(count, max(1, int(duration // min_seconds)))
        if max_seconds > 0:
            count = max(count, math.ceil(duration / max_seconds))
        count = max(1, min(count, 20))

        step = duration / count
        segments = [
            {
                "start": round(index * step, 3),
                "end": round((index + 1) * step, 3),
                "title": f"片段 {index + 1}",
            }
            for index in range(count)
        ]
        return {"segments": segments, "count": count}


class ExportVideoNode(Node):
    type = "video.export"

    async def run(self, ctx: RunContext, inputs: dict[str, Any]) -> dict[str, Any]:
        settings = get_settings()
        sources: list[str] = []
        clips = inputs["data"].get("clips") or []
        if clips:
            sources = [
                str(item["path"] if isinstance(item, dict) else item)
                for item in clips
            ]
        elif inputs["data"].get("path"):
            sources = [str(inputs["data"]["path"])]
        elif inputs["params"].get("path"):
            sources = [str(inputs["params"]["path"])]
        if not sources:
            raise ValueError("no source video to export")

        aspects = inputs["params"].get("aspects") or ["9:16"]
        output_dir = ctx.work_dir / EXPORTS_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        results: list[dict[str, Any]] = []

        for source in sources:
            source_path = Path(source)
            for aspect in aspects:
                if aspect not in ASPECT_SIZES:
                    raise ValueError(f"unsupported aspect ratio: {aspect}")
                width, height = ASPECT_SIZES[aspect]
                output = output_dir / f"{source_path.stem}_{width}x{height}.mp4"
                video_filter = (
                    f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                    f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1"
                )
                await run_command(
                    [
                        settings.ffmpeg_bin,
                        "-y",
                        "-i",
                        str(source_path),
                        "-vf",
                        video_filter,
                        "-c:v",
                        "libx264",
                        "-preset",
                        "veryfast",
                        "-crf",
                        "21",
                        "-c:a",
                        "aac",
                        "-b:a",
                        "128k",
                        "-movflags",
                        "+faststart",
                        str(output),
                    ],
                    timeout=3600,
                )
                results.append(
                    {
                        "path": str(output),
                        "aspect": aspect,
                        "width": width,
                        "height": height,
                        "source": str(source_path),
                    }
                )
        return {"outputs": results}


class BurnSubtitlesNode(Node):
    type = "video.burn_subtitles"

    async def run(self, ctx: RunContext, inputs: dict[str, Any]) -> dict[str, Any]:
        settings = get_settings()
        video = inputs["params"].get("video")
        subtitles = inputs["params"].get("subtitles")
        if not video or not subtitles:
            raise ValueError("video and subtitles parameters are required")

        video_path = ctx.resolve_path(str(video))
        subtitle_path = ctx.resolve_path(str(subtitles))
        output = ctx.work_dir / EXPORTS_DIR / f"{video_path.stem}_带字幕.mp4"
        output.parent.mkdir(parents=True, exist_ok=True)
        video_filter = f"subtitles='{_escape_filter_path(subtitle_path)}'"

        await run_command(
            [
                settings.ffmpeg_bin,
                "-y",
                "-i",
                str(video_path),
                "-vf",
                video_filter,
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "21",
                "-c:a",
                "copy",
                "-movflags",
                "+faststart",
                str(output),
            ],
            timeout=3600,
        )
        return {"path": str(output)}
