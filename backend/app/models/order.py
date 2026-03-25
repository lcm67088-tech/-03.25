"""
Order / OrderItem / OrderRawInput / OrderItemStatusHistory 모델
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
    from app.models.provider import ProviderOffering, SellableOffering
    from app.models.user import User


# OrderItem 상태 목록 (확정)
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


class OrderRawInput(ImmutableBase):
    """원본 주문 행 — 불변 저장. INSERT 전용."""
    __tablename__ = "order_raw_inputs"
    __table_args__ = {"comment": "원본 주문 행. INSERT 전용. UPDATE/DELETE 금지."}

    import_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True,
        comment="ImportJob UUID (loose reference, FK 없음)",
    )
    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="google_sheet_import | excel_import | manual_input",
    )
    source_ref: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    sheet_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    row_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
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
        return f"<OrderRawInput row={self.row_index} source={self.source_type}>"


class Order(BaseModel):
    """주문 헤더"""
    __tablename__ = "orders"
    __table_args__ = {"comment": "주문 헤더. 상태 추적은 OrderItem 레벨에서."}

    agency_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    agency_name_snapshot: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    sales_manager_snapshot: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    quote_manager_snapshot: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    raw_input_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True,
        comment="원본 OrderRawInput UUID (loose reference, FK 없음)",
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="draft", server_default="draft",
        index=True, comment="draft | confirmed | cancelled | closed",
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )

    agency: Mapped[Optional["Agency"]] = relationship("Agency", foreign_keys=[agency_id])
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
    items: Mapped[list["OrderItem"]] = relationship("OrderItem", back_populates="order", lazy="select")

    def __repr__(self) -> str:
        return f"<Order {self.id} [{self.status}]>"


class OrderItem(BaseModel):
    """주문 아이템 — 실제 상태 추적·라우팅·정산 단위"""
    __tablename__ = "order_items"
    __table_args__ = {"comment": "주문 아이템. 실제 상태 추적·라우팅·정산 단위."}

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True,
    )
    raw_input_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True,
        comment="원본 OrderRawInput UUID (loose reference)",
    )
    raw_row_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    item_index_in_row: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    sellable_offering_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sellable_offerings.id", ondelete="SET NULL"),
        nullable=True, index=True,
        comment="nullable — 미매핑 상태 허용, 자동 추정 금지",
    )
    provider_offering_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("provider_offerings.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    place_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("places.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    product_type_snapshot: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    product_subtype: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    place_name_snapshot: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    keyword_snapshot: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    total_qty: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    daily_qty: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    unit_price_snapshot: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_amount_snapshot: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    spec_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="received", server_default="received",
        index=True,
        comment="received|on_hold|reviewing|ready_to_route|assigned|in_progress|done|confirmed|settlement_ready|closed|cancelled",
    )
    status_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assigned_provider_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("providers.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    assigned_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    operator_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    order: Mapped["Order"] = relationship("Order", back_populates="items")
    place: Mapped[Optional["Place"]] = relationship("Place", foreign_keys=[place_id])
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
    """OrderItem 상태 변화 이력 — 불변 저장. INSERT 전용."""
    __tablename__ = "order_item_status_histories"
    __table_args__ = {"comment": "OrderItem 상태 이력. INSERT 전용. RESTRICT 삭제."}

    order_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("order_items.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    from_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    to_status: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    extra_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    order_item: Mapped["OrderItem"] = relationship("OrderItem", back_populates="status_histories")

    def __repr__(self) -> str:
        return f"<OrderItemStatusHistory {self.from_status}→{self.to_status}>"
