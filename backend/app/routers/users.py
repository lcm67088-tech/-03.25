"""
사용자 관리 라우터 (ADMIN 전용)
GET    /api/v1/users          — 목록
POST   /api/v1/users          — 생성
GET    /api/v1/users/{id}     — 상세
PATCH  /api/v1/users/{id}     — 수정
DELETE /api/v1/users/{id}     — 비활성화 (소프트 삭제)
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.core.security import hash_password
from app.core.response import ok, paginated
from app.core.exceptions import NotFoundError, ConflictError
from app.models.user import User

router = APIRouter()

VALID_ROLES = {"ADMIN", "OPERATOR"}


# ── 스키마 ───────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str
    role: str = "OPERATOR"


class UserUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str
    is_active: bool

    @classmethod
    def from_orm(cls, user: User) -> "UserOut":
        return cls(
            id=str(user.id),
            email=user.email,
            name=user.name,
            role=user.role,
            is_active=user.is_active,
        )


# ── 엔드포인트 ──────────────────────────────────────────────────

@router.get("", summary="사용자 목록 (ADMIN)")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    offset = (page - 1) * page_size
    total = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    rows = (
        await db.execute(
            select(User).order_by(User.created_at.desc()).offset(offset).limit(page_size)
        )
    ).scalars().all()
    return paginated([UserOut.from_orm(u).model_dump() for u in rows], total, page, page_size)


@router.post("", status_code=status.HTTP_201_CREATED, summary="사용자 생성 (ADMIN)")
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    if body.role not in VALID_ROLES:
        raise HTTPException(400, f"역할은 {VALID_ROLES} 중 하나여야 합니다.")

    existing = (
        await db.execute(select(User).where(User.email == body.email))
    ).scalar_one_or_none()
    if existing:
        raise ConflictError("USER_EMAIL_CONFLICT", f"이미 사용 중인 이메일입니다: {body.email}")

    user = User(
        email=body.email,
        name=body.name,
        hashed_pw=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return ok(UserOut.from_orm(user).model_dump())


@router.get("/{user_id}", summary="사용자 상세 (ADMIN)")
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise NotFoundError("USER_NOT_FOUND", f"사용자를 찾을 수 없습니다: {user_id}")
    return ok(UserOut.from_orm(user).model_dump())


@router.patch("/{user_id}", summary="사용자 수정 (ADMIN)")
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise NotFoundError("USER_NOT_FOUND", f"사용자를 찾을 수 없습니다: {user_id}")

    if body.name is not None:
        user.name = body.name
    if body.role is not None:
        if body.role not in VALID_ROLES:
            raise HTTPException(400, f"역할은 {VALID_ROLES} 중 하나여야 합니다.")
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active

    await db.commit()
    await db.refresh(user)
    return ok(UserOut.from_orm(user).model_dump())


@router.delete("/{user_id}", summary="사용자 비활성화 (ADMIN)")
async def deactivate_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if str(user_id) == str(current_user.id):
        raise HTTPException(400, "자기 자신은 비활성화할 수 없습니다.")

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise NotFoundError("USER_NOT_FOUND", f"사용자를 찾을 수 없습니다: {user_id}")

    user.is_active = False
    await db.commit()
    return ok({"message": "사용자가 비활성화되었습니다.", "id": str(user_id)})
