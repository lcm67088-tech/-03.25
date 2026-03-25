"""
대시보드 라우터
GET /api/v1/dashboard  — 운영 현황 요약 (Wave 1: 기본 카운트)
"""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.response import ok
from app.models.order import OrderItem
from app.models.place import Place
from app.models.import_job import ImportJob
from app.models.user import User

router = APIRouter()


@router.get("", summary="운영 현황 요약")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Wave 1 최소 대시보드.
    - Place 검수 현황
    - OrderItem 상태별 카운트
    - 최근 ImportJob 상태
    """
    # Place 현황
    place_stats_rows = (
        await db.execute(
            select(Place.review_status, func.count().label("cnt"))
            .where(Place.is_deleted.is_(False))
            .group_by(Place.review_status)
        )
    ).all()
    place_stats = {row[0]: row[1] for row in place_stats_rows}

    # OrderItem 상태별 카운트
    item_stats_rows = (
        await db.execute(
            select(OrderItem.status, func.count().label("cnt"))
            .where(OrderItem.is_deleted.is_(False))
            .group_by(OrderItem.status)
        )
    ).all()
    item_stats = {row[0]: row[1] for row in item_stats_rows}

    # ImportJob 최근 5건
    recent_jobs = (
        await db.execute(
            select(ImportJob)
            .order_by(ImportJob.created_at.desc())
            .limit(5)
        )
    ).scalars().all()

    return ok({
        "place": {
            "pending_review": place_stats.get("pending_review", 0),
            "in_review": place_stats.get("in_review", 0),
            "confirmed": place_stats.get("confirmed", 0),
            "rejected": place_stats.get("rejected", 0),
            "total": sum(place_stats.values()),
        },
        "order_items": {
            status: item_stats.get(status, 0)
            for status in [
                "received", "on_hold", "reviewing", "ready_to_route",
                "assigned", "in_progress", "done", "confirmed",
                "settlement_ready", "closed", "cancelled",
            ]
        },
        "order_items_total": sum(item_stats.values()),
        "recent_import_jobs": [
            {
                "id": str(j.id),
                "job_type": j.job_type,
                "source_type": j.source_type,
                "status": j.status,
                "total_rows": j.total_rows,
                "success_rows": j.success_rows,
                "created_at": j.created_at.isoformat(),
            }
            for j in recent_jobs
        ],
    })
