"""
Order 라우터

엔드포인트:
  GET    /api/v1/orders                  — 주문 목록 (필터: agency_id, source_type, status)
  POST   /api/v1/orders/from-raw         — raw input → Order + OrderItem 표준화 (핵심 경로)
  POST   /api/v1/orders                  — 직접 주문 생성 (web_portal 주 경로 / manual_input)
  GET    /api/v1/orders/{id}             — 주문 상세
  PATCH  /api/v1/orders/{id}             — 주문 수정
  DELETE /api/v1/orders/{id}             — 소프트 삭제 (ADMIN)
  GET    /api/v1/orders/raw-inputs       — raw input 목록
  GET    /api/v1/orders/raw-inputs/{id}  — raw input 상세

source_type 정책:
  - web_portal        : 주 경로 — 플랫폼 UI 직접 생성
  - google_sheet_import: 보조 경로 — 시트 URL → raw → from-raw 표준화
  - excel_import      : 보조 경로 Wave 2
  - manual_input      : 개발/디버그 직접 API 호출
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

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
    ORDER_SOURCE_TYPES,
)
from app.models.user import User

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
