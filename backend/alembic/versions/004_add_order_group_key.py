"""
004 — order_group_key 컬럼 추가 (Wave 2 Phase Step 1)

대상 테이블:
  - orders            : order_group_key TEXT NULL + 인덱스
  - order_raw_inputs  : order_group_key TEXT NULL + 인덱스

설계 원칙 (Option A 확정):
  - 같은 order_group_key → 동일 Order로 묶음 (draft Order 재사용)
  - 빈 값 / NULL        → 행마다 별도 Order 생성
  - 같은 key + agency/brand 불일치 → on_hold 처리 (또는 에러)

  order_raw_inputs.order_group_key:
    · 시트/파일 행에서 파싱한 원본 group key 저장 (immutable)
    · import_service._save_raw_input() 에서 채움

  orders.order_group_key:
    · standardize_service.resolve_order_group() 로직에서 채움
    · 같은 key의 첫 번째 Order에만 설정 → 후속 raw 행은 이 Order를 재사용

인덱스:
  - ix_orders_order_group_key            : 그룹 조회 최적화 (NULL 제외 partial은 DB 설정 생략)
  - ix_order_raw_inputs_order_group_key  : import 처리 시 그룹 조회

Revision: 004
Depends on: 003
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── orders: order_group_key ────────────────────────────────────────────
    op.add_column(
        "orders",
        sa.Column(
            "order_group_key",
            sa.Text,
            nullable=True,
            comment=(
                "같은 key면 동일 Order로 묶음. NULL/빈값이면 행마다 별도 Order 생성. "
                "같은 key 내 agency/brand 불일치 시 on_hold 처리."
            ),
        ),
    )
    op.create_index(
        "ix_orders_order_group_key",
        "orders",
        ["order_group_key"],
    )

    # ── order_raw_inputs: order_group_key ──────────────────────────────────
    op.add_column(
        "order_raw_inputs",
        sa.Column(
            "order_group_key",
            sa.Text,
            nullable=True,
            comment="시트/파일 행에서 파싱한 원본 order_group_key. immutable 보존.",
        ),
    )
    op.create_index(
        "ix_order_raw_inputs_order_group_key",
        "order_raw_inputs",
        ["order_group_key"],
    )


def downgrade() -> None:
    # order_raw_inputs
    op.drop_index("ix_order_raw_inputs_order_group_key", table_name="order_raw_inputs")
    op.drop_column("order_raw_inputs", "order_group_key")

    # orders
    op.drop_index("ix_orders_order_group_key", table_name="orders")
    op.drop_column("orders", "order_group_key")
