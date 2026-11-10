from __future__ import annotations

from typing import Any

import httpx

from app.gateway.base import ChatMessage, ChatResult, EndpointConfig

ALLOWED_OPTIONS = {
    "temperature",
    "top_p",
    "max_tokens",
    "stop",
    "presence_penalty",
    "thinking",
}


def _provider_error_message(
    provider: str,
    model: str,
    status_code: int,
    code: str,
    message: str,
) -> str:
    if code == "ModelNotOpen":
        return (
            f"{provider} 模型 {model} 尚未开通。请到对应平台控制台开通模型，"
            "或改用已创建的推理接入点 ID。"
        )
    if code == "InvalidEndpointOrModel.NotFound":
        return (
            f"{provider} 模型或接入点 {model} 不存在或无权限，请检查模型 ID / ep-... 接入点。"
        )
    if code in {"AuthenticationError", "InvalidApiKey", "InvalidAuthentication"}:
        return f"{provider} API Key 无效，请重新检查密钥配置。"
    detail = f"：{message}" if message else ""
    return f"{provider} 调用失败（HTTP {status_code}，{code or 'unknown'}）{detail}"


class OpenAICompatibleChat:
    """Works with DeepSeek, Qwen, Doubao, GLM, Moonshot and similar providers."""

    def __init__(self, endpoint: EndpointConfig) -> None:
        self.endpoint = endpoint

    async def chat(self, messages: list[ChatMessage], **options: Any) -> ChatResult:
        payload: dict[str, Any] = {
            "model": self.endpoint.model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
            "temperature": 0.3,
        }
        for key, value in options.items():
            if key in ALLOWED_OPTIONS:
                payload[key] = value
        if "thinking" not in payload:
            thinking = self.endpoint.meta.get("thinking")
            if thinking:
                payload["thinking"] = (
                    thinking
                    if isinstance(thinking, dict)
                    else {"type": str(thinking)}
                )

        headers = {"Content-Type": "application/json"}
        if self.endpoint.api_key:
            headers["Authorization"] = f"Bearer {self.endpoint.api_key}"

        async with httpx.AsyncClient(
            base_url=self.endpoint.base_url.rstrip("/"),
            timeout=self.endpoint.timeout_s,
        ) as client:
            response = await client.post("/chat/completions", headers=headers, json=payload)
            if response.status_code >= 400:
                try:
                    error = (response.json() or {}).get("error") or {}
                except ValueError:
                    error = {}
                code = str(error.get("code") or "")
                message = str(error.get("message") or response.text or "")[:500]
                raise ValueError(
                    _provider_error_message(
                        self.endpoint.provider,
                        self.endpoint.model,
                        response.status_code,
                        code,
                        message,
                    )
                )
            data = response.json()

        return ChatResult(
            text=data["choices"][0]["message"]["content"],
            model=self.endpoint.model,
            usage=data.get("usage") or {},
        )
