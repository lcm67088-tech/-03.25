"""
ImportJob / AuditLog 모델
- ImportJob  : Google Sheet / Excel 임포트 작업 추적
- AuditLog   : 전체 도메인 감사 로그 (불변)
"""
import uuid
from typing import Any, Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, ImmutableBase


class ImportJob(BaseModel):
    """
    Google Sheet / Excel 임포트 작업
    source_type: google_sheet_import(1차) | excel_import(보조)
    status: pending → running → done | failed | partial

    Wave 1: 운영자가 Google Sheet URL을 직접 입력하여 임포트 요청.
    """
    __tablename__ = "import_jobs"
    __table_args__ = {
        "comment": "Google Sheet / Excel 임포트 작업. source_type: google_sheet_import | excel_import."
    }

    job_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="place_import | order_import",
    )
    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="google_sheet_import(1차) | excel_import(보조)",
    )
    source_url: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
        comment="Google Sheet URL",
    )
    source_sheet_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Google Sheet 특정 시트명 (미지정 시 기본 시트)",
    )
    source_file_name: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="업로드 파일명",
    )

    # ── 상태 ─────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
        comment="pending | running | done | failed | partial",
    )
    total_rows: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="전체 처리 행 수"
    )
    processed_rows: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="처리 완료 행 수"
    )
    failed_rows: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="실패 행 수"
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="실패 메시지",
    )
    error_detail: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="실패 상세 로그 (JSONB)",
    )

    # ── 요청자 ────────────────────────────────────────────────
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
        comment="재시도 시 원본 Job ID",
    )
    requested_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="임포트 요청 운영자 FK",
    )

    def __repr__(self) -> str:
        return f"<ImportJob {self.job_type} [{self.status}] src={self.source_url}>"


class AuditLog(ImmutableBase):
    """
    전체 도메인 감사 로그 — 불변 저장
    INSERT 전용. 모든 주요 변경·전이에 기록.
    actor_id는 SET NULL (사용자 삭제 시 로그 보존).

    DB 실제 컬럼 (001_initial_schema.py 기준):
      id, actor_id, actor_role, entity_type, entity_id,
      action, field_name, before_value, after_value, extra_data, created_at
    """
    __tablename__ = "audit_logs"
    __table_args__ = {
        "comment": "전체 도메인 감사 로그. INSERT 전용."
    }

    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="행위자 FK (SET NULL — 사용자 삭제 시 로그 보존)",
    )
    actor_role: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="행위 시점 역할 스냅샷"
    )

    # ── 대상 ─────────────────────────────────────────────────
    entity_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="대상 엔티티 유형: Place | Order | OrderItem | ImportJob | ...",
    )
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="대상 엔티티 UUID (Loose reference)",
    )

    # ── 행위 ─────────────────────────────────────────────────
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="create | update | delete | status_change | confirm | assign | import | ...",
    )
    field_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="변경된 필드명"
    )
    before_value: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="변경 전 값 (텍스트 직렬화)"
    )
    after_value: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="변경 후 값 (텍스트 직렬화)"
    )
    extra_data: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="추가 컨텍스트 (JSONB)"
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog {self.action} on {self.entity_type}:{self.entity_id}>"
        )
