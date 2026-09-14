from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional
from uuid import UUID
from pydantic import BaseModel
from datetime import datetime

from database import get_db
from auth.service import get_current_user, require_permission
from models.orm import User, Role, Permission, RolePermission
from audit.service import log_audit_event

router = APIRouter()


class RoleCreate(BaseModel):
    name: str
    display_name: str
    description: Optional[str] = None


class RoleUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None


class PermissionAssign(BaseModel):
    permission_ids: list[UUID]


@router.get("/")
async def list_roles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Role).options(selectinload(Role.permissions).selectinload(RolePermission.permission))
    result = await db.execute(stmt)
    roles = result.scalars().all()
    return {
        "roles": [
            {
                "id": str(r.id),
                "name": r.name,
                "display_name": r.display_name,
                "description": r.description,
                "is_system": r.is_system,
                "permissions": [rp.permission.name for rp in r.permissions if rp.permission],
            }
            for r in roles
        ]
    }


@router.get("/permissions")
async def list_permissions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Permission).order_by(Permission.category, Permission.name)
    result = await db.execute(stmt)
    perms = result.scalars().all()
    return {
        "permissions": [
            {
                "id": str(p.id),
                "name": p.name,
                "display_name": p.display_name,
                "description": p.description,
                "category": p.category,
            }
            for p in perms
        ]
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_role(
    data: RoleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("manage_roles")),
):
    existing = await db.execute(select(Role).where(Role.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Role already exists")

    role = Role(name=data.name, display_name=data.display_name, description=data.description)
    db.add(role)
    await db.flush()

    await log_audit_event(db, current_user.id, "role_created", "role", str(role.id), {"name": data.name})
    return {"id": str(role.id), "message": "Role created"}


@router.patch("/{role_id}")
async def update_role(
    role_id: UUID,
    data: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("manage_roles")),
):
    stmt = select(Role).where(Role.id == role_id)
    result = await db.execute(stmt)
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.is_system:
        raise HTTPException(status_code=403, detail="Cannot modify system role")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(role, key, value)
    await db.flush()

    await log_audit_event(db, current_user.id, "role_updated", "role", str(role_id), update_data)
    return {"message": "Role updated"}


@router.post("/{role_id}/permissions")
async def assign_permissions(
    role_id: UUID,
    data: PermissionAssign,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("manage_roles")),
):
    stmt = select(Role).where(Role.id == role_id)
    result = await db.execute(stmt)
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    # Remove existing
    existing = await db.execute(select(RolePermission).where(RolePermission.role_id == role_id))
    for rp in existing.scalars().all():
        await db.delete(rp)

    # Add new
    for perm_id in data.permission_ids:
        rp = RolePermission(role_id=role_id, permission_id=perm_id)
        db.add(rp)
    await db.flush()

    await log_audit_event(db, current_user.id, "permissions_assigned", "role", str(role_id),
                          {"permission_count": len(data.permission_ids)})
    return {"message": f"Assigned {len(data.permission_ids)} permissions to role"}
