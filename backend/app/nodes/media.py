from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.core.commands import run_command
from app.core.workflow.context import RunContext
from app.core.workflow.node import Node

ASPECT_SIZES: dict[str, tuple[int, int]] = {
    "9:16": (1080, 1920),
    "4:5": (1080, 1350),
    "1:1": (1080, 1080),
    "16:9": (1920, 1080),
}


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


class ProbeMediaNode(Node):
    type = "media.probe"

    async def run(self, ctx: RunContext, inputs: dict[str, Any]) -> dict[str, Any]:
        settings = get_settings()
        path = _input_path(ctx, inputs)
        if not path.exists():
            raise FileNotFoundError(f"input not found: {path}")

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
        output_dir = ctx.work_dir / "audio"
        output_dir.mkdir(parents=True, exist_ok=True)
        output = output_dir / "audio.wav"

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
    if end <= start:
        raise ValueError(f"invalid range: {start} -> {end}")
    output.parent.mkdir(parents=True, exist_ok=True)
    await run_command(
        [
            settings.ffmpeg_bin,
            "-y",
            "-ss",
            f"{start:.3f}",
            "-i",
            str(source),
            "-t",
            f"{end - start:.3f}",
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
        output = ctx.work_dir / "clips" / f"clip_{int(start * 1000):08d}.mp4"
        await _cut_video(source, start, end, output)
        return {"path": str(output), "start": start, "end": end}


class CutClipsNode(Node):
    type = "video.cut_many"

    async def run(self, ctx: RunContext, inputs: dict[str, Any]) -> dict[str, Any]:
        source = _input_path(ctx, inputs)
        segments = inputs["params"].get("segments") or inputs["data"].get("segments") or []
        if not segments:
            raise ValueError("no segments to cut")

        clips: list[dict[str, Any]] = []
        for index, segment in enumerate(segments):
            start = float(segment["start"])
            end = float(segment["end"])
            output = (
                ctx.work_dir
                / "clips"
                / f"clip_{index:02d}_{int(start * 1000):08d}_{int(end * 1000):08d}.mp4"
            )
            await _cut_video(source, start, end, output)
            clips.append(
                {
                    "path": str(output),
                    "start": start,
                    "end": end,
                    "index": index,
                    "title": segment.get("title", ""),
                }
            )
        return {"clips": clips}


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
        output_dir = ctx.work_dir / "exports"
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
        output = ctx.work_dir / "exports" / f"{video_path.stem}_subtitled.mp4"
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
