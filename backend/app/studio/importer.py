from __future__ import annotations

import asyncio
import ipaddress
import shutil
import socket
import uuid
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.studio.store import StudioStore

CONTENT_EXTENSIONS = {
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/mp4": ".m4a",
}

URL_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".webm",
    ".mkv",
    ".avi",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".mp3",
    ".wav",
    ".m4a",
    ".flac",
}


class NotMediaError(ValueError):
    pass


class YtDlpUnavailableError(RuntimeError):
    pass


def validate_public_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("只支持 http/https 链接")
    host = parsed.hostname
    if not host:
        raise ValueError("链接缺少域名")
    try:
        addresses = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise ValueError("域名无法解析") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
        ):
            raise ValueError("不允许访问内网地址")
    return url.strip()


def guess_extension(url: str, content_type: str) -> str:
    if content_type in CONTENT_EXTENSIONS:
        return CONTENT_EXTENSIONS[content_type]
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in URL_EXTENSIONS:
        return suffix
    return ".bin"


def kind_from_name(name: str, content_type: str = "") -> str:
    if content_type.startswith("video/"):
        return "video"
    if content_type.startswith("image/"):
        return "image"
    if content_type.startswith("audio/"):
        return "audio"
    suffix = Path(name).suffix.lower()
    if suffix in {".mp4", ".mov", ".webm", ".mkv", ".avi"}:
        return "video"
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}:
        return "image"
    if suffix in {".mp3", ".wav", ".m4a", ".flac", ".aac"}:
        return "audio"
    return "file"


async def _preview_direct(url: str) -> dict[str, object]:
    headers = {"User-Agent": "Mozilla/5.0 YunLiuYing/0.1"}
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=30.0,
        headers=headers,
    ) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            content_type = (
                response.headers.get("content-type", "").split(";")[0].strip().lower()
            )
            if content_type.startswith("text/html"):
                raise NotMediaError("链接是网页，尝试用 yt-dlp 解析")
            filename = Path(urlparse(url).path).name or "media"
            size = int(response.headers.get("content-length") or 0)
            return {
                "title": filename,
                "kind": kind_from_name(filename, content_type),
                "size_bytes": size,
                "duration": 0,
                "thumbnail": "",
                "provider": "direct",
                "source_url": url,
                "can_download": True,
            }


def _preview_ytdlp(url: str) -> dict[str, object]:
    try:
        import yt_dlp
    except ImportError as exc:
        raise YtDlpUnavailableError(
            "平台链接需要 yt-dlp，请执行 pip install yt-dlp"
        ) from exc

    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=False)

    extension = str(info.get("ext") or "")
    filename = f"media.{extension}" if extension else "media"
    size = info.get("filesize") or info.get("filesize_approx") or 0
    return {
        "title": str(info.get("title") or filename),
        "kind": kind_from_name(filename),
        "size_bytes": int(size or 0),
        "duration": float(info.get("duration") or 0),
        "thumbnail": str(info.get("thumbnail") or ""),
        "provider": str(info.get("extractor_key") or "yt-dlp"),
        "source_url": url,
        "can_download": True,
    }


async def preview_asset(
    studio: StudioStore,
    project_id: str,
    url: str,
) -> dict[str, object]:
    if studio.get_project(project_id) is None:
        raise KeyError("project not found")
    await asyncio.to_thread(validate_public_url, url)
    try:
        return await _preview_direct(url)
    except (NotMediaError, httpx.HTTPError):
        return await asyncio.to_thread(_preview_ytdlp, url)


async def download_direct(
    url: str,
    target_dir: Path,
    max_bytes: int,
) -> tuple[Path, dict[str, str]]:
    token = uuid.uuid4().hex[:10]
    headers = {"User-Agent": "Mozilla/5.0 YunLiuYing/0.1"}
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=60.0,
        headers=headers,
    ) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            content_type = (
                response.headers.get("content-type", "").split(";")[0].strip().lower()
            )
            if content_type.startswith("text/html"):
                raise NotMediaError("链接是网页，尝试用 yt-dlp 解析")
            suffix = guess_extension(url, content_type)
            target = target_dir / f"{token}{suffix}"
            written = 0
            try:
                with target.open("wb") as handle:
                    async for chunk in response.aiter_bytes():
                        written += len(chunk)
                        if written > max_bytes:
                            raise ValueError("文件超过大小限制")
                        handle.write(chunk)
            except Exception:
                target.unlink(missing_ok=True)
                raise
    return target, {"content_type": content_type, "source": "direct"}


def download_with_ytdlp(
    url: str,
    target_dir: Path,
    max_bytes: int,
) -> tuple[Path, dict[str, str]]:
    try:
        import yt_dlp
    except ImportError as exc:
        raise YtDlpUnavailableError(
            "平台链接需要 yt-dlp，请执行 pip install yt-dlp"
        ) from exc

    token = uuid.uuid4().hex[:10]
    temp_dir = target_dir.parent / f".import-{token}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    options = {
        "outtmpl": str(temp_dir / "%(title).80s-%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "max_filesize": max_bytes,
    }
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            downloader.extract_info(url, download=True)
        files = [path for path in temp_dir.rglob("*") if path.is_file()]
        if not files:
            raise ValueError("没有下载到文件")
        source = max(files, key=lambda path: path.stat().st_size)
        target = target_dir / f"{token}{source.suffix}"
        shutil.move(str(source), target)
        return target, {"content_type": "", "source": "yt-dlp"}
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


async def import_asset(
    studio: StudioStore,
    project_id: str,
    url: str,
) -> dict[str, object]:
    if studio.get_project(project_id) is None:
        raise KeyError("project not found")
    await asyncio.to_thread(validate_public_url, url)

    settings = get_settings()
    max_bytes = settings.asset_import_max_mb * 1024 * 1024
    target_dir = studio.work_root / "projects" / project_id / "assets"
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        path, meta = await download_direct(url, target_dir, max_bytes)
    except (NotMediaError, httpx.HTTPError):
        path, meta = await asyncio.to_thread(
            download_with_ytdlp,
            url,
            target_dir,
            max_bytes,
        )

    size = path.stat().st_size
    if size > max_bytes:
        path.unlink(missing_ok=True)
        raise ValueError("文件超过大小限制")

    storage_key = str(path.relative_to(studio.work_root)).replace("\\", "/")
    return studio.add_asset(
        project_id,
        path.name,
        storage_key,
        size,
        {"provider": "import", "url": url, **meta},
    )
