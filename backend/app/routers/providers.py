"""
Provider (실행처) 라우터
GET    /api/v1/providers          — 목록
POST   /api/v1/providers          — 생성 (OPERATOR+)
GET    /api/v1/providers/{id}     — 상세
PATCH  /api/v1/providers/{id}     — 수정 (OPERATOR+)
"""
import uuid
from typing import Optional, Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_operator
from app.core.response import ok, paginated
from app.core.exceptions import NotFoundError
from app.models.provider import Provider
from app.models.user import User

router = APIRouter()


class ProviderCreate(BaseModel):
    name: str
    provider_type: Optional[str] = None
    contact_info: Optional[dict[str, Any]] = None
    note: Optional[str] = None


class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    provider_type: Optional[str] = None
    contact_info: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None
    note: Optional[str] = None


class ProviderOut(BaseModel):
    id: str
    name: str
    provider_type: Optional[str]
    contact_info: Optional[dict]
    is_active: bool
    note: Optional[str]

    @classmethod
    def from_orm(cls, p: Provider) -> "ProviderOut":
        return cls(
            id=str(p.id),
            name=p.name,
            provider_type=p.provider_type,
            contact_info=p.contact_info,
            is_active=p.is_active,
            note=p.note,
        )


@router.get("", summary="실행처 목록")
async def list_providers(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(Provider)
    if is_active is not None:
        q = q.where(Provider.is_active == is_active)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    offset = (page - 1) * page_size
    rows = (
        await db.execute(q.order_by(Provider.name).offset(offset).limit(page_size))
    ).scalars().all()

    return paginated([ProviderOut.from_orm(p).model_dump() for p in rows], total, page, page_size)


@router.post("", status_code=status.HTTP_201_CREATED, summary="실행처 생성")
async def create_provider(
    body: ProviderCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    provider = Provider(**body.model_dump())
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return ok(ProviderOut.from_orm(provider).model_dump())


@router.get("/{provider_id}", summary="실행처 상세")
async def get_provider(
    provider_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    provider = (
        await db.execute(select(Provider).where(Provider.id == provider_id))
    ).scalar_one_or_none()
    if not provider:
        raise NotFoundError("PROVIDER_NOT_FOUND", f"실행처를 찾을 수 없습니다: {provider_id}")
    return ok(ProviderOut.from_orm(provider).model_dump())


@router.patch("/{provider_id}", summary="실행처 수정")
async def update_provider(
    provider_id: uuid.UUID,
    body: ProviderUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    provider = (
        await db.execute(select(Provider).where(Provider.id == provider_id))
    ).scalar_one_or_none()
    if not provider:
        raise NotFoundError("PROVIDER_NOT_FOUND", f"실행처를 찾을 수 없습니다: {provider_id}")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(provider, field, value)

    await db.commit()
    await db.refresh(provider)
    return ok(ProviderOut.from_orm(provider).model_dump())
