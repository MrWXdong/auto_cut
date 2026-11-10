from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.agents.tools import execute_tool, route_tool
from app.api.deps import get_rag_store, get_service, get_studio_store
from app.rag.store import RagStore
from app.service import JobService
from app.studio.store import StudioStore

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    project_id: str | None = None
    knowledge_base_id: str | None = None
    model: str | None = None


@router.post("/api/v1/chat")
async def chat(
    payload: ChatRequest,
    studio: StudioStore = Depends(get_studio_store),
    rag: RagStore = Depends(get_rag_store),
    service: JobService = Depends(get_service),
) -> dict[str, object]:
    conversation = None
    if payload.conversation_id:
        conversation = studio.get_conversation(payload.conversation_id)
    if conversation is None:
        conversation = studio.create_conversation(payload.message[:24] or "新对话")

    studio.add_message(conversation["id"], "user", payload.message)
    tool = route_tool(payload.message)
    outcome = await execute_tool(
        studio,
        rag,
        service,
        tool,
        payload.message,
        payload.project_id,
        payload.knowledge_base_id,
        payload.model,
    )
    studio.add_message(
        conversation["id"],
        "assistant",
        outcome.reply,
        {"tool": tool, "files": outcome.files, "data": outcome.data},
    )

    return {
        "conversation_id": conversation["id"],
        "intent": {"name": tool, "confidence": 1.0},
        "plan": {
            "skill": tool,
            "workflow": "quick_cut" if tool == "create_edit_job" else None,
            "inputs": {
                "project_id": payload.project_id,
                "knowledge_base_id": payload.knowledge_base_id,
            },
        },
        "reply": outcome.reply,
        "tool": tool,
        "files": outcome.files,
        "result": outcome.data,
        "shell": False,
    }


@router.get("/api/v1/conversations")
async def list_conversations(
    studio: StudioStore = Depends(get_studio_store),
) -> dict[str, list[dict[str, object]]]:
    return {"items": studio.list_conversations()}


@router.get("/api/v1/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    studio: StudioStore = Depends(get_studio_store),
) -> dict[str, object]:
    conversation = studio.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return conversation


@router.delete("/api/v1/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    studio: StudioStore = Depends(get_studio_store),
) -> dict[str, str]:
    if not studio.delete_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="conversation not found")
    return {"status": "deleted"}
