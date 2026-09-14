import os
import uuid
import hashlib
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional
from uuid import UUID
from pydantic import BaseModel

from database import get_db
from config import get_settings
from auth.service import get_current_user, require_permission
from models.orm import User, Document, DocumentPermission, DocumentClassification
from audit.service import log_audit_event

router = APIRouter()
settings = get_settings()


class DocumentPermissionGrant(BaseModel):
    user_id: Optional[UUID] = None
    role_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    can_read: bool = True
    can_download: bool = False


def get_authorized_documents_query(user: User):
    """Build query that only returns documents the user is authorized to access."""
    return select(Document).where(
        or_(
            Document.owner_id == user.id,
            Document.id.in_(
                select(DocumentPermission.document_id).where(
                    or_(
                        DocumentPermission.user_id == user.id,
                        DocumentPermission.role_id == user.role_id,
                        DocumentPermission.department_id == user.department_id,
                    )
                )
            ),
            Document.classification == DocumentClassification.PUBLIC,
        )
    )


@router.get("/")
async def list_documents(
    skip: int = 0,
    limit: int = 50,
    classification: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = get_authorized_documents_query(current_user)
    if classification:
        stmt = stmt.where(Document.classification == classification)
    stmt = stmt.offset(skip).limit(limit).order_by(Document.created_at.desc())
    result = await db.execute(stmt)
    docs = result.scalars().all()

    return {
        "documents": [
            {
                "id": str(d.id),
                "filename": d.original_filename,
                "mime_type": d.mime_type,
                "size": d.file_size,
                "classification": d.classification.value if d.classification else "internal",
                "is_indexed": d.is_indexed,
                "is_ocr_processed": d.is_ocr_processed,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in docs
        ]
    }


@router.get("/{document_id}")
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = get_authorized_documents_query(current_user).where(Document.id == document_id)
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=403, detail="Access denied")

    await log_audit_event(db, current_user.id, "document_accessed", "document", str(document_id))
    return {
        "id": str(doc.id),
        "filename": doc.original_filename,
        "mime_type": doc.mime_type,
        "size": doc.file_size,
        "classification": doc.classification.value if doc.classification else "internal",
        "page_count": doc.page_count,
        "is_indexed": doc.is_indexed,
        "is_ocr_processed": doc.is_ocr_processed,
        "metadata": doc.metadata_json,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    classification: str = Form("INTERNAL"),
    department_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("view_documents")),
):
    if file.size and file.size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large")

    content = await file.read()
    checksum = hashlib.sha256(content).hexdigest()

    file_id = uuid.uuid4()
    ext = os.path.splitext(file.filename)[1] if file.filename else ""
    stored_filename = f"{file_id}{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, stored_filename)

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(content)

    doc = Document(
        id=file_id,
        filename=stored_filename,
        original_filename=file.filename or "unnamed",
        mime_type=file.content_type or "application/octet-stream",
        file_size=len(content),
        file_path=file_path,
        classification=DocumentClassification(classification.lower()),
        owner_id=current_user.id,
        department_id=uuid.UUID(department_id) if department_id else current_user.department_id,
    )
    db.add(doc)

    # Owner always has full access
    perm = DocumentPermission(
        document_id=file_id,
        user_id=current_user.id,
        can_read=True,
        can_download=True,
    )
    db.add(perm)
    await db.flush()

    await log_audit_event(db, current_user.id, "document_uploaded", "document", str(file_id),
                          {"filename": file.filename, "size": len(content)})

    return {"id": str(file_id), "filename": file.filename, "status": "uploaded"}


@router.post("/{document_id}/permissions")
async def grant_document_permission(
    document_id: UUID,
    data: DocumentPermissionGrant,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("manage_users")),
):
    stmt = select(Document).where(Document.id == document_id)
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    perm = DocumentPermission(
        document_id=document_id,
        user_id=data.user_id,
        role_id=data.role_id,
        department_id=data.department_id,
        can_read=data.can_read,
        can_download=data.can_download,
    )
    db.add(perm)
    await db.flush()

    await log_audit_event(db, current_user.id, "permission_granted", "document", str(document_id))
    return {"message": "Permission granted"}


@router.delete("/{document_id}")
async def delete_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("manage_users")),
):
    stmt = select(Document).where(Document.id == document_id)
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    await db.delete(doc)
    await db.flush()

    await log_audit_event(db, current_user.id, "document_deleted", "document", str(document_id))
    return {"message": "Document deleted"}
