"""사용자 스키마"""
import uuid
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8)
    role: str = Field(default="OPERATOR", pattern="^(ADMIN|OPERATOR)$")


class UserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    role: Optional[str] = Field(default=None, pattern="^(ADMIN|OPERATOR)$")
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}
