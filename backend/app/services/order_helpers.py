"""
Order 도메인 공통 헬퍼

이 모듈은 orders.py / order_items.py / standardize_service.py 에서 공유되는
공통 서비스 로직을 모아 관리합니다.

포함 항목:
  - add_status_history()       : OrderItem 상태 이력 INSERT-only 기록
  - get_order_or_404()         : Order 조회 + 삭제 검사
  - get_order_item_or_404()    : OrderItem 조회 + 삭제 검사
  - parse_date_flexible()      : 날짜 문자열 유연 파싱 (Wave 2 Sheet import 대비)

리팩터링 노트 (Wave 2 Phase 2-E):
  - orders.py / order_items.py 의 인라인 _get_order_or_404, _get_item_or_404,
    _add_status_history 는 이 모듈의 함수를 참조하도록 점진 교체 예정.
  - 현재는 양측 공존 허용 (하위 호환).
"""
import uuid
from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order, OrderItem, OrderItemStatusHistory


# ── 상태 이력 기록 ──────────────────────────────────────────────────────────

async def add_status_history(
    db: AsyncSession,
    item_id: uuid.UUID,
    from_status: Optional[str],
    to_status: str,
    changed_by: Optional[uuid.UUID],
    reason: Optional[str] = None,
) -> None:
    """
    OrderItem 상태 이력을 INSERT-only로 기록합니다.

    - commit()은 호출자가 담당합니다.
    - 동일 트랜잭션 내 flush()와 함께 사용 가능합니다.

    사용처:
      - order_items.py: create_order_item(), transition_status(), assign_provider()
      - standardize_service.py: standardize_raw_input() 내부 헬퍼
    """
    history = OrderItemStatusHistory(
        order_item_id=item_id,
        from_status=from_status,
        to_status=to_status,
        changed_by=changed_by,
        reason=reason,
    )
    db.add(history)


# ── Order 조회 헬퍼 ────────────────────────────────────────────────────────

async def get_order_or_404(order_id: uuid.UUID, db: AsyncSession) -> Order:
    """
    Order를 조회합니다. 존재하지 않거나 소프트 삭제된 경우 NotFoundError를 발생시킵니다.
    """
    from app.core.exceptions import NotFoundError  # 순환 임포트 방지

    order = (
        await db.execute(
            select(Order).where(
                Order.id == order_id,
                Order.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()
    if not order:
        raise NotFoundError("ORDER_NOT_FOUND", f"Order를 찾을 수 없습니다: {order_id}")
    return order


async def get_order_item_or_404(item_id: uuid.UUID, db: AsyncSession) -> OrderItem:
    """
    OrderItem을 조회합니다. 존재하지 않거나 소프트 삭제된 경우 NotFoundError를 발생시킵니다.
    """
    from app.core.exceptions import NotFoundError  # 순환 임포트 방지

    item = (
        await db.execute(
            select(OrderItem).where(
                OrderItem.id == item_id,
                OrderItem.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()
    if not item:
        raise NotFoundError("ORDER_ITEM_NOT_FOUND", f"OrderItem을 찾을 수 없습니다: {item_id}")
    return item


# ── 날짜 파싱 유틸 (Wave 2 Sheet import 대비) ───────────────────────────────

def parse_date_flexible(value: str) -> Optional[date]:
    """
    날짜 문자열을 유연하게 파싱하여 date 객체로 반환합니다.

    허용 형식 (Option B 확정):
      - YYYY-MM-DD  (예: 2026-01-15)
      - YYYY/MM/DD  (예: 2026/01/15)
      - MM/DD/YYYY  (예: 01/15/2026)

    모호한 형식(예: 1/2/2026 — 1월 2일 vs 2월 1일)은 자동 추정하지 않고
    ValueError를 발생시킵니다. 호출자는 on_hold 처리 또는 에러 응답을 담당합니다.

    반환값:
      - date 객체 (성공)
      - ValueError (미지원 형식 또는 모호한 날짜)

    사용처:
      - standardize_service.py (기존)
      - Wave 2 Google Sheet import 파서
    """
    from datetime import datetime

    value = value.strip()

    # 형식 1: YYYY-MM-DD
    if len(value) == 10 and value[4] == "-" and value[7] == "-":
        return datetime.strptime(value, "%Y-%m-%d").date()

    # 형식 2: YYYY/MM/DD
    if len(value) == 10 and value[4] == "/" and value[7] == "/":
        return datetime.strptime(value, "%Y/%m/%d").date()

    # 형식 3: MM/DD/YYYY (미국식)
    # 슬래시 분리 후 마지막 파트가 4자리 연도인 경우만 허용
    parts = value.split("/")
    if len(parts) == 3 and len(parts[2]) == 4:
        return datetime.strptime(value, "%m/%d/%Y").date()

    raise ValueError(
        f"지원하지 않는 날짜 형식입니다: '{value}'. "
        "허용 형식: YYYY-MM-DD, YYYY/MM/DD, MM/DD/YYYY"
    )
