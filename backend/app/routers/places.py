"""
Place 라우터
GET    /api/v1/places                      — 목록 (필터: review_status, agency_id)
POST   /api/v1/places                      — 수동 생성 (OPERATOR+)
GET    /api/v1/places/{id}                 — 상세
PATCH  /api/v1/places/{id}                 — 확정값 수정 (OPERATOR+)
DELETE /api/v1/places/{id}                 — 소프트 삭제 (ADMIN)

POST   /api/v1/places/snapshots            — 원본 스냅샷 저장 (INSERT 전용)
GET    /api/v1/places/{id}/snapshots       — 스냅샷 목록

POST   /api/v1/places/{id}/review/confirm  — 검수 확정 (OPERATOR+)
POST   /api/v1/places/{id}/review/reject   — 검수 거부 (OPERATOR+)
GET    /api/v1/places/{id}/review-logs     — 검수 이력
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_operator, require_admin
from app.core.response import ok, paginated
from app.core.exceptions import NotFoundError, ForbiddenError
from app.models.place import Place, PlaceRawSnapshot, PlaceReviewLog
from app.models.user import User

router = APIRouter()


# ── 스키마 ───────────────────────────────────────────────────────

class PlaceCreate(BaseModel):
    naver_place_id: Optional[str] = None
    naver_place_url: Optional[str] = None
    confirmed_name: Optional[str] = None
    confirmed_category: Optional[str] = None
    confirmed_address: Optional[str] = None
    confirmed_phone: Optional[str] = None
    agency_id: Optional[uuid.UUID] = None
    agency_name_snapshot: Optional[str] = None
    brand_id: Optional[uuid.UUID] = None
    brand_name_snapshot: Optional[str] = None
    operator_note: Optional[str] = None


class PlaceUpdate(BaseModel):
    confirmed_name: Optional[str] = None
    confirmed_category: Optional[str] = None
    confirmed_address: Optional[str] = None
    confirmed_phone: Optional[str] = None
    agency_id: Optional[uuid.UUID] = None
    agency_name_snapshot: Optional[str] = None
    brand_id: Optional[uuid.UUID] = None
    brand_name_snapshot: Optional[str] = None
    operator_note: Optional[str] = None


class PlaceOut(BaseModel):
    id: str
    naver_place_id: Optional[str]
    naver_place_url: Optional[str]
    confirmed_name: Optional[str]
    confirmed_category: Optional[str]
    confirmed_address: Optional[str]
    confirmed_phone: Optional[str]
    agency_id: Optional[str]
    agency_name_snapshot: Optional[str]
    brand_id: Optional[str]
    brand_name_snapshot: Optional[str]
    review_status: str
    reviewed_at: Optional[datetime]
    is_deleted: bool
    operator_note: Optional[str]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm(cls, p: Place) -> "PlaceOut":
        return cls(
            id=str(p.id),
            naver_place_id=p.naver_place_id,
            naver_place_url=p.naver_place_url,
            confirmed_name=p.confirmed_name,
            confirmed_category=p.confirmed_category,
            confirmed_address=p.confirmed_address,
            confirmed_phone=p.confirmed_phone,
            agency_id=str(p.agency_id) if p.agency_id else None,
            agency_name_snapshot=p.agency_name_snapshot,
            brand_id=str(p.brand_id) if p.brand_id else None,
            brand_name_snapshot=p.brand_name_snapshot,
            review_status=p.review_status,
            reviewed_at=p.reviewed_at,
            is_deleted=p.is_deleted,
            operator_note=p.operator_note,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )


class SnapshotCreate(BaseModel):
    source_type: str  # google_sheet_import | manual_input | excel_import | url_parse
    source_ref: Optional[str] = None
    import_job_id: Optional[uuid.UUID] = None
    place_id: Optional[uuid.UUID] = None
    raw_data: dict


class ReviewAction(BaseModel):
    note: Optional[str] = None


class ReviewConfirm(BaseModel):
    confirmed_name: Optional[str] = None
    confirmed_category: Optional[str] = None
    confirmed_address: Optional[str] = None
    confirmed_phone: Optional[str] = None
    note: Optional[str] = None


# ── 헬퍼 ────────────────────────────────────────────────────────

async def _get_place_or_404(place_id: uuid.UUID, db: AsyncSession) -> Place:
    place = (
        await db.execute(
            select(Place).where(Place.id == place_id, Place.is_deleted.is_(False))
        )
    ).scalar_one_or_none()
    if not place:
        raise NotFoundError("PLACE_NOT_FOUND", f"Place를 찾을 수 없습니다: {place_id}")
    return place


async def _add_review_log(
    db: AsyncSession,
    place_id: uuid.UUID,
    action: str,
    actor_id: uuid.UUID,
    *,
    snapshot_id: Optional[uuid.UUID] = None,
    field_name: Optional[str] = None,
    before_value: Optional[str] = None,
    after_value: Optional[str] = None,
    note: Optional[str] = None,
) -> None:
    log = PlaceReviewLog(
        place_id=place_id,
        snapshot_id=snapshot_id,
        action=action,
        field_name=field_name,
        before_value=before_value,
        after_value=after_value,
        actor_id=actor_id,
        note=note,
    )
    db.add(log)


# ── Place CRUD ──────────────────────────────────────────────────

@router.get("", summary="Place 목록")
async def list_places(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    review_status: Optional[str] = Query(None),
    agency_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(Place).where(Place.is_deleted.is_(False))
    if review_status:
        q = q.where(Place.review_status == review_status)
    if agency_id:
        q = q.where(Place.agency_id == agency_id)

    total = (
        await db.execute(select(func.count()).select_from(q.subquery()))
    ).scalar_one()
    offset = (page - 1) * page_size
    rows = (
        await db.execute(q.order_by(Place.created_at.desc()).offset(offset).limit(page_size))
    ).scalars().all()

    return paginated([PlaceOut.from_orm(p).model_dump() for p in rows], total, page, page_size)


@router.post("", status_code=status.HTTP_201_CREATED, summary="Place 수동 생성")
async def create_place(
    body: PlaceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    place = Place(**body.model_dump())
    db.add(place)
    await db.flush()

    await _add_review_log(db, place.id, "note_added", current_user.id, note="수동 생성")
    await db.commit()
    await db.refresh(place)
    return ok(PlaceOut.from_orm(place).model_dump())


@router.get("/snapshots", summary="전체 스냅샷 목록 (raw)")
async def list_snapshots(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    source_type: Optional[str] = Query(None),
    is_processed: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(PlaceRawSnapshot)
    if source_type:
        q = q.where(PlaceRawSnapshot.source_type == source_type)
    if is_processed is not None:
        q = q.where(PlaceRawSnapshot.is_processed == is_processed)

    total = (
        await db.execute(select(func.count()).select_from(q.subquery()))
    ).scalar_one()
    offset = (page - 1) * page_size
    rows = (
        await db.execute(
            q.order_by(PlaceRawSnapshot.created_at.desc()).offset(offset).limit(page_size)
        )
    ).scalars().all()

    def _snap_dict(s: PlaceRawSnapshot) -> dict:
        return {
            "id": str(s.id),
            "place_id": str(s.place_id) if s.place_id else None,
            "source_type": s.source_type,
            "source_ref": s.source_ref,
            "import_job_id": str(s.import_job_id) if s.import_job_id else None,
            "raw_data": s.raw_data,
            "is_processed": s.is_processed,
            "created_at": s.created_at.isoformat(),
        }

    return paginated([_snap_dict(s) for s in rows], total, page, page_size)


@router.post("/snapshots", status_code=status.HTTP_201_CREATED, summary="원본 스냅샷 저장 (INSERT 전용)")
async def create_snapshot(
    body: SnapshotCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """
    원본 불변 저장. INSERT 전용.
    이 엔드포인트로 저장된 스냅샷은 UPDATE/DELETE 불가.
    """
    snap = PlaceRawSnapshot(
        source_type=body.source_type,
        source_ref=body.source_ref,
        import_job_id=body.import_job_id,
        place_id=body.place_id,
        raw_data=body.raw_data,
    )
    db.add(snap)
    await db.commit()
    await db.refresh(snap)
    return ok({
        "id": str(snap.id),
        "place_id": str(snap.place_id) if snap.place_id else None,
        "source_type": snap.source_type,
        "is_processed": snap.is_processed,
        "created_at": snap.created_at.isoformat(),
    })


@router.get("/{place_id}", summary="Place 상세")
async def get_place(
    place_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    place = await _get_place_or_404(place_id, db)
    return ok(PlaceOut.from_orm(place).model_dump())


@router.patch("/{place_id}", summary="Place 확정값 수정")
async def update_place(
    place_id: uuid.UUID,
    body: PlaceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    place = await _get_place_or_404(place_id, db)

    updated_fields = {}
    for field, value in body.model_dump(exclude_none=True).items():
        old_val = str(getattr(place, field, None))
        setattr(place, field, value)
        updated_fields[field] = {"before": old_val, "after": str(value)}

    for field_name, vals in updated_fields.items():
        await _add_review_log(
            db, place.id, "field_edited", current_user.id,
            field_name=field_name,
            before_value=vals["before"],
            after_value=vals["after"],
        )

    await db.commit()
    await db.refresh(place)
    return ok(PlaceOut.from_orm(place).model_dump())


@router.delete("/{place_id}", summary="Place 소프트 삭제 (ADMIN)")
async def delete_place(
    place_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    place = await _get_place_or_404(place_id, db)

    # 검수 로그가 있으면 RESTRICT — DB 레벨에서도 막히지만 명시적 체크
    log_count = (
        await db.execute(
            select(func.count()).where(PlaceReviewLog.place_id == place_id)
        )
    ).scalar_one()
    if log_count > 0:
        raise ForbiddenError(
            "PLACE_HAS_REVIEW_LOGS",
            f"검수 이력({log_count}건)이 있는 Place는 삭제할 수 없습니다. 소프트 삭제만 가능합니다.",
        )

    place.is_deleted = True
    place.deleted_at = datetime.now(timezone.utc)
    place.deleted_by = current_user.id
    await db.commit()
    return ok({"message": "Place가 소프트 삭제되었습니다.", "id": str(place_id)})


@router.get("/{place_id}/snapshots", summary="Place 스냅샷 목록")
async def get_place_snapshots(
    place_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    await _get_place_or_404(place_id, db)
    snaps = (
        await db.execute(
            select(PlaceRawSnapshot)
            .where(PlaceRawSnapshot.place_id == place_id)
            .order_by(PlaceRawSnapshot.created_at.desc())
        )
    ).scalars().all()
    return ok([
        {
            "id": str(s.id),
            "source_type": s.source_type,
            "source_ref": s.source_ref,
            "import_job_id": str(s.import_job_id) if s.import_job_id else None,
            "raw_data": s.raw_data,
            "is_processed": s.is_processed,
            "created_at": s.created_at.isoformat(),
        }
        for s in snaps
    ])


@router.post("/{place_id}/review/confirm", summary="검수 확정")
async def confirm_place(
    place_id: uuid.UUID,
    body: ReviewConfirm,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    place = await _get_place_or_404(place_id, db)

    if place.review_status == "confirmed":
        raise HTTPException(400, "이미 확정된 Place입니다.")

    old_status = place.review_status

    # 확정값 업데이트
    for field in ("confirmed_name", "confirmed_category", "confirmed_address", "confirmed_phone"):
        val = getattr(body, field, None)
        if val is not None:
            setattr(place, field, val)

    place.review_status = "confirmed"
    place.reviewed_by = current_user.id
    place.reviewed_at = datetime.now(timezone.utc)

    await _add_review_log(
        db, place.id, "confirmed", current_user.id,
        before_value=old_status,
        after_value="confirmed",
        note=body.note,
    )
    await db.commit()
    await db.refresh(place)
    return ok(PlaceOut.from_orm(place).model_dump())


@router.post("/{place_id}/review/reject", summary="검수 거부")
async def reject_place(
    place_id: uuid.UUID,
    body: ReviewAction,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    place = await _get_place_or_404(place_id, db)
    old_status = place.review_status

    place.review_status = "rejected"
    place.reviewed_by = current_user.id
    place.reviewed_at = datetime.now(timezone.utc)

    await _add_review_log(
        db, place.id, "rejected", current_user.id,
        before_value=old_status,
        after_value="rejected",
        note=body.note,
    )
    await db.commit()
    await db.refresh(place)
    return ok(PlaceOut.from_orm(place).model_dump())


@router.get("/{place_id}/review-logs", summary="검수 이력 조회")
async def get_review_logs(
    place_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    await _get_place_or_404(place_id, db)
    logs = (
        await db.execute(
            select(PlaceReviewLog)
            .where(PlaceReviewLog.place_id == place_id)
            .order_by(PlaceReviewLog.created_at.desc())
        )
    ).scalars().all()
    return ok([
        {
            "id": str(lg.id),
            "action": lg.action,
            "field_name": lg.field_name,
            "before_value": lg.before_value,
            "after_value": lg.after_value,
            "actor_id": str(lg.actor_id) if lg.actor_id else None,
            "note": lg.note,
            "created_at": lg.created_at.isoformat(),
        }
        for lg in logs
    ])
