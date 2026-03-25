"""
Standardize Service — OrderRawInput → Order + OrderItem(s) 변환

설계 원칙:
  - 1 OrderRawInput 행 → 1 Order + N OrderItem (기본 1:1, 확장 가능)
  - 매핑 실패 시 sellable_offering_id = null로 보존 (자동 추정 금지)
  - 변환 실패 아이템은 on_hold 상태 보존 (DROP 금지)
  - product_type_code: 시트 상품명 키워드 기반 추정 (불확실 시 on_hold)

컬럼명 기준: 마이그레이션 001_initial_schema.py (수정 라운드 2026-03-25)
  - product_type_snapshot    → product_type_code
  - keyword_snapshot         → main_keyword
  - naver_place_url_snapshot → place_url_snapshot
  - keywords (ARRAY)         → keywords_raw (Text, 쉼표 구분)
  - unit_price_snapshot      → unit_price
  - total_amount_snapshot    → total_amount
  - assigned_provider_id     → provider_id
  - assigned_at/by           → routed_at / routed_by
  - actor_id                 → changed_by (OrderItemStatusHistory)

핵심 컬럼 매핑 (취합 시트 기반):
  대행사명           → order.agency_name_snapshot
  영업 담당자         → order.sales_rep_name
  견적 담당자         → order.estimator_name
  플레이스 URL        → item.place_url_snapshot
  업체명              → item.place_name_snapshot
  작업키워드          → item.main_keyword
  상품명/시트명       → item.product_type_code (표준화)
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


# ── 상품 코드 매핑 테이블 ────────────────────────────────────────

# 시트명 / 상품명 키워드 → product_type_code 추정
# BLOG_DISPATCH: CHOEBL(최블), NBBL(엔비블) 통합 처리
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

# BLOG_DISPATCH 세부 구분 (product_subtype)
BLOG_DISPATCH_SUBTYPES: dict[str, str] = {
    "최블": "CHOEBL",
    "엔비블": "NBBL",
    "블엔비블": "NBBL",
}


def _infer_product_type(
    raw_data: dict[str, Any],
    sheet_name: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    """
    raw_data + sheet_name에서 product_type_code, product_subtype 추정.
    확실하지 않으면 (None, None) 반환 → on_hold 처리.
    """
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
    from datetime import datetime as dt
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%m/%d/%Y"):
        try:
            return dt.strptime(s, fmt).date()
        except (ValueError, AttributeError):
            continue
    try:
        if "T" in s:
            return dt.fromisoformat(s).date()
    except (ValueError, AttributeError):
        pass
    return None


def _parse_int(value: Any) -> Optional[int]:
    """정수 파싱. 실패 시 None."""
    if value is None or value == "":
        return None
    try:
        return int(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _str(value: Any) -> Optional[str]:
    """None/빈 문자열 정규화."""
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _extract_naver_place_id(url: str) -> Optional[str]:
    """Naver Place URL에서 MID 추출."""
    if not url:
        return None
    match = re.search(r"/place(?:s)?/(\d+)", url)
    if not match:
        match = re.search(r"/(\d{8,})", url)
    return match.group(1) if match else None


async def _find_place_id(
    db: AsyncSession,
    place_url: Optional[str],
) -> Optional[uuid.UUID]:
    """
    Place URL 기준으로 Place 레코드 조회.
    미등록 플레이스는 None 반환 (자동 생성 금지 — 운영자 직접 등록).
    """
    if not place_url:
        return None
    naver_id = _extract_naver_place_id(place_url)
    if naver_id:
        result = await db.execute(
            select(Place).where(
                Place.naver_place_id == naver_id,
                Place.is_deleted.is_(False),
            )
        )
        place = result.scalar_one_or_none()
        if place:
            return place.id
    return None


# ── 핵심 변환 함수 ────────────────────────────────────────────────

async def standardize_raw_input(
    db: AsyncSession,
    raw: OrderRawInput,
    actor: Optional[User],
) -> StandardizeResult:
    """
    OrderRawInput 1행 → Order 1개 + OrderItem N개 변환.

    아이템 분리 기준:
      - 기본: 1 raw → 1 item
      - 확장: raw_data에 'items' 배열이 있으면 각각 별도 아이템 생성
      - 향후: 다수 키워드 → N 아이템 분리 가능

    매핑 실패 시:
      - sellable_offering_id = null (자동 추정 금지)
      - status = on_hold
      - status_note에 사유 기록
    """
    rd = raw.raw_data

    # ── 1. Order 헤더 생성 ─────────────────────────────────────
    order = Order(
        agency_name_snapshot=_str(rd.get("대행사명") or rd.get("대행사")),
        sales_rep_name=_str(rd.get("영업 담당자") or rd.get("영업담당자")),
        estimator_name=_str(rd.get("견적 담당자") or rd.get("견적담당자")),
        raw_input_id=raw.id,
        source_type=raw.source_type,
        status="draft",
    )
    db.add(order)
    await db.flush()  # order.id 확보

    # ── 2. OrderItem 후보 추출 ─────────────────────────────────
    # raw_data에 'items' 배열이 있으면 N개, 없으면 단일 행
    item_specs: list[dict[str, Any]] = []
    if isinstance(rd.get("items"), list) and rd["items"]:
        item_specs = rd["items"]
    else:
        item_specs = [rd]

    items: list[OrderItem] = []
    held_items: list[OrderItem] = []

    for idx, spec in enumerate(item_specs):
        item = await _build_order_item(
            db=db,
            order_id=order.id,
            item_index=idx,
            spec=spec,
            raw_input_id=raw.id,
            source_row_index=raw.source_row_index,
        )
        db.add(item)
        await db.flush()  # item.id 확보

        # 이력 INSERT-only
        history = OrderItemStatusHistory(
            order_item_id=item.id,
            from_status=None,
            to_status=item.status,
            changed_by=actor.id if actor else None,
            reason="raw 변환 생성",
        )
        db.add(history)

        if item.status == "on_hold":
            held_items.append(item)
        else:
            items.append(item)

    # ── 3. raw 처리 완료 표시 ─────────────────────────────────
    raw.is_processed = True
    raw.result_order_id = order.id

    await db.commit()
    await db.refresh(order)

    return StandardizeResult(order=order, items=items, held_items=held_items)


async def _build_order_item(
    db: AsyncSession,
    order_id: uuid.UUID,
    item_index: int,
    spec: dict[str, Any],
    raw_input_id: Optional[uuid.UUID] = None,
    source_row_index: Optional[int] = None,
) -> OrderItem:
    """
    단일 spec dict → OrderItem 변환.
    매핑 불확실 시 on_hold 반환.

    컬럼명: 마이그레이션 기준 (002 — raw 추적 컬럼 포함)
      raw_input_id      — loose ref (FK 없음). standardize 경유 시 채워넣음.
      source_row_index  — 원본 시트/파일 행 번호 (OrderRawInput.source_row_index)
      item_index_in_row — 같은 행 내 아이템 순번 (0-based, item_index 파라미터)
    """
    product_type_code, product_subtype = _infer_product_type(
        spec, spec.get("__sheet__")
    )

    # 플레이스 URL (place_url_snapshot: 구 naver_place_url_snapshot)
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

    place_id = await _find_place_id(db, place_url)

    # Naver Place ID 추출
    naver_place_id_snapshot = _extract_naver_place_id(place_url) if place_url else None

    # 날짜
    start_date = _parse_date(
        spec.get("시작일") or spec.get("구동시작") or spec.get("구동 시작")
    )
    end_date = _parse_date(
        spec.get("종료일") or spec.get("구동종료") or spec.get("구동 종료")
    )

    # 수량
    daily_qty = _parse_int(
        spec.get("일 구동 수량") or spec.get("일진행개수") or spec.get("일 수량")
    )
    total_qty = _parse_int(
        spec.get("총 구동 수량") or spec.get("총진행개수") or spec.get("총 수량")
    )

    # 키워드 (main_keyword: 구 keyword_snapshot, keywords_raw: 구 keywords ARRAY)
    keywords_raw_value = _str(
        spec.get("작업키워드") or spec.get("메인 키워드") or spec.get("키워드")
    )
    # main_keyword: 쉼표 첫 번째 값
    main_keyword = None
    if keywords_raw_value:
        parts = [k.strip() for k in keywords_raw_value.split(",") if k.strip()]
        main_keyword = parts[0] if parts else keywords_raw_value

    # 상태 결정: 상품 타입 추정 불가 → on_hold
    item_status = "received"
    status_note: Optional[str] = None
    if product_type_code is None:
        item_status = "on_hold"
        status_note = (
            "상품 유형을 자동으로 추정할 수 없습니다. "
            "운영자가 직접 product_type_code 및 sellable_offering_id를 지정해야 합니다."
        )

    return OrderItem(
        order_id=order_id,
        # ── raw 추적 컬럼 (B안 · 마이그레이션 002) ──────────────
        raw_input_id=raw_input_id,          # loose ref, FK 없음
        source_row_index=source_row_index,  # 원본 시트 행 번호
        item_index_in_row=item_index,       # 행 내 아이템 순번 (0-based)
        # ── 플레이스 ────────────────────────────────────────────
        place_id=place_id,
        place_name_snapshot=place_name,
        place_url_snapshot=place_url,
        naver_place_id_snapshot=naver_place_id_snapshot,
        # ── 상품 ────────────────────────────────────────────────
        product_type_code=product_type_code,
        product_subtype=product_subtype,
        # ── 키워드 ──────────────────────────────────────────────
        main_keyword=main_keyword,
        keywords_raw=keywords_raw_value,
        # ── 기간·수량 ────────────────────────────────────────────
        start_date=start_date,
        end_date=end_date,
        daily_qty=daily_qty,
        total_qty=total_qty,
        # ── 보조 데이터 (spec_data에도 raw 추적 정보 병기) ──────
        spec_data={
            "source_columns": {
                k: str(v) for k, v in spec.items()
                if k not in ("items", "__sheet__") and v is not None
            },
            # spec_data에도 추적 정보 병기 (B안 구조화 컬럼이 primary)
            "raw_tracking": {
                "raw_input_id": str(raw_input_id) if raw_input_id else None,
                "source_row_index": source_row_index,
                "item_index_in_row": item_index,
            },
        },
        status=item_status,
        operator_note=status_note,
        # sellable_offering_id = null (자동 추정 금지)
    )
