from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID
from pydantic import BaseModel
import json

from database import get_db
from config import get_settings
from auth.service import get_current_user
from models.orm import User, Document, DocumentChunk, DocumentPermission, DocumentClassification
from rag.service import RAGService
from audit.service import log_audit_event

router = APIRouter()
settings = get_settings()


class RAGQuery(BaseModel):
    query: str
    mode: str = "balanced"  # fast, balanced, quality
    include_citations: bool = True
    max_context_chunks: int = 5


@router.post("/query")
async def rag_query(
    data: RAGQuery,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rag_service = RAGService(db, current_user)
    result = await rag_service.query(
        query=data.query,
        mode=data.mode,
        include_citations=data.include_citations,
        max_chunks=data.max_context_chunks,
    )

    await log_audit_event(db, current_user.id, "rag_query", "rag", None,
                          {"query": data.query[:100], "mode": data.mode})
    return result


@router.post("/query/stream")
async def rag_query_stream(
    data: RAGQuery,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rag_service = RAGService(db, current_user)

    async def event_stream():
        async for event in rag_service.query_stream(
            query=data.query,
            mode=data.mode,
            include_citations=data.include_citations,
            max_chunks=data.max_context_chunks,
        ):
            yield f"data: {json.dumps(event)}\n\n"
        yield "data: [DONE]\n\n"

    await log_audit_event(db, current_user.id, "rag_query_stream", "rag", None,
                          {"query": data.query[:100], "mode": data.mode})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
