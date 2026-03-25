"""
OrderItem 라우터
GET    /api/v1/order-items                    — 목록 (필터: order_id, status, place_id)
GET    /api/v1/order-items/{id}               — 상세
PATCH  /api/v1/order-items/{id}               — 필드 수정
POST   /api/v1/order-items/{id}/status        — 상태 전이 (핵심)
POST   /api/v1/order-items/{id}/assign        — 실행처 배정 (수동 라우팅)
GET    /api/v1/order-items/{id}/history       — 상태 이력

Wave 1 상태 전이 매트릭스:
  received    → reviewing | on_hold | cancelled
  reviewing   → ready_to_route | on_hold | cancelled
  on_hold     → reviewing | cancelled
  ready_to_route → assigned | cancelled
  assigned    → in_progress | cancelled
  in_progress → done | on_hold
  done        → confirmed
  confirmed   → settlement_ready
  settlement_ready → closed
  cancelled   → (종료)
  closed      → (종료)
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
from app.models.order import OrderItem, OrderItemStatusHistory
from app.models.user import User

router = APIRouter()

# 상태 전이 허용 매트릭스
ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    "received":        ["reviewing", "on_hold", "cancelled"],
    "reviewing":       ["ready_to_route", "on_hold", "cancelled"],
    "on_hold":         ["reviewing", "cancelled"],
    "ready_to_route":  ["assigned", "cancelled"],
    "assigned":        ["in_progress", "cancelled"],
    "in_progress":     ["done", "on_hold"],
    "done":            ["confirmed"],
    "confirmed":       ["settlement_ready"],
    "settlement_ready":["closed"],
    "cancelled":       [],
    "closed":          [],
}

# ADMIN만 허용되는 전이 (역방향 또는 고급)
ADMIN_ONLY_TRANSITIONS: set[tuple[str, str]] = {
    ("done", "confirmed"),
    ("confirmed", "settlement_ready"),
    ("settlement_ready", "closed"),
}


# ── 스키마 ───────────────────────────────────────────────────────

class OrderItemUpdate(BaseModel):
    place_id: Optional[uuid.UUID] = None
    place_name_snapshot: Optional[str] = None
    naver_place_url_snapshot: Optional[str] = None
    sellable_offering_id: Optional[uuid.UUID] = None
    product_type_code_snapshot: Optional[str] = None
    product_subtype: Optional[str] = None
    keywords: Optional[list[str]] = None
    spec_data: Optional[dict] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    daily_qty: Optional[int] = None
    quantity: Optional[int] = None
    unit_price: Optional[int] = None
    total_amount: Optional[int] = None
    operator_note: Optional[str] = None
    proof_url: Optional[str] = None


class StatusTransitionRequest(BaseModel):
    to_status: str
    note: Optional[str] = None


class AssignProviderRequest(BaseModel):
    provider_id: uuid.UUID
    provider_offering_id: Optional[uuid.UUID] = None
    provider_name_snapshot: Optional[str] = None
    note: Optional[str] = None


class OrderItemOut(BaseModel):
    id: str
    order_id: str
    place_id: Optional[str]
    place_name_snapshot: Optional[str]
    naver_place_url_snapshot: Optional[str]
    sellable_offering_id: Optional[str]
    product_type_code_snapshot: Optional[str]
    product_subtype: Optional[str]
    assigned_provider_id: Optional[str]
    provider_name_snapshot: Optional[str]
    keywords: Optional[list]
    spec_data: Optional[dict]
    start_date: Optional[date]
    end_date: Optional[date]
    daily_qty: Optional[int]
    quantity: Optional[int]
    unit_price: Optional[int]
    total_amount: Optional[int]
    status: str
    operator_note: Optional[str]
    proof_url: Optional[str]
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
            naver_place_url_snapshot=item.naver_place_url_snapshot,
            sellable_offering_id=str(item.sellable_offering_id) if item.sellable_offering_id else None,
            product_type_code_snapshot=item.product_type_code_snapshot,
            product_subtype=item.product_subtype,
            assigned_provider_id=str(item.assigned_provider_id) if item.assigned_provider_id else None,
            provider_name_snapshot=item.provider_name_snapshot,
            keywords=item.keywords,
            spec_data=item.spec_data,
            start_date=item.start_date,
            end_date=item.end_date,
            daily_qty=item.daily_qty,
            quantity=item.quantity,
            unit_price=item.unit_price,
            total_amount=item.total_amount,
            status=item.status,
            operator_note=item.operator_note,
            proof_url=item.proof_url,
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
    actor_id: Optional[uuid.UUID],
    note: Optional[str] = None,
    extra_data: Optional[dict] = None,
) -> None:
    history = OrderItemStatusHistory(
        order_item_id=item_id,
        from_status=from_status,
        to_status=to_status,
        actor_id=actor_id,
        note=note,
        extra_data=extra_data,
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
        q = q.where(OrderItem.assigned_provider_id == provider_id)

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
    일부 전이는 ADMIN만 가능 (ADMIN_ONLY_TRANSITIONS).
    """
    item = await _get_item_or_404(item_id, db)
    from_status = item.status
    to_status = body.to_status

    # 허용 전이 검증
    allowed = ALLOWED_TRANSITIONS.get(from_status, [])
    if to_status not in allowed:
        raise HTTPException(
            400,
            f"허용되지 않는 상태 전이입니다: {from_status} → {to_status}. "
            f"허용: {allowed}",
        )

    # ADMIN 전용 전이 검증
    if (from_status, to_status) in ADMIN_ONLY_TRANSITIONS:
        if not current_user.is_admin:
            raise HTTPException(
                403,
                f"이 전이({from_status} → {to_status})는 ADMIN만 가능합니다.",
            )

    item.status = to_status
    await _add_status_history(
        db, item.id, from_status, to_status, current_user.id, note=body.note
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
    배정 후 상태를 ready_to_route → assigned로 자동 전이.
    """
    item = await _get_item_or_404(item_id, db)

    if item.status not in ("ready_to_route", "reviewing"):
        raise HTTPException(
            400,
            f"ready_to_route 또는 reviewing 상태일 때만 배정 가능합니다. 현재: {item.status}",
        )

    old_status = item.status
    item.assigned_provider_id = body.provider_id
    item.assigned_provider_offering_id = body.provider_offering_id
    if body.provider_name_snapshot:
        item.provider_name_snapshot = body.provider_name_snapshot

    # 상태 자동 전이
    if old_status != "assigned":
        item.status = "assigned"
        await _add_status_history(
            db, item.id, old_status, "assigned", current_user.id,
            note=body.note or "실행처 수동 배정",
            extra_data={"provider_id": str(body.provider_id)},
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
            "actor_id": str(h.actor_id) if h.actor_id else None,
            "note": h.note,
            "extra_data": h.extra_data,
            "created_at": h.created_at.isoformat(),
        }
        for h in histories
    ])
