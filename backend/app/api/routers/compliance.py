from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_compliance_service, get_studio_store, get_tenant_id
from app.studio.compliance import ComplianceService
from app.studio.store import StudioStore

router = APIRouter(tags=["compliance"])

class ComplianceCheckRequest(BaseModel):
    project_id: str | None = None
    asset_id: str | None = None
    platform: str = "抖音"
    text: str = Field(default="", max_length=20000)


@router.post("/api/v1/compliance/check", status_code=201)
async def compliance_check(
    payload: ComplianceCheckRequest,
    service: ComplianceService = Depends(get_compliance_service),
    studio: StudioStore = Depends(get_studio_store),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    if not payload.text.strip() and not payload.asset_id:
        raise HTTPException(status_code=422, detail="请提供文案或选择一个视频素材")
    try:
        return await service.check(
            studio,
            platform=payload.platform,
            project_id=payload.project_id,
            asset_id=payload.asset_id,
            text=payload.text,
            tenant_id=tenant_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/v1/compliance/reports")
async def list_compliance_reports(
    limit: int = 50,
    service: ComplianceService = Depends(get_compliance_service),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, list[dict[str, object]]]:
    return {"items": service.list_reports(tenant_id, limit)}


@router.delete("/api/v1/compliance/reports/{report_id}")
async def delete_compliance_report(
    report_id: str,
    service: ComplianceService = Depends(get_compliance_service),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, str]:
    if not service.delete_report(report_id, tenant_id):
        raise HTTPException(status_code=404, detail="compliance report not found")
    return {"status": "deleted"}
