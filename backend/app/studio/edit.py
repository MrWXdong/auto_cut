from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

from app.config import Settings


def edit_capabilities(settings: Settings) -> dict[str, object]:
    """Report what the automatic editing pipeline can actually run."""
    ffmpeg_ready = (
        Path(settings.ffmpeg_bin).is_file()
        or shutil.which(settings.ffmpeg_bin) is not None
    )
    llm_ready = bool(settings.llm_api_key)
    if settings.asr_provider.lower() == "local":
        asr_ready = importlib.util.find_spec("faster_whisper") is not None
    else:
        asr_ready = bool(settings.asr_api_key or settings.llm_api_key) and bool(
            settings.asr_base_url or settings.llm_base_url
        )
    ai_ready = ffmpeg_ready and llm_ready and asr_ready
    if not ffmpeg_ready:
        reason = "FFmpeg 未就绪"
    elif not llm_ready:
        reason = "LLM 未配置"
    elif not asr_ready:
        reason = "ASR 未配置"
    else:
        reason = "AI 自动剪辑可用：语音转写 + 大模型选高光"
    return {
        "ai_ready": ai_ready,
        "rule_ready": True,
        "ffmpeg": ffmpeg_ready,
        "asr": asr_ready,
        "llm": llm_ready,
        "asr_options": [
            {
                "provider": "cloud",
                "model": settings.asr_model or "glm-asr-2512",
                "label": "智谱 GLM-ASR（云端）",
                "ready": asr_ready,
            },
            {
                "provider": "local",
                "model": settings.asr_local_model,
                "label": f"本地 Whisper {settings.asr_local_model}",
                "ready": importlib.util.find_spec("faster_whisper") is not None,
            },
        ],
        "reason": reason if ai_ready else f"{reason}，当前使用规则切片",
    }


def choose_workflow(settings: Settings) -> tuple[str, str]:
    """Return (workflow name, mode label)."""
    if edit_capabilities(settings)["ai_ready"]:
        return "clip", "ai"
    return "quick_cut", "rule"
