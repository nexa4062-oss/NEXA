from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime
from uuid import UUID

from database import get_db
from auth.service import get_current_user, require_permission
from models.orm import User
from audit.service import AuditService

router = APIRouter()


@router.get("/events")
async def list_audit_events(
    user_id: Optional[UUID] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    severity: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    current_user: User = Depends(require_permission("view_audit")),
    db: AsyncSession = Depends(get_db),
):
    audit_service = AuditService(db)
    events = await audit_service.get_events(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        severity=severity,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )
    return {
        "events": [
            {
                "id": str(e.id),
                "user_id": str(e.user_id) if e.user_id else None,
                "action": e.action,
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
                "details": e.details,
                "severity": e.severity,
                "ip_address": e.ip_address,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ],
        "limit": limit,
        "offset": offset,
    }


@router.get("/security-events")
async def list_security_events(
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    current_user: User = Depends(require_permission("view_audit")),
    db: AsyncSession = Depends(get_db),
):
    audit_service = AuditService(db)
    events = await audit_service.get_security_events(
        event_type=event_type,
        severity=severity,
        limit=limit,
        offset=offset,
    )
    return {
        "events": [
            {
                "id": str(e.id),
                "event_type": e.event_type,
                "source": e.source,
                "destination": e.destination,
                "action_taken": e.action_taken,
                "details": e.details,
                "severity": e.severity,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ],
        "limit": limit,
        "offset": offset,
    }
