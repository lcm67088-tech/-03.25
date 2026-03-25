"""
Offering 라우터 (상품 구조)
GET    /api/v1/offerings/standard-types          — StandardProductType 목록
GET    /api/v1/offerings/sellable                — SellableOffering 목록
POST   /api/v1/offerings/sellable                — SellableOffering 생성 (OPERATOR+)
GET    /api/v1/offerings/sellable/{id}           — SellableOffering 상세 (매핑 포함)
GET    /api/v1/offerings/provider                — ProviderOffering 목록
POST   /api/v1/offerings/provider                — ProviderOffering 생성 (OPERATOR+)
POST   /api/v1/offerings/mappings                — SellableOffering ↔ ProviderOffering 연결
GET    /api/v1/offerings/mappings                — 매핑 목록
DELETE /api/v1/offerings/mappings/{id}           — 매핑 해제 (ADMIN)
"""
import uuid
from typing import Optional, Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_operator, require_admin
from app.core.response import ok, paginated
from app.core.exceptions import NotFoundError, ConflictError
from app.models.provider import (
    StandardProductType,
    SellableOffering,
    ProviderOffering,
    SellableProviderMapping,
)
from app.models.user import User

router = APIRouter()


# ── 스키마 ───────────────────────────────────────────────────────

class SellableCreate(BaseModel):
    standard_product_type_id: uuid.UUID
    name: str
    description: Optional[str] = None
    base_price: Optional[int] = None
    unit: Optional[str] = None
    spec_data: Optional[dict[str, Any]] = None
    note: Optional[str] = None


class ProviderOfferingCreate(BaseModel):
    standard_product_type_id: uuid.UUID
    provider_id: uuid.UUID
    name: str
    cost_price: Optional[int] = None
    unit: Optional[str] = None
    spec_data: Optional[dict[str, Any]] = None
    note: Optional[str] = None


class MappingCreate(BaseModel):
    sellable_offering_id: uuid.UUID
    provider_offering_id: uuid.UUID
    is_default: bool = False
    priority: int = 0
    routing_conditions: Optional[dict[str, Any]] = None


# ── 엔드포인트 ──────────────────────────────────────────────────

@router.get("/standard-types", summary="[초안] StandardProductType 목록")
async def list_standard_types(
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """[초안/제안안] 취합 데이터 기반 제안. 확정본 아님."""
    q = select(StandardProductType)
    if is_active is not None:
        q = q.where(StandardProductType.is_active == is_active)
    rows = (
        await db.execute(q.order_by(StandardProductType.sort_order))
    ).scalars().all()
    return ok([
        {
            "id": str(t.id),
            "code": t.code,
            "display_name": t.display_name,
            "description": t.description,
            "channel": t.channel,
            "requires_period": t.requires_period,
            "requires_daily_qty": t.requires_daily_qty,
            "supports_subtype": t.supports_subtype,
            "is_active": t.is_active,
            "sort_order": t.sort_order,
        }
        for t in rows
    ])


@router.get("/sellable", summary="SellableOffering 목록")
async def list_sellable(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    type_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(SellableOffering).where(SellableOffering.is_active.is_(True))
    if type_id:
        q = q.where(SellableOffering.standard_product_type_id == type_id)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    offset = (page - 1) * page_size
    rows = (await db.execute(q.offset(offset).limit(page_size))).scalars().all()

    def _so_dict(s: SellableOffering) -> dict:
        return {
            "id": str(s.id),
            "standard_product_type_id": str(s.standard_product_type_id),
            "name": s.name,
            "base_price": s.base_price,
            "unit": s.unit,
            "spec_data": s.spec_data,
            "is_active": s.is_active,
        }

    return paginated([_so_dict(s) for s in rows], total, page, page_size)


@router.post("/sellable", status_code=status.HTTP_201_CREATED, summary="SellableOffering 생성")
async def create_sellable(
    body: SellableCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    offering = SellableOffering(**body.model_dump())
    db.add(offering)
    await db.commit()
    await db.refresh(offering)
    return ok({"id": str(offering.id), "name": offering.name})


@router.get("/sellable/{offering_id}", summary="SellableOffering 상세 (매핑 포함)")
async def get_sellable(
    offering_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    offering = (
        await db.execute(
            select(SellableOffering).where(SellableOffering.id == offering_id)
        )
    ).scalar_one_or_none()
    if not offering:
        raise NotFoundError("SELLABLE_NOT_FOUND", f"SellableOffering을 찾을 수 없습니다: {offering_id}")

    mappings = (
        await db.execute(
            select(SellableProviderMapping)
            .where(
                SellableProviderMapping.sellable_offering_id == offering_id,
                SellableProviderMapping.is_active.is_(True),
            )
            .order_by(SellableProviderMapping.priority)
        )
    ).scalars().all()

    return ok({
        "id": str(offering.id),
        "standard_product_type_id": str(offering.standard_product_type_id),
        "name": offering.name,
        "description": offering.description,
        "base_price": offering.base_price,
        "unit": offering.unit,
        "spec_data": offering.spec_data,
        "is_active": offering.is_active,
        "provider_mappings": [
            {
                "id": str(m.id),
                "provider_offering_id": str(m.provider_offering_id),
                "is_default": m.is_default,
                "priority": m.priority,
                "routing_conditions": m.routing_conditions,
            }
            for m in mappings
        ],
    })


@router.get("/provider", summary="ProviderOffering 목록")
async def list_provider_offerings(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    provider_id: Optional[uuid.UUID] = Query(None),
    type_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(ProviderOffering).where(ProviderOffering.is_active.is_(True))
    if provider_id:
        q = q.where(ProviderOffering.provider_id == provider_id)
    if type_id:
        q = q.where(ProviderOffering.standard_product_type_id == type_id)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    offset = (page - 1) * page_size
    rows = (await db.execute(q.offset(offset).limit(page_size))).scalars().all()

    def _po_dict(p: ProviderOffering) -> dict:
        return {
            "id": str(p.id),
            "standard_product_type_id": str(p.standard_product_type_id),
            "provider_id": str(p.provider_id),
            "name": p.name,
            "cost_price": p.cost_price,
            "unit": p.unit,
            "spec_data": p.spec_data,
            "is_active": p.is_active,
        }

    return paginated([_po_dict(p) for p in rows], total, page, page_size)


@router.post("/provider", status_code=status.HTTP_201_CREATED, summary="ProviderOffering 생성")
async def create_provider_offering(
    body: ProviderOfferingCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    offering = ProviderOffering(**body.model_dump())
    db.add(offering)
    await db.commit()
    await db.refresh(offering)
    return ok({"id": str(offering.id), "name": offering.name})


@router.post("/mappings", status_code=status.HTTP_201_CREATED, summary="Sellable ↔ Provider 연결")
async def create_mapping(
    body: MappingCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    existing = (
        await db.execute(
            select(SellableProviderMapping).where(
                SellableProviderMapping.sellable_offering_id == body.sellable_offering_id,
                SellableProviderMapping.provider_offering_id == body.provider_offering_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise ConflictError("MAPPING_CONFLICT", "이미 존재하는 매핑입니다.")

    mapping = SellableProviderMapping(**body.model_dump())
    db.add(mapping)
    await db.commit()
    await db.refresh(mapping)
    return ok({"id": str(mapping.id)})


@router.get("/mappings", summary="매핑 목록")
async def list_mappings(
    sellable_id: Optional[uuid.UUID] = Query(None),
    provider_offering_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(SellableProviderMapping).where(SellableProviderMapping.is_active.is_(True))
    if sellable_id:
        q = q.where(SellableProviderMapping.sellable_offering_id == sellable_id)
    if provider_offering_id:
        q = q.where(SellableProviderMapping.provider_offering_id == provider_offering_id)

    rows = (await db.execute(q.order_by(SellableProviderMapping.priority))).scalars().all()
    return ok([
        {
            "id": str(m.id),
            "sellable_offering_id": str(m.sellable_offering_id),
            "provider_offering_id": str(m.provider_offering_id),
            "is_default": m.is_default,
            "priority": m.priority,
            "routing_conditions": m.routing_conditions,
            "is_active": m.is_active,
        }
        for m in rows
    ])


@router.delete("/mappings/{mapping_id}", summary="매핑 해제 (ADMIN)")
async def delete_mapping(
    mapping_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    mapping = (
        await db.execute(
            select(SellableProviderMapping).where(SellableProviderMapping.id == mapping_id)
        )
    ).scalar_one_or_none()
    if not mapping:
        raise NotFoundError("MAPPING_NOT_FOUND", f"매핑을 찾을 수 없습니다: {mapping_id}")

    mapping.is_active = False
    await db.commit()
    return ok({"message": "매핑이 비활성화되었습니다.", "id": str(mapping_id)})
