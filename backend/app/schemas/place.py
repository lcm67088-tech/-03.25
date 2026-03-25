"""
Place 도메인 스키마
"""
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema


# ── PlaceRawSnapshot ──────────────────────────────────────
class PlaceRawSnapshotCreate(BaseSchema):
    source_type: str = Field(
        default="manual_input",
        description="google_sheet_import | excel_import | manual_input | url_parse",
    )
    source_ref: Optional[str] = None
    import_job_id: Optional[UUID] = None
    raw_data: Dict[str, Any]


class PlaceRawSnapshotRead(BaseSchema):
    id: UUID
    place_id: Optional[UUID]
    source_type: str
    source_ref: Optional[str]
    import_job_id: Optional[UUID]
    raw_data: Dict[str, Any]
    is_processed: bool
    created_at: datetime


# ── Place ─────────────────────────────────────────────────
class PlaceCreate(BaseSchema):
    naver_place_id: Optional[str] = None
    naver_place_url: Optional[str] = None
    confirmed_name: Optional[str] = None
    confirmed_category: Optional[str] = None
    confirmed_address: Optional[str] = None
    confirmed_phone: Optional[str] = None
    agency_id: Optional[UUID] = None
    agency_name_snapshot: Optional[str] = None
    brand_id: Optional[UUID] = None
    brand_name_snapshot: Optional[str] = None
    operator_note: Optional[str] = None


class PlaceUpdate(BaseSchema):
    naver_place_id: Optional[str] = None
    naver_place_url: Optional[str] = None
    confirmed_name: Optional[str] = None
    confirmed_category: Optional[str] = None
    confirmed_address: Optional[str] = None
    confirmed_phone: Optional[str] = None
    agency_id: Optional[UUID] = None
    agency_name_snapshot: Optional[str] = None
    brand_id: Optional[UUID] = None
    brand_name_snapshot: Optional[str] = None
    operator_note: Optional[str] = None


class PlaceRead(BaseSchema):
    id: UUID
    naver_place_id: Optional[str]
    naver_place_url: Optional[str]
    confirmed_name: Optional[str]
    confirmed_category: Optional[str]
    confirmed_address: Optional[str]
    confirmed_phone: Optional[str]
    agency_id: Optional[UUID]
    agency_name_snapshot: Optional[str]
    brand_id: Optional[UUID]
    brand_name_snapshot: Optional[str]
    review_status: str
    reviewed_at: Optional[datetime]
    is_deleted: bool
    operator_note: Optional[str]
    created_at: datetime
    updated_at: datetime


# ── PlaceReviewLog ────────────────────────────────────────
class PlaceReviewAction(BaseSchema):
    action: str = Field(
        description="confirmed | rejected | note_added | field_edited"
    )
    field_name: Optional[str] = None
    before_value: Optional[str] = None
    after_value: Optional[str] = None
    note: Optional[str] = None


class PlaceReviewLogRead(BaseSchema):
    id: UUID
    place_id: UUID
    snapshot_id: Optional[UUID]
    action: str
    field_name: Optional[str]
    before_value: Optional[str]
    after_value: Optional[str]
    actor_id: Optional[UUID]
    note: Optional[str]
    created_at: datetime
