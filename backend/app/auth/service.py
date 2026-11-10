from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from app.auth.store import AuthStore
from app.config import Settings

PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")
DEMO_CODE = "123456"
DemoUser: dict[str, Any] = {
    "id": "demo",
    "email": "demo@local",
    "name": "Demo Owner",
    "role": "owner",
    "plan": "trial",
}


class AuthService:
    def __init__(self, store: AuthStore, settings: Settings) -> None:
        self._store = store
        self._settings = settings

    @property
    def sms_ready(self) -> bool:
        return self._settings.demo_mode or bool(
            self._settings.sms_provider
            and self._settings.sms_access_key_id
            and self._settings.sms_sign_name
            and self._settings.sms_template_code
        )

    @property
    def wechat_ready(self) -> bool:
        return bool(
            self._settings.wechat_app_id
            and self._settings.wechat_app_secret
            and self._settings.wechat_redirect_uri
        )

    def methods(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "password",
                "name": "账号密码",
                "enabled": True,
                "reason": "",
            },
            {
                "id": "sms",
                "name": "手机验证码",
                "enabled": self.sms_ready,
                "reason": "" if self.sms_ready else "未配置短信服务",
            },
            {
                "id": "wechat",
                "name": "微信扫码",
                "enabled": self.wechat_ready,
                "reason": "" if self.wechat_ready else "未配置微信开放平台",
            },
        ]

    def send_sms(self, phone: str) -> dict[str, Any]:
        phone = phone.strip()
        if not PHONE_PATTERN.match(phone):
            raise ValueError("手机号格式不正确")
        if not self.sms_ready:
            raise NotImplementedError("短信服务未配置")
        if not self._settings.demo_mode:
            raise NotImplementedError("短信供应商适配器待接入")

        self._store.save_code(phone, DEMO_CODE, ttl_seconds=300)
        return {"status": "sent", "demo_code": DEMO_CODE, "expires_in": 300}

    def verify_sms(self, phone: str, code: str) -> dict[str, Any]:
        phone = phone.strip()
        code = code.strip()
        if not PHONE_PATTERN.match(phone):
            raise ValueError("手机号格式不正确")
        row = self._store.get_code(phone)
        if row is None:
            raise ValueError("请先获取验证码")
        if datetime.fromisoformat(row["expires_at"]) < datetime.now(UTC):
            self._store.delete_code(phone)
            raise ValueError("验证码已过期")
        if row["attempts"] >= 5:
            self._store.delete_code(phone)
            raise ValueError("验证码错误次数过多，请重新获取")
        if not secrets.compare_digest(row["code"], code):
            self._store.increment_attempts(phone)
            raise ValueError("验证码错误")

        self._store.delete_code(phone)
        return {
            "access_token": secrets.token_urlsafe(24),
            "token_type": "bearer",
            "user": DemoUser,
        }

    def wechat_authorize_url(self) -> str:
        if not self.wechat_ready:
            raise NotImplementedError("微信开放平台未配置")
        state = secrets.token_urlsafe(16)
        query = urlencode(
            {
                "appid": self._settings.wechat_app_id,
                "redirect_uri": self._settings.wechat_redirect_uri,
                "response_type": "code",
                "scope": "snsapi_login",
                "state": state,
            }
        )
        return f"https://open.weixin.qq.com/connect/qrconnect?{query}#wechat_redirect"
