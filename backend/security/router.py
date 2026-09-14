from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from typing import Optional

from database import get_db
from auth.service import get_current_user, require_permission
from models.orm import User, SecurityEvent, AuditEvent
from config import get_settings
from security import settings_service
from audit.service import log_audit_event

router = APIRouter()
settings = get_settings()


class AgenticSettingsUpdate(BaseModel):
    hitl_enabled: Optional[bool] = None
    sensitive_actions: Optional[list[str]] = None


@router.get("/settings/agentic")
async def get_agentic_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Any authenticated user can see whether HITL is on (it affects how
    their own requests behave); only 'manage_security' can change it."""
    return await settings_service.get_agentic_settings(db)


@router.put("/settings/agentic")
async def update_agentic_settings(
    data: AgenticSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("manage_security")),
):
    if data.hitl_enabled is not None:
        await settings_service.set_config(db, settings_service.HITL_ENABLED_KEY, data.hitl_enabled, current_user.id)
    if data.sensitive_actions is not None:
        await settings_service.set_config(db, settings_service.HITL_SENSITIVE_ACTIONS_KEY, data.sensitive_actions, current_user.id)

    await log_audit_event(db, current_user.id, "agentic_settings_updated", "system_config", None,
                           {"hitl_enabled": data.hitl_enabled, "sensitive_actions": data.sensitive_actions})

    return await settings_service.get_agentic_settings(db)


@router.get("/overview")
async def security_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("manage_security")),
):
    since = datetime.utcnow() - timedelta(hours=24)

    # Failed logins
    failed_logins = await db.execute(
        select(func.count(AuditEvent.id)).where(
            AuditEvent.action == "login_failed",
            AuditEvent.created_at >= since,
        )
    )

    # Security events
    sec_events = await db.execute(
        select(func.count(SecurityEvent.id)).where(SecurityEvent.created_at >= since)
    )

    # Blocked connections
    blocked = await db.execute(
        select(func.count(SecurityEvent.id)).where(
            SecurityEvent.event_type == "outbound_blocked",
            SecurityEvent.created_at >= since,
        )
    )

    return {
        "period": "24h",
        "failed_logins": failed_logins.scalar() or 0,
        "security_events": sec_events.scalar() or 0,
        "blocked_connections": blocked.scalar() or 0,
        "air_gapped": settings.AIR_GAPPED_MODE,
        "status": "secure",
    }


@router.get("/events")
async def security_events(
    limit: int = 50,
    severity: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("manage_security")),
):
    stmt = select(SecurityEvent).order_by(SecurityEvent.created_at.desc()).limit(limit)
    if severity:
        stmt = stmt.where(SecurityEvent.severity == severity)
    result = await db.execute(stmt)
    events = result.scalars().all()

    return {
        "events": [
            {
                "id": str(e.id),
                "type": e.event_type,
                "source": e.source,
                "destination": e.destination,
                "action": e.action_taken,
                "severity": e.severity,
                "details": e.details,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ]
    }
