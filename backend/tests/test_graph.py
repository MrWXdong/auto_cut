from __future__ import annotations

from pathlib import Path

import pytest

from app.core.workflow.errors import WorkflowValidationError
from app.core.workflow.graph import NodeSpec, WorkflowSpec


def make_workflow(*nodes: NodeSpec) -> WorkflowSpec:
    return WorkflowSpec(name="test", nodes=tuple(nodes))


def test_levels_group_independent_nodes() -> None:
    workflow = make_workflow(
        NodeSpec("a", "test"),
        NodeSpec("b", "test"),
        NodeSpec("c", "test", needs=("a", "b")),
        NodeSpec("d", "test", needs=("c",)),
    )
    levels = [[node.id for node in level] for level in workflow.levels()]
    assert levels == [["a", "b"], ["c"], ["d"]]


def test_cycle_is_rejected() -> None:
    workflow = make_workflow(
        NodeSpec("a", "test", needs=("b",)),
        NodeSpec("b", "test", needs=("a",)),
    )
    with pytest.raises(WorkflowValidationError, match="cycle"):
        workflow.validate()


def test_duplicate_ids_are_rejected() -> None:
    workflow = make_workflow(NodeSpec("a", "x"), NodeSpec("a", "y"))
    with pytest.raises(WorkflowValidationError, match="duplicate"):
        workflow.validate()


def test_unknown_dependency_is_rejected() -> None:
    workflow = make_workflow(NodeSpec("a", "test", needs=("missing",)))
    with pytest.raises(WorkflowValidationError, match="unknown node"):
        workflow.validate()


def test_from_dict_reads_params_and_needs() -> None:
    workflow = WorkflowSpec.from_dict(
        {
            "name": "demo",
            "version": "2",
            "nodes": [
                {"id": "a", "type": "media.probe", "params": {"path": "in.mp4"}},
                {"id": "b", "type": "video.cut", "needs": ["a"]},
            ],
        }
    )
    assert workflow.name == "demo"
    assert workflow.version == "2"
    assert workflow.nodes[0].params == {"path": "in.mp4"}
    assert workflow.nodes[1].needs == ("a",)


def test_bundled_workflows_are_valid() -> None:
    workflow_dir = Path(__file__).resolve().parents[1] / "app" / "workflows"
    files = sorted(workflow_dir.glob("*.yaml"))
    assert files
    for path in files:
        WorkflowSpec.from_yaml(path).validate()
