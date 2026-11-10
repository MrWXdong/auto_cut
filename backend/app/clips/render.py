from __future__ import annotations

from pathlib import Path

from app.config import get_settings
from app.core.commands import run_command
from app.nodes.media import ASPECT_SIZES


async def render_clip(
    source: Path,
    start: float,
    end: float,
    aspect: str,
    output: Path,
) -> None:
    if end - start < 0.05:
        raise ValueError("clip duration is too short")
    if aspect not in ASPECT_SIZES:
        raise ValueError(f"unsupported aspect ratio: {aspect}")

    settings = get_settings()
    width, height = ASPECT_SIZES[aspect]
    duration = end - start
    fade = min(0.18, max(0.05, duration / 5))
    video_filter = (
        f"fade=t=in:st=0:d={fade:.3f},"
        f"fade=t=out:st={max(0.0, duration - fade):.3f}:d={fade:.3f},"
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1"
    )
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
            f"{duration:.3f}",
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
