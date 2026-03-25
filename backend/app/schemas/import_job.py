"""
ImportJob 스키마
"""
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema


class ImportJobCreate(BaseSchema):
    """Import Job 생성 요청"""
    source_type: str = Field(
        default="google_sheet_import",
        description="google_sheet_import | excel_import",
    )
    job_type: str = Field(
        description="order_sheet_import | place_sheet_import"
    )
    source_url: Optional[str] = Field(
        default=None,
        description="Google Sheet URL (source_type=google_sheet_import 시 필수)",
    )
    source_sheet_name: Optional[str] = Field(
        default=None,
        description="특정 시트명 (null이면 전체 시트 대상)",
    )


class ImportJobRead(BaseSchema):
    id: UUID
    source_type: str
    job_type: str
    source_url: Optional[str]
    source_sheet_name: Optional[str]
    source_file_name: Optional[str]
    status: str
    total_rows: Optional[int]
    processed_rows: Optional[int]
    failed_rows: Optional[int]
    error_message: Optional[str]
    error_detail: Optional[Dict[str, Any]]
    requested_by: Optional[UUID]
    retry_count: int
    parent_job_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime


class ImportJobRetryRequest(BaseSchema):
    """실패한 ImportJob 재시도"""
    failed_rows_only: bool = Field(
        default=True,
        description="True: 실패 행만 재시도. False: 전체 재시도.",
    )


class AuditLogRead(BaseSchema):
    id: UUID
    actor_id: Optional[UUID]
    actor_role: Optional[str]
    entity_type: str
    entity_id: Optional[UUID]
    action: str
    field_name: Optional[str]
    before_value: Optional[str]
    after_value: Optional[str]
    extra_data: Optional[Dict[str, Any]]
    created_at: datetime
