from __future__ import annotations

from app.agents.base import Intent, IntentResult, Plan

KEYWORDS: dict[Intent, tuple[str, ...]] = {
    Intent.SUBTITLE: ("字幕", "srt", "转写", "听写"),
    Intent.PROMPT: ("提示词", "脚本", "分镜", "文案", "prompt"),
    Intent.VIDEO: ("视频", "剪辑", "切片", "成片", "混剪", "卡点"),
    Intent.KNOWLEDGE: ("知识库", "资料", "文档", "品牌规范", "根据我的"),
}


class RuleBasedIntentRouter:
    """Deterministic fallback used when no model is configured."""

    async def detect(self, text: str) -> IntentResult:
        normalized = text.lower()
        scores = {
            intent: sum(1 for keyword in keywords if keyword in normalized)
            for intent, keywords in KEYWORDS.items()
        }
        best, hits = max(scores.items(), key=lambda item: item[1])
        total = sum(scores.values())
        if hits == 0 or total == 0:
            return IntentResult(Intent.CHAT, 0.3)
        return IntentResult(
            best,
            confidence=round(min(0.95, 0.45 + hits / total * 0.5), 2),
        )


class AgentRouter:
    def __init__(self, intent_router: RuleBasedIntentRouter | None = None) -> None:
        self._intent_router = intent_router or RuleBasedIntentRouter()

    async def detect(self, text: str) -> IntentResult:
        return await self._intent_router.detect(text)

    def plan(self, result: IntentResult) -> Plan:
        mapping = {
            Intent.PROMPT: Plan(skill="prompt.generate"),
            Intent.VIDEO: Plan(skill="video.generate", workflow="clip"),
            Intent.SUBTITLE: Plan(skill="subtitle.generate", workflow="subtitle"),
            Intent.KNOWLEDGE: Plan(skill="knowledge.answer"),
            Intent.CHAT: Plan(skill="chat"),
        }
        return mapping[result.intent]
