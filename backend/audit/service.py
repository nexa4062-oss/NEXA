import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.orm import AuditEvent, SecurityEvent


async def log_audit_event(
    db: AsyncSession,
    user_id: Optional[uuid.UUID],
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
    severity: str = "info",
) -> AuditEvent:
    event = AuditEvent(
        id=uuid.uuid4(),
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
        ip_address=ip_address,
        severity=severity,
        created_at=datetime.utcnow(),
    )
    db.add(event)
    await db.flush()
    return event


async def log_security_event(
    db: AsyncSession,
    event_type: str,
    action_taken: str,
    source: Optional[str] = None,
    destination: Optional[str] = None,
    details: Optional[dict] = None,
    severity: str = "warning",
) -> SecurityEvent:
    event = SecurityEvent(
        id=uuid.uuid4(),
        event_type=event_type,
        source=source,
        destination=destination,
        action_taken=action_taken,
        details=details or {},
        severity=severity,
        created_at=datetime.utcnow(),
    )
    db.add(event)
    await db.flush()
    return event


class AuditService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        action: str,
        user_id: Optional[uuid.UUID] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        severity: str = "info",
    ) -> AuditEvent:
        event = AuditEvent(
            id=uuid.uuid4(),
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            severity=severity,
            created_at=datetime.utcnow(),
        )
        self.db.add(event)
        await self.db.flush()
        return event

    async def log_security_event(
        self,
        event_type: str,
        action_taken: str,
        source: Optional[str] = None,
        destination: Optional[str] = None,
        details: Optional[dict] = None,
        severity: str = "warning",
    ) -> SecurityEvent:
        event = SecurityEvent(
            id=uuid.uuid4(),
            event_type=event_type,
            source=source,
            destination=destination,
            action_taken=action_taken,
            details=details or {},
            severity=severity,
            created_at=datetime.utcnow(),
        )
        self.db.add(event)
        await self.db.flush()
        return event

    async def get_events(
        self,
        user_id: Optional[uuid.UUID] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        severity: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditEvent]:
        stmt = select(AuditEvent)
        conditions = []

        if user_id:
            conditions.append(AuditEvent.user_id == user_id)
        if action:
            conditions.append(AuditEvent.action == action)
        if resource_type:
            conditions.append(AuditEvent.resource_type == resource_type)
        if severity:
            conditions.append(AuditEvent.severity == severity)
        if start_date:
            conditions.append(AuditEvent.created_at >= start_date)
        if end_date:
            conditions.append(AuditEvent.created_at <= end_date)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(AuditEvent.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_security_events(
        self,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SecurityEvent]:
        stmt = select(SecurityEvent)
        conditions = []

        if event_type:
            conditions.append(SecurityEvent.event_type == event_type)
        if severity:
            conditions.append(SecurityEvent.severity == severity)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(SecurityEvent.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
