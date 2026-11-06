from __future__ import annotations

from app.core.workflow.registry import NodeRegistry
from app.nodes import register_nodes


def build_registry() -> NodeRegistry:
    registry = NodeRegistry()
    register_nodes(registry)
    return registry
