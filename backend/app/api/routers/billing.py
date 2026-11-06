from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["billing"])


class RedeemRequest(BaseModel):
    code: str


@router.get("/api/v1/billing/plan")
async def get_plan() -> dict[str, object]:
    return {
        "code": "trial",
        "name": "试用版",
        "price_cents": 0,
        "period": "month",
        "limits": {
            "videos": 3,
            "prompts": 10,
            "storage_gb": 1,
            "concurrency": 1,
        },
    }


@router.get("/api/v1/billing/usage")
async def get_usage() -> dict[str, object]:
    return {
        "period": "2026-11",
        "items": [
            {"kind": "videos", "used": 0, "limit": 3, "unit": "条"},
            {"kind": "prompts", "used": 0, "limit": 10, "unit": "次"},
            {"kind": "storage_gb", "used": 0, "limit": 1, "unit": "GB"},
        ],
    }


@router.post("/api/v1/billing/redeem")
async def redeem(payload: RedeemRequest) -> dict[str, object]:
    raise HTTPException(status_code=501, detail="redeem is a shell")
