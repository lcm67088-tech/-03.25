"""
사용자 관리 라우터 (ADMIN 전용)
GET    /api/v1/users          — 목록
POST   /api/v1/users          — 생성
PATCH  /api/v1/users/{id}     — 수정
DELETE /api/v1/users/{id}     — 비활성화
"""
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.dependencies import AdminUser, DBSession
from app.core.security import hash_password
from app.models.user import User
from app.schemas.auth import UserCreate, UserRead, UserUpdate
from app.schemas.common import MessageResponse

router = APIRouter(tags=["사용자"])


@router.get("/", response_model=list[UserRead])
async def list_users(db: DBSession, _: AdminUser):
    """사용자 목록 (ADMIN 전용)"""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, db: DBSession, _: AdminUser):
    """사용자 생성 (ADMIN 전용)"""
    existing = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 사용 중인 이메일입니다.")

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


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(user_id: UUID, body: UserUpdate, db: DBSession, _: AdminUser):
    """사용자 수정 (ADMIN 전용)"""
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

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


@router.delete("/{user_id}", response_model=MessageResponse)
async def deactivate_user(user_id: UUID, db: DBSession, current_user: AdminUser):
    """사용자 비활성화 (ADMIN 전용)"""
    if user_id == current_user.id:
        raise HTTPException(400, "자기 자신은 비활성화할 수 없습니다.")

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    user.is_active = False
    await db.flush()
    return MessageResponse(message=f"사용자({user.email})가 비활성화되었습니다.")
