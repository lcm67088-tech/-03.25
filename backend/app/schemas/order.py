"""
Order 도메인 스키마

컬럼명 기준: 마이그레이션 001_initial_schema.py (수정 라운드 2026-03-25)
변경 사항:
  - OrderRawInput: source_sheet_name / source_row_index (구 sheet_name/row_index)
  - Order: sales_rep_name, estimator_name, operator_note, deleted_by, source_type 추가
         brand_id, brand_name_snapshot, order_number 제거 (마이그레이션에 없음)
  - OrderItem: product_type_code, place_url_snapshot, naver_place_id_snapshot,
               main_keyword, keywords_raw, unit_price, total_amount, working_days,
               standard_product_type_id, provider_id, routed_at, routed_by, deleted_by 정합
  - OrderItemStatusHistory: changed_by (구 actor_id), reason (구 note)
  - source_type: web_portal(주경로) 포함
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema


# ── OrderRawInput ─────────────────────────────────────────────

class OrderRawInputRead(BaseSchema):
    id: UUID
    source_type: str
    source_ref: Optional[str]
    source_sheet_name: Optional[str]       # 구 sheet_name
    source_row_index: Optional[int]        # 구 row_index
    import_job_id: Optional[UUID]
    raw_data: Dict[str, Any]
    is_processed: bool
    process_error: Optional[str]
    result_order_id: Optional[UUID]
    created_at: datetime


# ── OrderItemStatusHistory ────────────────────────────────────

class OrderItemStatusHistoryRead(BaseSchema):
    id: UUID
    order_item_id: UUID
    from_status: Optional[str]
    to_status: str
    changed_by: Optional[UUID]             # 구 actor_id
    reason: Optional[str]                  # 구 note
    created_at: datetime


# ── OrderItem ─────────────────────────────────────────────────

class OrderItemStatusUpdate(BaseSchema):
    """OrderItem 상태 전이 요청"""
    to_status: str = Field(
        description=(
            "received | on_hold | reviewing | ready_to_route | "
            "assigned | in_progress | done | confirmed | "
            "settlement_ready | closed | cancelled"
        )
    )
    reason: Optional[str] = None           # 구 note → reason


class OrderItemRead(BaseSchema):
    id: UUID
    order_id: UUID
    standard_product_type_id: Optional[UUID]
    product_type_code: Optional[str]       # 구 product_type_snapshot
    product_subtype: Optional[str]
    sellable_offering_id: Optional[UUID]
    place_id: Optional[UUID]
    place_name_snapshot: Optional[str]
    place_url_snapshot: Optional[str]      # 구 naver_place_url_snapshot
    naver_place_id_snapshot: Optional[str]
    main_keyword: Optional[str]            # 구 keyword_snapshot
    keywords_raw: Optional[str]            # 구 keywords ARRAY → Text 쉼표구분
    start_date: Optional[date]
    end_date: Optional[date]
    total_qty: Optional[int]
    daily_qty: Optional[int]
    working_days: Optional[int]
    unit_price: Optional[int]              # 구 unit_price_snapshot
    total_amount: Optional[int]            # 구 total_amount_snapshot
    spec_data: Optional[Dict[str, Any]]
    status: str
    provider_id: Optional[UUID]            # 구 assigned_provider_id
    provider_offering_id: Optional[UUID]
    routed_at: Optional[datetime]          # 구 assigned_at
    routed_by: Optional[UUID]              # 구 assigned_by
    is_deleted: bool
    operator_note: Optional[str]
    created_at: datetime
    updated_at: datetime


class OrderItemUpdate(BaseSchema):
    """운영자 수정 (선택 필드만)"""
    product_type_code: Optional[str] = None
    product_subtype: Optional[str] = None
    standard_product_type_id: Optional[UUID] = None
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


# ── Order ─────────────────────────────────────────────────────

class OrderRead(BaseSchema):
    id: UUID
    agency_id: Optional[UUID]
    agency_name_snapshot: Optional[str]
    sales_rep_name: Optional[str]          # 구 sales_manager_snapshot
    estimator_name: Optional[str]          # 구 quote_manager_snapshot
    status: str
    raw_input_id: Optional[UUID]
    source_type: Optional[str]             # web_portal | google_sheet_import | ...
    is_deleted: bool
    operator_note: Optional[str]           # 구 note
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemRead] = []


class OrderCreate(BaseSchema):
    """직접 주문 생성 (web_portal 주 경로)"""
    agency_id: Optional[UUID] = None
    agency_name_snapshot: Optional[str] = None
    sales_rep_name: Optional[str] = None
    estimator_name: Optional[str] = None
    source_type: Optional[str] = Field(
        default="web_portal",
        description="web_portal(주경로) | google_sheet_import | excel_import | manual_input",
    )
    operator_note: Optional[str] = None


class OrderUpdate(BaseSchema):
    agency_id: Optional[UUID] = None
    agency_name_snapshot: Optional[str] = None
    sales_rep_name: Optional[str] = None
    estimator_name: Optional[str] = None
    status: Optional[str] = None
    operator_note: Optional[str] = None


# ── 라우팅 ────────────────────────────────────────────────────

class RouteAssignRequest(BaseSchema):
    provider_id: UUID
    provider_offering_id: Optional[UUID] = None
    reason: Optional[str] = None


class RoutingCandidateRead(BaseSchema):
    provider_id: UUID
    provider_name: str
    provider_offering_id: Optional[UUID]
    provider_offering_name: Optional[str]
    is_default: bool
    priority: int
