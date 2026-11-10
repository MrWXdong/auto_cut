from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.api.deps import get_rag_store
from app.rag.service import RagService
from app.rag.store import RagStore

router = APIRouter(tags=["knowledge"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


class KnowledgeBaseCreate(BaseModel):
    name: str
    description: str = ""


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    token_budget: int = 1200


def decode_text(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise HTTPException(status_code=422, detail="无法识别文件编码，请使用 UTF-8")


@router.get("/api/v1/knowledge-bases")
async def list_knowledge_bases(
    store: RagStore = Depends(get_rag_store),
) -> dict[str, list[dict[str, object]]]:
    return {"items": store.list_kbs()}


@router.post("/api/v1/knowledge-bases", status_code=201)
async def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    store: RagStore = Depends(get_rag_store),
) -> dict[str, object]:
    try:
        return store.create_kb(payload.name, payload.description)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/api/v1/knowledge-bases/{kb_id}")
async def delete_knowledge_base(
    kb_id: str,
    store: RagStore = Depends(get_rag_store),
) -> dict[str, str]:
    if not store.delete_kb(kb_id):
        raise HTTPException(status_code=404, detail="knowledge base not found")
    return {"status": "deleted"}


@router.post("/api/v1/knowledge-bases/{kb_id}/documents", status_code=201)
async def upload_document(
    kb_id: str,
    file: UploadFile = File(...),
    source: str = Form(default=""),
    store: RagStore = Depends(get_rag_store),
) -> dict[str, object]:
    filename = file.filename or "document.txt"
    raw = await file.read()
    await file.close()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="file too large")
    text = decode_text(raw)
    try:
        return store.add_document(kb_id, filename, text, source)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/v1/knowledge-bases/{kb_id}/documents")
async def list_documents(
    kb_id: str,
    store: RagStore = Depends(get_rag_store),
) -> dict[str, list[dict[str, object]]]:
    if store.get_kb(kb_id) is None:
        raise HTTPException(status_code=404, detail="knowledge base not found")
    return {"items": store.list_documents(kb_id)}


@router.delete("/api/v1/knowledge-bases/{kb_id}/documents/{document_id}")
async def delete_document(
    kb_id: str,
    document_id: str,
    store: RagStore = Depends(get_rag_store),
) -> dict[str, str]:
    if not store.delete_document(document_id, kb_id):
        raise HTTPException(status_code=404, detail="document not found")
    return {"status": "deleted"}


@router.post("/api/v1/knowledge-bases/{kb_id}/search")
async def search_knowledge_base(
    kb_id: str,
    payload: SearchRequest,
    store: RagStore = Depends(get_rag_store),
) -> dict[str, object]:
    if store.get_kb(kb_id) is None:
        raise HTTPException(status_code=404, detail="knowledge base not found")
    result = RagService(store).search(
        kb_id,
        payload.query,
        requested_top_k=payload.top_k,
        token_budget=payload.token_budget,
    )
    return {
        "hits": result.hits,
        "context": result.context,
        "tokens": result.tokens,
        "top_k": result.top_k,
        "profile": result.profile,
    }
