from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .events import NodeEvent


@dataclass
class RunContext:
    job_id: str
    work_dir: Path
    params: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    events: list[NodeEvent] = field(default_factory=list)
    on_event: Callable[[NodeEvent], Awaitable[None]] | None = None

    def resolve_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return (self.work_dir / path).resolve()

    async def emit(self, event: NodeEvent) -> None:
        self.events.append(event)
        if self.on_event is not None:
            await self.on_event(event)
