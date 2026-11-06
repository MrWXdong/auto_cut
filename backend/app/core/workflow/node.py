from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar

from .context import RunContext


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 1
    initial_delay: float = 2.0
    max_delay: float = 30.0


class Node(ABC):
    """A reusable step in a workflow.

    Nodes receive a JSON-serialisable input dict with three keys:
    ``params`` (static YAML parameters), ``upstream`` (outputs keyed by node id)
    and ``data`` (all upstream outputs merged for convenience).
    """

    type: ClassVar[str] = ""
    retry: ClassVar[RetryPolicy] = RetryPolicy()

    @abstractmethod
    async def run(self, ctx: RunContext, inputs: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
