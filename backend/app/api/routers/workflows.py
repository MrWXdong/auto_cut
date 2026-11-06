from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.core.workflow.graph import WorkflowSpec

router = APIRouter(tags=["workflows"])
WORKFLOW_DIR = Path(__file__).resolve().parents[2] / "workflows"


@router.get("/api/v1/workflows")
async def list_workflows() -> dict[str, list[dict[str, object]]]:
    items: list[dict[str, object]] = []
    for path in sorted(WORKFLOW_DIR.glob("*.yaml")):
        spec = WorkflowSpec.from_yaml(path)
        items.append(
            {
                "name": spec.name,
                "version": spec.version,
                "description": spec.description,
                "node_count": len(spec.nodes),
            }
        )
    return {"items": items}


@router.get("/api/v1/workflows/{name}")
async def get_workflow(name: str) -> dict[str, object]:
    path = WORKFLOW_DIR / f"{name}.yaml"
    if not path.exists():
        raise HTTPException(status_code=404, detail="workflow not found")
    spec = WorkflowSpec.from_yaml(path)
    spec.validate()
    return {
        "name": spec.name,
        "version": spec.version,
        "description": spec.description,
        "nodes": [
            {
                "id": node.id,
                "type": node.type,
                "needs": list(node.needs),
                "params": node.params,
            }
            for node in spec.nodes
        ],
    }
