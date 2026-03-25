"""
인증 라우터
POST /auth/login
POST /auth/logout
GET  /auth/me
"""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.dependencies import AdminUser, CurrentUser, DBSession, OperatorUser
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserCreate, UserRead, UserUpdate
from app.schemas.common import MessageResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: DBSession):
    """이메일 + 비밀번호 로그인 → JWT 발급"""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.hashed_pw):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    # 마지막 로그인 시각 갱신
    user.last_login_at = datetime.now(timezone.utc)

    token = create_access_token(
        subject=str(user.id),
        extra_claims={"role": user.role, "name": user.name},
    )

    from app.core.config import get_settings
    settings = get_settings()
    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(current_user: CurrentUser):
    """
    로그아웃 (클라이언트 측 토큰 폐기)
    Wave 1: 서버 측 블랙리스트 없음. 클라이언트가 토큰을 삭제하는 것으로 처리.
    Wave 2 이후: Redis 블랙리스트 도입 예정.
    """
    return MessageResponse(message="Logged out successfully")


@router.get("/me", response_model=UserRead)
async def me(current_user: CurrentUser):
    """현재 로그인 사용자 정보"""
    return current_user


# ── 사용자 관리 (ADMIN 전용) ──────────────────────────────
users_router = APIRouter(prefix="/users", tags=["users"])


@users_router.get("/", response_model=list[UserRead])
async def list_users(db: DBSession, _: AdminUser):
    """사용자 목록 (ADMIN 전용)"""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


@users_router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, db: DBSession, _: AdminUser):
    """사용자 생성 (ADMIN 전용)"""
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=body.email,
        name=body.name,
        hashed_pw=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@users_router.patch("/{user_id}", response_model=UserRead)
async def update_user(user_id: str, body: UserUpdate, db: DBSession, _: AdminUser):
    """사용자 수정 (ADMIN 전용)"""
    from uuid import UUID
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.name is not None:
        user.name = body.name
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.password is not None:
        user.hashed_pw = hash_password(body.password)

    await db.flush()
    await db.refresh(user)
    return user
