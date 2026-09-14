import os
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID

from database import get_db
from config import get_settings
from auth.service import get_current_user, require_permission
from models.orm import User, Document, DocumentChunk, DocumentPermission, DocumentClassification
from knowledge.processor import DocumentProcessor
from audit.service import log_audit_event
from rag.embeddings import get_embedding

router = APIRouter()
settings = get_settings()


@router.post("/index/{document_id}")
async def index_document(
    document_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("search_documents")),
):
    stmt = select(Document).where(Document.id == document_id)
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only document owner can trigger indexing")

    background_tasks.add_task(process_and_index_document, str(document_id))
    await log_audit_event(db, current_user.id, "document_indexing_started", "document", str(document_id))
    # Starlette runs BackgroundTasks as part of finishing *this* response,
    # before this request's own get_db() dependency has committed/closed
    # its session (that only happens once this endpoint function returns
    # control all the way back up). Without this, the audit-log INSERT
    # above sits uncommitted - holding SQLite's one write lock - for the
    # entire time the background indexing task is waiting for that same
    # lock to write its own results. That's a genuine deadlock, only
    # ever "resolved" by the busy_timeout expiring ~30s later with a
    # "database is locked" error. Committing explicitly here releases
    # the lock immediately so the background task can proceed right away.
    await db.commit()
    return {"message": "Document indexing started", "document_id": str(document_id)}


@router.post("/backfill-embeddings")
async def backfill_embeddings(
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("manage_models")),
):
    """Generate embeddings for chunks that were indexed before a local
    embedding model was available (embedding IS NULL). Safe to call
    repeatedly - only touches chunks still missing an embedding, and
    processes at most `limit` per call so a large backlog doesn't tie up
    one request."""
    stmt = select(DocumentChunk).where(DocumentChunk.embedding.is_(None)).limit(limit)
    result = await db.execute(stmt)
    chunks = result.scalars().all()

    updated = 0
    skipped = 0
    for chunk in chunks:
        vector = await get_embedding(chunk.content)
        if vector:
            chunk.embedding = vector
            updated += 1
        else:
            skipped += 1

    await db.commit()
    return {"updated": updated, "skipped_no_model": skipped, "remaining_checked": len(chunks)}


@router.get("/search")
async def search_knowledge(
    query: str,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("search_documents")),
):
    # Permission-filtered search: only return chunks from authorized documents
    authorized_doc_ids = select(Document.id).where(
        or_(
            Document.owner_id == current_user.id,
            Document.id.in_(
                select(DocumentPermission.document_id).where(
                    or_(
                        DocumentPermission.user_id == current_user.id,
                        DocumentPermission.role_id == current_user.role_id,
                        DocumentPermission.department_id == current_user.department_id,
                    )
                )
            ),
            Document.classification == DocumentClassification.PUBLIC,
        )
    )

    stmt = (
        select(DocumentChunk)
        .where(DocumentChunk.document_id.in_(authorized_doc_ids))
        .limit(limit)
    )
    result = await db.execute(stmt)
    chunks = result.scalars().all()

    await log_audit_event(db, current_user.id, "knowledge_search", "knowledge", None, {"query": query[:100]})

    return {
        "results": [
            {
                "chunk_id": str(c.id),
                "document_id": str(c.document_id),
                "content": c.content[:500],
                "page_number": c.page_number,
                "section": c.section,
                "score": 0.0,
            }
            for c in chunks
        ],
        "total": len(chunks),
    }


@router.get("/stats")
async def knowledge_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import func

    doc_count = await db.execute(select(func.count(Document.id)).where(Document.is_indexed == True))
    chunk_count = await db.execute(select(func.count(DocumentChunk.id)))

    return {
        "indexed_documents": doc_count.scalar() or 0,
        "total_chunks": chunk_count.scalar() or 0,
    }


async def process_and_index_document(document_id: str):
    """Background task to process and index a document."""
    from database import get_db_context
    try:
        async with get_db_context() as db:
            processor = DocumentProcessor()
            stmt = select(Document).where(Document.id == uuid.UUID(document_id))
            result = await db.execute(stmt)
            doc = result.scalar_one_or_none()
            if not doc:
                return

            chunks = await processor.process(doc.file_path, doc.mime_type)

            for i, chunk_data in enumerate(chunks):
                # Embed each chunk now, at index time, rather than at
                # every query - one embedding call per chunk here vs. one
                # per query is the right tradeoff since a chunk is
                # written once but queried many times. get_embedding()
                # returns None (never raises) if no embedding model is
                # installed locally - those chunks just fall back to
                # keyword search in rag/service.py rather than blocking
                # indexing on a model that may not be pulled yet.
                embedding = await get_embedding(chunk_data["content"])
                chunk = DocumentChunk(
                    document_id=doc.id,
                    chunk_index=i,
                    content=chunk_data["content"],
                    page_number=chunk_data.get("page_number"),
                    section=chunk_data.get("section"),
                    embedding=embedding,
                    metadata_json=chunk_data.get("metadata", {}),
                )
                db.add(chunk)

            doc.is_indexed = True
            doc.is_ocr_processed = processor.last_used_ocr
            # get_db_context() commits on clean exit, and rolls back
            # automatically (without saving partial chunks/flags) if
            # anything above raises - it never leaves a document
            # half-indexed.
    except Exception as e:
        print(f"Error indexing document {document_id}: {e}")
