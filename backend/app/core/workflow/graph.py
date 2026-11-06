from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .errors import WorkflowValidationError


@dataclass(frozen=True)
class NodeSpec:
    id: str
    type: str
    params: dict[str, Any] = field(default_factory=dict)
    needs: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkflowSpec:
    name: str
    version: str = "1"
    description: str = ""
    nodes: tuple[NodeSpec, ...] = ()

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> WorkflowSpec:
        if not isinstance(raw, dict):
            raise WorkflowValidationError("workflow definition must be a mapping")
        raw_nodes = raw.get("nodes") or []
        nodes = tuple(
            NodeSpec(
                id=str(item["id"]),
                type=str(item["type"]),
                params=dict(item.get("params") or {}),
                needs=tuple(str(dep) for dep in (item.get("needs") or ())),
            )
            for item in raw_nodes
        )
        return cls(
            name=str(raw.get("name") or ""),
            version=str(raw.get("version") or "1"),
            description=str(raw.get("description") or ""),
            nodes=nodes,
        )

    @classmethod
    def from_yaml(cls, path: Path) -> WorkflowSpec:
        with path.open("r", encoding="utf-8") as handle:
            return cls.from_dict(yaml.safe_load(handle) or {})

    def validate(self) -> None:
        if not self.name:
            raise WorkflowValidationError("workflow name is required")
        if not self.nodes:
            raise WorkflowValidationError("workflow must contain at least one node")

        known: set[str] = set()
        for spec in self.nodes:
            if not spec.id:
                raise WorkflowValidationError("node id is required")
            if spec.id in known:
                raise WorkflowValidationError(f"duplicate node id: {spec.id}")
            if not spec.type:
                raise WorkflowValidationError(f"node {spec.id} has no type")
            known.add(spec.id)

        for spec in self.nodes:
            for dep in spec.needs:
                if dep == spec.id:
                    raise WorkflowValidationError(f"node {spec.id} cannot depend on itself")
                if dep not in known:
                    raise WorkflowValidationError(
                        f"node {spec.id} depends on unknown node: {dep}"
                    )

        self.levels()

    def levels(self) -> list[list[NodeSpec]]:
        """Group nodes into topological levels; nodes in a level can run together."""
        by_id = {spec.id: spec for spec in self.nodes}
        order = [spec.id for spec in self.nodes]
        indegree = {spec.id: len(spec.needs) for spec in self.nodes}
        children: dict[str, list[str]] = {spec.id: [] for spec in self.nodes}

        for spec in self.nodes:
            for dep in spec.needs:
                if dep in by_id:
                    children[dep].append(spec.id)

        current = [node_id for node_id in order if indegree[node_id] == 0]
        levels: list[list[NodeSpec]] = []
        visited = 0

        while current:
            levels.append([by_id[node_id] for node_id in current])
            visited += len(current)
            ready: set[str] = set()
            for node_id in current:
                for child in children[node_id]:
                    indegree[child] -= 1
                    if indegree[child] == 0:
                        ready.add(child)
            current = [node_id for node_id in order if node_id in ready]

        if visited != len(self.nodes):
            raise WorkflowValidationError("workflow contains a cycle")
        return levels
