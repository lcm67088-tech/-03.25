"""
표준 응답 래퍼
{ "data": ..., "meta": ..., "error": null }
"""
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Meta(BaseModel):
    total: int
    page: int
    page_size: int


class ApiResponse(BaseModel, Generic[T]):
    data: Optional[T] = None
    meta: Optional[Meta] = None
    error: Optional[Any] = None


def ok(data: Any, meta: Optional[Meta] = None) -> dict:
    return {"data": data, "meta": meta, "error": None}


def paginated(data: Any, total: int, page: int, page_size: int) -> dict:
    return {
        "data": data,
        "meta": {"total": total, "page": page, "page_size": page_size},
        "error": None,
    }
