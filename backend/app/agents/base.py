from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class Intent(str, Enum):
    PROMPT = "prompt.generate"
    VIDEO = "video.generate"
    SUBTITLE = "subtitle.generate"
    KNOWLEDGE = "knowledge.answer"
    CHAT = "chat"


@dataclass
class IntentResult:
    intent: Intent
    confidence: float = 0.0
    slots: dict[str, Any] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)


@dataclass
class Plan:
    skill: str
    workflow: str | None = None
    inputs: dict[str, Any] = field(default_factory=dict)


class Skill(Protocol):
    name: str

    async def run(self, ctx: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]: ...
