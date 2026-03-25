"""
002 — order_items raw 추적 컬럼 추가 (Wave 1 보강 · B안)

추가 컬럼:
  raw_input_id      UUID  NULL  — OrderRawInput UUID (loose reference, FK 제약 없음)
  source_row_index  INT   NULL  — 원본 시트/파일 행 번호 (0-based)
  item_index_in_row INT   NULL  — 같은 raw 행 내 아이템 순번 (0-based, 1→N 분기 추적)

설계 원칙:
  - FK 제약 없음: OrderRawInput 삭제/정리 시 OrderItem에 영향 없음
  - web_portal 직접 생성: 세 컬럼 모두 NULL (raw 경유 없음)
  - google_sheet_import / excel_import: standardize_service가 채워넣음
  - 인덱스: raw_input_id에 일반 인덱스 부여 (추적 쿼리 최적화)

Revision: 002
Depends on: 001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "002"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── raw 추적 컬럼 3개 추가 ────────────────────────────────────
    op.add_column(
        "order_items",
        sa.Column(
            "raw_input_id",
            UUID(as_uuid=True),
            nullable=True,
            comment="OrderRawInput UUID. loose reference — FK 제약 없음. web_portal 직접 생성 시 NULL.",
        ),
    )
    op.add_column(
        "order_items",
        sa.Column(
            "source_row_index",
            sa.Integer,
            nullable=True,
            comment="원본 시트/파일 행 번호 (0-based). raw 경유 생성 시 채워넣음.",
        ),
    )
    op.add_column(
        "order_items",
        sa.Column(
            "item_index_in_row",
            sa.Integer,
            nullable=True,
            comment="같은 raw 행 내 아이템 순번 (0-based). 1 row → N items 분기 추적용.",
        ),
    )

    # raw_input_id 인덱스 — "이 raw_input에서 생성된 OrderItem 전체" 조회용
    op.create_index(
        "ix_order_items_raw_input_id",
        "order_items",
        ["raw_input_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_order_items_raw_input_id", table_name="order_items")
    op.drop_column("order_items", "item_index_in_row")
    op.drop_column("order_items", "source_row_index")
    op.drop_column("order_items", "raw_input_id")
