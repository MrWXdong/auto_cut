from __future__ import annotations

import pytest

from app.core.workflow.context import RunContext
from app.core.workflow.executor import WorkflowExecutor
from app.core.workflow.graph import NodeSpec, WorkflowSpec
from app.core.workflow.node import Node, RetryPolicy
from app.core.workflow.registry import NodeRegistry


class AddNode(Node):
    type = "test.add"

    async def run(self, ctx: RunContext, inputs: dict) -> dict:
        params = inputs["params"]
        return {"value": params["a"] + params["b"]}


class DoubleNode(Node):
    type = "test.double"

    async def run(self, ctx: RunContext, inputs: dict) -> dict:
        return {"value": inputs["data"]["value"] * 2}


class FlakyNode(Node):
    type = "test.flaky"
    retry = RetryPolicy(max_attempts=3, initial_delay=0.0, max_delay=0.0)
    calls = 0

    async def run(self, ctx: RunContext, inputs: dict) -> dict:
        type(self).calls += 1
        if type(self).calls < 3:
            raise RuntimeError("temporary failure")
        return {"ok": True}


class FailNode(Node):
    type = "test.fail"

    async def run(self, ctx: RunContext, inputs: dict) -> dict:
        raise ValueError("permanent failure")


def make_registry() -> NodeRegistry:
    registry = NodeRegistry()
    for node_cls in (AddNode, DoubleNode, FlakyNode, FailNode):
        registry.register(node_cls)
    return registry


@pytest.mark.asyncio
async def test_runs_dag_and_writes_checkpoint(tmp_path) -> None:
    workflow = WorkflowSpec(
        name="dag",
        nodes=(
            NodeSpec("add", "test.add", {"a": 1, "b": 2}),
            NodeSpec("double", "test.double", needs=("add",)),
        ),
    )
    result = await WorkflowExecutor(make_registry()).run(
        workflow,
        RunContext(job_id="job-1", work_dir=tmp_path),
    )
    assert result.status == "succeeded"
    assert result.outputs["double"]["value"] == 6
    assert (tmp_path / "checkpoint.json").exists()


@pytest.mark.asyncio
async def test_retries_then_succeeds(tmp_path) -> None:
    FlakyNode.calls = 0
    workflow = WorkflowSpec(name="retry", nodes=(NodeSpec("flaky", "test.flaky"),))
    result = await WorkflowExecutor(make_registry()).run(
        workflow,
        RunContext(job_id="job-2", work_dir=tmp_path),
    )
    assert result.status == "succeeded"
    assert FlakyNode.calls == 3
    assert [event.status for event in result.events].count("retrying") == 2


@pytest.mark.asyncio
async def test_checkpoint_skips_completed_nodes(tmp_path) -> None:
    FlakyNode.calls = 0
    workflow = WorkflowSpec(name="resume", nodes=(NodeSpec("flaky", "test.flaky"),))
    executor = WorkflowExecutor(make_registry())
    await executor.run(workflow, RunContext(job_id="job-3", work_dir=tmp_path))
    calls_after_first_run = FlakyNode.calls

    result = await executor.run(
        workflow,
        RunContext(job_id="job-3", work_dir=tmp_path),
    )
    assert result.status == "succeeded"
    assert FlakyNode.calls == calls_after_first_run
    assert "cached" in [event.status for event in result.events]


@pytest.mark.asyncio
async def test_failure_marks_downstream_skipped(tmp_path) -> None:
    workflow = WorkflowSpec(
        name="fail",
        nodes=(
            NodeSpec("bad", "test.fail"),
            NodeSpec("never", "test.double", needs=("bad",)),
        ),
    )
    result = await WorkflowExecutor(make_registry()).run(
        workflow,
        RunContext(job_id="job-4", work_dir=tmp_path),
    )
    assert result.status == "failed"
    assert "permanent failure" in (result.error or "")
    assert "never" not in result.outputs
    assert "skipped" in [event.status for event in result.events]
