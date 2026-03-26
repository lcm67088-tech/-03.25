"""
ImportJob 라우터
POST   /api/v1/import-jobs           — Google Sheet URL 입력하여 임포트 요청
GET    /api/v1/import-jobs           — 목록
GET    /api/v1/import-jobs/{id}      — 상세 (상태 폴링용)
POST   /api/v1/import-jobs/{id}/retry — 재시도 (OPERATOR+)

Wave 1: Google Sheet URL 직접 입력. xlsx 업로드는 보조 경로.
실제 시트 파싱은 Wave 1에서 서비스 레이어에서 처리 (gspread).
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_operator
from app.core.response import ok, paginated
from app.core.exceptions import NotFoundError
from app.models.import_job import ImportJob
from app.models.user import User
from app.services.import_service import run_import_job

router = APIRouter()


# ── 스키마 ───────────────────────────────────────────────────────

class ImportJobCreate(BaseModel):
    job_type: str                        # place_import | order_import
    source_type: str = "google_sheet_import"  # google_sheet_import | excel_import
    source_url: Optional[str] = None    # Google Sheet URL
    source_file_name: Optional[str] = None  # 업로드 파일명
    source_sheet_name: Optional[str] = None  # 특정 시트명 (미지정 시 기본 시트)


class ImportJobOut(BaseModel):
    id: str
    job_type: str
    source_type: str
    source_url: Optional[str]
    source_file_name: Optional[str]
    source_sheet_name: Optional[str]
    status: str
    total_rows: Optional[int]
    processed_rows: Optional[int]
    failed_rows: Optional[int]
    retry_count: int
    error_message: Optional[str]
    requested_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm(cls, j: ImportJob) -> "ImportJobOut":
        return cls(
            id=str(j.id),
            job_type=j.job_type,
            source_type=j.source_type,
            source_url=j.source_url,
            source_file_name=j.source_file_name,
            source_sheet_name=j.source_sheet_name,
            status=j.status,
            total_rows=j.total_rows,
            processed_rows=j.processed_rows,
            failed_rows=j.failed_rows,
            retry_count=j.retry_count,
            error_message=j.error_message,
            requested_by=str(j.requested_by) if j.requested_by else None,
            created_at=j.created_at,
            updated_at=j.updated_at,
        )


# ── 엔드포인트 ──────────────────────────────────────────────────

@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    summary="임포트 요청 (Google Sheet URL 직접 입력)",
)
async def create_import_job(
    body: ImportJobCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """
    Wave 1 — Google Sheet URL 직접 입력 방식.
    1. ImportJob 레코드 생성 (status=pending)
    2. 비동기 처리 시작 (Wave 1: 동기 처리. Wave 2: Celery 이관)
    3. 202 Accepted 즉시 반환
    """
    VALID_JOB_TYPES = {"place_import", "order_import"}
    VALID_SOURCE_TYPES = {"google_sheet_import", "excel_import"}

    if body.job_type not in VALID_JOB_TYPES:
        from fastapi import HTTPException
        raise HTTPException(400, f"job_type은 {VALID_JOB_TYPES} 중 하나여야 합니다.")
    if body.source_type not in VALID_SOURCE_TYPES:
        from fastapi import HTTPException
        raise HTTPException(400, f"source_type은 {VALID_SOURCE_TYPES} 중 하나여야 합니다.")

    job = ImportJob(
        job_type=body.job_type,
        source_type=body.source_type,
        source_url=body.source_url,
        source_file_name=body.source_file_name,
        source_sheet_name=body.source_sheet_name,
        status="pending",
        requested_by=current_user.id,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Wave 1: 동기 처리 시작 (Wave 2에서 Celery로 이관 예정)
    # 실제 처리는 서비스 레이어에서 수행
    await run_import_job(job.id, db)

    # 최신 상태 다시 조회
    await db.refresh(job)
    return ok(ImportJobOut.from_orm(job).model_dump())


@router.get("", summary="임포트 작업 목록")
async def list_import_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    job_type: Optional[str] = Query(None),
    job_status: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(ImportJob)
    if job_type:
        q = q.where(ImportJob.job_type == job_type)
    if job_status:
        q = q.where(ImportJob.status == job_status)

    total = (
        await db.execute(select(func.count()).select_from(q.subquery()))
    ).scalar_one()
    offset = (page - 1) * page_size
    rows = (
        await db.execute(
            q.order_by(ImportJob.created_at.desc()).offset(offset).limit(page_size)
        )
    ).scalars().all()

    return paginated(
        [ImportJobOut.from_orm(j).model_dump() for j in rows],
        total, page, page_size,
    )


@router.get("/{job_id}", summary="임포트 작업 상세 (상태 폴링)")
async def get_import_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    job = (
        await db.execute(select(ImportJob).where(ImportJob.id == job_id))
    ).scalar_one_or_none()
    if not job:
        raise NotFoundError("IMPORT_JOB_NOT_FOUND", f"ImportJob을 찾을 수 없습니다: {job_id}")
    return ok(ImportJobOut.from_orm(job).model_dump())


@router.post("/{job_id}/retry", summary="임포트 재시도")
async def retry_import_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    job = (
        await db.execute(select(ImportJob).where(ImportJob.id == job_id))
    ).scalar_one_or_none()
    if not job:
        raise NotFoundError("IMPORT_JOB_NOT_FOUND", f"ImportJob을 찾을 수 없습니다: {job_id}")

    if job.status not in ("failed", "partial"):
        from fastapi import HTTPException
        raise HTTPException(400, f"failed 또는 partial 상태일 때만 재시도 가능합니다. 현재: {job.status}")

    job.status = "pending"
    job.requested_by = current_user.id
    await db.commit()
    await db.refresh(job)

    await run_import_job(job.id, db)
    await db.refresh(job)
    return ok(ImportJobOut.from_orm(job).model_dump())
