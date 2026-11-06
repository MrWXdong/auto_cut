from __future__ import annotations

from typing import Any

from app.gateway.base import ChatMessage, ChatModel


class PromptSkill:
    name = "prompt.generate"

    def __init__(self, chat: ChatModel | None = None) -> None:
        self._chat = chat

    async def run(self, ctx: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
        product = str(inputs.get("product") or "产品")
        platform = str(inputs.get("platform") or "抖音")
        style = str(inputs.get("style") or "口播")

        if self._chat is None:
            return {
                "prompt": (
                    f"{platform} {style}短视频，主题：{product}。"
                    "前 3 秒抛钩子，中段讲清一个核心卖点，结尾给行动指令。"
                ),
                "shell": True,
                "model": None,
            }

        result = await self._chat.chat(
            [
                ChatMessage(
                    role="system",
                    content="你是资深短视频编导，输出可直接拍摄的提示词和分镜。",
                ),
                ChatMessage(
                    role="user",
                    content=f"平台：{platform}\n风格：{style}\n产品：{product}",
                ),
            ],
            temperature=0.6,
        )
        return {
            "prompt": result.text,
            "shell": False,
            "model": result.model,
            "usage": result.usage,
        }
