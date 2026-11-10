from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_studio_store
from app.studio.quality import check_asset
from app.studio.store import StudioStore

router = APIRouter(tags=["quality"])


class QualityCheckRequest(BaseModel):
    project_id: str
    asset_id: str
    required_keywords: list[str] = Field(default_factory=list)
    banned_words: list[str] = Field(default_factory=list)


class QualityFeedbackRequest(BaseModel):
    asset_id: str | None = None
    job_id: str | None = None
    project_id: str | None = None
    rating: int = Field(ge=1, le=5)
    tags: list[str] = Field(default_factory=list)
    comment: str = ""


@router.post("/api/v1/quality/check")
async def check_quality(
    payload: QualityCheckRequest,
    studio: StudioStore = Depends(get_studio_store),
) -> dict[str, object]:
    asset = studio.get_asset(payload.asset_id)
    if asset is None or asset["project_id"] != payload.project_id:
        raise HTTPException(status_code=404, detail="asset not found")

    root = studio.work_root.resolve()
    path = (root / asset["storage_key"]).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(status_code=404, detail="asset file not found")

    report = check_asset(
        path,
        str(asset["kind"]),
        payload.required_keywords,
        payload.banned_words,
    )
    return {
        "asset_id": payload.asset_id,
        "kind": asset["kind"],
        "filename": asset["filename"],
        **report.to_dict(),
    }


@router.post("/api/v1/quality/feedback", status_code=201)
async def submit_feedback(
    payload: QualityFeedbackRequest,
    studio: StudioStore = Depends(get_studio_store),
) -> dict[str, object]:
    return studio.add_feedback(
        payload.rating,
        project_id=payload.project_id,
        asset_id=payload.asset_id,
        job_id=payload.job_id,
        tags=payload.tags,
        comment=payload.comment,
    )


@router.get("/api/v1/quality/feedback")
async def list_feedback(
    project_id: str | None = None,
    studio: StudioStore = Depends(get_studio_store),
) -> dict[str, object]:
    return {
        "items": studio.list_feedback(project_id),
        "summary": studio.feedback_summary(),
    }
