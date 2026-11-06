from __future__ import annotations

from .node import Node


class NodeRegistry:
    def __init__(self) -> None:
        self._types: dict[str, type[Node]] = {}

    def register(self, node_cls: type[Node]) -> type[Node]:
        if not issubclass(node_cls, Node):
            raise TypeError(f"{node_cls!r} is not a Node subclass")
        node_type = getattr(node_cls, "type", "")
        if not node_type:
            raise ValueError(f"{node_cls.__name__} must define a non-empty type")
        if node_type in self._types:
            raise ValueError(f"duplicate node type: {node_type}")
        self._types[node_type] = node_cls
        return node_cls

    def create(self, node_type: str) -> Node:
        try:
            node_cls = self._types[node_type]
        except KeyError:
            raise KeyError(f"unknown node type: {node_type}") from None
        return node_cls()

    def types(self) -> list[str]:
        return sorted(self._types)
