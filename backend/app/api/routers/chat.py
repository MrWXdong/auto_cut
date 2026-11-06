from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.agents import AgentRouter

router = APIRouter(tags=["chat"])
_agent_router = AgentRouter()


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


@router.post("/api/v1/chat")
async def chat(payload: ChatRequest) -> dict[str, object]:
    intent = await _agent_router.detect(payload.message)
    plan = _agent_router.plan(intent)
    return {
        "conversation_id": payload.conversation_id or "demo",
        "intent": {"name": intent.intent.value, "confidence": intent.confidence},
        "plan": {
            "skill": plan.skill,
            "workflow": plan.workflow,
            "inputs": plan.inputs,
        },
        "reply": (
            f"识别为「{intent.intent.value}」，准备调用 {plan.skill}。"
            "当前为空壳，没有真正执行模型调用。"
        ),
        "shell": True,
    }


@router.get("/api/v1/conversations")
async def list_conversations() -> dict[str, list[object]]:
    return {"items": []}
