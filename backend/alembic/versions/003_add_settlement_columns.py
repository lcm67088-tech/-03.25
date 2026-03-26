"""
003 — 정산 추적 컬럼 추가 (Wave 2 Phase 2-C)

대상 테이블: order_items, orders

order_items 추가 컬럼:
  confirmed_at        TIMESTAMP WITH TIME ZONE  NULL  — done→confirmed 전이 시각
  settlement_ready_at TIMESTAMP WITH TIME ZONE  NULL  — confirmed→settlement_ready 전이 시각
  closed_at           TIMESTAMP WITH TIME ZONE  NULL  — settlement_ready→closed 전이 시각 (ADMIN 승인 시각)
  settlement_note     TEXT                      NULL  — 정산 관련 운영자 메모

orders 추가 컬럼:
  closed_at           TIMESTAMP WITH TIME ZONE  NULL  — Order 전체 종료 시각
  closed_by           UUID                      NULL  — Order 종료 처리자 (FK: users, SET NULL)

설계 원칙:
  - 상태 전이 이력은 order_item_status_histories 에서 관리 (INSERT 전용)
  - 이 컬럼들은 "빠른 조회·정산 집계"를 위한 비정규화 타임스탬프
  - 전이 시각은 상태 전이 엔드포인트(POST /status)에서 자동 기록
  - closed_at 기준 인덱스 추가 (정산 기간 조회 최적화)

Revision: 003
Depends on: 002
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── order_items: 정산 추적 타임스탬프 ──────────────────────────────────
    op.add_column(
        "order_items",
        sa.Column(
            "confirmed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="done→confirmed 전이 시각 (비정규화 타임스탬프)",
        ),
    )
    op.add_column(
        "order_items",
        sa.Column(
            "settlement_ready_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="confirmed→settlement_ready 전이 시각",
        ),
    )
    op.add_column(
        "order_items",
        sa.Column(
            "closed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="settlement_ready→closed 전이 시각 (ADMIN 최종 승인 시각)",
        ),
    )
    op.add_column(
        "order_items",
        sa.Column(
            "settlement_note",
            sa.Text,
            nullable=True,
            comment="정산 관련 운영자 메모 (정산 단계에서 추가 기입)",
        ),
    )

    # 정산 기간 조회 최적화 인덱스
    op.create_index(
        "ix_order_items_closed_at",
        "order_items",
        ["closed_at"],
    )
    op.create_index(
        "ix_order_items_settlement_ready_at",
        "order_items",
        ["settlement_ready_at"],
    )

    # ── orders: 헤더 레벨 종료 추적 ────────────────────────────────────────
    op.add_column(
        "orders",
        sa.Column(
            "closed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Order 전체 종료 시각 (모든 OrderItem closed 후 기록)",
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "closed_by",
            UUID(as_uuid=True),
            nullable=True,
            comment="Order 종료 처리자 UUID (loose reference, FK 없음)",
        ),
    )


def downgrade() -> None:
    # orders
    op.drop_column("orders", "closed_by")
    op.drop_column("orders", "closed_at")

    # order_items
    op.drop_index("ix_order_items_settlement_ready_at", table_name="order_items")
    op.drop_index("ix_order_items_closed_at", table_name="order_items")
    op.drop_column("order_items", "settlement_note")
    op.drop_column("order_items", "closed_at")
    op.drop_column("order_items", "settlement_ready_at")
    op.drop_column("order_items", "confirmed_at")
