"""
대시보드 라우터

엔드포인트:
  GET /api/v1/dashboard                    — 운영 현황 요약 (기본)
  GET /api/v1/dashboard/summary            — 확장 운영 요약 (Wave 2-A)
  GET /api/v1/dashboard/items-by-status    — OrderItem 상태별 집계 (Wave 2-A)
  GET /api/v1/dashboard/orders-by-agency   — 대행사별 주문 집계 (Wave 2-A)
  GET /api/v1/dashboard/settlement         — 정산 현황 (Phase 2-C, ADMIN, UTC 기간 필터)
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, case, literal, text
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


@router.get("/settlement", summary="정산 현황 (ADMIN 전용, Phase 2-C)")
async def get_settlement_dashboard(
    closed_from: Optional[str] = Query(
        None,
        description="정산 종료 기간 시작 (UTC, ISO 8601: YYYY-MM-DDTHH:MM:SSZ 또는 YYYY-MM-DD)",
        alias="closed_from",
    ),
    closed_to: Optional[str] = Query(
        None,
        description="정산 종료 기간 끝 (UTC, ISO 8601: YYYY-MM-DDTHH:MM:SSZ 또는 YYYY-MM-DD, 포함)",
        alias="closed_to",
    ),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    Phase 2-C 정산 현황 (ADMIN 전용).

    정산 흐름:
      done → confirmed (OPERATOR) → confirmed_at 기록
      confirmed → settlement_ready (OPERATOR) → settlement_ready_at 기록
      settlement_ready → closed (ADMIN 최종 승인) → closed_at 기록

    기간 필터 (closed_from / closed_to):
      - OrderItem.closed_at 기준으로 필터링 (UTC)
      - 날짜만 전달 시 (YYYY-MM-DD) 해당 일 00:00:00Z ~ 23:59:59.999999Z 범위로 처리
      - 기간 미지정 시 전체 집계

    Agency 집계:
      - OrderItem → Order JOIN 후 agency_name_snapshot 기준 집계
      - agency_id가 NULL이거나 agency_name_snapshot이 NULL인 경우
        → "(미지정)" 키로 fallback 집계 (누락 없음)
    """
    # ── 기간 필터 파싱 (UTC 강제) ─────────────────────────────
    def _parse_utc(value: Optional[str], end_of_day: bool = False) -> Optional[datetime]:
        """
        ISO 8601 문자열을 UTC datetime으로 파싱.
        날짜만 오는 경우(YYYY-MM-DD): end_of_day=False면 00:00:00Z, True면 23:59:59.999999Z
        """
        if not value:
            return None
        value = value.strip()
        # 날짜만인 경우
        if len(value) == 10 and "T" not in value:
            from datetime import timedelta
            from datetime import date as _date
            d = datetime.strptime(value, "%Y-%m-%d")
            if end_of_day:
                return d.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc)
            return d.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
        # ISO 8601 datetime
        try:
            # Z suffix → UTC
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt
        except ValueError:
            return None

    dt_from = _parse_utc(closed_from, end_of_day=False)
    dt_to = _parse_utc(closed_to, end_of_day=True)

    # ── 기본 필터 조건 구성 ──────────────────────────────────
    SETTLEMENT_STATUSES = ["done", "confirmed", "settlement_ready", "closed"]

    base_where = [
        OrderItem.is_deleted.is_(False),
        OrderItem.status.in_(SETTLEMENT_STATUSES),
    ]

    # closed_at 기간 필터: closed 상태 아이템에 대해서만 closed_at 범위 적용
    # 단, done/confirmed/settlement_ready 는 기간 필터와 무관하게 항상 포함
    # (기간 필터는 closed 상태만 필터링 — settlement pipeline 전체 현황 파악 목적)
    closed_at_conditions = []
    if dt_from:
        closed_at_conditions.append(OrderItem.closed_at >= dt_from)
    if dt_to:
        closed_at_conditions.append(OrderItem.closed_at <= dt_to)

    # ── 1. 전체 파이프라인 집계 ──────────────────────────────
    pipeline_q = (
        select(
            OrderItem.status,
            func.count().label("cnt"),
            func.coalesce(func.sum(OrderItem.total_amount), 0).label("total_amount"),
        )
        .where(*base_where)
    )

    # closed 상태에만 기간 필터 적용 (OR로 non-closed 포함)
    if closed_at_conditions:
        from sqlalchemy import or_, and_
        pipeline_q = pipeline_q.where(
            or_(
                OrderItem.status != "closed",
                and_(*closed_at_conditions),
            )
        )

    pipeline_q = pipeline_q.group_by(OrderItem.status)
    pipeline_rows = (await db.execute(pipeline_q)).all()
    stats = {row[0]: {"count": row[1], "total_amount": int(row[2])} for row in pipeline_rows}

    # ── 2. Agency별 closed 아이템 집계 ──────────────────────
    # OrderItem → Order JOIN
    # agency_name_snapshot NULL인 경우 "(미지정)"으로 fallback
    # PostgreSQL GROUP BY: 원본 컬럼(Order.agency_name_snapshot, Order.agency_id)으로
    # GROUP BY하고 SELECT에서 COALESCE 적용
    agency_q = (
        select(
            Order.agency_name_snapshot,
            Order.agency_id,
            func.count(OrderItem.id).label("cnt"),
            func.coalesce(func.sum(OrderItem.total_amount), 0).label("total_amount"),
        )
        .join(Order, OrderItem.order_id == Order.id)
        .where(
            OrderItem.is_deleted.is_(False),
            OrderItem.status == "closed",
            Order.is_deleted.is_(False),
        )
    )

    if closed_at_conditions:
        for cond in closed_at_conditions:
            agency_q = agency_q.where(cond)

    agency_q = (
        agency_q
        .group_by(Order.agency_name_snapshot, Order.agency_id)
        .order_by(func.sum(OrderItem.total_amount).desc().nullslast())
    )

    agency_rows = (await db.execute(agency_q)).all()

    agency_breakdown = [
        {
            # agency_name_snapshot NULL → "(미지정)" fallback
            "agency_name": row[0] if row[0] else "(미지정)",
            "agency_id": str(row[1]) if row[1] else None,
            "closed_count": row[2],
            "total_amount": int(row[3]),
        }
        for row in agency_rows
    ]

    # ── 3. settlement_ready_at 기준 대기 집계 ────────────────
    # pending_admin_approval: settlement_ready 아이템 (기간 필터 미적용 — 전체 대기 현황)
    pending_count = stats.get("settlement_ready", {}).get("count", 0)
    pending_amount = stats.get("settlement_ready", {}).get("total_amount", 0)

    # ── 응답 구성 ─────────────────────────────────────────────
    filter_info: dict = {
        "closed_from": dt_from.isoformat() if dt_from else None,
        "closed_to": dt_to.isoformat() if dt_to else None,
        "timezone": "UTC",
        "note": "closed_from/to 필터는 OrderItem.closed_at(UTC) 기준. closed 상태에만 적용.",
    }

    return ok({
        "filter": filter_info,
        "pipeline": {
            st: {
                "count": stats.get(st, {}).get("count", 0),
                "total_amount": stats.get(st, {}).get("total_amount", 0),
            }
            for st in SETTLEMENT_STATUSES
        },
        "pending_admin_approval": {
            "count": pending_count,
            "total_amount": pending_amount,
            "description": "settlement_ready → closed 전이는 ADMIN 최종 승인 필요",
        },
        "total_closed": {
            "count": stats.get("closed", {}).get("count", 0),
            "total_amount": stats.get("closed", {}).get("total_amount", 0),
        },
        "closed_by_agency": agency_breakdown,
    })
