from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path
from typing import Any

from app.bootstrap import build_registry
from app.config import get_settings
from app.core.workflow.context import RunContext
from app.core.workflow.executor import WorkflowExecutor
from app.core.workflow.graph import WorkflowSpec


def _workflow_path(name: str) -> Path:
    return Path(__file__).resolve().parent / "workflows" / f"{name}.yaml"


def _parse_overrides(values: list[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for value in values:
        key, separator, raw = value.partition("=")
        if not key or not separator:
            raise SystemExit(f"invalid --set value (expected KEY=VALUE): {value}")
        overrides[key] = raw
    return overrides


async def _run(args: argparse.Namespace) -> int:
    settings = get_settings()
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        print(f"input not found: {input_path}", file=sys.stderr)
        return 2

    workflow_path = _workflow_path(args.workflow)
    if not workflow_path.exists():
        print(f"workflow not found: {workflow_path}", file=sys.stderr)
        return 2

    workflow = WorkflowSpec.from_yaml(workflow_path)
    job_id = args.job_id or uuid.uuid4().hex[:12]
    work_dir = (settings.work_root / job_id).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    params: dict[str, Any] = {"input_path": str(input_path)}
    params.update(_parse_overrides(args.set))

    context = RunContext(job_id=job_id, work_dir=work_dir, params=params)
    executor = WorkflowExecutor(
        build_registry(),
        max_concurrency=settings.max_concurrency,
    )
    result = await executor.run(workflow, context)

    print(
        json.dumps(
            {
                "job_id": result.job_id,
                "status": result.status,
                "duration_ms": result.duration_ms,
                "error": result.error,
                "outputs": result.outputs,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.succeeded else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="autocut", description="AutoCut workflow CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="run a workflow against a local file")
    run_parser.add_argument("workflow", help="workflow name, for example subtitle or clip")
    run_parser.add_argument("--input", required=True, help="path to the source video")
    run_parser.add_argument("--job-id", default=None, help="reuse an existing job directory")
    run_parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="override a workflow parameter",
    )

    args = parser.parse_args(argv)
    if args.command == "run":
        return asyncio.run(_run(args))
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
