from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.storage_names import CHECKPOINT_FILE, SYSTEM_DIR

from .context import RunContext
from .errors import NodeExecutionError, WorkflowValidationError
from .events import NodeEvent
from .graph import NodeSpec, WorkflowSpec
from .registry import NodeRegistry


@dataclass
class WorkflowResult:
    job_id: str
    status: str
    outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    events: list[NodeEvent] = field(default_factory=list)
    error: str | None = None
    duration_ms: int = 0

    @property
    def succeeded(self) -> bool:
        return self.status == "succeeded"


class WorkflowExecutor:
    def __init__(self, registry: NodeRegistry, max_concurrency: int = 2) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be greater than zero")
        self._registry = registry
        self._max_concurrency = max_concurrency

    async def run(self, workflow: WorkflowSpec, ctx: RunContext) -> WorkflowResult:
        workflow.validate()
        started_at = time.monotonic()
        checkpoint_path = ctx.work_dir / SYSTEM_DIR / CHECKPOINT_FILE
        checkpoint = self._load_checkpoint(checkpoint_path)
        for node_id, record in checkpoint.items():
            ctx.outputs[node_id] = record.get("outputs", {})

        checkpoint_lock = asyncio.Lock()
        failed = False
        error: str | None = None
        skipped: set[str] = set()
        semaphore = asyncio.Semaphore(self._max_concurrency)

        for level in workflow.levels():
            runnable: list[NodeSpec] = []
            for spec in level:
                if spec.id in checkpoint:
                    await ctx.emit(
                        NodeEvent(
                            job_id=ctx.job_id,
                            node_id=spec.id,
                            node_type=spec.type,
                            status="cached",
                        )
                    )
                else:
                    runnable.append(spec)

            if not runnable:
                continue

            async def run_one(spec: NodeSpec) -> dict[str, Any]:
                async with semaphore:
                    return await self._run_node(
                        spec,
                        ctx,
                        checkpoint,
                        checkpoint_path,
                        checkpoint_lock,
                    )

            results = await asyncio.gather(
                *(run_one(spec) for spec in runnable),
                return_exceptions=True,
            )
            failure = next(
                (item for item in results if isinstance(item, BaseException)),
                None,
            )
            if failure is not None:
                failed = True
                error = f"{type(failure).__name__}: {failure}"
                for spec in workflow.nodes:
                    if spec.id not in checkpoint:
                        skipped.add(spec.id)
                break

        if failed:
            for spec in workflow.nodes:
                if spec.id in skipped:
                    await ctx.emit(
                        NodeEvent(
                            job_id=ctx.job_id,
                            node_id=spec.id,
                            node_type=spec.type,
                            status="skipped",
                        )
                    )

        duration_ms = int((time.monotonic() - started_at) * 1000)
        return WorkflowResult(
            job_id=ctx.job_id,
            status="failed" if failed else "succeeded",
            outputs=dict(ctx.outputs),
            events=list(ctx.events),
            error=error,
            duration_ms=duration_ms,
        )

    async def _run_node(
        self,
        spec: NodeSpec,
        ctx: RunContext,
        checkpoint: dict[str, dict[str, Any]],
        checkpoint_path: Path,
        checkpoint_lock: asyncio.Lock,
    ) -> dict[str, Any]:
        node = self._registry.create(spec.type)
        inputs = self._build_inputs(spec, ctx)
        policy = node.retry
        last_error: BaseException | None = None

        for attempt in range(1, policy.max_attempts + 1):
            node_started = time.monotonic()
            await ctx.emit(
                NodeEvent(
                    job_id=ctx.job_id,
                    node_id=spec.id,
                    node_type=spec.type,
                    status="started",
                    attempt=attempt,
                )
            )
            try:
                outputs = await node.run(ctx, inputs)
                if not isinstance(outputs, dict):
                    raise TypeError(
                        f"node {spec.id} must return a dict, got {type(outputs).__name__}"
                    )
                ctx.outputs[spec.id] = outputs
                duration_ms = int((time.monotonic() - node_started) * 1000)
                await ctx.emit(
                    NodeEvent(
                        job_id=ctx.job_id,
                        node_id=spec.id,
                        node_type=spec.type,
                        status="succeeded",
                        attempt=attempt,
                        duration_ms=duration_ms,
                        outputs=outputs,
                    )
                )
                async with checkpoint_lock:
                    checkpoint[spec.id] = {"status": "succeeded", "outputs": outputs}
                    self._save_checkpoint(checkpoint_path, checkpoint)
                return outputs
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                last_error = exc
                duration_ms = int((time.monotonic() - node_started) * 1000)
                if attempt < policy.max_attempts:
                    delay = min(
                        policy.initial_delay * (2 ** (attempt - 1)),
                        policy.max_delay,
                    )
                    await ctx.emit(
                        NodeEvent(
                            job_id=ctx.job_id,
                            node_id=spec.id,
                            node_type=spec.type,
                            status="retrying",
                            attempt=attempt,
                            duration_ms=duration_ms,
                            error=str(exc),
                        )
                    )
                    await asyncio.sleep(delay)
                else:
                    await ctx.emit(
                        NodeEvent(
                            job_id=ctx.job_id,
                            node_id=spec.id,
                            node_type=spec.type,
                            status="failed",
                            attempt=attempt,
                            duration_ms=duration_ms,
                            error=str(exc),
                        )
                    )

        raise NodeExecutionError(spec.id, spec.type, policy.max_attempts, last_error)

    @staticmethod
    def _build_inputs(spec: NodeSpec, ctx: RunContext) -> dict[str, Any]:
        upstream: dict[str, dict[str, Any]] = {}
        merged: dict[str, Any] = {}
        for dep in spec.needs:
            data = ctx.outputs.get(dep, {})
            upstream[dep] = data
            merged.update(data)
        return {
            "params": WorkflowExecutor._resolve_value(spec.params, ctx.params),
            "upstream": upstream,
            "data": merged,
            "job_params": ctx.params,
        }

    @staticmethod
    def _resolve_value(value: Any, params: dict[str, Any]) -> Any:
        if isinstance(value, str):
            if value.startswith("${") and value.endswith("}"):
                key = value[2:-1]
                if key not in params:
                    raise WorkflowValidationError(f"workflow parameter not provided: {key}")
                return params[key]
            return value
        if isinstance(value, dict):
            return {
                key: WorkflowExecutor._resolve_value(item, params)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [WorkflowExecutor._resolve_value(item, params) for item in value]
        return value

    @staticmethod
    def _load_checkpoint(path: Path) -> dict[str, dict[str, Any]]:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        nodes = payload.get("nodes")
        return nodes if isinstance(nodes, dict) else {}

    @staticmethod
    def _save_checkpoint(path: Path, nodes: dict[str, dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps({"nodes": nodes}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_path.replace(path)
