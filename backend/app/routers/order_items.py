"""
OrderItem 라우터

엔드포인트:
  POST   /api/v1/order-items              — OrderItem 직접 생성 (web_portal 주 경로)
  GET    /api/v1/order-items              — 목록 (필터: order_id, status, place_id, provider_id, raw_input_id)
  GET    /api/v1/order-items/{id}         — 상세
  PATCH  /api/v1/order-items/{id}         — 필드 수정
  POST   /api/v1/order-items/{id}/status  — 상태 전이 (핵심)
  POST   /api/v1/order-items/{id}/assign  — 실행처 배정 (수동 라우팅)
  GET    /api/v1/order-items/{id}/history — 상태 이력

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

컬럼명 기준: 마이그레이션 002 (001 + raw 추적 컬럼 추가)
  raw_input_id      — loose ref, FK 없음. web_portal 생성 시 NULL
  source_row_index  — 원본 행 번호 (0-based)
  item_index_in_row — 행 내 아이템 순번 (0-based)
"""
import uuid
from datetime import date, datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_operator, require_admin
from app.core.response import ok, paginated
from app.core.exceptions import NotFoundError
from app.models.order import (
    Order, OrderItem, OrderItemStatusHistory,
    ORDER_ITEM_TRANSITIONS, ORDER_ITEM_STATUSES,
)
from app.models.provider import (
    SellableProviderMapping, ProviderOffering, Provider, SellableOffering, StandardProductType
)
from app.models.user import User

router = APIRouter()

# 상태 전이 허용 매트릭스
ALLOWED_TRANSITIONS: dict[str, list[str]] = ORDER_ITEM_TRANSITIONS

# ADMIN만 허용되는 전이
# Wave 2-A 결정: confirmed→settlement_ready 는 OPERATOR 허용, settlement_ready→closed 만 ADMIN 전용
ADMIN_ONLY_TRANSITIONS: set[tuple[str, str]] = {
    ("settlement_ready", "closed"),
}


# ── 인라인 스키마 ───────────────────────────────────────────────

class OrderItemCreate(BaseModel):
    """
    OrderItem 직접 생성 스키마 (web_portal 주 경로).

    POST /api/v1/orders 로 Order 헤더 생성 후
    이 엔드포인트로 아이템을 하나씩 추가합니다.

    raw 추적 컬럼(raw_input_id, source_row_index, item_index_in_row)은
    web_portal 직접 생성 시 전달하지 않습니다 (NULL 저장).
    standardize_service(from-raw 경유)에서만 채워넣습니다.
    """
    order_id: uuid.UUID = Field(..., description="소속 Order UUID (필수)")

    # 상품 정보
    product_type_code: Optional[str] = Field(
        None,
        description="상품 유형 코드. 예: TRAFFIC, SAVE, AI_REAL. 미입력 시 on_hold 상태로 생성.",
    )
    product_subtype: Optional[str] = None
    standard_product_type_id: Optional[uuid.UUID] = None
    sellable_offering_id: Optional[uuid.UUID] = None

    # 플레이스 정보
    place_id: Optional[uuid.UUID] = None
    place_name_snapshot: Optional[str] = Field(None, description="업체명 스냅샷")
    place_url_snapshot: Optional[str] = Field(None, description="네이버 플레이스 URL 스냅샷")
    naver_place_id_snapshot: Optional[str] = None

    # 키워드
    main_keyword: Optional[str] = Field(None, description="메인 작업 키워드")
    keywords_raw: Optional[str] = Field(None, description="추가 키워드 (쉼표 구분)")

    # 구동 기간·수량·금액
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    total_qty: Optional[int] = None
    daily_qty: Optional[int] = None
    working_days: Optional[int] = None
    unit_price: Optional[int] = None
    total_amount: Optional[int] = None

    # 부가
    spec_data: Optional[dict] = None
    operator_note: Optional[str] = None


class OrderItemUpdate(BaseModel):
    """운영자 수정 가능 필드 (마이그레이션 컬럼명 기준)"""
    place_id: Optional[uuid.UUID] = None
    place_name_snapshot: Optional[str] = None
    place_url_snapshot: Optional[str] = None
    naver_place_id_snapshot: Optional[str] = None
    sellable_offering_id: Optional[uuid.UUID] = None
    standard_product_type_id: Optional[uuid.UUID] = None
    product_type_code: Optional[str] = None
    product_subtype: Optional[str] = None
    main_keyword: Optional[str] = None
    keywords_raw: Optional[str] = None
    spec_data: Optional[dict] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    daily_qty: Optional[int] = None
    total_qty: Optional[int] = None
    working_days: Optional[int] = None
    unit_price: Optional[int] = None
    total_amount: Optional[int] = None
    operator_note: Optional[str] = None


class StatusTransitionRequest(BaseModel):
    to_status: str
    reason: Optional[str] = None


class AssignProviderRequest(BaseModel):
    provider_id: uuid.UUID
    provider_offering_id: Optional[uuid.UUID] = None
    reason: Optional[str] = None


class OrderItemOut(BaseModel):
    """
    OrderItem 응답 스키마.
    raw 추적 컬럼 포함 (마이그레이션 002 기준).
    """
    id: str
    order_id: str

    # raw 추적 (B안) — web_portal 직접 생성 시 null
    raw_input_id: Optional[str]
    source_row_index: Optional[int]
    item_index_in_row: Optional[int]

    # 플레이스
    place_id: Optional[str]
    place_name_snapshot: Optional[str]
    place_url_snapshot: Optional[str]
    naver_place_id_snapshot: Optional[str]

    # 상품
    standard_product_type_id: Optional[str]
    sellable_offering_id: Optional[str]
    product_type_code: Optional[str]
    product_subtype: Optional[str]

    # 실행처
    provider_id: Optional[str]
    provider_offering_id: Optional[str]

    # 키워드
    main_keyword: Optional[str]
    keywords_raw: Optional[str]

    # 기간·수량·금액
    spec_data: Optional[dict]
    start_date: Optional[date]
    end_date: Optional[date]
    daily_qty: Optional[int]
    total_qty: Optional[int]
    working_days: Optional[int]
    unit_price: Optional[int]
    total_amount: Optional[int]

    # 상태
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
            # raw 추적
            raw_input_id=str(item.raw_input_id) if item.raw_input_id else None,
            source_row_index=item.source_row_index,
            item_index_in_row=item.item_index_in_row,
            # 플레이스
            place_id=str(item.place_id) if item.place_id else None,
            place_name_snapshot=item.place_name_snapshot,
            place_url_snapshot=item.place_url_snapshot,
            naver_place_id_snapshot=item.naver_place_id_snapshot,
            # 상품
            standard_product_type_id=(
                str(item.standard_product_type_id) if item.standard_product_type_id else None
            ),
            sellable_offering_id=(
                str(item.sellable_offering_id) if item.sellable_offering_id else None
            ),
            product_type_code=item.product_type_code,
            product_subtype=item.product_subtype,
            # 실행처
            provider_id=str(item.provider_id) if item.provider_id else None,
            provider_offering_id=(
                str(item.provider_offering_id) if item.provider_offering_id else None
            ),
            # 키워드
            main_keyword=item.main_keyword,
            keywords_raw=item.keywords_raw,
            # 기간·수량·금액
            spec_data=item.spec_data,
            start_date=item.start_date,
            end_date=item.end_date,
            daily_qty=item.daily_qty,
            total_qty=item.total_qty,
            working_days=item.working_days,
            unit_price=item.unit_price,
            total_amount=item.total_amount,
            # 상태
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


async def _get_order_or_404(order_id: uuid.UUID, db: AsyncSession) -> Order:
    order = (
        await db.execute(
            select(Order).where(
                Order.id == order_id,
                Order.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()
    if not order:
        raise NotFoundError("ORDER_NOT_FOUND", f"Order를 찾을 수 없습니다: {order_id}")
    return order


async def _add_status_history(
    db: AsyncSession,
    item_id: uuid.UUID,
    from_status: Optional[str],
    to_status: str,
    changed_by: Optional[uuid.UUID],
    reason: Optional[str] = None,
) -> None:
    """상태 이력 INSERT-only 기록."""
    history = OrderItemStatusHistory(
        order_item_id=item_id,
        from_status=from_status,
        to_status=to_status,
        changed_by=changed_by,
        reason=reason,
    )
    db.add(history)


# ── 엔드포인트 ──────────────────────────────────────────────────

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="OrderItem 직접 생성 (web_portal 주 경로)",
)
async def create_order_item(
    body: OrderItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """
    web_portal 주 경로: `POST /api/v1/orders` 로 Order 헤더 생성 후
    이 엔드포인트로 아이템을 하나씩 추가합니다.

    동작:
    - order_id 유효성 검사 (삭제된 Order 거부)
    - product_type_code 미입력 시 status = on_hold (매핑 보류)
    - product_type_code 입력 시 status = received
    - 초기 상태 이력 자동 기록 (changed_by = 요청자)
    - raw 추적 컬럼(raw_input_id, source_row_index, item_index_in_row)은 NULL
      (web_portal 직접 생성 = raw 경유 없음)
    """
    # Order 존재·삭제 여부 확인
    await _get_order_or_404(body.order_id, db)

    # 상품 유형 미입력 시 on_hold
    initial_status = "received" if body.product_type_code else "on_hold"
    initial_note = (
        body.operator_note
        if body.product_type_code
        else (
            (body.operator_note + " | " if body.operator_note else "")
            + "product_type_code 미입력 — 운영자 직접 지정 필요"
        )
    )

    item = OrderItem(
        order_id=body.order_id,
        # raw 추적 컬럼: web_portal 직접 생성이므로 모두 NULL
        raw_input_id=None,
        source_row_index=None,
        item_index_in_row=None,
        # 상품
        product_type_code=body.product_type_code,
        product_subtype=body.product_subtype,
        standard_product_type_id=body.standard_product_type_id,
        sellable_offering_id=body.sellable_offering_id,
        # 플레이스
        place_id=body.place_id,
        place_name_snapshot=body.place_name_snapshot,
        place_url_snapshot=body.place_url_snapshot,
        naver_place_id_snapshot=body.naver_place_id_snapshot,
        # 키워드
        main_keyword=body.main_keyword,
        keywords_raw=body.keywords_raw,
        # 기간·수량·금액
        start_date=body.start_date,
        end_date=body.end_date,
        total_qty=body.total_qty,
        daily_qty=body.daily_qty,
        working_days=body.working_days,
        unit_price=body.unit_price,
        total_amount=body.total_amount,
        spec_data=body.spec_data,
        # 상태
        status=initial_status,
        operator_note=initial_note if initial_note else None,
    )
    db.add(item)
    await db.flush()  # item.id 확보

    # 초기 상태 이력
    await _add_status_history(
        db, item.id,
        from_status=None,
        to_status=initial_status,
        changed_by=current_user.id,
        reason="web_portal 직접 생성",
    )

    await db.commit()
    await db.refresh(item)
    return ok(OrderItemOut.from_orm(item).model_dump())


@router.get("", summary="OrderItem 목록")
async def list_order_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    order_id: Optional[uuid.UUID] = Query(None),
    item_status: Optional[str] = Query(None, alias="status"),
    place_id: Optional[uuid.UUID] = Query(None),
    provider_id: Optional[uuid.UUID] = Query(None),
    raw_input_id: Optional[uuid.UUID] = Query(None, description="raw_input_id 기준 필터 (B안 추적용)"),
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
    if raw_input_id:
        q = q.where(OrderItem.raw_input_id == raw_input_id)

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
            f"허용되지 않는 상태 전이: {from_status} → {to_status}. 허용: {allowed}",
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


@router.get(
    "/{item_id}/routing-candidates",
    summary="라우팅 후보 실행처 목록 (Wave 2-B)",
)
async def get_routing_candidates(
    item_id: uuid.UUID,
    limit: int = Query(5, ge=1, le=20, description="최대 후보 수 (1~20, 기본 5)"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """
    Wave 2-B: 라우팅 후보 실행처 목록.

    매칭 기준:
      1. OrderItem.sellable_offering_id 또는 product_type_code 기반 SellableOffering 조회
      2. SellableProviderMapping 테이블에서 매칭된 후보 조회
      3. 후보 정렬 순서:
           a. SellableProviderMapping.priority ASC (낙을수우선)
           b. provider_offering.cost_price ASC (cost_price <= item.unit_price면 is_price_ok=True)
           c. Provider.created_at ASC
      4. is_active=True 매핑과 Provider만 포함
      5. 단가 조건은 하드 필터 아님 — 응답에 is_price_ok 플래그로 리턴

    sellable_offering_id와 product_type_code 중 하나라도 없으면 204 리턴.
    """
    item = await _get_item_or_404(item_id, db)

    # sellable_offering_id 또는 product_type_code 기반 SellableOffering ID 목록
    sellable_ids: list[uuid.UUID] = []

    if item.sellable_offering_id:
        sellable_ids.append(item.sellable_offering_id)
    elif item.product_type_code:
        # product_type_code 매칭 시 SellableOffering 전체 조회
        spt_row = (
            await db.execute(
                select(StandardProductType).where(
                    StandardProductType.code == item.product_type_code,
                    StandardProductType.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if spt_row:
            so_rows = (
                await db.execute(
                    select(SellableOffering.id).where(
                        SellableOffering.standard_product_type_id == spt_row.id,
                        SellableOffering.is_active.is_(True),
                    )
                )
            ).scalars().all()
            sellable_ids.extend(so_rows)

    if not sellable_ids:
        return ok({
            "item_id": str(item_id),
            "product_type_code": item.product_type_code,
            "sellable_offering_id": None,
            "candidates": [],
            "message": "SellableOffering 연결 없음. sellable_offering_id 또는 product_type_code를 먼저 설정하세요.",
        })

    # SellableProviderMapping JOIN ProviderOffering JOIN Provider
    mapping_rows = (
        await db.execute(
            select(
                SellableProviderMapping,
                ProviderOffering,
                Provider,
            )
            .join(
                ProviderOffering,
                SellableProviderMapping.provider_offering_id == ProviderOffering.id,
            )
            .join(
                Provider,
                ProviderOffering.provider_id == Provider.id,
            )
            .where(
                SellableProviderMapping.sellable_offering_id.in_(sellable_ids),
                SellableProviderMapping.is_active.is_(True),
                ProviderOffering.is_active.is_(True),
                Provider.is_active.is_(True),
            )
            .order_by(
                SellableProviderMapping.priority.asc(),
                ProviderOffering.cost_price.asc().nullslast(),
                Provider.created_at.asc(),
            )
            .limit(limit)
        )
    ).all()

    candidates = []
    for rank, (mapping, po, prov) in enumerate(mapping_rows, start=1):
        # 단가 적합 여부 (is_price_ok): cost_price <= item.unit_price
        is_price_ok: Optional[bool] = None
        if po.cost_price is not None and item.unit_price is not None:
            is_price_ok = po.cost_price <= item.unit_price

        match_reasons = []
        if mapping.is_default:
            match_reasons.append("default_mapping")
        if is_price_ok is True:
            match_reasons.append("price_ok")
        elif is_price_ok is False:
            match_reasons.append("price_over")
        if mapping.priority == 0:
            match_reasons.append("top_priority")

        candidates.append({
            "rank": rank,
            "provider_id": str(prov.id),
            "provider_name": prov.name,
            "provider_offering_id": str(po.id),
            "provider_offering_name": po.name,
            "sellable_offering_id": str(mapping.sellable_offering_id),
            "mapping_priority": mapping.priority,
            "is_default": mapping.is_default,
            "cost_price": po.cost_price,
            "item_unit_price": item.unit_price,
            "is_price_ok": is_price_ok,
            "match_reasons": match_reasons,
        })

    return ok({
        "item_id": str(item_id),
        "product_type_code": item.product_type_code,
        "sellable_offering_id": (
            str(item.sellable_offering_id) if item.sellable_offering_id else None
        ),
        "candidates": candidates,
        "total_candidates": len(candidates),
    })
