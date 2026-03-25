"""
Order 라우터
GET    /api/v1/orders                    — 목록
POST   /api/v1/orders/from-raw           — raw input → Order + OrderItem 표준화 (핵심)
POST   /api/v1/orders                    — 수동 생성 (보조, Wave 1 최소 구현)
GET    /api/v1/orders/{id}               — 상세
PATCH  /api/v1/orders/{id}               — 수정
DELETE /api/v1/orders/{id}               — 소프트 삭제 (ADMIN)

GET    /api/v1/orders/raw-inputs          — 원본 입력 목록
GET    /api/v1/orders/raw-inputs/{id}     — 원본 입력 상세
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_operator, require_admin
from app.core.response import ok, paginated
from app.core.exceptions import NotFoundError
from app.models.order import Order, OrderRawInput, OrderItem, OrderItemStatusHistory
from app.models.user import User

router = APIRouter()


# ── 스키마 ───────────────────────────────────────────────────────

class OrderFromRaw(BaseModel):
    """
    raw input → Order + OrderItem 표준화
    Wave 1: 1 raw_input_id → 1 OrderItem (1:1 고정)
    """
    raw_input_id: uuid.UUID
    # 표준화 힌트 — 없으면 raw_data에서 파싱 시도
    agency_name_snapshot: Optional[str] = None
    brand_name_snapshot: Optional[str] = None
    note: Optional[str] = None


class OrderCreate(BaseModel):
    """수동 생성 (보조 경로, Wave 1 최소)"""
    agency_id: Optional[uuid.UUID] = None
    agency_name_snapshot: Optional[str] = None
    brand_id: Optional[uuid.UUID] = None
    brand_name_snapshot: Optional[str] = None
    source_type: str = "manual_input"
    note: Optional[str] = None


class OrderOut(BaseModel):
    id: str
    raw_input_id: Optional[str]
    order_number: Optional[str]
    agency_id: Optional[str]
    agency_name_snapshot: Optional[str]
    brand_id: Optional[str]
    brand_name_snapshot: Optional[str]
    source_type: str
    note: Optional[str]
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    item_count: int = 0

    @classmethod
    def from_orm(cls, o: Order, item_count: int = 0) -> "OrderOut":
        return cls(
            id=str(o.id),
            raw_input_id=str(o.raw_input_id) if o.raw_input_id else None,
            order_number=o.order_number,
            agency_id=str(o.agency_id) if o.agency_id else None,
            agency_name_snapshot=o.agency_name_snapshot,
            brand_id=str(o.brand_id) if o.brand_id else None,
            brand_name_snapshot=o.brand_name_snapshot,
            source_type=o.source_type,
            note=o.note,
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
    source_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(Order).where(Order.is_deleted.is_(False))
    if agency_id:
        q = q.where(Order.agency_id == agency_id)
    if source_type:
        q = q.where(Order.source_type == source_type)

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
    summary="raw input → Order + OrderItem 표준화 (핵심 경로)",
)
async def create_order_from_raw(
    body: OrderFromRaw,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """
    Wave 1 핵심 엔드포인트.
    1 raw_input (1 row) → 1 Order + 1 OrderItem (1:1 고정).
    raw_data에서 place_url, keywords, product_type 등을 파싱하여 OrderItem 생성.
    """
    # 1. raw input 조회
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

    # 2. raw_data에서 기본 정보 파싱 (Wave 1: 유연한 파싱)
    raw_data: dict = raw.raw_data or {}

    agency_name = body.agency_name_snapshot or raw_data.get("대행사명") or raw_data.get("agency_name")
    brand_name = body.brand_name_snapshot or raw_data.get("브랜드") or raw_data.get("brand_name")
    place_url = raw_data.get("모바일플레이스URL") or raw_data.get("naver_place_url") or raw_data.get("place_url")
    place_name = raw_data.get("업체명") or raw_data.get("place_name")
    product_name = raw_data.get("상품명") or raw_data.get("product_name")
    keywords_raw = raw_data.get("키워드") or raw_data.get("keywords") or []

    # 키워드 처리 (문자열이면 쉼표 분리)
    if isinstance(keywords_raw, str):
        keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]
    elif isinstance(keywords_raw, list):
        keywords = keywords_raw
    else:
        keywords = []

    # 3. Order 생성
    order = Order(
        raw_input_id=raw.id,
        agency_name_snapshot=agency_name,
        brand_name_snapshot=brand_name,
        source_type=raw.source_type,
        note=body.note,
    )
    db.add(order)
    await db.flush()  # order.id 확보

    # 4. OrderItem 생성 (Wave 1: 1:1 고정)
    item = OrderItem(
        order_id=order.id,
        place_name_snapshot=place_name,
        naver_place_url_snapshot=place_url,
        product_type_code_snapshot=product_name,
        keywords=keywords if keywords else None,
        spec_data=raw_data,  # raw_data 전체를 spec_data에 보관
        status="received",
    )
    db.add(item)
    await db.flush()  # item.id 확보

    # 5. 상태 이력 초기 기록
    history = OrderItemStatusHistory(
        order_item_id=item.id,
        from_status=None,
        to_status="received",
        actor_id=current_user.id,
        note="from-raw 표준화 생성",
    )
    db.add(history)

    # 6. raw input 처리 완료 표시 (loose reference)
    # NOTE: raw input은 불변이므로 is_processed만 업데이트
    raw.is_processed = True
    raw.result_order_id = order.id  # loose reference

    await db.commit()
    await db.refresh(order)

    return ok({
        "order": OrderOut.from_orm(order, item_count=1).model_dump(),
        "order_item_id": str(item.id),
        "status": item.status,
    })


@router.post("", status_code=status.HTTP_201_CREATED, summary="주문 수동 생성 (보조 경로)")
async def create_order(
    body: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Wave 1 최소 구현. 메인 흐름은 /from-raw 사용."""
    order = Order(
        agency_id=body.agency_id,
        agency_name_snapshot=body.agency_name_snapshot,
        brand_id=body.brand_id,
        brand_name_snapshot=body.brand_name_snapshot,
        source_type=body.source_type,
        note=body.note,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return ok(OrderOut.from_orm(order).model_dump())


@router.get("/raw-inputs", summary="원본 입력 목록 (ORDER_RAW)")
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
    body: OrderCreate,
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

    # OrderItem이 있으면 삭제 불가 (RESTRICT)
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
