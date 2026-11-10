from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import imageio_ffmpeg
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_ffmpeg_bin() -> str:
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AUTOCUT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "云流影"
    environment: str = "dev"
    demo_mode: bool = True
    work_root: Path = Path("work")
    database_path: Path = Path("work/autocut.db")
    max_upload_mb: int = 2048
    max_concurrency: int = 2
    ffmpeg_bin: str = Field(default_factory=_default_ffmpeg_bin)
    ffprobe_bin: str = "ffprobe"
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    image_base_url: str = ""
    image_api_key: str = ""
    image_model: str = "cogview-3-flash"
    doubao_image_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    doubao_image_model: str = "doubao-seedream-5-0-flash-260915"
    doubao_thinking: bool = False
    deepseek_api_key: str = ""
    qwen_api_key: str = ""
    doubao_api_key: str = ""
    zhipu_api_key: str = ""
    moonshot_api_key: str = ""
    asr_provider: str = "cloud"
    asr_base_url: str = ""
    asr_api_key: str = ""
    asr_model: str = ""
    asr_local_model: str = "small"
    tts_provider: str = "edge"
    tts_voice: str = "zh-CN-XiaoxiaoNeural"
    tts_rate: str = "+0%"
    embedding_provider: str = "cloud"
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = ""
    rag_token_budget: int = 1200
    trend_auto_refresh: bool = True
    trend_refresh_interval_seconds: int = 3600
    trend_ttl_seconds: int = 300
    trend_retention_days: int = 90
    object_storage_backend: str = "local"
    s3_endpoint_url: str = ""
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "auto"
    s3_prefix: str = "autocut"
    s3_path_style: bool = True
    s3_presign_seconds: int = 3600
    asset_import_max_mb: int = 500
    sms_provider: str = ""
    sms_access_key_id: str = ""
    sms_access_key_secret: str = ""
    sms_sign_name: str = ""
    sms_template_code: str = ""
    wechat_app_id: str = ""
    wechat_app_secret: str = ""
    wechat_redirect_uri: str = ""
    auth_secret: str = "dev-secret-change-me"
    platform_admin_email: str = "admin@local"
    platform_admin_password: str = "admin"
    seed_demo_tenant: bool = True
    payment_webhook_secret: str = ""

    def provider_api_key(self, provider: str) -> str:
        return {
            "deepseek": self.deepseek_api_key,
            "qwen": self.qwen_api_key,
            "doubao": self.doubao_api_key,
            "zhipu": self.zhipu_api_key,
            "moonshot": self.moonshot_api_key,
        }.get(provider, "")


@lru_cache
def get_settings() -> Settings:
    return Settings()
