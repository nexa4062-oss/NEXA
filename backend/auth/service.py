import uuid
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import get_settings
from database import get_db
from models.orm import User, UserStatus, Role, RolePermission, UserPermission, Session as SessionModel
from auth.passwords import password_hasher

settings = get_settings()
security = HTTPBearer()


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def authenticate(self, username: str, password: str) -> Optional[User]:
        stmt = (
            select(User)
            .options(selectinload(User.role))
            .where(
                (User.username == username) | (User.employee_id == username)
            )
        )
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            return None

        if user.status == UserStatus.LOCKED:
            if user.locked_until and user.locked_until > datetime.utcnow():
                return None
            user.status = UserStatus.ACTIVE
            user.failed_attempts = 0

        if user.status != UserStatus.ACTIVE:
            return None

        if not password_hasher.verify(user.password_hash, password):
            user.failed_attempts += 1
            if user.failed_attempts >= settings.MAX_LOGIN_ATTEMPTS:
                user.status = UserStatus.LOCKED
                user.locked_until = datetime.utcnow() + timedelta(
                    minutes=settings.LOCKOUT_DURATION_MINUTES
                )
            await self.db.flush()
            return None

        user.failed_attempts = 0
        user.last_login = datetime.utcnow()
        await self.db.flush()
        return user

    def create_access_token(self, user: User) -> str:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {
            "sub": str(user.id),
            "username": user.username,
            "role": user.role.name if user.role else None,
            "exp": expire,
            "type": "access",
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    def create_refresh_token(self, user: User) -> str:
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        payload = {
            "sub": str(user.id),
            "exp": expire,
            "type": "refresh",
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    async def create_session(self, user: User, token: str) -> SessionModel:
        import hashlib
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        session = SessionModel(
            id=uuid.uuid4(),
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
            is_active=True,
        )
        self.db.add(session)
        await self.db.flush()
        return session

    async def invalidate_session(self, token: str):
        import hashlib
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        stmt = select(SessionModel).where(
            SessionModel.token_hash == token_hash,
            SessionModel.is_active == True,
        )
        result = await self.db.execute(stmt)
        sessions = result.scalars().all()
        for session in sessions:
            session.is_active = False
        await self.db.flush()

    @staticmethod
    def decode_token(token: str) -> dict:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            return payload
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    payload = AuthService.decode_token(token)

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    stmt = (
        select(User)
        .options(
            selectinload(User.role).selectinload(Role.permissions).selectinload(RolePermission.permission),
            selectinload(User.permissions).selectinload(UserPermission.permission),
            selectinload(User.department),
        )
        .where(User.id == uuid.UUID(user_id))
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return user


def collect_permissions(user: User) -> set:
    """All permission names granted to a user, via their role and any
    direct per-user grants. Shared by require_permission() (route-level
    403s) and the agent's own permission gate (agents/orchestrator.py),
    so both enforce the exact same RBAC - never two copies that could
    drift apart."""
    user_permissions = set()

    if user.role and user.role.permissions:
        for rp in user.role.permissions:
            if rp.permission:
                user_permissions.add(rp.permission.name)

    if user.permissions:
        for up in user.permissions:
            if up.permission:
                user_permissions.add(up.permission.name)

    return user_permissions


def user_has_permission(user: User, permission_name: str) -> bool:
    return permission_name in collect_permissions(user)


def require_permission(permission_name: str):
    async def permission_checker(user: User = Depends(get_current_user)):
        if not user_has_permission(user, permission_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission_name} required",
            )
        return user
    return permission_checker
