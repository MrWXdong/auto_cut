from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NodeEvent:
    job_id: str
    node_id: str
    node_type: str
    status: str
    attempt: int = 1
    duration_ms: int | None = None
    error: str | None = None
    outputs: dict[str, Any] | None = None
    timestamp: float = field(default_factory=time.time)
