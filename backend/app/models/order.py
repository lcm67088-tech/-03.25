"""
Order / OrderItem / OrderRawInput / OrderItemStatusHistory 모델

정합성 기준: alembic/versions/001_initial_schema.py
수정 라운드: 2026-03-25 — 마이그레이션 ↔ 모델 정합성 1차 수정
"""
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey,
    Integer, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, ImmutableBase

if TYPE_CHECKING:
    from app.models.agency import Agency
    from app.models.place import Place
    from app.models.provider import ProviderOffering, SellableOffering, StandardProductType
    from app.models.user import User


# ── OrderItem 상태 목록 (확정) ─────────────────────────────────
ORDER_ITEM_STATUSES = [
    "received",
    "on_hold",
    "reviewing",
    "ready_to_route",
    "assigned",
    "in_progress",
    "done",
    "confirmed",
    "settlement_ready",
    "closed",
    "cancelled",
]

# 허용 상태 전이 규칙 (from → [to, ...])
ORDER_ITEM_TRANSITIONS: dict[str, list[str]] = {
    "received":         ["on_hold", "reviewing", "cancelled"],
    "on_hold":          ["reviewing", "cancelled"],
    "reviewing":        ["ready_to_route", "on_hold", "cancelled"],
    "ready_to_route":   ["assigned", "on_hold", "cancelled"],
    "assigned":         ["in_progress", "ready_to_route", "cancelled"],
    "in_progress":      ["done", "assigned", "cancelled"],
    "done":             ["confirmed", "in_progress"],
    "confirmed":        ["settlement_ready"],
    "settlement_ready": ["closed"],
    "closed":           [],
    "cancelled":        [],
}

# source_type 허용 값
ORDER_SOURCE_TYPES = [
    "web_portal",           # 주 경로: 플랫폼 UI 직접 입력
    "google_sheet_import",  # 보조 경로: Google Sheet URL 일괄 접수
    "excel_import",         # 보조 경로: Excel 파일 업로드 (Wave 2)
    "manual_input",         # 개발/디버그용 직접 API 호출
]


class OrderRawInput(ImmutableBase):
    """원본 주문 행 — 불변 저장. INSERT 전용.

    마이그레이션 컬럼과 1:1 대응 (001_initial_schema.py 기준).
    """
    __tablename__ = "order_raw_inputs"
    __table_args__ = {"comment": "주문 원본 입력. INSERT 전용."}

    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="web_portal(주경로)|google_sheet_import|excel_import|manual_input",
    )
    source_ref: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    source_sheet_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    source_row_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    import_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True,
        comment="ImportJob UUID (loose reference, FK 없음)",
    )
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_processed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    process_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_order_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True,
        comment="생성된 Order UUID (loose reference, FK 없음)",
    )

    def __repr__(self) -> str:
        return f"<OrderRawInput row={self.source_row_index} source={self.source_type}>"


class Order(BaseModel):
    """주문 헤더.

    마이그레이션 컬럼과 1:1 대응 (001_initial_schema.py 기준).
    상태 추적은 OrderItem 레벨에서 수행.
    """
    __tablename__ = "orders"
    __table_args__ = {"comment": "주문 헤더. 상태 추적은 OrderItem 레벨에서."}

    agency_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    agency_name_snapshot: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # 마이그레이션 기준: sales_rep_name (구 sales_manager_snapshot)
    sales_rep_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # 마이그레이션 기준: estimator_name (구 quote_manager_snapshot)
    estimator_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="draft", server_default="draft",
        index=True, comment="draft | confirmed | cancelled | closed",
    )
    raw_input_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("order_raw_inputs.id", ondelete="SET NULL"),
        nullable=True,
        comment="원본 OrderRawInput UUID (FK: SET NULL)",
    )
    # 주 경로: web_portal / 보조: google_sheet_import, excel_import, manual_input
    source_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="web_portal(주경로)|google_sheet_import|excel_import|manual_input",
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    # 마이그레이션 기준: operator_note (구 note)
    operator_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    agency: Mapped[Optional["Agency"]] = relationship("Agency", foreign_keys=[agency_id])
    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Order {self.id} [{self.status}]>"


class OrderItem(BaseModel):
    """주문 아이템 — 실제 상태 추적·라우팅·정산 단위.

    마이그레이션 컬럼과 1:1 대응 (001_initial_schema.py 기준).
    """
    __tablename__ = "order_items"
    __table_args__ = {"comment": "주문 아이템. 실제 상태 추적·라우팅·정산 단위."}

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    # ── raw 추적 컬럼 (B안 · Wave 1 보강) ─────────────────────
    # loose reference: FK 제약 없음 — OrderRawInput 삭제/정리 시 영향 없음
    # web_portal 직접 생성 시 세 컬럼 모두 NULL
    raw_input_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True,
        comment="OrderRawInput UUID. loose ref (FK 없음). web_portal 직접 생성 시 NULL.",
    )
    source_row_index: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="원본 시트/파일 행 번호 (0-based). raw 경유 생성 시 채워넣음.",
    )
    item_index_in_row: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="같은 raw 행 내 아이템 순번 (0-based). 1 row → N items 분기 추적.",
    )
    # ── 표준 상품 유형 FK (nullable — 미매핑 허용)
    standard_product_type_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("standard_product_types.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    # 마이그레이션 기준: product_type_code (구 product_type_snapshot)
    product_type_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    product_subtype: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sellable_offering_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sellable_offerings.id", ondelete="SET NULL"),
        nullable=True, index=True,
        comment="nullable — 미매핑 상태 허용, 자동 추정 금지",
    )
    place_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("places.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    place_name_snapshot: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # 마이그레이션 기준: place_url_snapshot (구 naver_place_url_snapshot)
    place_url_snapshot: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    naver_place_id_snapshot: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # 마이그레이션 기준: main_keyword (구 keyword_snapshot)
    main_keyword: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # 쉼표 구분 키워드 원문 Text (구 keywords ARRAY)
    keywords_raw: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    total_qty: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    daily_qty: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    working_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 마이그레이션 기준: unit_price (구 unit_price_snapshot)
    unit_price: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 마이그레이션 기준: total_amount (구 total_amount_snapshot)
    total_amount: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    spec_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="received", server_default="received",
        index=True,
        comment=(
            "received|on_hold|reviewing|ready_to_route|assigned|"
            "in_progress|done|confirmed|settlement_ready|closed|cancelled"
        ),
    )
    # 마이그레이션 기준: provider_id (구 assigned_provider_id)
    provider_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("providers.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    provider_offering_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("provider_offerings.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    # 마이그레이션 기준: routed_at / routed_by (구 assigned_at / assigned_by)
    routed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    routed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    operator_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    order: Mapped["Order"] = relationship("Order", back_populates="items")
    place: Mapped[Optional["Place"]] = relationship("Place", foreign_keys=[place_id])
    standard_product_type: Mapped[Optional["StandardProductType"]] = relationship(
        "StandardProductType", foreign_keys=[standard_product_type_id]
    )
    sellable_offering: Mapped[Optional["SellableOffering"]] = relationship(
        "SellableOffering", foreign_keys=[sellable_offering_id]
    )
    provider_offering: Mapped[Optional["ProviderOffering"]] = relationship(
        "ProviderOffering", foreign_keys=[provider_offering_id]
    )
    status_histories: Mapped[list["OrderItemStatusHistory"]] = relationship(
        "OrderItemStatusHistory", back_populates="order_item", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<OrderItem {self.id} [{self.status}] order={self.order_id}>"


class OrderItemStatusHistory(ImmutableBase):
    """OrderItem 상태 변화 이력 — 불변 저장. INSERT 전용.

    마이그레이션 컬럼과 1:1 대응 (001_initial_schema.py 기준).
    """
    __tablename__ = "order_item_status_histories"
    __table_args__ = {"comment": "OrderItem 상태 이력. INSERT 전용. RESTRICT 삭제."}

    order_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("order_items.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    from_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    to_status: Mapped[str] = mapped_column(String(50), nullable=False)
    # 마이그레이션 기준: changed_by (구 actor_id)
    changed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    order_item: Mapped["OrderItem"] = relationship(
        "OrderItem", back_populates="status_histories"
    )

    def __repr__(self) -> str:
        return f"<OrderItemStatusHistory {self.from_status}→{self.to_status}>"
