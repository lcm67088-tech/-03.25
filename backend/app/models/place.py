"""
Place 도메인 모델
- Place: 운영자 확정값 저장
- PlaceRawSnapshot: 원본 불변 (INSERT 전용)
- PlaceReviewLog: 검수 이력 불변 (INSERT 전용)

설계 원칙:
- PlaceRawSnapshot은 INSERT 전용. 부모(Place) 삭제 시 SET NULL으로 고아 보존.
- Place 삭제는 소프트 삭제(is_deleted) 사용.
- PlaceReviewLog는 RESTRICT — 로그가 있으면 Place 삭제 불가.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, ImmutableBase


class Place(BaseModel):
    """
    네이버 플레이스 확정 레코드
    원본(PlaceRawSnapshot) → 검수 → 이 테이블에 확정값 저장
    """
    __tablename__ = "places"
    __table_args__ = {"comment": "네이버 플레이스 확정 레코드"}

    # ── 네이버 플레이스 식별 ──────────────────────────────────
    naver_place_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        unique=True,
        nullable=True,
        index=True,
        comment="네이버 플레이스 MID (URL에서 파싱)",
    )
    naver_place_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="네이버 플레이스 URL",
    )

    # ── 운영자 확정값 (검수 후 채워짐) ───────────────────────
    confirmed_name: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="확정 업체명"
    )
    confirmed_category: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="확정 업종 카테고리"
    )
    confirmed_address: Mapped[Optional[str]] = mapped_column(
        String(300), nullable=True, comment="확정 주소"
    )
    confirmed_phone: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="확정 전화번호"
    )

    # ── 대행사/브랜드 연결 (Wave 1: nullable. Wave 2 이후 강제 운영) ──
    agency_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="대행사 FK (nullable, Wave 2 이후 강제 운영)",
    )
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="SET NULL"),
        nullable=True,
        comment="브랜드 FK (nullable, Wave 2 이후 강제 운영)",
    )
    agency_name_snapshot: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="대행사명 스냅샷 (FK 없어도 보존)"
    )
    brand_name_snapshot: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="브랜드명 스냅샷"
    )

    # ── 검수 상태 ─────────────────────────────────────────────
    review_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending_review",
        server_default="pending_review",
        index=True,
        comment="검수 상태: pending_review | in_review | confirmed | rejected",
    )
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="검수 확정 운영자 FK",
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="검수 확정 시각"
    )

    # ── 소프트 삭제 (raw 원본 보존을 위해 하드 삭제 대신 사용) ──
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="소프트 삭제 여부",
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    operator_note: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="운영자 메모"
    )

    # ── Relations ─────────────────────────────────────────────
    agency: Mapped[Optional["Agency"]] = relationship("Agency", foreign_keys=[agency_id])  # noqa: F821
    brand: Mapped[Optional["Brand"]] = relationship("Brand", foreign_keys=[brand_id])  # noqa: F821
    reviewer: Mapped[Optional["User"]] = relationship("User", foreign_keys=[reviewed_by])  # noqa: F821
    raw_snapshots: Mapped[list["PlaceRawSnapshot"]] = relationship(
        "PlaceRawSnapshot", back_populates="place"
    )
    review_logs: Mapped[list["PlaceReviewLog"]] = relationship(
        "PlaceReviewLog", back_populates="place"
    )

    def __repr__(self) -> str:
        return f"<Place {self.confirmed_name or self.naver_place_id} [{self.review_status}]>"


class PlaceRawSnapshot(ImmutableBase):
    """
    Place 원본 파싱 결과 — 불변 저장
    INSERT 전용. UPDATE/DELETE 금지.
    부모(Place) 삭제 시 SET NULL으로 고아 레코드 보존.
    """
    __tablename__ = "place_raw_snapshots"
    __table_args__ = {
        "comment": "Place 원본 스냅샷. INSERT 전용. UPDATE/DELETE 금지."
    }

    place_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("places.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="연결된 Place FK (검수 전에는 null, SET NULL으로 고아 보존)",
    )

    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment=(
            "입력 출처: google_sheet_import(1차) | manual_input | excel_import | url_parse"
        ),
    )
    source_ref: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="원본 출처 참조 (시트명, 파일명, URL 등)",
    )

    # Loose reference — FK 없음, 고아 허용
    import_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="ImportJob UUID (loose reference, FK 없음 — 고아 허용)",
    )

    raw_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="원본 데이터 그대로. 구조 고정 없음.",
    )
    is_processed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="검수 큐 진입 여부",
    )

    # ── Relations ─────────────────────────────────────────────
    place: Mapped[Optional["Place"]] = relationship("Place", back_populates="raw_snapshots")

    def __repr__(self) -> str:
        return f"<PlaceRawSnapshot {self.source_type} place={self.place_id}>"


class PlaceReviewLog(ImmutableBase):
    """
    Place 검수 이력 — 불변 저장
    INSERT 전용. Place 삭제 시 RESTRICT (로그 있으면 삭제 불가).
    """
    __tablename__ = "place_review_logs"
    __table_args__ = {
        "comment": "Place 검수 이력. INSERT 전용. Place 삭제 시 RESTRICT."
    }

    place_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("places.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    snapshot_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("place_raw_snapshots.id", ondelete="SET NULL"),
        nullable=True,
    )

    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="field_edited | status_changed | confirmed | rejected | note_added",
    )
    field_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="수정된 필드명 (field_edited 시)"
    )
    before_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    after_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Relations ─────────────────────────────────────────────
    place: Mapped["Place"] = relationship("Place", back_populates="review_logs")
    actor: Mapped[Optional["User"]] = relationship("User", foreign_keys=[actor_id])  # noqa: F821

    def __repr__(self) -> str:
        return f"<PlaceReviewLog {self.action} place={self.place_id}>"
