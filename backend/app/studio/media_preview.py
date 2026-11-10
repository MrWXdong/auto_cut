from __future__ import annotations

import asyncio
import re
from pathlib import Path

from app.config import get_settings
from app.core.commands import CommandError, run_command
from app.studio.store import StudioStore

_active: set[str] = set()
_tasks: set[asyncio.Task] = set()


def preview_path(store: StudioStore, asset_id: str) -> Path:
    return (store.work_root / "previews" / f"{asset_id}.mp4").resolve()


def is_browser_video_codec(codec: str) -> bool:
    return codec.lower() in {"h264", "avc1", "vp8", "vp9", "av1"}


async def probe_video_codec(path: Path) -> str:
    settings = get_settings()
    try:
        await run_command(
            [settings.ffmpeg_bin, "-hide_banner", "-i", str(path)],
            timeout=60,
        )
        return ""
    except CommandError as exc:
        text = exc.stderr
    except OSError:
        return ""
    match = re.search(r"Video:\s*([^\s,]+)", text)
    return match.group(1).lower() if match else ""


def is_preview_active(asset_id: str) -> bool:
    return asset_id in _active


async def build_video_preview(store: StudioStore, asset_id: str, source: Path) -> Path:
    settings = get_settings()
    output = preview_path(store, asset_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.is_file() and output.stat().st_size > 0:
        return output
    if asset_id in _active:
        return output
    _active.add(asset_id)
    try:
        await run_command(
            [
                settings.ffmpeg_bin,
                "-y",
                "-i",
                str(source),
                "-vf",
                "scale='min(720,iw)':-2",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "24",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                str(output),
            ],
            timeout=7200,
        )
    finally:
        _active.discard(asset_id)
    return output


async def ensure_video_preview(
    store: StudioStore,
    asset_id: str,
    source: Path,
) -> str:
    output = preview_path(store, asset_id)
    if output.is_file() and output.stat().st_size > 0:
        return "ready"
    if asset_id in _active:
        return "generating"
    task = asyncio.create_task(build_video_preview(store, asset_id, source))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return "generating"
