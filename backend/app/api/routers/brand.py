from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.api.deps import get_studio_store, get_tenant_id
from app.studio.store import StudioStore

router = APIRouter(tags=["brand"])

MAX_LOGO_BYTES = 10 * 1024 * 1024
HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
LOGO_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".svg"}


class BrandKitUpdate(BaseModel):
    brand_name: str | None = Field(default=None, max_length=80)
    slogan: str | None = Field(default=None, max_length=160)
    primary_color: str | None = None
    secondary_color: str | None = None
    font_family: str | None = Field(default=None, max_length=80)
    watermark_text: str | None = Field(default=None, max_length=80)
    voice_tone: str | None = Field(default=None, max_length=160)
    intro_text: str | None = Field(default=None, max_length=500)
    outro_text: str | None = Field(default=None, max_length=500)


def _validate_colors(values: dict[str, object]) -> None:
    for key in ("primary_color", "secondary_color"):
        color = values.get(key)
        if color is not None and not HEX_COLOR.fullmatch(str(color)):
            raise HTTPException(status_code=422, detail=f"{key} must be #RRGGBB")


@router.get("/api/v1/brand-kit")
async def get_brand_kit(
    store: StudioStore = Depends(get_studio_store),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    return store.get_brand_kit(tenant_id)


@router.put("/api/v1/brand-kit")
async def update_brand_kit(
    payload: BrandKitUpdate,
    store: StudioStore = Depends(get_studio_store),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    values = payload.model_dump(exclude_none=True)
    _validate_colors(values)
    return store.set_brand_kit(values, tenant_id)


@router.post("/api/v1/brand-kit/logo", status_code=201)
async def upload_brand_logo(
    file: UploadFile = File(...),
    store: StudioStore = Depends(get_studio_store),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    filename = file.filename or "logo.png"
    suffix = Path(filename).suffix.lower()
    if suffix not in LOGO_SUFFIXES:
        raise HTTPException(status_code=422, detail="logo must be png, jpg, webp or svg")

    current = store.get_brand_kit(tenant_id)
    storage_key = f"brands/{tenant_id}/logo-{uuid.uuid4().hex[:10]}{suffix}"
    root = store.work_root.resolve()
    target = (root / storage_key).resolve()
    if not target.is_relative_to(root):
        raise HTTPException(status_code=400, detail="invalid storage path")
    target.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    try:
        with target.open("wb") as handle:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > MAX_LOGO_BYTES:
                    raise HTTPException(status_code=413, detail="logo too large")
                handle.write(chunk)
    except HTTPException:
        target.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    old_key = str(current.get("logo_storage_key") or "")
    updated = store.set_brand_kit(
        {
            "logo_filename": filename,
            "logo_storage_key": storage_key,
        },
        tenant_id,
    )
    if old_key and old_key != storage_key:
        old_path = (root / old_key).resolve()
        if old_path.is_relative_to(root):
            old_path.unlink(missing_ok=True)
    return updated


@router.get("/api/v1/brand-kit/logo")
async def get_brand_logo(
    store: StudioStore = Depends(get_studio_store),
    tenant_id: str = Depends(get_tenant_id),
) -> FileResponse:
    brand = store.get_brand_kit(tenant_id)
    storage_key = str(brand.get("logo_storage_key") or "")
    if not storage_key:
        raise HTTPException(status_code=404, detail="brand logo not configured")
    root = store.work_root.resolve()
    path = (root / storage_key).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(status_code=404, detail="brand logo file not found")
    return FileResponse(
        path,
        filename=str(brand.get("logo_filename") or "logo"),
        content_disposition_type="inline",
    )
