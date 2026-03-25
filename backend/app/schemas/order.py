"""
Order 도메인 스키마
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema


# ── OrderRawInput ─────────────────────────────────────────
class OrderRawInputRead(BaseSchema):
    id: UUID
    source_type: str
    source_ref: Optional[str]
    source_sheet_name: Optional[str]
    source_row_index: Optional[int]
    import_job_id: Optional[UUID]
    raw_data: Dict[str, Any]
    is_processed: bool
    process_error: Optional[str]
    result_order_id: Optional[UUID]
    created_at: datetime


# ── OrderItemStatusHistory ────────────────────────────────
class OrderItemStatusHistoryRead(BaseSchema):
    id: UUID
    order_item_id: UUID
    from_status: Optional[str]
    to_status: str
    changed_by: Optional[UUID]
    reason: Optional[str]
    created_at: datetime


# ── OrderItem ─────────────────────────────────────────────
class OrderItemStatusUpdate(BaseSchema):
    """OrderItem 상태 전이 요청"""
    to_status: str = Field(
        description=(
            "received | on_hold | reviewing | ready_to_route | "
            "assigned | in_progress | done | confirmed | "
            "settlement_ready | closed | cancelled"
        )
    )
    reason: Optional[str] = None


class OrderItemRead(BaseSchema):
    id: UUID
    order_id: UUID
    standard_product_type_id: Optional[UUID]
    product_type_code: Optional[str]
    product_subtype: Optional[str]
    sellable_offering_id: Optional[UUID]
    place_id: Optional[UUID]
    place_name_snapshot: Optional[str]
    place_url_snapshot: Optional[str]
    naver_place_id_snapshot: Optional[str]
    main_keyword: Optional[str]
    keywords_raw: Optional[str]
    start_date: Optional[date]
    end_date: Optional[date]
    total_qty: Optional[int]
    daily_qty: Optional[int]
    working_days: Optional[int]
    unit_price: Optional[int]
    total_amount: Optional[int]
    spec_data: Optional[Dict[str, Any]]
    status: str
    provider_id: Optional[UUID]
    provider_offering_id: Optional[UUID]
    routed_at: Optional[datetime]
    routed_by: Optional[UUID]
    is_deleted: bool
    operator_note: Optional[str]
    created_at: datetime
    updated_at: datetime


class OrderItemUpdate(BaseSchema):
    """운영자 수정 (선택 필드만)"""
    product_type_code: Optional[str] = None
    product_subtype: Optional[str] = None
    place_id: Optional[UUID] = None
    place_name_snapshot: Optional[str] = None
    place_url_snapshot: Optional[str] = None
    naver_place_id_snapshot: Optional[str] = None
    main_keyword: Optional[str] = None
    keywords_raw: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    total_qty: Optional[int] = None
    daily_qty: Optional[int] = None
    working_days: Optional[int] = None
    unit_price: Optional[int] = None
    total_amount: Optional[int] = None
    spec_data: Optional[Dict[str, Any]] = None
    operator_note: Optional[str] = None


# ── Order ─────────────────────────────────────────────────
class OrderRead(BaseSchema):
    id: UUID
    agency_id: Optional[UUID]
    agency_name_snapshot: Optional[str]
    sales_rep_name: Optional[str]
    estimator_name: Optional[str]
    status: str
    raw_input_id: Optional[UUID]
    source_type: Optional[str]
    is_deleted: bool
    operator_note: Optional[str]
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemRead] = []


class OrderCreate(BaseSchema):
    """수동 주문 생성 (Wave 1 최소 기능)"""
    agency_id: Optional[UUID] = None
    agency_name_snapshot: Optional[str] = None
    sales_rep_name: Optional[str] = None
    estimator_name: Optional[str] = None
    operator_note: Optional[str] = None


class OrderUpdate(BaseSchema):
    agency_id: Optional[UUID] = None
    agency_name_snapshot: Optional[str] = None
    sales_rep_name: Optional[str] = None
    estimator_name: Optional[str] = None
    status: Optional[str] = None
    operator_note: Optional[str] = None


# ── 라우팅 ────────────────────────────────────────────────
class RouteAssignRequest(BaseSchema):
    provider_id: UUID
    provider_offering_id: Optional[UUID] = None


class RoutingCandidateRead(BaseSchema):
    provider_id: UUID
    provider_name: str
    provider_offering_id: Optional[UUID]
    provider_offering_name: Optional[str]
    is_default: bool
    priority: int
