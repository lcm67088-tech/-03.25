"""
인증 관련 스키마
"""
from typing import Optional
from uuid import UUID

from pydantic import EmailStr, Field

from app.schemas.common import BaseSchema


# ── 로그인 ────────────────────────────────────────────────
class LoginRequest(BaseSchema):
    email: EmailStr
    password: str = Field(min_length=6)


class TokenResponse(BaseSchema):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # 초 단위


# ── 사용자 정보 ────────────────────────────────────────────
class UserRead(BaseSchema):
    id: UUID
    email: str
    name: str
    role: str
    is_active: bool


class UserCreate(BaseSchema):
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=6)
    role: str = Field(default="OPERATOR", pattern="^(ADMIN|OPERATOR)$")


class UserUpdate(BaseSchema):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    role: Optional[str] = Field(default=None, pattern="^(ADMIN|OPERATOR)$")
    is_active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=6)
