"""
ImportJob / AuditLog 모델

ImportJob: Google Sheet / Excel import 작업 상태 추적
AuditLog: 주요 변경 이력 불변 기록 (INSERT 전용)
"""
import uuid
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, ImmutableBase

if TYPE_CHECKING:
    from app.models.user import User


# ─────────────────────────────────────────────────────────
#  ImportJob — 가져오기 작업
# ─────────────────────────────────────────────────────────
class ImportJob(BaseModel):
    """
    Google Sheet / Excel import 작업 추적

    source_type 우선순위:
      1. google_sheet_import (주 흐름)
      2. excel_import (보조)

    job_type: 어떤 데이터를 가져왔는지
      - order_sheet_import: 주문 취합 시트 import
      - place_sheet_import: Place 정보 import

    status 상태 흐름:
      pending → running → completed | failed | partial
    """
    __tablename__ = "import_jobs"
    __table_args__ = {
        "comment": "Google Sheet / Excel import 작업 추적"
    }

    # ── 출처 ──────────────────────────────────────────────
    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="google_sheet_import(1차) | excel_import(보조)",
    )
    job_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="order_sheet_import | place_sheet_import",
    )
    source_url: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
        comment="Google Sheet URL (source_type=google_sheet_import 시)",
    )
    source_sheet_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="대상 시트명 (트래픽 취합, 저장 취합 등). null이면 전체 시트.",
    )
    source_file_name: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="업로드된 파일명 (source_type=excel_import 시)",
    )

    # ── 진행 상태 ─────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
        comment="pending | running | completed | failed | partial",
    )
    total_rows: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="전체 처리 대상 행 수"
    )
    processed_rows: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="처리 완료 행 수"
    )
    failed_rows: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="처리 실패 행 수"
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="전체 실패 시 오류 메시지"
    )
    error_detail: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="행별 오류 상세. {row_index: error_message, ...}",
    )

    # ── 요청자 ────────────────────────────────────────────
    requested_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="요청 운영자 UUID (loose reference)",
    )

    # ── 재시도 ────────────────────────────────────────────
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="재시도 횟수",
    )
    parent_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="재시도 원본 ImportJob UUID (loose reference)",
    )

    def __repr__(self) -> str:
        return f"<ImportJob {self.job_type} [{self.status}]>"


# ─────────────────────────────────────────────────────────
#  AuditLog — 변경 이력 (불변)
# ─────────────────────────────────────────────────────────
class AuditLog(ImmutableBase):
    """
    주요 변경 이력 — 불변 기록
    INSERT 전용. 삭제/수정 금지.
    """
    __tablename__ = "audit_logs"
    __table_args__ = {
        "comment": "주요 변경 이력. INSERT 전용."
    }

    # ── 행위자 ────────────────────────────────────────────
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="행위자 UUID (loose reference, 시스템 자동 처리는 null)",
    )
    actor_role: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="행위 시점 역할 스냅샷"
    )

    # ── 행위 대상 ─────────────────────────────────────────
    entity_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="대상 엔티티 타입 (Place, Order, OrderItem, ImportJob, ...)",
        index=True,
    )
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="대상 엔티티 UUID",
        index=True,
    )

    # ── 행위 내용 ─────────────────────────────────────────
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment=(
            "create | update | delete | status_change | review | "
            "confirm | reject | route | import | retry"
        ),
    )
    field_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="수정된 필드명 (action=update 시)"
    )
    before_value: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="변경 전 값"
    )
    after_value: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="변경 후 값"
    )
    extra_data: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="추가 컨텍스트 (IP, User-Agent 등)"
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog {self.action} {self.entity_type}:{self.entity_id}"
            f" by={self.actor_id}>"
        )
