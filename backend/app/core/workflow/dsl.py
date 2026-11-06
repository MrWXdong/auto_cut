from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator

PortType = Literal[
    "string",
    "number",
    "boolean",
    "json",
    "video",
    "audio",
    "image",
    "file",
    "any",
]


class PortSpec(BaseModel):
    name: str = "out"
    type: PortType = "any"
    required: bool = True
    description: str = ""


class InputDef(BaseModel):
    name: str
    type: PortType = "string"
    required: bool = True
    default: Any = None
    description: str = ""


class VariableDef(BaseModel):
    name: str
    type: PortType = "json"
    default: Any = None


class NodeDef(BaseModel):
    id: str
    type: str
    title: str = ""
    inputs: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    join: Literal["all", "any"] = "all"


class EdgeDef(BaseModel):
    source: str
    source_port: str = "out"
    target: str
    target_port: str = "in"


class WorkflowDef(BaseModel):
    id: str
    name: str
    version: int = Field(default=1, ge=1)
    status: Literal["draft", "published"] = "draft"
    description: str = ""
    inputs: list[InputDef] = Field(default_factory=list)
    variables: list[VariableDef] = Field(default_factory=list)
    nodes: list[NodeDef] = Field(default_factory=list)
    edges: list[EdgeDef] = Field(default_factory=list)
    outputs: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> WorkflowDef:
        return cls.model_validate(raw)

    @classmethod
    def from_yaml(cls, path: Path) -> WorkflowDef:
        with path.open("r", encoding="utf-8") as handle:
            return cls.from_dict(yaml.safe_load(handle) or {})

    @model_validator(mode="after")
    def validate_graph(self) -> WorkflowDef:
        if not self.id.strip():
            raise ValueError("workflow id is required")
        if not self.name.strip():
            raise ValueError("workflow name is required")
        if not self.nodes:
            raise ValueError("workflow must contain at least one node")
        self._assert_unique("input", [item.name for item in self.inputs])
        self._assert_unique("variable", [item.name for item in self.variables])
        self._assert_unique("node", [node.id for node in self.nodes])

        starts = [node for node in self.nodes if node.type == "start"]
        ends = [node for node in self.nodes if node.type == "end"]
        if len(starts) != 1:
            raise ValueError("workflow must contain exactly one start node")
        if not ends:
            raise ValueError("workflow must contain at least one end node")

        node_ids = {node.id for node in self.nodes}
        incoming: set[str] = set()
        outgoing: set[str] = set()
        for edge in self.edges:
            if edge.source not in node_ids:
                raise ValueError(f"edge references unknown source node: {edge.source}")
            if edge.target not in node_ids:
                raise ValueError(f"edge references unknown target node: {edge.target}")
            if edge.source == edge.target:
                raise ValueError(f"node {edge.source} cannot connect to itself")
            outgoing.add(edge.source)
            incoming.add(edge.target)

        if starts[0].id in incoming:
            raise ValueError("start node cannot have incoming edges")
        for node in ends:
            if node.id in outgoing:
                raise ValueError(f"end node {node.id} cannot have outgoing edges")

        self.topological_order()
        return self

    @staticmethod
    def _assert_unique(kind: str, names: list[str]) -> None:
        seen: set[str] = set()
        for name in names:
            if name in seen:
                raise ValueError(f"duplicate {kind} name: {name}")
            seen.add(name)

    def topological_order(self) -> list[NodeDef]:
        by_id = {node.id: node for node in self.nodes}
        indegree = {node.id: 0 for node in self.nodes}
        children: dict[str, list[str]] = {node.id: [] for node in self.nodes}
        for edge in self.edges:
            indegree[edge.target] += 1
            children[edge.source].append(edge.target)

        queue = [node.id for node in self.nodes if indegree[node.id] == 0]
        ordered: list[NodeDef] = []
        while queue:
            current = queue.pop(0)
            ordered.append(by_id[current])
            for child in children[current]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)

        if len(ordered) != len(self.nodes):
            raise ValueError("workflow contains a cycle")
        return ordered

    def incoming_edges(self, node_id: str) -> list[EdgeDef]:
        return [edge for edge in self.edges if edge.target == node_id]

    def outgoing_edges(self, node_id: str) -> list[EdgeDef]:
        return [edge for edge in self.edges if edge.source == node_id]

    def default_inputs(self) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for item in self.inputs:
            if item.default is not None:
                values[item.name] = item.default
        return values

    def validate_inputs(self, values: dict[str, Any]) -> None:
        missing = [
            item.name
            for item in self.inputs
            if item.required and item.name not in values and item.default is None
        ]
        if missing:
            raise ValueError(f"missing required inputs: {', '.join(missing)}")
