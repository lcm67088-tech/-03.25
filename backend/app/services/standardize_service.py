"""
Standardize Service — OrderRawInput → Order + OrderItem(s) 변환

설계 원칙:
- 1 OrderRawInput 행 → 1 Order + N OrderItem (기본 1:1, 확장 가능)
- 매핑 실패 시 sellable_offering_id = null로 보존 (자동 추정 절대 금지)
- 변환 실패한 아이템은 on_hold 상태로 보존 (DROP 금지)
- StandardProductType 매핑은 product_type_snapshot(코드 문자열)으로 처리
- 구조: StandardizeResult (order + items + held_items)

핵심 컬럼 매핑 (취합 시트 기반):
  대행사명           → order.agency_name_snapshot
  영업 담당자         → order.sales_manager_snapshot
  견적 담당자         → order.quote_manager_snapshot
  플레이스 URL/명     → item.place_* + place_name_snapshot
  작업키워드          → item.keyword_snapshot
  상품명/시트명       → item.product_type_snapshot (표준화)
  시작일/종료일       → item.start_date, end_date
  일 구동 수량        → item.daily_qty
  총 구동 수량        → item.total_qty
"""
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order, OrderItem, OrderItemStatusHistory, OrderRawInput
from app.models.place import Place
from app.models.user import User

logger = logging.getLogger(__name__)


# ── 결과 구조 ────────────────────────────────────────────────────

@dataclass
class StandardizeResult:
    """
    1 OrderRawInput → 1 Order + N OrderItem 변환 결과.
    held_items: 매핑 실패·보류 아이템 (on_hold 상태).
    """
    order: Order
    items: list[OrderItem] = field(default_factory=list)
    held_items: list[OrderItem] = field(default_factory=list)


# ── 상품 코드 매핑 테이블 (초안 — 수정 가능) ─────────────────────

# 시트명 / 상품명 키워드 → StandardProductType.code 추정
# NOTE: 이것은 가정(assumption)임. 운영자 확인 필요.
PRODUCT_TYPE_HINTS: dict[str, str] = {
    "트래픽": "TRAFFIC",
    "저장": "SAVE",
    "ai(실계정)": "AI_REAL",
    "ai(비실계)": "AI_NONREAL",
    "ai 실계정": "AI_REAL",
    "ai 비실계": "AI_NONREAL",
    "기자단": "BLOG_REPORTER",
    "실리뷰어": "BLOG_REPORTER",
    "최블": "BLOG_DISPATCH",
    "엔비블": "BLOG_DISPATCH",
    "블엔비블": "BLOG_DISPATCH",
    "샤오홍슈": "XIAOHONGSHU",
    "따종디엔핑": "DIANPING",
    "xiaohongshu": "XIAOHONGSHU",
    "dianping": "DIANPING",
}

# BLOG_DISPATCH 세부 구분
BLOG_DISPATCH_SUBTYPES: dict[str, str] = {
    "최블": "CHOEBL",
    "엔비블": "NBBL",
    "블엔비블": "NBBL",
}


def _infer_product_type(raw_data: dict[str, Any], sheet_name: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """
    raw_data + sheet_name에서 product_type_snapshot, product_subtype 추정.
    확실하지 않으면 (None, None) 반환 → on_hold 처리.
    """
    # 상품명 컬럼 우선
    candidates = [
        str(raw_data.get("상품명", "") or "").strip().lower(),
        str(raw_data.get("접수 상품", "") or "").strip().lower(),
        str(sheet_name or "").strip().lower(),
    ]

    for candidate in candidates:
        for hint, code in PRODUCT_TYPE_HINTS.items():
            if hint in candidate:
                subtype = BLOG_DISPATCH_SUBTYPES.get(hint) if code == "BLOG_DISPATCH" else None
                return code, subtype

    return None, None


def _parse_date(value: Any) -> Optional[date]:
    """다양한 날짜 형식 파싱. 실패 시 None."""
    if not value:
        return None
    if isinstance(value, date):
        return value

    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            from datetime import datetime
            if "T" in s:
                return datetime.fromisoformat(s).date()
            from datetime import datetime as dt
            return dt.strptime(s, fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def _parse_int(value: Any) -> Optional[int]:
    """정수 파싱. 실패 시 None."""
    if value is None or value == "":
        return None
    try:
        return int(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _extract_naver_place_id(url: str) -> Optional[str]:
    """Naver Place URL에서 MID 추출."""
    if not url:
        return None
    match = re.search(r"/place(?:s)?/(\d+)", url)
    if not match:
        match = re.search(r"/(\d{8,})", url)
    return match.group(1) if match else None


async def _find_or_create_place(
    db: AsyncSession,
    place_url: Optional[str],
    place_name: Optional[str],
) -> Optional[uuid.UUID]:
    """
    Place URL 기준으로 Place 레코드 조회.
    없으면 None 반환 (자동 생성 금지 — 운영자가 직접 등록해야 함).
    """
    if not place_url:
        return None

    naver_id = _extract_naver_place_id(place_url)
    if naver_id:
        result = await db.execute(
            select(Place).where(Place.naver_place_id == naver_id, Place.is_deleted == False)
        )
        place = result.scalar_one_or_none()
        if place:
            return place.id

    return None  # 미등록 플레이스 → null 유지


# ── 핵심 변환 함수 ───────────────────────────────────────────────

async def standardize_raw_input(
    db: AsyncSession,
    raw: OrderRawInput,
    actor: Optional[User],
) -> StandardizeResult:
    """
    OrderRawInput 1행 → Order 1개 + OrderItem N개 변환.

    아이템 분리 기준:
    - 기본: 1 raw → 1 item
    - 확장: raw_data에 'items' 배열이 있으면 각각 별도 아이템
    - 향후: 다수 키워드 → N 아이템 분리 가능

    매핑 실패 시:
    - sellable_offering_id = null
    - status = on_hold
    - status_note에 실패 사유 기록
    """
    rd = raw.raw_data  # 원본 데이터

    # ── 1. Order 헤더 생성 ──────────────────────────────────────
    order = Order(
        agency_name_snapshot=_str(rd.get("대행사명") or rd.get("대행사")),
        sales_manager_snapshot=_str(rd.get("영업 담당자") or rd.get("영업담당자")),
        quote_manager_snapshot=_str(rd.get("견적 담당자") or rd.get("견적담당자")),
        raw_input_id=raw.id,
        status="draft",
        created_by=actor.id if actor else None,
    )
    db.add(order)
    await db.flush()  # order.id 확보

    # ── 2. OrderItem 후보 추출 ──────────────────────────────────
    # 기본: 단일 아이템. raw_data에 'items' 키가 있으면 다수.
    item_specs: list[dict[str, Any]] = []

    if isinstance(rd.get("items"), list) and rd["items"]:
        # 명시적 N 아이템 형식
        item_specs = rd["items"]
    else:
        # 단일 행 → 단일 아이템
        item_specs = [rd]

    items: list[OrderItem] = []
    held_items: list[OrderItem] = []

    for idx, spec in enumerate(item_specs):
        item = await _build_order_item(
            db=db,
            order_id=order.id,
            raw_id=raw.id,
            raw_row_index=raw.row_index,
            item_index=idx,
            spec=spec,
            actor=actor,
        )
        db.add(item)

        # 이력 INSERT
        history = OrderItemStatusHistory(
            order_item_id=item.id,
            from_status=None,
            to_status=item.status,
            reason="raw 변환 생성",
            actor_id=actor.id if actor else None,
        )
        db.add(history)

        if item.status == "on_hold":
            held_items.append(item)
        else:
            items.append(item)

    # ── 3. raw 처리 완료 표시 ──────────────────────────────────
    raw.is_processed = True
    raw.result_order_id = order.id

    await db.commit()
    await db.refresh(order)

    return StandardizeResult(order=order, items=items, held_items=held_items)


async def _build_order_item(
    db: AsyncSession,
    order_id: uuid.UUID,
    raw_id: Optional[uuid.UUID],
    raw_row_index: Optional[int],
    item_index: int,
    spec: dict[str, Any],
    actor: Optional[User],
) -> OrderItem:
    """
    단일 spec dict → OrderItem 변환.
    매핑 불확실 시 on_hold 반환.
    """
    # 상품 타입 추정
    product_type, product_subtype = _infer_product_type(
        spec, spec.get("__sheet__")
    )

    # 플레이스 연결
    place_url = _str(
        spec.get("플레이스 URL")
        or spec.get("플레이스URL")
        or spec.get("모바일플레이스URL")
        or spec.get("네이버 플레이스 주소")
    )
    place_name = _str(
        spec.get("플레이스 명")
        or spec.get("업체명")
        or spec.get("매장명")
    )

    place_id = await _find_or_create_place(db, place_url, place_name)

    # 날짜 파싱
    start_date = _parse_date(
        spec.get("시작일") or spec.get("구동시작") or spec.get("구동 시작")
    )
    end_date = _parse_date(
        spec.get("종료일") or spec.get("구동종료") or spec.get("구동 종료")
    )

    # 수량 파싱
    daily_qty = _parse_int(
        spec.get("일 구동 수량") or spec.get("일진행개수") or spec.get("일 수량")
    )
    total_qty = _parse_int(
        spec.get("총 구동 수량") or spec.get("총진행개수") or spec.get("총 수량")
    )

    # 키워드
    keyword = _str(
        spec.get("작업키워드") or spec.get("메인 키워드") or spec.get("키워드")
    )

    # 상태 결정
    # 상품 타입을 추정하지 못하면 → on_hold (자동 추정 금지)
    status = "received"
    hold_reason: Optional[str] = None

    if product_type is None:
        status = "on_hold"
        hold_reason = (
            "상품 유형을 자동으로 추정할 수 없습니다. "
            "운영자가 직접 sellable_offering_id를 지정해야 합니다."
        )

    item = OrderItem(
        order_id=order_id,
        raw_input_id=raw_id,
        raw_row_index=raw_row_index,
        item_index_in_row=item_index,
        place_id=place_id,
        place_name_snapshot=place_name,
        product_type_snapshot=product_type,
        product_subtype=product_subtype,
        keyword_snapshot=keyword,
        start_date=start_date,
        end_date=end_date,
        daily_qty=daily_qty,
        total_qty=total_qty,
        spec_data={
            "source_columns": {
                k: str(v) for k, v in spec.items()
                if k not in ("items", "__sheet__") and v is not None
            }
        },
        status=status,
        status_note=hold_reason,
        # sellable_offering_id = null (자동 추정 금지)
    )

    # id flush 필요
    await db.flush()
    return item


def _str(value: Any) -> Optional[str]:
    """None/빈 문자열 정규화."""
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None
