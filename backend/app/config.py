from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AUTOCUT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AutoCut"
    environment: str = "dev"
    demo_mode: bool = True
    work_root: Path = Path("work")
    database_path: Path = Path("work/autocut.db")
    max_upload_mb: int = 2048
    max_concurrency: int = 2
    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    asr_model: str = "small"


@lru_cache
def get_settings() -> Settings:
    return Settings()
