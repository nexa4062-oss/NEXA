from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from database import get_db
from auth.service import get_current_user, require_permission
from models.orm import User, SecurityEvent
from network.monitor import SovereigntyMonitor
from config import get_settings

router = APIRouter()
settings = get_settings()
monitor = SovereigntyMonitor()


@router.get("/status")
async def network_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    status = await monitor.get_status()

    # Get recent blocked connections
    since = datetime.utcnow() - timedelta(hours=24)
    stmt = select(func.count(SecurityEvent.id)).where(
        SecurityEvent.event_type == "outbound_blocked",
        SecurityEvent.created_at >= since,
    )
    result = await db.execute(stmt)
    blocked_24h = result.scalar() or 0

    return {
        "air_gapped_mode": settings.AIR_GAPPED_MODE,
        "status": status,
        "blocked_connections_24h": blocked_24h,
        "blocked_domains": settings.BLOCKED_DOMAINS,
    }


@router.get("/events")
async def network_events(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("manage_security")),
):
    stmt = (
        select(SecurityEvent)
        .where(SecurityEvent.event_type.in_(["outbound_blocked", "outbound_attempt", "connection_allowed"]))
        .order_by(SecurityEvent.created_at.desc())
        .limit(limit)
    )
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


@router.post("/test-block")
async def test_network_block(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("manage_security")),
):
    """Test that external connections are properly blocked."""
    results = await monitor.test_blocking()

    for result in results:
        event = SecurityEvent(
            event_type="outbound_blocked" if result["blocked"] else "outbound_attempt",
            source="sovereignty_test",
            destination=result["domain"],
            action_taken="blocked" if result["blocked"] else "allowed",
            severity="info" if result["blocked"] else "critical",
            details={"test": True, "reason": result.get("reason", "")},
        )
        db.add(event)
    await db.flush()

    return {"test_results": results, "all_blocked": all(r["blocked"] for r in results)}
