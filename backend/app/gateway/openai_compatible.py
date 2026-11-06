from __future__ import annotations

from typing import Any

import httpx

from app.gateway.base import ChatMessage, ChatResult, EndpointConfig

ALLOWED_OPTIONS = {"temperature", "top_p", "max_tokens", "stop", "presence_penalty"}


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

        headers = {"Content-Type": "application/json"}
        if self.endpoint.api_key:
            headers["Authorization"] = f"Bearer {self.endpoint.api_key}"

        async with httpx.AsyncClient(
            base_url=self.endpoint.base_url.rstrip("/"),
            timeout=self.endpoint.timeout_s,
        ) as client:
            response = await client.post("/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        return ChatResult(
            text=data["choices"][0]["message"]["content"],
            model=self.endpoint.model,
            usage=data.get("usage") or {},
        )
