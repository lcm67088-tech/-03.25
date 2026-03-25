"""
OrderItem 라우터

엔드포인트:
  GET    /api/v1/order-items                — 목록 (필터: order_id, status, place_id, provider_id)
  GET    /api/v1/order-items/{id}           — 상세
  PATCH  /api/v1/order-items/{id}           — 필드 수정
  POST   /api/v1/order-items/{id}/status    — 상태 전이 (핵심)
  POST   /api/v1/order-items/{id}/assign    — 실행처 배정 (수동 라우팅)
  GET    /api/v1/order-items/{id}/history   — 상태 이력

Wave 1 상태 전이 매트릭스:
  received        → reviewing | on_hold | cancelled
  reviewing       → ready_to_route | on_hold | cancelled
  on_hold         → reviewing | cancelled
  ready_to_route  → assigned | on_hold | cancelled
  assigned        → in_progress | ready_to_route | cancelled
  in_progress     → done | assigned | cancelled
  done            → confirmed | in_progress
  confirmed       → settlement_ready
  settlement_ready→ closed
  cancelled       → (종료)
  closed          → (종료)

컬럼명 기준: 마이그레이션 001_initial_schema.py
"""
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_operator, require_admin
from app.core.response import ok, paginated
from app.core.exceptions import NotFoundError
from app.models.order import OrderItem, OrderItemStatusHistory, ORDER_ITEM_TRANSITIONS
from app.models.user import User

router = APIRouter()

# 상태 전이 허용 매트릭스 (models.order.ORDER_ITEM_TRANSITIONS 미러)
ALLOWED_TRANSITIONS: dict[str, list[str]] = ORDER_ITEM_TRANSITIONS

# ADMIN만 허용되는 전이 (정산 완료 단계)
ADMIN_ONLY_TRANSITIONS: set[tuple[str, str]] = {
    ("confirmed", "settlement_ready"),
    ("settlement_ready", "closed"),
}


# ── 인라인 스키마 ───────────────────────────────────────────────

class OrderItemUpdate(BaseModel):
    """운영자 수정 가능 필드 (마이그레이션 컬럼명 기준)"""
    place_id: Optional[uuid.UUID] = None
    place_name_snapshot: Optional[str] = None
    place_url_snapshot: Optional[str] = None           # 구 naver_place_url_snapshot
    naver_place_id_snapshot: Optional[str] = None
    sellable_offering_id: Optional[uuid.UUID] = None
    standard_product_type_id: Optional[uuid.UUID] = None
    product_type_code: Optional[str] = None            # 구 product_type_code_snapshot
    product_subtype: Optional[str] = None
    main_keyword: Optional[str] = None                 # 구 keyword_snapshot
    keywords_raw: Optional[str] = None                 # 쉼표 구분 키워드 원문 (구 keywords ARRAY)
    spec_data: Optional[dict] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    daily_qty: Optional[int] = None
    total_qty: Optional[int] = None
    working_days: Optional[int] = None
    unit_price: Optional[int] = None                   # 구 unit_price_snapshot
    total_amount: Optional[int] = None                 # 구 total_amount_snapshot
    operator_note: Optional[str] = None


class StatusTransitionRequest(BaseModel):
    to_status: str
    reason: Optional[str] = None                       # 구 note → reason (모델 기준)


class AssignProviderRequest(BaseModel):
    provider_id: uuid.UUID
    provider_offering_id: Optional[uuid.UUID] = None
    reason: Optional[str] = None


class OrderItemOut(BaseModel):
    id: str
    order_id: str
    place_id: Optional[str]
    place_name_snapshot: Optional[str]
    place_url_snapshot: Optional[str]
    naver_place_id_snapshot: Optional[str]
    standard_product_type_id: Optional[str]
    sellable_offering_id: Optional[str]
    product_type_code: Optional[str]
    product_subtype: Optional[str]
    provider_id: Optional[str]                         # 구 assigned_provider_id
    provider_offering_id: Optional[str]
    main_keyword: Optional[str]
    keywords_raw: Optional[str]
    spec_data: Optional[dict]
    start_date: Optional[date]
    end_date: Optional[date]
    daily_qty: Optional[int]
    total_qty: Optional[int]
    working_days: Optional[int]
    unit_price: Optional[int]
    total_amount: Optional[int]
    status: str
    routed_at: Optional[datetime]
    operator_note: Optional[str]
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm(cls, item: OrderItem) -> "OrderItemOut":
        return cls(
            id=str(item.id),
            order_id=str(item.order_id),
            place_id=str(item.place_id) if item.place_id else None,
            place_name_snapshot=item.place_name_snapshot,
            place_url_snapshot=item.place_url_snapshot,
            naver_place_id_snapshot=item.naver_place_id_snapshot,
            standard_product_type_id=(
                str(item.standard_product_type_id) if item.standard_product_type_id else None
            ),
            sellable_offering_id=(
                str(item.sellable_offering_id) if item.sellable_offering_id else None
            ),
            product_type_code=item.product_type_code,
            product_subtype=item.product_subtype,
            provider_id=str(item.provider_id) if item.provider_id else None,
            provider_offering_id=(
                str(item.provider_offering_id) if item.provider_offering_id else None
            ),
            main_keyword=item.main_keyword,
            keywords_raw=item.keywords_raw,
            spec_data=item.spec_data,
            start_date=item.start_date,
            end_date=item.end_date,
            daily_qty=item.daily_qty,
            total_qty=item.total_qty,
            working_days=item.working_days,
            unit_price=item.unit_price,
            total_amount=item.total_amount,
            status=item.status,
            routed_at=item.routed_at,
            operator_note=item.operator_note,
            is_deleted=item.is_deleted,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )


# ── 헬퍼 ────────────────────────────────────────────────────────

async def _get_item_or_404(item_id: uuid.UUID, db: AsyncSession) -> OrderItem:
    item = (
        await db.execute(
            select(OrderItem).where(
                OrderItem.id == item_id,
                OrderItem.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()
    if not item:
        raise NotFoundError("ORDER_ITEM_NOT_FOUND", f"OrderItem을 찾을 수 없습니다: {item_id}")
    return item


async def _add_status_history(
    db: AsyncSession,
    item_id: uuid.UUID,
    from_status: Optional[str],
    to_status: str,
    changed_by: Optional[uuid.UUID],
    reason: Optional[str] = None,
) -> None:
    """상태 이력 INSERT-only 기록 (changed_by = 마이그레이션 컬럼명)."""
    history = OrderItemStatusHistory(
        order_item_id=item_id,
        from_status=from_status,
        to_status=to_status,
        changed_by=changed_by,
        reason=reason,
    )
    db.add(history)


# ── 엔드포인트 ──────────────────────────────────────────────────

@router.get("", summary="OrderItem 목록")
async def list_order_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    order_id: Optional[uuid.UUID] = Query(None),
    item_status: Optional[str] = Query(None, alias="status"),
    place_id: Optional[uuid.UUID] = Query(None),
    provider_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(OrderItem).where(OrderItem.is_deleted.is_(False))
    if order_id:
        q = q.where(OrderItem.order_id == order_id)
    if item_status:
        q = q.where(OrderItem.status == item_status)
    if place_id:
        q = q.where(OrderItem.place_id == place_id)
    if provider_id:
        q = q.where(OrderItem.provider_id == provider_id)

    total = (
        await db.execute(select(func.count()).select_from(q.subquery()))
    ).scalar_one()
    offset = (page - 1) * page_size
    rows = (
        await db.execute(
            q.order_by(OrderItem.created_at.desc()).offset(offset).limit(page_size)
        )
    ).scalars().all()

    return paginated(
        [OrderItemOut.from_orm(i).model_dump() for i in rows],
        total, page, page_size,
    )


@router.get("/{item_id}", summary="OrderItem 상세")
async def get_order_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    item = await _get_item_or_404(item_id, db)
    return ok(OrderItemOut.from_orm(item).model_dump())


@router.patch("/{item_id}", summary="OrderItem 필드 수정")
async def update_order_item(
    item_id: uuid.UUID,
    body: OrderItemUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    item = await _get_item_or_404(item_id, db)

    if item.status in ("closed", "cancelled"):
        raise HTTPException(400, f"종료된 아이템은 수정할 수 없습니다. 상태: {item.status}")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(item, field, value)

    await db.commit()
    await db.refresh(item)
    return ok(OrderItemOut.from_orm(item).model_dump())


@router.post("/{item_id}/status", summary="상태 전이")
async def transition_status(
    item_id: uuid.UUID,
    body: StatusTransitionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """
    Wave 1 상태 전이.
    ADMIN_ONLY_TRANSITIONS에 해당하는 전이는 ADMIN만 가능.
    """
    item = await _get_item_or_404(item_id, db)
    from_status = item.status
    to_status = body.to_status

    allowed = ALLOWED_TRANSITIONS.get(from_status, [])
    if to_status not in allowed:
        raise HTTPException(
            400,
            f"허용되지 않는 상태 전이입니다: {from_status} → {to_status}. 허용: {allowed}",
        )

    if (from_status, to_status) in ADMIN_ONLY_TRANSITIONS:
        if not current_user.is_admin:
            raise HTTPException(
                403,
                f"이 전이({from_status} → {to_status})는 ADMIN만 가능합니다.",
            )

    item.status = to_status
    await _add_status_history(
        db, item.id, from_status, to_status,
        changed_by=current_user.id,
        reason=body.reason,
    )
    await db.commit()
    await db.refresh(item)
    return ok(OrderItemOut.from_orm(item).model_dump())


@router.post("/{item_id}/assign", summary="실행처 수동 배정 (라우팅)")
async def assign_provider(
    item_id: uuid.UUID,
    body: AssignProviderRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """
    Wave 1: 수동 라우팅.
    ready_to_route 또는 reviewing 상태에서 provider 배정.
    배정 후 상태를 자동으로 assigned로 전이.
    """
    item = await _get_item_or_404(item_id, db)

    if item.status not in ("ready_to_route", "reviewing"):
        raise HTTPException(
            400,
            f"ready_to_route 또는 reviewing 상태일 때만 배정 가능합니다. 현재: {item.status}",
        )

    old_status = item.status
    item.provider_id = body.provider_id
    item.provider_offering_id = body.provider_offering_id
    item.routed_at = datetime.now(timezone.utc)
    item.routed_by = current_user.id

    # 상태 자동 전이
    item.status = "assigned"
    await _add_status_history(
        db, item.id, old_status, "assigned",
        changed_by=current_user.id,
        reason=body.reason or "실행처 수동 배정",
    )

    await db.commit()
    await db.refresh(item)
    return ok(OrderItemOut.from_orm(item).model_dump())


@router.get("/{item_id}/history", summary="상태 이력 조회")
async def get_status_history(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    await _get_item_or_404(item_id, db)
    histories = (
        await db.execute(
            select(OrderItemStatusHistory)
            .where(OrderItemStatusHistory.order_item_id == item_id)
            .order_by(OrderItemStatusHistory.created_at.asc())
        )
    ).scalars().all()
    return ok([
        {
            "id": str(h.id),
            "from_status": h.from_status,
            "to_status": h.to_status,
            "changed_by": str(h.changed_by) if h.changed_by else None,
            "reason": h.reason,
            "created_at": h.created_at.isoformat(),
        }
        for h in histories
    ])
