"""
Order 도메인 공통 헬퍼

이 모듈은 orders.py / order_items.py / standardize_service.py 에서 공유되는
공통 서비스 로직을 모아 관리합니다.

포함 항목:
  - add_status_history()           : OrderItem 상태 이력 INSERT-only 기록
  - get_order_or_404()             : Order 조회 + 삭제 검사
  - get_order_item_or_404()        : OrderItem 조회 + 삭제 검사
  - parse_date_strict()            : 날짜 문자열 엄격 파싱 (Option B 확정)
  - resolve_order_group()          : order_group_key 기반 Order 조회/생성 (Option A)
  - check_group_key_conflict()     : 같은 order_group_key 내 agency/brand 불일치 검사

날짜 파싱 Option B 확정 사양:
  허용: YYYY-MM-DD | YYYY/MM/DD | MM/DD/YYYY
  거부: 모호한 형식(예: 1/2/2026, 2026.01.15) → ValueError 발생 → on_hold 또는 에러 응답

order_group_key Option A 확정 사양:
  - 같은 key → 동일 Order로 묶음 (기존 draft Order 재사용)
  - 빈 key   → 행마다 별도 Order 생성
  - 같은 key + agency/brand 불일치 → 에러 또는 on_hold 처리
    · group_key_conflict_policy='error'  (기본): OrderGroupKeyConflictError 발생
    · group_key_conflict_policy='on_hold': 아이템을 on_hold 상태로 생성하고 계속
"""
import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order, OrderItem, OrderItemStatusHistory


# ── 예외 ────────────────────────────────────────────────────────────────────

class OrderGroupKeyConflictError(Exception):
    """
    같은 order_group_key에 속한 raw 행들이 서로 다른 agency 또는 brand를 가질 때 발생.

    필드:
      key          — 충돌이 발생한 order_group_key 값
      existing     — 기존 Order의 (agency_id, agency_name_snapshot) 정보
      incoming     — 새로 들어온 행의 (agency_id, agency_name_snapshot) 정보
      conflict_on  — 'agency' | 'brand' | 'agency+brand'
    """
    def __init__(
        self,
        key: str,
        existing: dict,
        incoming: dict,
        conflict_on: str = "agency",
    ):
        self.key = key
        self.existing = existing
        self.incoming = incoming
        self.conflict_on = conflict_on
        super().__init__(
            f"order_group_key='{key}' 충돌: "
            f"{conflict_on} 불일치 "
            f"(기존={existing}, 신규={incoming})"
        )


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
      - orders.py: cancel_order(), bulk_create_order_items()
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


# ── 날짜 파싱 (Option B 확정) ────────────────────────────────────────────────

def parse_date_strict(value: str) -> date:
    """
    날짜 문자열을 엄격하게 파싱하여 date 객체로 반환합니다.

    허용 형식 (Option B 확정):
      - YYYY-MM-DD  예: 2026-01-15
      - YYYY/MM/DD  예: 2026/01/15
      - MM/DD/YYYY  예: 01/15/2026  (미국식; 마지막 파트가 4자리 연도인 경우만)

    모호한 형식 거부 예시:
      - 1/2/2026   → 1월 2일 vs 2월 1일 구분 불가 → ValueError
      - 2026.01.15 → 미지원 구분자 → ValueError
      - 26-01-15   → 연도 2자리 → ValueError

    반환값:
      - date 객체 (성공)

    예외:
      - ValueError: 미지원 형식, 모호한 날짜, 유효하지 않은 날짜값

    사용처:
      - standardize_service._parse_date_or_hold()
      - import_service 시트 파싱
      - orders.py / order_items.py 직접 날짜 입력 유효성 검사
    """
    if not value or not isinstance(value, str):
        raise ValueError(f"빈 값 또는 문자열이 아닙니다: {value!r}")

    value = value.strip()

    # ── 형식 1: YYYY-MM-DD ──────────────────────────────────────
    # 정확히 YYYY-MM-DD 형식만 허용 (4-2-2 자리, 하이픈 구분)
    if len(value) == 10 and value[4] == "-" and value[7] == "-":
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(f"유효하지 않은 날짜: '{value}' (형식 YYYY-MM-DD 감지됐으나 날짜 오류)")

    # ── 형식 2: YYYY/MM/DD ──────────────────────────────────────
    # 정확히 YYYY/MM/DD 형식만 허용 (4-2-2 자리, 슬래시 구분)
    if len(value) == 10 and value[4] == "/" and value[7] == "/":
        try:
            return datetime.strptime(value, "%Y/%m/%d").date()
        except ValueError:
            raise ValueError(f"유효하지 않은 날짜: '{value}' (형식 YYYY/MM/DD 감지됐으나 날짜 오류)")

    # ── 형식 3: MM/DD/YYYY (미국식) ─────────────────────────────
    # 슬래시 분리 후 마지막 파트가 정확히 4자리 연도인 경우만 허용.
    # 앞 두 파트(MM, DD)는 반드시 2자리여야 모호성 없음.
    # 예: 01/15/2026 허용 / 1/2/2026 거부 (모호)
    parts = value.split("/")
    if len(parts) == 3 and len(parts[2]) == 4:
        mm_str, dd_str, yyyy_str = parts
        if len(mm_str) == 2 and len(dd_str) == 2:
            try:
                return datetime.strptime(value, "%m/%d/%Y").date()
            except ValueError:
                raise ValueError(f"유효하지 않은 날짜: '{value}' (형식 MM/DD/YYYY 감지됐으나 날짜 오류)")
        else:
            # MM 또는 DD가 1자리 → 모호 (예: 1/2/2026)
            raise ValueError(
                f"모호한 날짜 형식: '{value}'. "
                "MM/DD/YYYY 형식에서 월과 일은 반드시 2자리여야 합니다 (예: 01/02/2026). "
                "자동 추정을 허용하지 않습니다."
            )

    raise ValueError(
        f"지원하지 않는 날짜 형식: '{value}'. "
        "허용 형식: YYYY-MM-DD, YYYY/MM/DD, MM/DD/YYYY (월/일 반드시 2자리)"
    )


def parse_date_or_none(value) -> Optional[date]:
    """
    날짜 파싱 시도. 실패하면 None 반환 (on_hold 처리는 호출자 책임).

    standardize_service의 내부 파싱에서 사용.
    None 반환 시 호출자가 on_hold 상태 설정 + 사유 기록 권장.
    """
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return parse_date_strict(str(value))
    except ValueError:
        return None


def parse_date_strict_or_raise(value) -> date:
    """
    날짜 파싱 실패 시 ValueError 발생. API 입력값 검증에 사용.

    사용처:
      - orders.py OrderCreate 날짜 필드 직접 입력 검증 (미래 확장)
      - import_service 시트 파싱 (모호한 날짜 → on_hold)
    """
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return parse_date_strict(str(value))


# ── order_group_key 로직 (Option A 확정) ───────────────────────────────────

def _normalize_group_key(key) -> Optional[str]:
    """
    order_group_key 값 정규화.
    빈 문자열, None, 공백만 있는 문자열 → None (별도 Order 생성).
    그 외 → strip한 문자열.
    """
    if key is None:
        return None
    s = str(key).strip()
    return s if s else None


async def resolve_order_group(
    db: AsyncSession,
    order_group_key: Optional[str],
    agency_id: Optional[uuid.UUID],
    agency_name_snapshot: Optional[str],
    source_type: str,
    raw_input_id: Optional[uuid.UUID],
    actor_id: Optional[uuid.UUID],
    *,
    conflict_policy: str = "on_hold",
) -> tuple[Order, Optional[str]]:
    """
    order_group_key 기반으로 Order를 조회하거나 신규 생성합니다.

    Option A 규칙:
      1. key = None/빈값  → 신규 Order 생성 (행마다 별도 Order)
      2. key 있음, 기존 draft Order 없음 → 신규 Order 생성 후 group_key 기록
      3. key 있음, 기존 draft Order 있음 → 기존 Order 재사용
         a. agency/brand 불일치 확인
            - conflict_policy='error'  → OrderGroupKeyConflictError 발생
            - conflict_policy='on_hold'→ (order, conflict_reason) 반환
              호출자가 OrderItem을 on_hold 상태로 생성해야 함.

    반환값:
      (Order, conflict_reason)
        - conflict_reason=None    : 충돌 없음, 정상 처리
        - conflict_reason=str     : 충돌 발생 (policy='on_hold'일 때). 아이템을 on_hold로 생성할 것.

    주의:
      - db.flush() 호출 후 order.id가 확보됩니다.
      - commit()은 호출자 책임입니다.
    """
    key = _normalize_group_key(order_group_key)

    # key 없음 → 별도 Order 생성
    if not key:
        order = Order(
            agency_id=agency_id,
            agency_name_snapshot=agency_name_snapshot,
            source_type=source_type,
            raw_input_id=raw_input_id,
            status="draft",
            order_group_key=None,
        )
        db.add(order)
        await db.flush()
        return order, None

    # key 있음 → 기존 draft Order 조회
    existing_order = (
        await db.execute(
            select(Order).where(
                Order.order_group_key == key,
                Order.is_deleted.is_(False),
                Order.status == "draft",
            )
        )
    ).scalar_one_or_none()

    if existing_order is None:
        # 신규 Order 생성
        order = Order(
            agency_id=agency_id,
            agency_name_snapshot=agency_name_snapshot,
            source_type=source_type,
            raw_input_id=raw_input_id,
            status="draft",
            order_group_key=key,
        )
        db.add(order)
        await db.flush()
        return order, None

    # 기존 Order 재사용 — agency 불일치 검사
    conflict_reason = _check_agency_conflict(
        existing_order=existing_order,
        new_agency_id=agency_id,
        new_agency_name=agency_name_snapshot,
        group_key=key,
    )

    if conflict_reason:
        if conflict_policy == "error":
            raise OrderGroupKeyConflictError(
                key=key,
                existing={
                    "agency_id": str(existing_order.agency_id) if existing_order.agency_id else None,
                    "agency_name_snapshot": existing_order.agency_name_snapshot,
                },
                incoming={
                    "agency_id": str(agency_id) if agency_id else None,
                    "agency_name_snapshot": agency_name_snapshot,
                },
                conflict_on="agency",
            )
        # on_hold 정책: 기존 Order 반환 + 충돌 사유 전달
        return existing_order, conflict_reason

    return existing_order, None


def _check_agency_conflict(
    existing_order: Order,
    new_agency_id: Optional[uuid.UUID],
    new_agency_name: Optional[str],
    group_key: str,
) -> Optional[str]:
    """
    같은 order_group_key의 기존 Order와 신규 행의 agency 정보를 비교합니다.

    불일치 판단 기준:
      - 둘 다 agency_id 있고 다르면 → 충돌
      - agency_id 없고 agency_name_snapshot이 있으면 name 비교
        (대소문자 무시, strip)
      - 한쪽만 없으면 관대하게 허용 (신규 행이 빈 경우 기존 값 상속)

    반환:
      - None: 충돌 없음
      - str : 충돌 사유 메시지
    """
    # agency_id 기준 비교 (둘 다 있을 때만 엄격 비교)
    if existing_order.agency_id and new_agency_id:
        if existing_order.agency_id != new_agency_id:
            return (
                f"order_group_key='{group_key}' 내 agency_id 불일치: "
                f"기존={existing_order.agency_id}, 신규={new_agency_id}"
            )

    # agency_id 없으면 name 비교
    if (
        not existing_order.agency_id
        and not new_agency_id
        and existing_order.agency_name_snapshot
        and new_agency_name
    ):
        if existing_order.agency_name_snapshot.strip().lower() != new_agency_name.strip().lower():
            return (
                f"order_group_key='{group_key}' 내 agency_name 불일치: "
                f"기존='{existing_order.agency_name_snapshot}', 신규='{new_agency_name}'"
            )

    return None
