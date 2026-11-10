from __future__ import annotations

import pytest

from app.gateway.base import ChatMessage, ChatResult
from app.skills.prompt import PromptSkill


class FakeChat:
    def __init__(self) -> None:
        self.calls = 0
        self.messages: list[ChatMessage] = []

    async def chat(self, messages: list[ChatMessage], **options) -> ChatResult:
        self.calls += 1
        self.messages = messages
        return ChatResult(text="真实模型输出", model="fake-model")


@pytest.mark.asyncio
async def test_prompt_skill_uses_model_when_available() -> None:
    chat = FakeChat()
    result = await PromptSkill(chat).run(
        {},
        {"product": "面膜", "platform": "抖音", "style": "口播"},
    )
    assert result["prompt"] == "真实模型输出"
    assert result["shell"] is False
    assert result["model"] == "fake-model"
    assert chat.calls == 1


@pytest.mark.asyncio
async def test_prompt_skill_falls_back_to_template() -> None:
    result = await PromptSkill().run(
        {},
        {"product": "面膜", "platform": "小红书", "style": "测评"},
    )
    assert result["shell"] is True
    assert "面膜" in result["prompt"]


@pytest.mark.asyncio
async def test_prompt_skill_includes_creative_brief() -> None:
    chat = FakeChat()
    await PromptSkill(chat).run(
        {},
        {
            "product": "燕云十六声",
            "platform": "抖音",
            "style": "热血燃向",
            "brief": "面向新玩家，重点讲具体玩法，不要空泛口号",
            "task": "script",
        },
    )
    assert "面向新玩家，重点讲具体玩法" in chat.messages[-1].content
