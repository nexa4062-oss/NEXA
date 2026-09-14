import os
import uuid
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime
from sqlalchemy import select
from database import get_db
from config import get_settings
from auth.service import get_current_user, require_permission, user_has_permission
from models.orm import User, GeneratedFile
from generation.service import FileGenerator
from audit.service import log_audit_event

router = APIRouter()
settings = get_settings()
generator = FileGenerator()


class GenerateRequest(BaseModel):
    title: str
    content: str
    format: str  # docx, pptx, xlsx, pdf
    template: Optional[str] = None
    classification: str = "INTERNAL"


@router.post("/generate")
async def generate_file(
    data: GenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("generate_files")),
):
    if data.format not in ("docx", "pptx", "xlsx", "pdf"):
        raise HTTPException(status_code=400, detail=f"Unsupported format: {data.format}")

    file_path = await generator.generate(
        title=data.title,
        content=data.content,
        format=data.format,
        classification=data.classification,
    )

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=500, detail="File generation failed")

    file_size = os.path.getsize(file_path)
    filename = os.path.basename(file_path)

    db.add(GeneratedFile(
        id=uuid.uuid4(), filename=filename, title=data.title, format=data.format,
        classification=data.classification, size_bytes=file_size, source="manual", owner_id=current_user.id,
    ))
    await log_audit_event(db, current_user.id, "file_generated", "generation", filename,
                          {"format": data.format, "size": file_size, "classification": data.classification})

    return {
        "filename": filename,
        "format": data.format,
        "size": file_size,
        "classification": data.classification,
        "download_url": f"/api/generation/download/{filename}",
    }


@router.get("/download/{filename}")
async def download_file(
    filename: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Path traversal guard - filename must resolve to a plain file directly
    # inside GENERATED_DIR, never a parent path via '../' or an absolute path.
    file_path = os.path.join(settings.GENERATED_DIR, filename)
    real_path = os.path.realpath(file_path)
    real_generated = os.path.realpath(settings.GENERATED_DIR)
    if not real_path.startswith(real_generated + os.sep):
        raise HTTPException(status_code=403, detail="Access denied")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    # Ownership check: a generated file is private to whoever (or
    # whichever agent run, on their behalf) created it, unless the
    # requester can manage document permissions generally. Without
    # this, any authenticated user who guessed/saw a filename could
    # download anyone else's generated report.
    record = (await db.execute(select(GeneratedFile).where(GeneratedFile.filename == filename))).scalar_one_or_none()
    is_owner = record is not None and record.owner_id == current_user.id
    is_admin = user_has_permission(current_user, "manage_document_permissions")
    if not is_owner and not is_admin:
        raise HTTPException(status_code=403, detail="You do not have access to this generated file")

    await log_audit_event(db, current_user.id, "file_downloaded", "generation", filename)

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream",
    )


@router.get("/formats")
async def supported_formats(current_user: User = Depends(get_current_user)):
    return {
        "formats": [
            {"id": "docx", "name": "Word Document", "extension": ".docx"},
            {"id": "pptx", "name": "PowerPoint Presentation", "extension": ".pptx"},
            {"id": "xlsx", "name": "Excel Spreadsheet", "extension": ".xlsx"},
            {"id": "pdf", "name": "PDF Document", "extension": ".pdf"},
        ]
    }
