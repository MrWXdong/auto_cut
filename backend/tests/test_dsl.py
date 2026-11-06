from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.workflow.dsl import EdgeDef, NodeDef, WorkflowDef


def make_workflow(**overrides) -> WorkflowDef:
    payload = {
        "id": "wf_demo",
        "name": "demo",
        "nodes": [
            {"id": "start", "type": "start"},
            {"id": "probe", "type": "media.probe", "inputs": {"path": "{{start.source}}"}},
            {"id": "end", "type": "end"},
        ],
        "edges": [
            {"source": "start", "target": "probe"},
            {"source": "probe", "target": "end"},
        ],
    }
    payload.update(overrides)
    return WorkflowDef.from_dict(payload)


def test_builds_and_orders_nodes() -> None:
    workflow = make_workflow()
    assert [node.id for node in workflow.topological_order()] == ["start", "probe", "end"]
    assert len(workflow.incoming_edges("probe")) == 1
    assert len(workflow.outgoing_edges("probe")) == 1


def test_default_inputs_are_extracted() -> None:
    workflow = make_workflow(
        inputs=[
            {"name": "source", "type": "video"},
            {"name": "max_clips", "type": "number", "default": 5},
        ]
    )
    assert workflow.default_inputs() == {"max_clips": 5}
    with pytest.raises(ValueError, match="missing required inputs"):
        workflow.validate_inputs({})
    workflow.validate_inputs({"source": "in.mp4"})


def test_rejects_duplicate_node_ids() -> None:
    with pytest.raises(ValidationError, match="duplicate node"):
        make_workflow(
            nodes=[
                {"id": "start", "type": "start"},
                {"id": "start", "type": "end"},
            ],
            edges=[],
        )


def test_rejects_edge_to_unknown_node() -> None:
    with pytest.raises(ValidationError, match="unknown target"):
        make_workflow(edges=[{"source": "start", "target": "missing"}])


def test_rejects_cycle() -> None:
    with pytest.raises(ValidationError, match="cycle"):
        make_workflow(
            nodes=[
                {"id": "start", "type": "start"},
                {"id": "a", "type": "logic.condition"},
                {"id": "b", "type": "logic.condition"},
                {"id": "end", "type": "end"},
            ],
            edges=[
                {"source": "start", "target": "a"},
                {"source": "a", "target": "b"},
                {"source": "b", "target": "a"},
                {"source": "b", "target": "end"},
            ],
        )


def test_requires_exactly_one_start() -> None:
    with pytest.raises(ValidationError, match="exactly one start"):
        make_workflow(nodes=[{"id": "end", "type": "end"}], edges=[])


def test_start_cannot_have_incoming_edges() -> None:
    with pytest.raises(ValidationError, match="start node cannot have incoming"):
        make_workflow(
            edges=[
                {"source": "probe", "target": "start"},
                {"source": "start", "target": "end"},
            ]
        )


def test_edge_defaults() -> None:
    edge = EdgeDef(source="a", target="b")
    assert edge.source_port == "out"
    assert edge.target_port == "in"


def test_node_defaults() -> None:
    node = NodeDef(id="a", type="start")
    assert node.join == "all"
    assert node.inputs == {}
    assert node.config == {}
