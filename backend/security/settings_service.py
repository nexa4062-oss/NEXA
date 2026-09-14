"""Organisation-level settings backed by the system_config table.

Currently used for the agentic workflow's Human-in-the-Loop (HITL)
toggle. Deliberately tiny: get/set on a key-value table, nothing else.
"""
from datetime import datetime
from typing import Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.orm import SystemConfig

HITL_ENABLED_KEY = "agentic.hitl_enabled"
HITL_SENSITIVE_ACTIONS_KEY = "agentic.sensitive_actions"

# Default set of task types/actions that require human approval when HITL
# is turned on. Kept small and explicit per the "do not make every action
# require approval" requirement - code execution is the clear high-impact
# default; admins can widen this via PUT /api/security/settings/agentic.
DEFAULT_SENSITIVE_ACTIONS = ["coding"]


async def get_config(db: AsyncSession, key: str, default: Any = None) -> Any:
    result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        return default
    return row.value


async def set_config(db: AsyncSession, key: str, value: Any, user_id=None) -> None:
    result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        row = SystemConfig(key=key, value=value, updated_by=user_id, updated_at=datetime.utcnow())
        db.add(row)
    else:
        row.value = value
        row.updated_by = user_id
        row.updated_at = datetime.utcnow()
    await db.flush()


async def is_hitl_enabled(db: AsyncSession) -> bool:
    return bool(await get_config(db, HITL_ENABLED_KEY, default=False))


async def get_sensitive_actions(db: AsyncSession) -> list[str]:
    value = await get_config(db, HITL_SENSITIVE_ACTIONS_KEY, default=None)
    if not value:
        return list(DEFAULT_SENSITIVE_ACTIONS)
    return list(value)


async def get_agentic_settings(db: AsyncSession) -> dict:
    return {
        "hitl_enabled": await is_hitl_enabled(db),
        "sensitive_actions": await get_sensitive_actions(db),
    }
