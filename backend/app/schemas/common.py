"""
공통 스키마
페이지네이션, 응답 래퍼 등
"""
from typing import Any, Generic, List, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class BaseSchema(BaseModel):
    """모든 스키마의 기반 — ORM 모드 활성화"""
    model_config = ConfigDict(from_attributes=True)


class PaginatedResponse(BaseSchema, Generic[T]):
    """페이지네이션 응답"""
    items: List[T]
    total: int
    page: int
    size: int
    pages: int


class MessageResponse(BaseSchema):
    """단순 메시지 응답"""
    message: str


class IDResponse(BaseSchema):
    """ID 반환 응답"""
    id: UUID


class ErrorResponse(BaseSchema):
    """오류 응답"""
    error: str
    detail: Optional[Any] = None
