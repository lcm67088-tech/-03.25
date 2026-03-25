"""
인증 라우터
POST /api/v1/auth/login   — JWT 발급
POST /api/v1/auth/logout  — 로그아웃
GET  /api/v1/auth/me      — 현재 사용자 정보
"""
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.dependencies import CurrentUser, DBSession
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserRead
from app.schemas.common import MessageResponse

router = APIRouter(tags=["인증"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: DBSession):
    """이메일 + 비밀번호 로그인 → JWT 발급"""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.hashed_pw):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다.",
        )

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    from app.core.config import get_settings
    settings = get_settings()

    token = create_access_token(
        subject=str(user.id),
        extra_claims={"role": user.role, "name": user.name},
    )

    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(current_user: CurrentUser):
    """
    로그아웃 (클라이언트 측 토큰 폐기)
    Wave 1: 서버 측 블랙리스트 없음.
    Wave 2 이후: Redis 블랙리스트 도입 예정.
    """
    return MessageResponse(message="로그아웃 되었습니다. 클라이언트에서 토큰을 삭제하세요.")


@router.get("/me", response_model=UserRead)
async def me(current_user: CurrentUser):
    """현재 로그인 사용자 정보"""
    return current_user
