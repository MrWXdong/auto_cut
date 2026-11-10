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
        brief = str(inputs.get("brief") or "").strip()
        task = str(inputs.get("task") or "prompt")

        if self._chat is None:
            if task == "script":
                return {
                    "prompt": (
                        f"【口播稿】\n"
                        f"今天想和你聊聊{product}。\n"
                        f"如果你也在寻找更省心、更稳定的选择，可以先看这三点："
                        f"第一，它适合{platform}用户的真实使用场景；"
                        f"第二，使用方式简单，不需要复杂准备；"
                        f"第三，整体风格保持{style}，信息清楚、重点明确。\n"
                        "如果你感兴趣，可以先收藏，再按自己的需求进一步了解。"
                    ),
                    "shell": True,
                    "model": None,
                }
            return {
                "prompt": (
                    f"{platform} {style}短视频，主题：{product}。"
                    "前 3 秒抛钩子，中段讲清一个核心卖点，结尾给行动指令。"
                ),
                "shell": True,
                "model": None,
            }

        if task == "script":
            result = await self._chat.chat(
                [
                    ChatMessage(
                        role="system",
                        content=(
                            "你是资深短视频口播编剧。只输出可直接配音的口播文案，"
                            "不要输出分镜、镜头说明、画面提示词、标题、标签或解释。"
                            "不要用【】小标题、不要写多段口号、不要空泛排比。"
                            "开头 3 秒必须有具体钩子，中段只讲 2-3 个具体信息点，"
                            "结尾给自然的行动引导。"
                        ),
                    ),
                    ChatMessage(
                        role="user",
                        content=(
                            f"平台：{platform}\n风格：{style}\n产品：{product}\n"
                            f"用户创作需求：{brief or '无特别要求'}\n"
                            "请输出一篇完整的 30-60 秒口播稿，按自然段组织，"
                            "语言适合直接朗读。必须优先满足用户创作需求；"
                            "宁可少讲一点，也不要堆口号、形容词和空泛排比。"
                        ),
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
