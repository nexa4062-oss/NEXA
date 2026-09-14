from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr
from datetime import datetime

from database import get_db
from auth.service import get_current_user, require_permission
from auth.passwords import password_hasher
from models.orm import User, UserStatus, Role, Department
from audit.service import log_audit_event

router = APIRouter()


class UserCreate(BaseModel):
    employee_id: str
    username: str
    display_name: str
    email: Optional[str] = None
    department_id: Optional[UUID] = None
    designation: Optional[str] = None
    role_id: UUID
    password: str


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    email: Optional[str] = None
    department_id: Optional[UUID] = None
    designation: Optional[str] = None
    role_id: Optional[UUID] = None
    status: Optional[str] = None


class UserResponse(BaseModel):
    id: UUID
    employee_id: str
    username: str
    display_name: str
    email: Optional[str]
    department_id: Optional[UUID]
    designation: Optional[str]
    role_id: UUID
    status: str
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


@router.get("/")
async def list_users(
    skip: int = 0,
    limit: int = 50,
    status_filter: Optional[str] = None,
    department_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("manage_users")),
):
    stmt = select(User).options(selectinload(User.role), selectinload(User.department))
    if status_filter:
        stmt = stmt.where(User.status == status_filter)
    if department_id:
        stmt = stmt.where(User.department_id == department_id)
    stmt = stmt.offset(skip).limit(limit).order_by(User.created_at.desc())
    result = await db.execute(stmt)
    users = result.scalars().all()

    count_stmt = select(func.count(User.id))
    count_result = await db.execute(count_stmt)
    total = count_result.scalar()

    return {"users": [UserResponse.model_validate(u) for u in users], "total": total}


@router.get("/{user_id}")
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("manage_users")),
):
    stmt = select(User).options(
        selectinload(User.role), selectinload(User.department)
    ).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("manage_users")),
):
    existing = await db.execute(
        select(User).where((User.username == data.username) | (User.employee_id == data.employee_id))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username or employee ID already exists")

    role = await db.execute(select(Role).where(Role.id == data.role_id))
    if not role.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Invalid role_id")

    user = User(
        employee_id=data.employee_id,
        username=data.username,
        display_name=data.display_name,
        email=data.email,
        department_id=data.department_id,
        designation=data.designation,
        role_id=data.role_id,
        password_hash=password_hasher.hash(data.password),
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    await db.flush()

    await log_audit_event(db, current_user.id, "user_created", "user", str(user.id), {"username": data.username})
    return {"id": str(user.id), "message": "User created successfully"}


@router.patch("/{user_id}")
async def update_user(
    user_id: UUID,
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("manage_users")),
):
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)
    user.updated_at = datetime.utcnow()
    await db.flush()

    await log_audit_event(db, current_user.id, "user_updated", "user", str(user_id), update_data)
    return {"message": "User updated successfully"}


@router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("manage_users")),
):
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    temp_password = "TempPass123!"
    user.password_hash = password_hasher.hash(temp_password)
    user.failed_attempts = 0
    user.locked_until = None
    user.status = UserStatus.ACTIVE
    await db.flush()

    await log_audit_event(db, current_user.id, "password_reset", "user", str(user_id))
    return {"message": "Password reset. Temporary password: " + temp_password}


@router.get("/me/profile")
async def get_my_profile(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)
