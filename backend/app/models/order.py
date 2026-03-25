"""
Order 도메인 모델
- OrderRawInput  : 원본 입력 불변 (INSERT 전용)
- Order          : 표준화 주문 헤더
- OrderItem      : 개별 작업 단위 (Wave 1: 1 raw row → 1 OrderItem)
- OrderItemStatusHistory : 상태 이력 불변 (INSERT 전용)

설계 원칙:
- OrderRawInput은 INSERT 전용. UPDATE/DELETE 금지.
- Order/OrderItem 삭제는 소프트 삭제만 허용.
- OrderItemStatusHistory는 INSERT 전용. 상태 전이마다 한 행씩 추가.
- import_job_id, result_order_id는 Loose reference (FK 없음, 고아 허용).

OrderItem 상태 전이 (Wave 1 최소 집합):
  received → reviewing / on_hold / cancelled
  reviewing → ready_to_route / on_hold / cancelled
  on_hold → reviewing / cancelled
  ready_to_route → assigned / cancelled
  assigned → in_progress / cancelled
  in_progress → done / on_hold
  done → confirmed
  confirmed → settlement_ready
  settlement_ready → closed
"""
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, ImmutableBase

if TYPE_CHECKING:
    from app.models.place import Place
    from app.models.provider import ProviderOffering, SellableOffering
    from app.models.user import User


# ─────────────────────────────────────────────────────────────
# OrderRawInput — 원본 입력 (불변)
# ─────────────────────────────────────────────────────────────

class OrderRawInput(ImmutableBase):
    """
    고객 접수 원본 입력 — 불변 저장
    INSERT 전용. UPDATE/DELETE 금지.
    source_type 우선순위: google_sheet_import > excel_import > manual_input

    Loose reference:
    - import_job_id  : FK 없음, 고아 허용
    - result_order_id: FK 없음, 표준화 완료 후 채워짐 (nullable)
    """
    __tablename__ = "order_raw_inputs"
    __table_args__ = {
        "comment": "고객 접수 원본 입력. INSERT 전용. UPDATE/DELETE 금지."
    }

    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="google_sheet_import(1차) | excel_import(보조) | manual_input",
    )
    source_ref: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="원본 참조 (시트 URL, 파일명, 행 식별자 등)",
    )

    # Loose references — FK 없음
    import_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="ImportJob UUID (loose reference, FK 없음 — 고아 허용)",
    )
    result_order_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="표준화 완료 후 생성된 Order UUID (loose reference, FK 없음)",
    )

    raw_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="원본 행 데이터 그대로. 구조 고정 없음.",
    )
    is_processed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="표준화 처리 완료 여부",
    )
    process_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="표준화 실패 시 오류 메시지",
    )

    def __repr__(self) -> str:
        return f"<OrderRawInput {self.source_type} processed={self.is_processed}>"


# ─────────────────────────────────────────────────────────────
# Order — 표준화 주문 헤더
# ─────────────────────────────────────────────────────────────

class Order(BaseModel):
    """
    표준화 주문 헤더
    원본(OrderRawInput) → 표준화 → 이 테이블에 확정값 저장.
    하나의 Order에 1개 이상의 OrderItem 포함 (Wave 1: 1:1 고정).
    """
    __tablename__ = "orders"
    __table_args__ = {"comment": "표준화 주문 헤더. OrderRawInput → 표준화 결과."}

    # ── 원본 연결 ──────────────────────────────────────────────
    raw_input_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="OrderRawInput UUID (loose reference, FK 없음 — 원본 보존)",
    )

    # ── 고객 정보 (Wave 1: snapshot 텍스트 우선, FK Wave 2) ────
    agency_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="대행사 FK (nullable, Wave 2 이후 강제 운영)",
    )
    agency_name_snapshot: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="대행사명 스냅샷 (FK 없어도 보존)",
    )
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="SET NULL"),
        nullable=True,
        comment="브랜드 FK (nullable)",
    )
    brand_name_snapshot: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="브랜드명 스냅샷"
    )

    # ── 주문 메타 ─────────────────────────────────────────────
    order_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        unique=True,
        comment="내부 주문 번호 (자동 생성 또는 수동 입력)",
    )
    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="google_sheet_import",
        comment="google_sheet_import | excel_import | manual_input",
    )
    note: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="주문 단위 운영자 메모"
    )

    # ── 소프트 삭제 ───────────────────────────────────────────
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Relations ─────────────────────────────────────────────
    order_items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Order {self.order_number or self.id}>"


# ─────────────────────────────────────────────────────────────
# OrderItem — 개별 작업 단위
# ─────────────────────────────────────────────────────────────

class OrderItem(BaseModel):
    """
    개별 작업 단위.
    Wave 1: 1 OrderRawInput → 1 OrderItem (1:1 고정).
    상태 전이마다 OrderItemStatusHistory에 INSERT.
    """
    __tablename__ = "order_items"
    __table_args__ = {
        "comment": "개별 작업 단위. Wave 1: 1:1 raw input 매핑."
    }

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="소속 Order FK (RESTRICT — 아이템 있으면 Order 삭제 불가)",
    )

    # ── Place 연결 ─────────────────────────────────────────────
    place_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("places.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Place FK (nullable, 검수 전에는 null 가능)",
    )
    place_name_snapshot: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="업체명 스냅샷"
    )
    naver_place_url_snapshot: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="네이버 플레이스 URL 스냅샷"
    )

    # ── 상품 연결 ─────────────────────────────────────────────
    sellable_offering_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sellable_offerings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="SellableOffering FK (nullable, 미매핑 허용)",
    )
    product_type_code_snapshot: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="StandardProductType 코드 스냅샷 (FK 없어도 보존)",
    )
    product_subtype: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="세부 구분 (BLOG_DISPATCH: 최블/엔비블 등)",
    )

    # ── 실행처 배정 ───────────────────────────────────────────
    assigned_provider_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("providers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="배정된 실행처 FK (라우팅 후 채워짐)",
    )
    assigned_provider_offering_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("provider_offerings.id", ondelete="SET NULL"),
        nullable=True,
        comment="배정된 ProviderOffering FK",
    )
    provider_name_snapshot: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="실행처명 스냅샷"
    )

    # ── 키워드 / 작업 스펙 ────────────────────────────────────
    keywords: Mapped[Optional[list[str]]] = mapped_column(
        JSONB,
        nullable=True,
        comment='키워드 목록. 예: ["네이버 맛집", "강남 카페"]',
    )
    spec_data: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="작업 스펙 (수량, 기간, 일 수량 등 유연 저장)",
    )
    start_date: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True, comment="작업 시작일"
    )
    end_date: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True, comment="작업 종료일"
    )
    daily_qty: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="일 수량 (트래픽·저장형)"
    )
    quantity: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="총 수량 (건수형)"
    )

    # ── 금액 ─────────────────────────────────────────────────
    unit_price: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="단가 (nullable, 미확정 허용)"
    )
    total_amount: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="합계 금액"
    )

    # ── 상태 ─────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="received",
        server_default="received",
        index=True,
        comment=(
            "OrderItem 상태 (Wave 1 최소 집합): "
            "received | on_hold | reviewing | ready_to_route | "
            "assigned | in_progress | done | confirmed | "
            "settlement_ready | closed | cancelled"
        ),
    )

    # ── 기타 ─────────────────────────────────────────────────
    operator_note: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="운영자 메모"
    )
    proof_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="완료 증빙 URL"
    )

    # ── 소프트 삭제 ───────────────────────────────────────────
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Relations ─────────────────────────────────────────────
    order: Mapped["Order"] = relationship("Order", back_populates="order_items")
    status_histories: Mapped[list["OrderItemStatusHistory"]] = relationship(
        "OrderItemStatusHistory", back_populates="order_item", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<OrderItem {self.id} [{self.status}]>"


# ─────────────────────────────────────────────────────────────
# OrderItemStatusHistory — 상태 이력 (불변)
# ─────────────────────────────────────────────────────────────

class OrderItemStatusHistory(ImmutableBase):
    """
    OrderItem 상태 전이 이력 — 불변 저장
    INSERT 전용. 전이마다 한 행씩 추가.
    OrderItem 삭제 시 RESTRICT (이력 있으면 삭제 불가).
    """
    __tablename__ = "order_item_status_histories"
    __table_args__ = {
        "comment": "OrderItem 상태 이력. INSERT 전용. 전이마다 한 행 추가."
    }

    order_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("order_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="OrderItem FK (RESTRICT — 이력 있으면 삭제 불가)",
    )

    from_status: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="전이 전 상태 (최초 생성 시 null)"
    )
    to_status: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="전이 후 상태"
    )

    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="전이를 실행한 운영자 FK",
    )
    note: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="전이 사유 또는 메모"
    )
    extra_data: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="추가 컨텍스트 (유연)"
    )

    # ── Relations ─────────────────────────────────────────────
    order_item: Mapped["OrderItem"] = relationship(
        "OrderItem", back_populates="status_histories"
    )

    def __repr__(self) -> str:
        return (
            f"<OrderItemStatusHistory "
            f"{self.from_status} → {self.to_status} item={self.order_item_id}>"
        )
