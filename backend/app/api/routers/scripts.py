from __future__ import annotations

import json
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import (
    get_platform_store,
    get_rag_store,
    get_studio_store,
    get_tenant_id,
)
from app.billing.quota_guard import ensure_quota
from app.config import get_settings
from app.gateway.base import ChatMessage
from app.gateway.factory import build_chat_model
from app.platform.store import PlatformStore
from app.rag.service import RagService
from app.rag.store import RagStore
from app.skills import PromptSkill
from app.studio.store import StudioStore
from app.studio.storyboard import build_storyboard

router = APIRouter(tags=["scripts"])


class ScriptCreate(BaseModel):
    title: str
    body: str
    project_id: str | None = None
    tags: list[str] = []


class ScriptUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    tags: list[str] | None = None


class GenerateRequest(BaseModel):
    product: str
    platform: str = "抖音"
    style: str = "口播"
    brief: str = ""
    project_id: str | None = None
    knowledge_base_id: str | None = None


class TopicRequest(BaseModel):
    product: str
    platform: str = "抖音"
    style: str = "口播"
    brief: str = ""


@router.get("/api/v1/script-styles")
async def list_script_style_presets(
    store: PlatformStore = Depends(get_platform_store),
) -> dict[str, list[dict[str, object]]]:
    return {"items": store.list_script_styles(include_disabled=False)}


@router.get("/api/v1/scripts")
async def list_scripts(
    project_id: str | None = None,
    store: StudioStore = Depends(get_studio_store),
) -> dict[str, list[dict[str, object]]]:
    return {"items": store.list_scripts(project_id)}


@router.post("/api/v1/scripts", status_code=201)
async def create_script(
    payload: ScriptCreate,
    store: StudioStore = Depends(get_studio_store),
    platform: PlatformStore = Depends(get_platform_store),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    ensure_quota(store, platform, tenant_id, "scripts")
    try:
        return store.create_script(
            payload.title,
            payload.body,
            payload.project_id,
            payload.tags,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/v1/scripts/{script_id}")
async def get_script(
    script_id: str,
    store: StudioStore = Depends(get_studio_store),
) -> dict[str, object]:
    script = store.get_script(script_id)
    if script is None:
        raise HTTPException(status_code=404, detail="script not found")
    return script


@router.patch("/api/v1/scripts/{script_id}")
async def update_script(
    script_id: str,
    payload: ScriptUpdate,
    store: StudioStore = Depends(get_studio_store),
) -> dict[str, object]:
    script = store.update_script(script_id, payload.model_dump(exclude_none=True))
    if script is None:
        raise HTTPException(status_code=404, detail="script not found")
    return script


@router.delete("/api/v1/scripts/{script_id}")
async def delete_script(
    script_id: str,
    store: StudioStore = Depends(get_studio_store),
) -> dict[str, str]:
    if not store.delete_script(script_id):
        raise HTTPException(status_code=404, detail="script not found")
    return {"status": "deleted"}


@router.post("/api/v1/scripts/generate", status_code=201)
async def generate_script(
    payload: GenerateRequest,
    store: StudioStore = Depends(get_studio_store),
    rag: RagStore = Depends(get_rag_store),
    platform: PlatformStore = Depends(get_platform_store),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    product = payload.product.strip()
    if not product:
        raise HTTPException(status_code=422, detail="product is required")
    ensure_quota(store, platform, tenant_id, "scripts")

    context = ""
    retrieved = None
    if payload.knowledge_base_id:
        retrieved = RagService(rag).search(
            payload.knowledge_base_id,
            product,
            requested_top_k=5,
            token_budget=get_settings().rag_token_budget,
        )
        context = retrieved.context

    prompt_input = product
    if context:
        prompt_input = f"{product}\n\n参考资料：\n{context}"

    style = payload.style
    style_profile = store.effective_style(payload.project_id)
    if style_profile:
        if style_profile.get("prompt"):
            style += f"；风格要求：{style_profile['prompt']}"
        if style_profile.get("shot_rhythm"):
            style += f"；节奏：{style_profile['shot_rhythm']}"

    result = await PromptSkill(build_chat_model()).run(
        {},
        {
            "product": prompt_input,
            "platform": payload.platform,
            "style": style,
            "brief": payload.brief,
            "task": "script",
        },
    )
    script = store.create_script(
        f"{product} · {payload.platform}",
        str(result.get("prompt") or ""),
        payload.project_id,
        [payload.platform, payload.style],
    )
    return {
        "script": script,
        "shell": result.get("shell", False),
        "model": result.get("model"),
        "rag_hits": retrieved.top_k if retrieved else 0,
        "rag_tokens": retrieved.tokens if retrieved else 0,
    }


def _extract_topic_json(text: str) -> list[dict[str, str]]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        return []
    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return []
    rows = payload.get("topics") if isinstance(payload, dict) else []
    items: list[dict[str, str]] = []
    if not isinstance(rows, list):
        return []
    for row in rows[:10]:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        items.append(
            {
                "title": title[:120],
                "angle": str(row.get("angle") or "").strip()[:240],
                "hook": str(row.get("hook") or "").strip()[:180],
                "format": str(row.get("format") or "口播").strip()[:40],
            }
        )
    return items


def _fallback_topics(payload: TopicRequest) -> list[dict[str, str]]:
    product = payload.product.strip() or "产品"
    return [
        {
            "title": f"{product}新手最容易踩的 3 个坑",
            "angle": "先讲错误做法，再给具体解决方法",
            "hook": f"刚开始接触{product}，这三个坑千万别踩",
            "format": "口播",
        },
        {
            "title": f"一条视频讲清{product}到底值不值得选",
            "angle": "从使用场景、成本和真实体验做判断",
            "hook": f"先说结论：{product}不是所有人都适合",
            "format": "测评",
        },
        {
            "title": f"{product}真实体验：优点和缺点都讲",
            "angle": "第一视角记录真实使用细节",
            "hook": "用了这么久，我终于敢说真实感受",
            "format": "Vlog",
        },
        {
            "title": f"{product}最容易被忽略的 5 个细节",
            "angle": "清单式盘点，突出具体信息",
            "hook": "第 3 个细节，很多人到现在都不知道",
            "format": "清单",
        },
        {
            "title": f"为什么别人讲{product}更容易让人听完",
            "angle": "拆解开头、结构、例子和节奏",
            "hook": "同样讲一个东西，差距从第一句话就开始了",
            "format": "教程",
        },
        {
            "title": f"用一个真实问题讲明白{product}",
            "angle": "从具体痛点切入，展示解决前后对比",
            "hook": "这个问题困扰我很久，直到我换了思路",
            "format": "剧情",
        },
    ]


@router.post("/api/v1/scripts/topics")
async def suggest_script_topics(payload: TopicRequest) -> dict[str, object]:
    model = build_chat_model()
    items: list[dict[str, str]] = []
    model_name = None
    if model is not None and payload.product.strip():
        try:
            result = await model.chat(
                [
                    ChatMessage(
                        role="system",
                        content=(
                            "你是短视频选题策划。只输出 JSON 对象："
                            '{"topics":[{"title":"","angle":"",'
                            '"hook":"","format":""}]}。不要输出 Markdown 或解释。'
                        ),
                    ),
                    ChatMessage(
                        role="user",
                        content=(
                            f"产品/主题：{payload.product}\n"
                            f"平台：{payload.platform}\n"
                            f"风格：{payload.style}\n"
                            f"用户需求：{payload.brief or '无特别要求'}\n"
                            "生成 6-8 个具体选题，必须围绕用户需求，"
                            "标题要具体，不要空泛口号。"
                        ),
                    ),
                ],
                temperature=0.7,
                max_tokens=900,
            )
            items = _extract_topic_json(result.text)
            model_name = result.model
        except Exception:
            items = []
    if not items:
        items = _fallback_topics(payload)
    return {"items": items, "model": model_name, "shell": model_name is None}


@router.post("/api/v1/scripts/{script_id}/storyboard", status_code=201)
async def generate_script_storyboard(
    script_id: str,
    store: StudioStore = Depends(get_studio_store),
) -> dict[str, object]:
    script = store.get_script(script_id)
    if script is None:
        raise HTTPException(status_code=404, detail="script not found")
    project_id = str(script.get("project_id") or "")
    if not project_id:
        raise HTTPException(status_code=422, detail="脚本没有关联项目")
    try:
        return await build_storyboard(
            store,
            project_id,
            script_id,
            str(script["body"]),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
