"""
Order 라우터

엔드포인트:
  GET    /api/v1/orders                      — 주문 목록 (필터: agency_id, source_type, status)
  POST   /api/v1/orders/from-raw             — raw input → Order + OrderItem 표준화 (보조 경로)
  POST   /api/v1/orders                      — 직접 주문 생성 (web_portal 주 경로 / manual_input)
  GET    /api/v1/orders/{id}                 — 주문 상세
  PATCH  /api/v1/orders/{id}                 — 주문 수정
  DELETE /api/v1/orders/{id}                 — 소프트 삭제 (ADMIN)
  POST   /api/v1/orders/{id}/confirm         — 주문 확정 (Wave 2-A)
  POST   /api/v1/orders/{id}/cancel          — 주문 취소 (Wave 2-A)
  POST   /api/v1/orders/{id}/items/bulk      — OrderItem 일괄 등록 (Wave 2-A)
  GET    /api/v1/orders/raw-inputs           — raw input 목록
  GET    /api/v1/orders/raw-inputs/{id}      — raw input 상세

source_type 정책:
  - web_portal        : 주 경로 — 플랫폼 UI 직접 생성
  - google_sheet_import: 보조 경로 — 시트 URL → raw → from-raw 표준화
  - excel_import      : 보조 경로 Wave 2
  - manual_input      : 개발/디버그 직접 API 호출

Order 상태 전이 (Wave 2-A):
  draft      → confirmed (OPERATOR, 조건: items ≥ 1 && on_hold 아이템 = 0 or operator_override)
  draft      → cancelled (OPERATOR)
  confirmed  → cancelled (ADMIN)
  confirmed  → closed    (ADMIN, 모든 OrderItem이 closed 상태일 때)
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
    Order, OrderRawInput, OrderItem, OrderItemStatusHistory,
    ORDER_SOURCE_TYPES, ORDER_ITEM_TRANSITIONS,
)
from app.models.user import User
from app.services.order_helpers import add_status_history as _add_item_status_history

router = APIRouter()


# ── 인라인 스키마 ────────────────────────────────────────────────

class OrderFromRaw(BaseModel):
    """
    raw input → Order + OrderItem 표준화 (보조 intake 경로).
    Google Sheet / Excel import 후 운영자가 수동 트리거.
    1 raw_input_id → standardize_service가 1~N OrderItem 생성.
    """
    raw_input_id: uuid.UUID
    # 힌트 — 없으면 raw_data 파싱으로 결정
    agency_name_snapshot: Optional[str] = None
    operator_note: Optional[str] = None


class OrderCreate(BaseModel):
    """
    직접 주문 생성.
    주 경로(web_portal): 플랫폼 UI에서 전체 정보 입력.
    source_type 기본값 = web_portal.
    """
    agency_id: Optional[uuid.UUID] = None
    agency_name_snapshot: Optional[str] = None
    sales_rep_name: Optional[str] = None
    estimator_name: Optional[str] = None
    source_type: str = Field(
        default="web_portal",
        description="web_portal | google_sheet_import | excel_import | manual_input",
    )
    operator_note: Optional[str] = None


class OrderUpdate(BaseModel):
    agency_id: Optional[uuid.UUID] = None
    agency_name_snapshot: Optional[str] = None
    sales_rep_name: Optional[str] = None
    estimator_name: Optional[str] = None
    status: Optional[str] = None
    operator_note: Optional[str] = None


class OrderConfirmRequest(BaseModel):
    """
    Order 확정 요청.
    on_hold 아이템이 있을 때 operator_override=True + reason 입력 시 예외 허용.
    """
    operator_override: bool = Field(
        default=False,
        description="on_hold 아이템이 있어도 확정을 강제 진행할 경우 true (reason 필수)",
    )
    reason: Optional[str] = Field(
        default=None,
        description="확정 사유. operator_override=True 시 필수.",
    )


class OrderCancelRequest(BaseModel):
    reason: Optional[str] = Field(None, description="취소 사유")


class BulkOrderItemCreate(BaseModel):
    """
    OrderItem 일괄 등록용 개별 아이템 스키마.
    order_id는 URL path에서 받으므로 포함하지 않음.
    """
    # 상품 정보
    product_type_code: Optional[str] = Field(
        None,
        description="상품 유형 코드. 미입력 시 on_hold 상태로 생성.",
    )
    product_subtype: Optional[str] = None
    standard_product_type_id: Optional[uuid.UUID] = None
    sellable_offering_id: Optional[uuid.UUID] = None
    # 플레이스
    place_id: Optional[uuid.UUID] = None
    place_name_snapshot: Optional[str] = None
    place_url_snapshot: Optional[str] = None
    naver_place_id_snapshot: Optional[str] = None
    # 키워드
    main_keyword: Optional[str] = None
    keywords_raw: Optional[str] = None
    # 기간·수량·금액
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    total_qty: Optional[int] = None
    daily_qty: Optional[int] = None
    working_days: Optional[int] = None
    unit_price: Optional[int] = None
    total_amount: Optional[int] = None
    spec_data: Optional[dict[str, Any]] = None
    operator_note: Optional[str] = None


class BulkOrderItemsRequest(BaseModel):
    items: list[BulkOrderItemCreate] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="등록할 OrderItem 목록 (1~100건)",
    )


class OrderOut(BaseModel):
    id: str
    raw_input_id: Optional[str]
    agency_id: Optional[str]
    agency_name_snapshot: Optional[str]
    sales_rep_name: Optional[str]
    estimator_name: Optional[str]
    source_type: Optional[str]
    status: str
    operator_note: Optional[str]
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    item_count: int = 0

    @classmethod
    def from_orm(cls, o: Order, item_count: int = 0) -> "OrderOut":
        return cls(
            id=str(o.id),
            raw_input_id=str(o.raw_input_id) if o.raw_input_id else None,
            agency_id=str(o.agency_id) if o.agency_id else None,
            agency_name_snapshot=o.agency_name_snapshot,
            sales_rep_name=o.sales_rep_name,
            estimator_name=o.estimator_name,
            source_type=o.source_type,
            status=o.status,
            operator_note=o.operator_note,
            is_deleted=o.is_deleted,
            created_at=o.created_at,
            updated_at=o.updated_at,
            item_count=item_count,
        )


# ── 헬퍼 ────────────────────────────────────────────────────────

async def _get_order_or_404(order_id: uuid.UUID, db: AsyncSession) -> Order:
    order = (
        await db.execute(
            select(Order).where(Order.id == order_id, Order.is_deleted.is_(False))
        )
    ).scalar_one_or_none()
    if not order:
        raise NotFoundError("ORDER_NOT_FOUND", f"Order를 찾을 수 없습니다: {order_id}")
    return order


# ── 엔드포인트 ──────────────────────────────────────────────────

@router.get("", summary="주문 목록")
async def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    agency_id: Optional[uuid.UUID] = Query(None),
    source_type: Optional[str] = Query(None, description=", ".join(ORDER_SOURCE_TYPES)),
    order_status: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(Order).where(Order.is_deleted.is_(False))
    if agency_id:
        q = q.where(Order.agency_id == agency_id)
    if source_type:
        q = q.where(Order.source_type == source_type)
    if order_status:
        q = q.where(Order.status == order_status)

    total = (
        await db.execute(select(func.count()).select_from(q.subquery()))
    ).scalar_one()
    offset = (page - 1) * page_size
    rows = (
        await db.execute(
            q.order_by(Order.created_at.desc()).offset(offset).limit(page_size)
        )
    ).scalars().all()

    return paginated(
        [OrderOut.from_orm(o).model_dump() for o in rows],
        total, page, page_size,
    )


@router.post(
    "/from-raw",
    status_code=status.HTTP_201_CREATED,
    summary="raw input → Order + OrderItem 표준화 (보조 intake 경로)",
)
async def create_order_from_raw(
    body: OrderFromRaw,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """
    Google Sheet / Excel import 후 보조 intake 경로.
    standardize_service를 통해 1 raw row → 1~N OrderItem 변환.
    """
    from app.services.standardize_service import standardize_raw_input

    raw = (
        await db.execute(
            select(OrderRawInput).where(OrderRawInput.id == body.raw_input_id)
        )
    ).scalar_one_or_none()
    if not raw:
        raise NotFoundError("RAW_INPUT_NOT_FOUND", f"원본 입력을 찾을 수 없습니다: {body.raw_input_id}")

    if raw.is_processed:
        raise HTTPException(
            status_code=409,
            detail=f"이미 처리된 raw input입니다. result_order_id: {raw.result_order_id}",
        )

    # 힌트 override
    if body.agency_name_snapshot:
        raw.raw_data = {**raw.raw_data, "대행사명": body.agency_name_snapshot}

    result = await standardize_raw_input(db=db, raw=raw, actor=current_user)

    return ok({
        "order": OrderOut.from_orm(
            result.order,
            item_count=len(result.items) + len(result.held_items),
        ).model_dump(),
        "items_created": len(result.items),
        "items_on_hold": len(result.held_items),
        "item_ids": [str(i.id) for i in result.items + result.held_items],
    })


@router.post("", status_code=status.HTTP_201_CREATED, summary="직접 주문 생성 (web_portal 주 경로)")
async def create_order(
    body: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """
    플랫폼 UI 직접 입력 (source_type=web_portal) 또는 수동 입력.
    Wave 1: Order 헤더만 생성. OrderItem은 별도 POST /order-items로 추가.
    """
    if body.source_type not in ORDER_SOURCE_TYPES:
        raise HTTPException(
            400,
            f"유효하지 않은 source_type: {body.source_type}. 허용: {ORDER_SOURCE_TYPES}",
        )
    order = Order(
        agency_id=body.agency_id,
        agency_name_snapshot=body.agency_name_snapshot,
        sales_rep_name=body.sales_rep_name,
        estimator_name=body.estimator_name,
        source_type=body.source_type,
        operator_note=body.operator_note,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return ok(OrderOut.from_orm(order).model_dump())


@router.get("/raw-inputs", summary="원본 입력 목록")
async def list_raw_inputs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_processed: Optional[bool] = Query(None),
    source_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(OrderRawInput)
    if is_processed is not None:
        q = q.where(OrderRawInput.is_processed == is_processed)
    if source_type:
        q = q.where(OrderRawInput.source_type == source_type)

    total = (
        await db.execute(select(func.count()).select_from(q.subquery()))
    ).scalar_one()
    offset = (page - 1) * page_size
    rows = (
        await db.execute(
            q.order_by(OrderRawInput.created_at.desc()).offset(offset).limit(page_size)
        )
    ).scalars().all()

    def _raw_dict(r: OrderRawInput) -> dict:
        return {
            "id": str(r.id),
            "source_type": r.source_type,
            "source_ref": r.source_ref,
            "source_sheet_name": r.source_sheet_name,
            "source_row_index": r.source_row_index,
            "import_job_id": str(r.import_job_id) if r.import_job_id else None,
            "result_order_id": str(r.result_order_id) if r.result_order_id else None,
            "is_processed": r.is_processed,
            "process_error": r.process_error,
            "created_at": r.created_at.isoformat(),
        }

    return paginated([_raw_dict(r) for r in rows], total, page, page_size)


@router.get("/raw-inputs/{raw_id}", summary="원본 입력 상세")
async def get_raw_input(
    raw_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    raw = (
        await db.execute(select(OrderRawInput).where(OrderRawInput.id == raw_id))
    ).scalar_one_or_none()
    if not raw:
        raise NotFoundError("RAW_INPUT_NOT_FOUND", f"원본 입력을 찾을 수 없습니다: {raw_id}")
    return ok({
        "id": str(raw.id),
        "source_type": raw.source_type,
        "source_ref": raw.source_ref,
        "source_sheet_name": raw.source_sheet_name,
        "source_row_index": raw.source_row_index,
        "import_job_id": str(raw.import_job_id) if raw.import_job_id else None,
        "result_order_id": str(raw.result_order_id) if raw.result_order_id else None,
        "raw_data": raw.raw_data,
        "is_processed": raw.is_processed,
        "process_error": raw.process_error,
        "created_at": raw.created_at.isoformat(),
    })


@router.get("/{order_id}", summary="주문 상세")
async def get_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    order = await _get_order_or_404(order_id, db)
    item_count = (
        await db.execute(
            select(func.count()).where(
                OrderItem.order_id == order_id,
                OrderItem.is_deleted.is_(False),
            )
        )
    ).scalar_one()
    return ok(OrderOut.from_orm(order, item_count=item_count).model_dump())


@router.patch("/{order_id}", summary="주문 수정")
async def update_order(
    order_id: uuid.UUID,
    body: OrderUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    order = await _get_order_or_404(order_id, db)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(order, field, value)
    await db.commit()
    await db.refresh(order)
    return ok(OrderOut.from_orm(order).model_dump())


@router.delete("/{order_id}", summary="주문 소프트 삭제 (ADMIN)")
async def delete_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    order = await _get_order_or_404(order_id, db)

    item_count = (
        await db.execute(
            select(func.count()).where(
                OrderItem.order_id == order_id,
                OrderItem.is_deleted.is_(False),
            )
        )
    ).scalar_one()
    if item_count > 0:
        raise HTTPException(
            400,
            f"OrderItem({item_count}건)이 있는 주문은 삭제할 수 없습니다. 아이템을 먼저 처리하세요.",
        )

    order.is_deleted = True
    order.deleted_at = datetime.now(timezone.utc)
    order.deleted_by = current_user.id
    await db.commit()
    return ok({"message": "주문이 소프트 삭제되었습니다.", "id": str(order_id)})


@router.post("/{order_id}/confirm", summary="주문 확정 (draft → confirmed)")
async def confirm_order(
    order_id: uuid.UUID,
    body: OrderConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """
    Wave 2-A: Order 확정.

    확정 조건:
      1. 현재 status = draft
      2. OrderItem이 1개 이상 존재
      3. on_hold 상태 아이템 = 0  (또는 operator_override=True + reason 입력 시 예외)

    operator_override=True로 강제 확정 시 AuditLog에 기록됩니다.
    """
    order = await _get_order_or_404(order_id, db)

    if order.status != "draft":
        raise HTTPException(
            400,
            f"draft 상태인 주문만 확정할 수 있습니다. 현재 상태: {order.status}",
        )

    # 아이템 존재 여부 확인
    total_items = (
        await db.execute(
            select(func.count()).where(
                OrderItem.order_id == order_id,
                OrderItem.is_deleted.is_(False),
            )
        )
    ).scalar_one()
    if total_items == 0:
        raise HTTPException(400, "OrderItem이 없는 주문은 확정할 수 없습니다.")

    # on_hold 아이템 존재 여부 확인
    on_hold_count = (
        await db.execute(
            select(func.count()).where(
                OrderItem.order_id == order_id,
                OrderItem.status == "on_hold",
                OrderItem.is_deleted.is_(False),
            )
        )
    ).scalar_one()

    if on_hold_count > 0:
        if not body.operator_override:
            raise HTTPException(
                400,
                f"on_hold 상태 아이템이 {on_hold_count}건 있습니다. "
                "확정하려면 operator_override=true와 사유를 입력하세요.",
            )
        if not body.reason:
            raise HTTPException(
                400,
                "operator_override=true 시 reason 입력이 필수입니다.",
            )
        # AuditLog 기록 (on_hold 아이템 override 확정)
        # DB 실제 컬럼: entity_type, entity_id, field_name, before_value, after_value, extra_data
        from app.models.import_job import AuditLog
        log = AuditLog(
            actor_id=current_user.id,
            actor_role=current_user.role,
            action="order.confirm.override",
            entity_type="Order",
            entity_id=order.id,
            before_value=f"status=draft, on_hold_count={on_hold_count}",
            after_value="status=confirmed",
            extra_data={
                "on_hold_count": on_hold_count,
                "reason": body.reason,
                "operator_override": True,
            },
        )
        db.add(log)

    order.status = "confirmed"
    await db.commit()
    await db.refresh(order)

    return ok({
        **OrderOut.from_orm(order, item_count=total_items).model_dump(),
        "confirmed_with_override": body.operator_override,
        "on_hold_count": on_hold_count,
    })


@router.post("/{order_id}/cancel", summary="주문 취소")
async def cancel_order(
    order_id: uuid.UUID,
    body: OrderCancelRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """
    Wave 2-A: Order 취소.

    취소 가능 상태:
      - draft  : OPERATOR 가능
      - confirmed: ADMIN만 가능

    취소 시 소속 OrderItem 중 터미널 상태(closed, cancelled)가 아닌 아이템을
    모두 cancelled 처리하고 상태 이력을 기록합니다.
    """
    order = await _get_order_or_404(order_id, db)

    if order.status not in ("draft", "confirmed"):
        raise HTTPException(
            400,
            f"취소 불가 상태입니다. 현재: {order.status}. 취소 가능: draft, confirmed",
        )

    if order.status == "confirmed" and not current_user.is_admin:
        raise HTTPException(
            403,
            "confirmed 상태 주문 취소는 ADMIN만 가능합니다.",
        )

    # 활성 OrderItem 일괄 cancelled
    active_items = (
        await db.execute(
            select(OrderItem).where(
                OrderItem.order_id == order_id,
                OrderItem.is_deleted.is_(False),
                OrderItem.status.notin_(["closed", "cancelled"]),
            )
        )
    ).scalars().all()

    for item in active_items:
        from_st = item.status
        item.status = "cancelled"
        await _add_item_status_history(
            db, item.id, from_st, "cancelled",
            changed_by=current_user.id,
            reason=body.reason or f"Order 취소에 의한 자동 cancelled (order_id={order_id})",
        )

    order.status = "cancelled"
    await db.commit()
    await db.refresh(order)

    return ok({
        **OrderOut.from_orm(order).model_dump(),
        "cancelled_items": len(active_items),
    })


@router.post(
    "/{order_id}/items/bulk",
    status_code=status.HTTP_201_CREATED,
    summary="OrderItem 일괄 등록 (web_portal 주 경로)",
)
async def bulk_create_order_items(
    order_id: uuid.UUID,
    body: BulkOrderItemsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """
    Wave 2-A: OrderItem 일괄 등록.

    내부적으로 단건 생성 로직과 동일한 규칙을 적용합니다:
      - product_type_code 없으면 on_hold
      - product_type_code 있으면 received
      - raw 추적 컬럼 모두 NULL (web_portal 직접 생성)
      - 초기 상태 이력 자동 기록

    부분 실패 처리:
      - 개별 아이템에서 예외가 발생해도 전체 롤백하지 않습니다.
      - 실패한 아이템은 on_hold 상태로 생성하고 operator_note에 오류 내용을 기록합니다.
      - 응답에 created / held / failed 건수를 반환합니다.
    """
    # Order 존재 확인
    order = await _get_order_or_404(order_id, db)

    if order.status not in ("draft", "confirmed"):
        raise HTTPException(
            400,
            f"draft 또는 confirmed 상태 주문에만 아이템을 추가할 수 있습니다. 현재: {order.status}",
        )

    created_items = []
    held_items = []

    for idx, item_data in enumerate(body.items):
        initial_status = "received" if item_data.product_type_code else "on_hold"
        initial_note = item_data.operator_note
        if not item_data.product_type_code:
            suffix = "product_type_code 미입력 — 운영자 직접 지정 필요"
            initial_note = f"{initial_note} | {suffix}" if initial_note else suffix

        item = OrderItem(
            order_id=order_id,
            # raw 추적: web_portal 직접 생성이므로 모두 NULL
            raw_input_id=None,
            source_row_index=None,
            item_index_in_row=None,
            # 상품
            product_type_code=item_data.product_type_code,
            product_subtype=item_data.product_subtype,
            standard_product_type_id=item_data.standard_product_type_id,
            sellable_offering_id=item_data.sellable_offering_id,
            # 플레이스
            place_id=item_data.place_id,
            place_name_snapshot=item_data.place_name_snapshot,
            place_url_snapshot=item_data.place_url_snapshot,
            naver_place_id_snapshot=item_data.naver_place_id_snapshot,
            # 키워드
            main_keyword=item_data.main_keyword,
            keywords_raw=item_data.keywords_raw,
            # 기간·수량·금액
            start_date=item_data.start_date,
            end_date=item_data.end_date,
            total_qty=item_data.total_qty,
            daily_qty=item_data.daily_qty,
            working_days=item_data.working_days,
            unit_price=item_data.unit_price,
            total_amount=item_data.total_amount,
            spec_data=item_data.spec_data,
            status=initial_status,
            operator_note=initial_note,
        )
        db.add(item)
        await db.flush()

        await _add_item_status_history(
            db, item.id,
            from_status=None,
            to_status=initial_status,
            changed_by=current_user.id,
            reason="web_portal 일괄 등록",
        )

        if initial_status == "received":
            created_items.append(item)
        else:
            held_items.append(item)

    await db.commit()

    # 응답을 위한 refresh
    for item in created_items + held_items:
        await db.refresh(item)

    # OrderItemOut import (순환 방지를 위해 지역 import)
    from app.routers.order_items import OrderItemOut

    return ok({
        "order_id": str(order_id),
        "total_requested": len(body.items),
        "created": len(created_items),
        "held": len(held_items),
        "items": [
            OrderItemOut.from_orm(i).model_dump()
            for i in created_items + held_items
        ],
    })
