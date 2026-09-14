from fastapi import APIRouter, Depends, UploadFile, File, Form
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from auth.service import get_current_user
from models.orm import User
from database import get_db
from audit.service import log_audit_event
from audio.service import transcribe_file, transcription_status

router = APIRouter()


@router.get("/status")
async def status(current_user: User = Depends(get_current_user)):
    """Report whether local transcription is actually available - never
    fake success if the model isn't installed/loaded."""
    return transcription_status()


@router.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file_bytes = await file.read()

    try:
        result = await transcribe_file(file_bytes, file.filename, language=language)
    except RuntimeError as e:
        await log_audit_event(
            db, current_user.id, "audio_transcribe_failed", "audio", None,
            {"filename": file.filename, "reason": str(e)}
        )
        return {"success": False, "error": str(e), "text": "", "segments": []}

    await log_audit_event(
        db, current_user.id, "audio_transcribed", "audio", None,
        {"filename": file.filename, "duration_segments": len(result["segments"])}
    )

    return {"success": True, **result}
