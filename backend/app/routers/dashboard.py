"""
대시보드 라우터

엔드포인트:
  GET /api/v1/dashboard                    — 운영 현황 요약 (기본)
  GET /api/v1/dashboard/summary            — 확장 운영 요약 (Wave 2-A)
  GET /api/v1/dashboard/items-by-status    — OrderItem 상태별 집계 (Wave 2-A)
  GET /api/v1/dashboard/orders-by-agency   — 대행사별 주문 집계 (Wave 2-A)
  GET /api/v1/dashboard/settlement         — 정산 현황 (Wave 2-A, ADMIN)
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.core.response import ok
from app.models.order import Order, OrderItem
from app.models.place import Place
from app.models.import_job import ImportJob
from app.models.user import User

router = APIRouter()


# ── 기존 GET / (Wave 1 호환 유지) ──────────────────────────────

@router.get("", summary="운영 현황 요약 (Wave 1 호환)")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Wave 1 최소 대시보드. /summary로 대체 예정이지만 하위 호환 유지.
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


# ── Wave 2-A 확장 대시보드 ──────────────────────────────────────

@router.get("/summary", summary="확장 운영 요약 (Wave 2-A)")
async def get_summary(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Wave 2-A 확장 운영 요약.

    응답:
      - orders: 상태별 주문 헤더 카운트
      - order_items: 상태별 아이템 카운트
      - amounts: 금액 집계 (total_amount 기준)
      - place: 검수 현황
    """
    # ── Order 상태별 집계
    order_status_rows = (
        await db.execute(
            select(Order.status, func.count().label("cnt"))
            .where(Order.is_deleted.is_(False))
            .group_by(Order.status)
        )
    ).all()
    order_stats = {row[0]: row[1] for row in order_status_rows}
    order_total = sum(order_stats.values())

    # ── OrderItem 상태별 집계
    item_status_rows = (
        await db.execute(
            select(OrderItem.status, func.count().label("cnt"))
            .where(OrderItem.is_deleted.is_(False))
            .group_by(OrderItem.status)
        )
    ).all()
    item_stats = {row[0]: row[1] for row in item_status_rows}
    item_total = sum(item_stats.values())

    # ── 금액 집계
    #  - total_contracted: confirmed + 이후 상태 아이템의 total_amount 합계
    #  - total_settlement_ready: settlement_ready 상태 합계
    #  - total_closed: closed 상태 합계
    CONTRACTED_STATUSES = [
        "confirmed", "settlement_ready", "closed",
    ]
    amount_rows = (
        await db.execute(
            select(
                OrderItem.status,
                func.coalesce(func.sum(OrderItem.total_amount), 0).label("total"),
            )
            .where(
                OrderItem.is_deleted.is_(False),
                OrderItem.status.in_(CONTRACTED_STATUSES + ["in_progress", "done"]),
            )
            .group_by(OrderItem.status)
        )
    ).all()
    amount_by_status = {row[0]: int(row[1]) for row in amount_rows}

    # ── Place 현황
    place_rows = (
        await db.execute(
            select(Place.review_status, func.count().label("cnt"))
            .where(Place.is_deleted.is_(False))
            .group_by(Place.review_status)
        )
    ).all()
    place_stats = {row[0]: row[1] for row in place_rows}

    return ok({
        "orders": {
            "total": order_total,
            "draft": order_stats.get("draft", 0),
            "confirmed": order_stats.get("confirmed", 0),
            "cancelled": order_stats.get("cancelled", 0),
            "closed": order_stats.get("closed", 0),
        },
        "order_items": {
            "total": item_total,
            **{
                st: item_stats.get(st, 0)
                for st in [
                    "received", "on_hold", "reviewing", "ready_to_route",
                    "assigned", "in_progress", "done", "confirmed",
                    "settlement_ready", "closed", "cancelled",
                ]
            },
        },
        "amounts": {
            "total_contracted": sum(
                amount_by_status.get(s, 0) for s in CONTRACTED_STATUSES
            ),
            "in_progress": amount_by_status.get("in_progress", 0),
            "done": amount_by_status.get("done", 0),
            "settlement_ready": amount_by_status.get("settlement_ready", 0),
            "closed": amount_by_status.get("closed", 0),
        },
        "place": {
            "total": sum(place_stats.values()),
            "pending_review": place_stats.get("pending_review", 0),
            "in_review": place_stats.get("in_review", 0),
            "confirmed": place_stats.get("confirmed", 0),
            "rejected": place_stats.get("rejected", 0),
        },
    })


@router.get("/items-by-status", summary="OrderItem 상태별 상세 집계 (Wave 2-A)")
async def get_items_by_status(
    source_type: Optional[str] = Query(None, description="source_type 필터"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    OrderItem 상태별 상세 집계.
    - 각 상태별 아이템 수, 금액 합계, 평균 단가 포함.
    - source_type 필터 적용 가능 (Order 테이블과 JOIN).
    """
    q = (
        select(
            OrderItem.status,
            func.count().label("cnt"),
            func.coalesce(func.sum(OrderItem.total_amount), 0).label("total_amount"),
            func.coalesce(func.avg(OrderItem.unit_price), 0).label("avg_unit_price"),
        )
        .where(OrderItem.is_deleted.is_(False))
    )

    if source_type:
        q = (
            q.join(Order, OrderItem.order_id == Order.id)
            .where(Order.source_type == source_type, Order.is_deleted.is_(False))
        )

    q = q.group_by(OrderItem.status).order_by(OrderItem.status)
    rows = (await db.execute(q)).all()

    ALL_STATUSES = [
        "received", "on_hold", "reviewing", "ready_to_route",
        "assigned", "in_progress", "done", "confirmed",
        "settlement_ready", "closed", "cancelled",
    ]
    stats_map = {row[0]: row for row in rows}

    return ok({
        "source_type_filter": source_type,
        "statuses": [
            {
                "status": st,
                "count": stats_map[st][1] if st in stats_map else 0,
                "total_amount": int(stats_map[st][2]) if st in stats_map else 0,
                "avg_unit_price": round(float(stats_map[st][3]), 0) if st in stats_map else 0,
            }
            for st in ALL_STATUSES
        ],
        "total_items": sum(r[1] for r in rows),
        "total_amount": sum(int(r[2]) for r in rows),
    })


@router.get("/orders-by-agency", summary="대행사별 주문 집계 (Wave 2-A)")
async def get_orders_by_agency(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    대행사별 주문 헤더 집계.
    agency_name_snapshot 기준으로 그룹핑합니다.
    """
    # Order 기준 집계 (agency_name_snapshot, agency_id 그룹핑)
    order_rows = (
        await db.execute(
            select(
                Order.agency_name_snapshot,
                Order.agency_id,
                func.count(Order.id).label("order_count"),
            )
            .where(Order.is_deleted.is_(False))
            .group_by(Order.agency_name_snapshot, Order.agency_id)
            .order_by(func.count(Order.id).desc())
        )
    ).all()

    total = len(order_rows)
    offset = (page - 1) * page_size
    paged = order_rows[offset: offset + page_size]

    return ok({
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": [
            {
                "agency_name": row[0] or "(미지정)",
                "agency_id": str(row[1]) if row[1] else None,
                "order_count": row[2],
            }
            for row in paged
        ],
    })


@router.get("/settlement", summary="정산 현황 (ADMIN 전용, Wave 2-A)")
async def get_settlement_dashboard(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    Wave 2-A 정산 현황 (ADMIN 전용).

    정산 흐름:
      done → confirmed (OPERATOR)
      confirmed → settlement_ready (OPERATOR)
      settlement_ready → closed (ADMIN 최종 승인)
    """
    SETTLEMENT_STATUSES = ["done", "confirmed", "settlement_ready", "closed"]

    rows = (
        await db.execute(
            select(
                OrderItem.status,
                func.count().label("cnt"),
                func.coalesce(func.sum(OrderItem.total_amount), 0).label("total_amount"),
            )
            .where(
                OrderItem.is_deleted.is_(False),
                OrderItem.status.in_(SETTLEMENT_STATUSES),
            )
            .group_by(OrderItem.status)
        )
    ).all()

    stats = {row[0]: {"count": row[1], "total_amount": int(row[2])} for row in rows}

    return ok({
        "pipeline": {
            st: {
                "count": stats.get(st, {}).get("count", 0),
                "total_amount": stats.get(st, {}).get("total_amount", 0),
            }
            for st in SETTLEMENT_STATUSES
        },
        "pending_admin_approval": {
            "count": stats.get("settlement_ready", {}).get("count", 0),
            "total_amount": stats.get("settlement_ready", {}).get("total_amount", 0),
            "description": "settlement_ready → closed 전이는 ADMIN 최종 승인 필요",
        },
        "total_closed": {
            "count": stats.get("closed", {}).get("count", 0),
            "total_amount": stats.get("closed", {}).get("total_amount", 0),
        },
    })
