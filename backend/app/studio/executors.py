from __future__ import annotations

import asyncio
import json
import math
import re
import textwrap
import uuid
import wave
from html import escape
from pathlib import Path
from typing import Any

import httpx

from app.billing.credits import CreditService
from app.config import get_settings
from app.core.commands import run_command
from app.gateway.factory import build_chat_model, build_image_model
from app.gateway.image import DoubaoImage
from app.skills import PromptSkill
from app.studio.quality import preset
from app.studio.store import StudioStore

RENDER_SIZES: dict[str, tuple[int, int]] = {
    "9:16": (1080, 1920),
    "4:5": (1080, 1350),
    "1:1": (1080, 1080),
    "16:9": (1920, 1080),
}


def _save_json_asset(
    studio: StudioStore,
    project_id: str,
    prefix: str,
    payload: dict[str, Any],
    meta: dict[str, Any],
) -> dict[str, Any]:
    token = uuid.uuid4().hex[:10]
    storage_key = f"projects/{project_id}/assets/{token}.json"
    path = studio.work_root / storage_key
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    path.write_text(text, encoding="utf-8")
    return studio.add_asset(
        project_id,
        f"{prefix}-{token}.json",
        storage_key,
        len(text.encode("utf-8")),
        meta,
    )


def _save_wav_asset(
    studio: StudioStore,
    project_id: str,
    seconds: int = 1,
) -> dict[str, Any]:
    token = uuid.uuid4().hex[:10]
    storage_key = f"projects/{project_id}/assets/{token}.wav"
    path = studio.work_root / storage_key
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(b"\x00\x00" * 16000 * seconds)
    return studio.add_asset(
        project_id,
        f"tts-{token}.wav",
        storage_key,
        path.stat().st_size,
        {"provider": "placeholder", "mode": "tts"},
    )


def _save_svg_cover(
    studio: StudioStore,
    project_id: str,
    mode: str,
    prompt: str,
    width: int = 1080,
    height: int = 1920,
    color: str = "#0f766e",
    variant: str = "",
) -> dict[str, Any]:
    token = uuid.uuid4().hex[:10]
    storage_key = f"projects/{project_id}/assets/{token}.svg"
    path = studio.work_root / storage_key
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = textwrap.wrap(prompt or "云流影", width=16)[:5] or ["云流影"]
    font_size = max(32, int(width * 0.052))
    spans = "".join(
        f'<tspan x="80" dy="{0 if index == 0 else font_size + 8}">{escape(line)}</tspan>'
        for index, line in enumerate(lines)
    )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        f'<rect width="{width}" height="{height}" fill="{color}"/>'
        f'<rect x="48" y="48" width="{width - 96}" height="{height - 96}" rx="24" fill="none" '
        'stroke="#ffffff" stroke-opacity="0.25" stroke-width="4"/>'
        f'<text x="80" y="{int(height * 0.43)}" '
        'font-family="Segoe UI, Microsoft YaHei, sans-serif" '
        f'font-size="{font_size}" font-weight="700" fill="#ffffff">{spans}</text>'
        f'<text x="80" y="{height - 80}" font-family="Segoe UI, sans-serif" '
        f'font-size="{max(20, int(width * 0.026))}" '
        'fill="#ffffff" fill-opacity="0.7">云流影 placeholder</text>'
        "</svg>"
    )
    path.write_text(svg, encoding="utf-8")
    return studio.add_asset(
        project_id,
        f"cover-{token}{variant}.svg",
        storage_key,
        len(svg.encode("utf-8")),
        {
            "provider": "placeholder",
            "mode": mode,
            "prompt": prompt,
            "width": width,
            "height": height,
            "variant": variant,
        },
    )


def _effective_style(
    studio: StudioStore,
    project_id: str | None,
) -> dict[str, Any] | None:
    return studio.effective_style(project_id)


def _preferred_model(studio: StudioStore, capability: str) -> str:
    preferences = studio.get_preference("models")
    if not isinstance(preferences, dict):
        return ""
    return str(preferences.get(capability) or "").strip()


async def _copywriting(
    studio: StudioStore,
    mode: str,
    prompt: str,
    params: dict[str, Any],
    project_id: str | None,
) -> dict[str, Any]:
    product = prompt.strip() or "未命名内容"
    quality = preset(str(params.get("quality") or "standard"))
    brand = studio.get_brand_kit()
    style_parts = [str(params.get("style") or "口播"), f"{quality['label']}质量"]
    if brand.get("configured") and brand.get("brand_name"):
        style_parts.append(f"品牌：{brand['brand_name']}")
    if brand.get("configured") and brand.get("slogan"):
        style_parts.append(f"品牌口号：{brand['slogan']}")
    if brand.get("configured") and brand.get("voice_tone"):
        style_parts.append(f"品牌语气：{brand['voice_tone']}")
    style_profile = _effective_style(studio, project_id)
    if style_profile:
        if style_profile.get("prompt"):
            style_parts.append(f"风格要求：{style_profile['prompt']}")
        if style_profile.get("shot_rhythm"):
            style_parts.append(f"节奏：{style_profile['shot_rhythm']}")
    model_ref = (
        str(params.get("model") or "").strip()
        or _preferred_model(studio, "chat")
    )
    result = await PromptSkill(build_chat_model(model_ref or None)).run(
        {},
        {
            "product": product,
            "platform": str(params.get("platform") or "抖音"),
            "style": "；".join(style_parts),
            "task": "script",
        },
    )
    body = str(result.get("prompt") or "").strip()
    if not body:
        return {"status": "failed", "result": None, "error": "empty copywriting result"}
    script = studio.create_script(
        product[:40],
        body,
        project_id,
        [mode],
    )
    return {
        "status": "succeeded",
        "result": {
            "script_id": script["id"],
            "shell": bool(result.get("shell")),
            "model": result.get("model"),
            "chars": len(body),
            "quality": str(params.get("quality") or "standard"),
        },
        "error": None,
    }


def _cogview_size(width: int, height: int) -> str:
    ratio = width / max(1, height)
    if ratio > 1.2:
        return "1344x768"
    if ratio > 1.05:
        return "1152x864"
    if ratio < 0.8:
        return "768x1344"
    if ratio < 0.95:
        return "864x1152"
    return "1024x1024"


def _doubao_size(width: int, height: int) -> str:
    ratio = width / max(1, height)
    if ratio > 1.05:
        return "1536x1024"
    if ratio < 0.8:
        return "1024x1536"
    return "1024x1024"


def _image_prompt(studio: StudioStore, project_id: str, prompt: str) -> str:
    parts = [prompt]
    brand = studio.get_brand_kit()
    if brand.get("configured") and brand.get("brand_name"):
        parts.append(f"品牌：{brand['brand_name']}")
    style_profile = _effective_style(studio, project_id)
    if style_profile and style_profile.get("prompt"):
        parts.append(f"风格：{style_profile['prompt']}")
    return "；".join(part for part in parts if part)


def _image_suffix(content: bytes, content_type: str = "") -> str:
    if content.startswith(b"\xff\xd8"):
        return ".jpg"
    if content.startswith(b"\x89PNG"):
        return ".png"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return ".webp"
    if "jpeg" in content_type:
        return ".jpg"
    if "webp" in content_type:
        return ".webp"
    return ".png"


async def _save_remote_image(
    studio: StudioStore,
    project_id: str,
    prompt: str,
    variant: int,
    url: str,
    model: str,
    provider: str = "zhipu",
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        content = response.content
        content_type = response.headers.get("content-type", "")
    suffix = _image_suffix(content, content_type)
    token = uuid.uuid4().hex[:10]
    filename = f"cover-{token}-v{variant}{suffix}"
    storage_key = f"projects/{project_id}/assets/{filename}"
    root = studio.work_root.resolve()
    target = (root / storage_key).resolve()
    if not target.is_relative_to(root):
        raise ValueError("invalid image storage path")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return studio.add_asset(
        project_id,
        filename,
        storage_key,
        len(content),
        {
            "provider": provider,
            "model": model,
            "prompt": prompt,
            "variant": variant,
            "source_url": url,
        },
    )


async def _image(
    studio: StudioStore,
    mode: str,
    prompt: str,
    params: dict[str, Any],
    project_id: str | None,
) -> dict[str, Any]:
    if not project_id:
        return {
            "status": "needs_config",
            "result": {"note": "先生成或选择一个项目"},
            "error": None,
        }
    quality_name = str(params.get("quality") or "standard")
    quality = preset(quality_name)
    width, height = quality["image_size"]
    brand = studio.get_brand_kit()
    brand_colors = []
    if brand.get("configured"):
        brand_colors = [
            str(brand.get("primary_color") or ""),
            str(brand.get("secondary_color") or ""),
        ]
    style_profile = _effective_style(studio, project_id)
    style_colors = []
    if style_profile:
        style_colors = [
            str(color)
            for color in style_profile.get("palette") or []
            if re.fullmatch(r"#[0-9a-fA-F]{6}", str(color))
        ]
    colors = list(
        dict.fromkeys(
            [
                *brand_colors,
                *style_colors,
                "#0f766e",
                "#1d4ed8",
                "#9a3412",
            ]
        )
    )
    colors = [color for color in colors if re.fullmatch(r"#[0-9a-fA-F]{6}", color)]
    model_ref = (
        str(params.get("model") or "").strip()
        or _preferred_model(studio, "image.generate")
    )
    image_model = build_image_model(model_ref or None)
    provider_error = ""
    if image_model is not None:
        try:
            candidates = []
            prompt_for_image = _image_prompt(studio, project_id, prompt)
            image_size = (
                _doubao_size(width, height)
                if isinstance(image_model, DoubaoImage)
                else _cogview_size(width, height)
            )
            provider_name = "doubao" if isinstance(image_model, DoubaoImage) else "zhipu"
            provider_label = "Seedream" if provider_name == "doubao" else "CogView"
            for index in range(int(quality["candidates"])):
                generated = await image_model.generate(
                    prompt_for_image,
                    size=image_size,
                )
                asset = await _save_remote_image(
                    studio,
                    project_id,
                    prompt_for_image,
                    index + 1,
                    str(generated["url"]),
                    str(generated["model"]),
                    provider_name,
                )
                candidates.append(
                    {
                        "asset_id": asset["id"],
                        "filename": asset["filename"],
                        "variant": index + 1,
                    }
                )
            chosen = candidates[0]
            return {
                "status": "succeeded",
                "result": {
                    "asset_id": chosen["asset_id"],
                    "candidates": candidates,
                    "quality": quality_name,
                    "score": 92,
                    "provider": provider_name,
                    "model": image_model.model,
                    "note": (
                        f"{provider_label} 生成 {len(candidates)} 个候选，默认使用第 1 个；"
                        "可分别下载每张原图"
                    ),
                },
                "error": None,
            }
        except Exception as exc:
            provider_error = f"{type(exc).__name__}: {exc}"

    if provider_error:
        return {
            "status": "failed",
            "result": None,
            "error": f"图像模型调用失败：{provider_error}",
        }

    candidates = []
    for index in range(int(quality["candidates"])):
        asset = _save_svg_cover(
            studio,
            project_id,
            mode,
            prompt,
            width,
            height,
            colors[index % len(colors)],
            f"-v{index + 1}",
        )
        candidates.append(
            {
                "asset_id": asset["id"],
                "filename": asset["filename"],
                "variant": index + 1,
            }
        )
    chosen = candidates[0]
    score = int(60 + min(1.0, min(width, height) / 1440) * 35)
    return {
        "status": "needs_config",
        "result": {
            "asset_id": chosen["asset_id"],
            "candidates": candidates,
            "quality": quality_name,
            "score": score,
            "provider": "placeholder",
            "note": (
                f"{quality['label']}档生成 {len(candidates)} 个候选，默认使用第 1 个；"
                "当前未配置可用的图像模型，产物是占位图，配置 API 后会替换为真实图片"
            ),
        },
        "error": None,
    }


def _storyboard(
    studio: StudioStore,
    mode: str,
    prompt: str,
    params: dict[str, Any],
    project_id: str | None,
) -> dict[str, Any]:
    if not project_id:
        return {
            "status": "needs_config",
            "result": {"note": "先生成或选择一个项目"},
            "error": None,
        }
    quality_name = str(params.get("quality") or "standard")
    quality = preset(quality_name)
    parts = [
        part.strip() for part in re.split(r"[。！？!?.\n]", prompt) if part.strip()
    ]
    parts = (parts or [prompt or "未命名镜头"])[: int(quality["scene_count"])]
    scenes = [
        {
            "index": index + 1,
            "shot": ["全景", "中景", "特写"][index % 3],
            "description": text,
            "duration": 3,
        }
        for index, text in enumerate(parts)
    ]
    asset = _save_json_asset(
        studio,
        project_id,
        "storyboard",
        {"mode": mode, "quality": quality_name, "scenes": scenes},
        {"provider": "local", "scenes": len(scenes), "quality": quality_name},
    )
    return {
        "status": "succeeded",
        "result": {
            "asset_id": asset["id"],
            "scene_count": len(scenes),
            "quality": quality_name,
            "note": "分镜已生成，可继续生成画面或调整镜头",
        },
        "error": None,
    }


async def _audio(
    studio: StudioStore,
    mode: str,
    prompt: str,
    params: dict[str, Any],
    project_id: str | None,
) -> dict[str, Any]:
    if mode != "tts":
        return {
            "status": "needs_config",
            "result": {"note": f"{mode} 需要接入云端语音 API"},
            "error": None,
        }
    if not project_id:
        return {
            "status": "needs_config",
            "result": {"note": "先生成或选择一个项目"},
            "error": None,
        }
    settings = get_settings()
    text = prompt.strip()
    script_id = str(params.get("script_id") or "")
    if script_id:
        script = studio.get_script(script_id)
        if script is not None:
            text = str(script.get("body") or "").strip() or text
    if not text:
        return {
            "status": "needs_config",
            "result": {"note": "TTS 需要一段可朗读的文案"},
            "error": None,
        }
    if settings.tts_provider == "edge":
        try:
            import edge_tts

            token = uuid.uuid4().hex[:10]
            filename = f"tts-{token}.mp3"
            storage_key = f"projects/{project_id}/assets/{filename}"
            output = studio.work_root / storage_key
            output.parent.mkdir(parents=True, exist_ok=True)
            voice = str(params.get("voice") or settings.tts_voice)
            rate = str(params.get("rate") or settings.tts_rate)
            await edge_tts.Communicate(
                text,
                voice,
                rate=rate,
            ).save(str(output))
            asset = studio.add_asset(
                project_id,
                filename,
                storage_key,
                output.stat().st_size,
                {
                    "provider": "edge-tts",
                    "voice": voice,
                    "rate": rate,
                    "text_chars": len(text),
                },
            )
            return {
                "status": "succeeded",
                "result": {
                    "asset_id": asset["id"],
                    "provider": "edge-tts",
                    "voice": voice,
                    "note": "Edge-TTS 配音已生成",
                },
                "error": None,
            }
        except ImportError:
            return {
                "status": "needs_config",
                "result": {
                    "note": "未安装 edge-tts，请执行 pip install edge-tts",
                },
                "error": None,
            }
        except Exception as exc:
            return {
                "status": "failed",
                "result": None,
                "error": f"Edge-TTS 配音失败：{type(exc).__name__}: {exc}",
            }
    asset = _save_wav_asset(studio, project_id)
    return {
        "status": "succeeded",
        "result": {
            "asset_id": asset["id"],
            "provider": "placeholder",
            "note": "本地静音占位，接入 TTS API 后替换",
        },
        "error": None,
    }


def _lora(
    studio: StudioStore,
    mode: str,
    prompt: str,
    params: dict[str, Any],
    project_id: str | None,
) -> dict[str, Any]:
    if not project_id:
        return {
            "status": "needs_config",
            "result": {"note": "先生成或选择一个项目"},
            "error": None,
        }
    dataset = [
        asset["id"]
        for asset in studio.list_assets(project_id)
        if asset["kind"] == "image"
    ]
    # TODO(api): submit this config to a GPU training service and store the
    # returned LoRA weights as a project asset.
    asset = _save_json_asset(
        studio,
        project_id,
        "lora",
        {
            "name": prompt or "style",
            "mode": mode,
            "dataset_assets": dataset,
            "note": "接入 GPU 训练服务后执行",
        },
        {"provider": "local", "dataset_size": len(dataset)},
    )
    style_id = str(params.get("style_id") or "")
    if style_id:
        studio.update_style(style_id, {"lora_status": "needs_config"})
    return {
        "status": "needs_config",
        "result": {
            "asset_id": asset["id"],
            "dataset_size": len(dataset),
            "note": "训练配置已生成，接入 GPU 训练服务后执行",
        },
        "error": None,
    }


def _asset_path(studio: StudioStore, asset: dict[str, Any]) -> Path | None:
    storage_key = str(asset.get("storage_key") or "")
    if not storage_key:
        return None
    root = studio.work_root.resolve()
    path = (root / storage_key).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        return None
    return path


async def _media_duration(path: Path) -> float:
    process = await asyncio.create_subprocess_exec(
        get_settings().ffmpeg_bin,
        "-hide_banner",
        "-i",
        str(path),
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


async def _render(
    studio: StudioStore,
    mode: str,
    prompt: str,
    params: dict[str, Any],
    project_id: str | None,
) -> dict[str, Any]:
    if not project_id:
        return {
            "status": "needs_config",
            "result": {"note": "先创建或选择一个项目"},
            "error": None,
        }
    project = studio.get_project(project_id) or {}
    aspect = str(project.get("aspect_ratio") or "9:16")
    width, height = RENDER_SIZES.get(aspect, RENDER_SIZES["9:16"])
    assets = studio.list_assets(project_id)
    by_id = {str(asset["id"]): asset for asset in assets}
    pipeline = params.get("pipeline")
    if not isinstance(pipeline, dict):
        pipeline = {}

    requested_images = [
        str(item)
        for item in pipeline.get("image_asset_ids") or []
        if str(item) in by_id
    ]
    if not requested_images:
        requested_images = [
            str(asset["id"])
            for asset in reversed(assets)
            if asset.get("kind") == "image"
            and not str(asset.get("filename") or "").lower().endswith(".svg")
        ][:6]

    images: list[Path] = []
    for asset_id in requested_images:
        path = _asset_path(studio, by_id[asset_id])
        if path is not None:
            images.append(path)
    if not images:
        return {
            "status": "needs_config",
            "result": {
                "note": "渲染需要先完成生图步骤；请保留流水线里的生图模块或先上传图片素材"
            },
            "error": None,
        }

    audio_path = None
    audio_id = str(pipeline.get("audio_asset_id") or "")
    audio_asset = by_id.get(audio_id)
    if audio_asset is not None and audio_asset.get("kind") == "audio":
        audio_path = _asset_path(studio, audio_asset)

    token = uuid.uuid4().hex[:10]
    filename = f"render-{token}.mp4"
    storage_key = f"projects/{project_id}/assets/{filename}"
    output = studio.work_root / storage_key
    output.parent.mkdir(parents=True, exist_ok=True)
    audio_duration = await _media_duration(audio_path) if audio_path is not None else 0.0
    scene_seconds = max(
        3,
        math.ceil(audio_duration / max(1, len(images))),
    )
    filter_parts = []
    command = [get_settings().ffmpeg_bin, "-y"]
    for index, image in enumerate(images):
        command.extend(["-loop", "1", "-t", str(scene_seconds), "-i", str(image)])
        filter_parts.append(
            f"[{index}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,"
            f"trim=duration={scene_seconds},setpts=PTS-STARTPTS[v{index}]"
        )
    filter_parts.append(
        "".join(f"[v{index}]" for index in range(len(images)))
        + f"concat=n={len(images)}:v=1:a=0[outv]"
    )
    audio_index = len(images)
    if audio_path is not None:
        command.extend(["-stream_loop", "-1", "-i", str(audio_path)])
    command.extend(["-filter_complex", ";".join(filter_parts), "-map", "[outv]"])
    if audio_path is not None:
        command.extend(
            [
                "-map",
                f"{audio_index}:a",
                "-af",
                "apad",
                "-c:a",
                "aac",
                "-b:a",
                "160k",
            ]
        )
    else:
        command.append("-an")
    command.extend(
        [
            "-r",
            "30",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-t",
            str(len(images) * scene_seconds),
            str(output),
        ]
    )
    try:
        await run_command(command, timeout=3600)
    except Exception as exc:
        return {
            "status": "failed",
            "result": None,
            "error": f"FFmpeg 渲染失败：{type(exc).__name__}: {exc}",
        }

    asset = studio.add_asset(
        project_id,
        filename,
        storage_key,
        output.stat().st_size,
        {
            "provider": "ffmpeg",
            "model": "ffmpeg",
            "mode": mode,
            "prompt": prompt,
            "width": width,
            "height": height,
            "images": len(images),
            "audio": audio_path is not None,
        },
    )
    return {
        "status": "succeeded",
        "result": {
            "asset_id": asset["id"],
            "filename": filename,
            "provider": "ffmpeg",
            "model": "ffmpeg",
            "width": width,
            "height": height,
            "duration": len(images) * scene_seconds,
            "images": len(images),
            "audio": audio_path is not None,
            "note": "FFmpeg 已合成 MP4，可在结果预览中播放或下载",
        },
        "error": None,
    }


def _manifest(
    studio: StudioStore,
    module: str,
    mode: str,
    prompt: str,
    params: dict[str, Any],
    project_id: str | None,
    integration: str,
) -> dict[str, Any]:
    if not project_id:
        return {
            "status": "needs_config",
            "result": {"note": "先生成或选择一个项目"},
            "error": None,
        }
    # TODO(api): dispatch to FFmpeg / batch scheduler and replace this manifest
    # with the real render result.
    asset = _save_json_asset(
        studio,
        project_id,
        module,
        {
            "module": module,
            "mode": mode,
            "prompt": prompt,
            "params": params,
            "note": f"接入 {integration} 后执行",
        },
        {"provider": "local", "integration": integration},
    )
    return {
        "status": "needs_config",
        "result": {
            "asset_id": asset["id"],
            "note": f"任务配置已生成，接入 {integration} 后执行",
        },
        "error": None,
    }


async def execute_module(
    studio: StudioStore,
    module: str,
    mode: str,
    prompt: str,
    params: dict[str, Any],
    project_id: str | None,
) -> dict[str, Any]:
    if module == "copywriting":
        return await _copywriting(studio, mode, prompt, params, project_id)
    if module == "image":
        return await _image(studio, mode, prompt, params, project_id)
    if module == "storyboard":
        return _storyboard(studio, mode, prompt, params, project_id)
    if module == "audio":
        return await _audio(studio, mode, prompt, params, project_id)
    if module == "lora":
        return _lora(studio, mode, prompt, params, project_id)
    if module == "render":
        return await _render(studio, mode, prompt, params, project_id)
    if module == "batch":
        return _manifest(
            studio,
            module,
            mode,
            prompt,
            params,
            project_id,
            "批量调度器",
        )
    return {
        "status": "needs_config",
        "result": {"note": f"{module} 执行器待接入"},
        "error": None,
    }


async def execute_module_job(
    studio: StudioStore,
    job: dict[str, Any],
    credits: CreditService | None = None,
) -> None:
    tenant_id = str(job.get("tenant_id") or "demo")
    try:
        outcome = await execute_module(
            studio,
            str(job["module"]),
            str(job["mode"]),
            str(job["prompt"]),
            dict(job.get("params") or {}),
            job.get("project_id"),
        )
    except Exception as exc:
        studio.update_job(
            job["id"],
            "failed",
            None,
            f"{type(exc).__name__}: {exc}",
        )
        if credits is not None:
            credits.refund_ref(tenant_id, "module_job", job["id"])
        return
    studio.update_job(
        job["id"],
        str(outcome["status"]),
        outcome.get("result"),
        outcome.get("error"),
    )
    if credits is not None:
        if outcome["status"] == "failed":
            credits.refund_ref(tenant_id, "module_job", job["id"])
        else:
            credits.settle_ref(tenant_id, "module_job", job["id"])


async def execute_pipeline(
    studio: StudioStore,
    pipeline: dict[str, Any],
    credits: CreditService | None = None,
) -> None:
    steps = list(pipeline["steps"])
    tenant_id = str(pipeline.get("tenant_id") or "demo")
    warning = False
    context: dict[str, Any] = {
        "script_id": "",
        "storyboard_asset_id": "",
        "image_asset_ids": [],
        "audio_asset_id": "",
    }

    for step in steps:
        if step["status"] not in {"queued", "running"}:
            continue
        step["status"] = "running"
        studio.update_pipeline(pipeline["id"], "running", steps)
        try:
            if step["module"] == "render":
                step_params = {"pipeline": dict(context)}
            elif step["module"] == "audio":
                step_params = {"script_id": context.get("script_id", "")}
            else:
                step_params = {}
            outcome = await execute_module(
                studio,
                str(step["module"]),
                str(step["mode"]),
                str(step["prompt"]),
                step_params,
                pipeline.get("project_id"),
            )
        except Exception as exc:
            step["status"] = "failed"
            step["error"] = f"{type(exc).__name__}: {exc}"
            step["result"] = {"error": step["error"]}
            studio.update_pipeline(pipeline["id"], "failed", steps)
            if credits is not None:
                credits.refund_ref(tenant_id, "pipeline", pipeline["id"])
            return

        step["status"] = str(outcome["status"])
        step["result"] = outcome.get("result")
        step["error"] = outcome.get("error")
        result = outcome.get("result")
        if isinstance(result, dict):
            if step["module"] == "copywriting":
                context["script_id"] = str(result.get("script_id") or "")
            elif step["module"] == "storyboard":
                context["storyboard_asset_id"] = str(result.get("asset_id") or "")
            elif step["module"] == "image":
                for candidate in result.get("candidates") or []:
                    if isinstance(candidate, dict) and candidate.get("asset_id"):
                        asset_id = str(candidate["asset_id"])
                        if asset_id not in context["image_asset_ids"]:
                            context["image_asset_ids"].append(asset_id)
                asset_id = str(result.get("asset_id") or "")
                if asset_id and asset_id not in context["image_asset_ids"]:
                    context["image_asset_ids"].append(asset_id)
            elif step["module"] == "audio":
                context["audio_asset_id"] = str(result.get("asset_id") or "")
        if step["status"] == "failed":
            studio.update_pipeline(pipeline["id"], "failed", steps)
            if credits is not None:
                credits.refund_ref(tenant_id, "pipeline", pipeline["id"])
            return
        if step["status"] == "needs_config":
            warning = True
        studio.update_pipeline(pipeline["id"], "running", steps)

    studio.update_pipeline(
        pipeline["id"],
        "needs_config" if warning else "succeeded",
        steps,
    )
    if credits is not None:
        credits.settle_ref(tenant_id, "pipeline", pipeline["id"])
