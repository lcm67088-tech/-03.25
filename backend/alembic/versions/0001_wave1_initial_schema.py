"""Wave 1 Initial Schema — 17 tables

Revision ID: 0001_wave1_initial
Revises:
Create Date: 2026-03-25

테이블 목록 (생성 순서 — FK 의존성 고려):
 1. users
 2. agencies
 3. brands
 4. places
 5. place_raw_snapshots
 6. place_review_logs
 7. providers
 8. standard_product_types
 9. sellable_offerings
10. provider_offerings
11. sellable_provider_mappings
12. order_raw_inputs
13. orders
14. order_items
15. order_item_status_histories
16. import_jobs
17. audit_logs

설계 원칙:
- *_raw_*, *_logs, *_histories: CASCADE DELETE 금지
  place_raw_snapshots: ON DELETE SET NULL (부모 삭제 허용, 고아 보존)
  place_review_logs:   ON DELETE RESTRICT
  order_raw_inputs:    INSERT 전용, 삭제 금지 (FK 없음)
  order_item_status_histories: ON DELETE RESTRICT
- places, orders, order_items: 소프트 삭제 (is_deleted + deleted_at)
- import_job_id, raw_input_id 등 일부 UUID 컬럼: Loose reference (FK 없음)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "0001_wave1_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. users ──────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(300), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("hashed_pw", sa.String(300), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="OPERATOR",
                  comment="ADMIN | OPERATOR (Wave 1). VIEWER 추후 추가."),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        comment="운영자 계정. Wave 1 역할: ADMIN | OPERATOR",
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── 2. agencies ───────────────────────────────────────────────
    op.create_table(
        "agencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        comment="대행사. Wave 1: optional. Wave 2 이후 FK 강제 운영.",
    )

    # ── 3. brands ────────────────────────────────────────────────
    op.create_table(
        "brands",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(
            ["agency_id"], ["agencies.id"], ondelete="SET NULL",
            name="fk_brands_agency_id"
        ),
        comment="브랜드. Wave 1: optional FK. Wave 2 이후 강제.",
    )

    # ── 4. places ─────────────────────────────────────────────────
    op.create_table(
        "places",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("naver_place_id", sa.String(100), nullable=True, unique=True),
        sa.Column("naver_place_url", sa.String(500), nullable=True),
        sa.Column("confirmed_name", sa.String(200), nullable=True),
        sa.Column("confirmed_category", sa.String(100), nullable=True),
        sa.Column("confirmed_address", sa.String(300), nullable=True),
        sa.Column("confirmed_phone", sa.String(50), nullable=True),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("agency_name_snapshot", sa.String(200), nullable=True),
        sa.Column("brand_name_snapshot", sa.String(200), nullable=True),
        sa.Column("review_status", sa.String(50), nullable=False,
                  server_default="pending_review",
                  comment="pending_review | in_review | confirmed | rejected"),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("operator_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="SET NULL",
                                name="fk_places_agency_id"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="SET NULL",
                                name="fk_places_brand_id"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL",
                                name="fk_places_reviewed_by"),
        sa.ForeignKeyConstraint(["deleted_by"], ["users.id"], ondelete="SET NULL",
                                name="fk_places_deleted_by"),
        comment="네이버 플레이스 확정 레코드. 소프트 삭제.",
    )
    op.create_index("ix_places_naver_place_id", "places", ["naver_place_id"])
    op.create_index("ix_places_review_status", "places", ["review_status"])

    # ── 5. place_raw_snapshots ────────────────────────────────────
    op.create_table(
        "place_raw_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("place_id", postgresql.UUID(as_uuid=True), nullable=True,
                  comment="연결된 Place FK (SET NULL — 부모 삭제 후 고아 보존)"),
        # import_job_id: Loose reference — FK 없음
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True), nullable=True,
                  comment="ImportJob UUID (loose reference, FK 없음 — 고아 허용)"),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_ref", sa.String(500), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(), nullable=False,
                  comment="원본 파싱 결과. 구조 고정 없음."),
        sa.Column("is_processed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(
            ["place_id"], ["places.id"], ondelete="SET NULL",
            name="fk_place_raw_snapshots_place_id",
            comment="SET NULL: 부모 삭제 허용, 고아 스냅샷 보존",
        ),
        comment="Place 원본 스냅샷. INSERT 전용. UPDATE/DELETE 금지.",
    )
    op.create_index("ix_place_raw_snapshots_place_id", "place_raw_snapshots", ["place_id"])

    # ── 6. place_review_logs ─────────────────────────────────────
    op.create_table(
        "place_review_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("place_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(50), nullable=False,
                  comment="field_edited | status_changed | confirmed | rejected | note_added"),
        sa.Column("field_name", sa.String(100), nullable=True),
        sa.Column("before_value", sa.Text(), nullable=True),
        sa.Column("after_value", sa.Text(), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(
            ["place_id"], ["places.id"], ondelete="RESTRICT",
            name="fk_place_review_logs_place_id",
            comment="RESTRICT: 로그 있으면 Place 삭제 불가",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["place_raw_snapshots.id"], ondelete="SET NULL",
            name="fk_place_review_logs_snapshot_id",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], ondelete="SET NULL",
            name="fk_place_review_logs_actor_id",
        ),
        comment="Place 검수 이력. INSERT 전용. RESTRICT 삭제.",
    )
    op.create_index("ix_place_review_logs_place_id", "place_review_logs", ["place_id"])

    # ── 7. providers ──────────────────────────────────────────────
    op.create_table(
        "providers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("provider_type", sa.String(50), nullable=True,
                  comment="media_company | individual | internal [가정: 미확정]"),
        sa.Column("contact_info", postgresql.JSONB(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        comment="실행처 (매체사 등). 취합 시트 매체사 컬럼 대응.",
    )

    # ── 8. standard_product_types ─────────────────────────────────
    op.create_table(
        "standard_product_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("code", sa.String(100), nullable=False, unique=True,
                  comment="[초안] TRAFFIC|SAVE|AI_REAL|AI_NONREAL|BLOG_REPORTER|BLOG_DISPATCH|XIAOHONGSHU|DIANPING"),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("channel", sa.String(50), nullable=True,
                  comment="naver_place | blog | xiaohongshu | dianping [가정]"),
        sa.Column("requires_period", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("requires_daily_qty", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("supports_subtype", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        comment="[초안/제안안] 표준 상품 유형. 확정본 아님.",
    )
    op.create_index("ix_standard_product_types_code", "standard_product_types", ["code"], unique=True)

    # ── 9. sellable_offerings ─────────────────────────────────────
    op.create_table(
        "sellable_offerings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("standard_product_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("base_price", sa.Integer(), nullable=True),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("spec_data", postgresql.JSONB(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(
            ["standard_product_type_id"], ["standard_product_types.id"],
            name="fk_sellable_offerings_spt_id",
        ),
        comment="고객 판매 상품. 판매 구조 축.",
    )
    op.create_index("ix_sellable_offerings_spt", "sellable_offerings", ["standard_product_type_id"])

    # ── 10. provider_offerings ────────────────────────────────────
    op.create_table(
        "provider_offerings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("standard_product_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("cost_price", sa.Integer(), nullable=True),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("spec_data", postgresql.JSONB(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(
            ["standard_product_type_id"], ["standard_product_types.id"],
            name="fk_provider_offerings_spt_id",
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"], ["providers.id"],
            name="fk_provider_offerings_provider_id",
        ),
        comment="실행처 실행 상품. 실행 구조 축.",
    )
    op.create_index("ix_provider_offerings_provider", "provider_offerings", ["provider_id"])

    # ── 11. sellable_provider_mappings ────────────────────────────
    op.create_table(
        "sellable_provider_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("sellable_offering_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_offering_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("routing_conditions", postgresql.JSONB(), nullable=True,
                  comment="[가정] 라우팅 조건 미확정 → JSONB"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(
            ["sellable_offering_id"], ["sellable_offerings.id"],
            name="fk_spm_sellable_offering_id",
        ),
        sa.ForeignKeyConstraint(
            ["provider_offering_id"], ["provider_offerings.id"],
            name="fk_spm_provider_offering_id",
        ),
        sa.UniqueConstraint(
            "sellable_offering_id", "provider_offering_id",
            name="uq_sellable_provider",
        ),
        comment="SellableOffering:ProviderOffering = 1:N 연결",
    )

    # ── 12. order_raw_inputs ──────────────────────────────────────
    op.create_table(
        "order_raw_inputs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        # Loose references — FK 없음
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True), nullable=True,
                  comment="ImportJob UUID (loose reference, FK 없음 — 고아 허용)"),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_ref", sa.String(500), nullable=True),
        sa.Column("sheet_name", sa.String(200), nullable=True),
        sa.Column("row_index", sa.Integer(), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(), nullable=False),
        sa.Column("is_processed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("process_error", sa.Text(), nullable=True),
        # Loose reference — FK 없음
        sa.Column("result_order_id", postgresql.UUID(as_uuid=True), nullable=True,
                  comment="생성된 Order UUID (loose reference, FK 없음)"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        comment="원본 주문 행. INSERT 전용. UPDATE/DELETE 금지.",
    )
    op.create_index("ix_order_raw_inputs_import_job_id", "order_raw_inputs", ["import_job_id"])

    # ── 13. orders ────────────────────────────────────────────────
    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("agency_name_snapshot", sa.String(200), nullable=True),
        sa.Column("sales_manager_snapshot", sa.String(100), nullable=True),
        sa.Column("quote_manager_snapshot", sa.String(100), nullable=True),
        # Loose reference — FK 없음
        sa.Column("raw_input_id", postgresql.UUID(as_uuid=True), nullable=True,
                  comment="원본 OrderRawInput UUID (loose reference, FK 없음)"),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft",
                  comment="draft | confirmed | cancelled | closed"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("extra_data", postgresql.JSONB(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="SET NULL",
                                name="fk_orders_agency_id"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL",
                                name="fk_orders_created_by"),
        comment="주문 헤더. 상태 추적은 OrderItem 레벨에서.",
    )
    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_index("ix_orders_agency_id", "orders", ["agency_id"])

    # ── 14. order_items ───────────────────────────────────────────
    op.create_table(
        "order_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Loose references — FK 없음
        sa.Column("raw_input_id", postgresql.UUID(as_uuid=True), nullable=True,
                  comment="원본 OrderRawInput UUID (loose reference)"),
        sa.Column("raw_row_index", sa.Integer(), nullable=True),
        sa.Column("item_index_in_row", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sellable_offering_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider_offering_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("place_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("product_type_snapshot", sa.String(100), nullable=True),
        sa.Column("product_subtype", sa.String(100), nullable=True),
        sa.Column("place_name_snapshot", sa.String(200), nullable=True),
        sa.Column("keyword_snapshot", sa.String(500), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("total_qty", sa.Integer(), nullable=True),
        sa.Column("daily_qty", sa.Integer(), nullable=True),
        sa.Column("unit_price_snapshot", sa.Integer(), nullable=True),
        sa.Column("total_amount_snapshot", sa.Integer(), nullable=True),
        sa.Column("spec_data", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="received",
                  comment="received|on_hold|reviewing|ready_to_route|assigned|in_progress|done|confirmed|settlement_ready|closed|cancelled"),
        sa.Column("status_note", sa.Text(), nullable=True),
        sa.Column("assigned_provider_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("operator_note", sa.Text(), nullable=True),
        sa.Column("extra_data", postgresql.JSONB(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"],
                                name="fk_order_items_order_id"),
        sa.ForeignKeyConstraint(["sellable_offering_id"], ["sellable_offerings.id"],
                                ondelete="SET NULL", name="fk_order_items_sellable_offering_id"),
        sa.ForeignKeyConstraint(["provider_offering_id"], ["provider_offerings.id"],
                                ondelete="SET NULL", name="fk_order_items_provider_offering_id"),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"],
                                ondelete="SET NULL", name="fk_order_items_place_id"),
        sa.ForeignKeyConstraint(["assigned_provider_id"], ["providers.id"],
                                ondelete="SET NULL", name="fk_order_items_assigned_provider_id"),
        sa.ForeignKeyConstraint(["assigned_by"], ["users.id"],
                                ondelete="SET NULL", name="fk_order_items_assigned_by"),
        comment="주문 아이템. 실제 상태 추적·라우팅·정산 단위.",
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])
    op.create_index("ix_order_items_status", "order_items", ["status"])
    op.create_index("ix_order_items_place_id", "order_items", ["place_id"])
    op.create_index("ix_order_items_assigned_provider", "order_items", ["assigned_provider_id"])

    # ── 15. order_item_status_histories ───────────────────────────
    op.create_table(
        "order_item_status_histories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("order_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_status", sa.String(50), nullable=True),
        sa.Column("to_status", sa.String(50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("extra_data", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(
            ["order_item_id"], ["order_items.id"], ondelete="RESTRICT",
            name="fk_oi_status_histories_order_item_id",
            comment="RESTRICT: 이력 있으면 OrderItem 삭제 불가 (소프트 삭제 사용)",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], ondelete="SET NULL",
            name="fk_oi_status_histories_actor_id",
        ),
        comment="OrderItem 상태 이력. INSERT 전용. RESTRICT 삭제.",
    )
    op.create_index("ix_oi_status_histories_item_id", "order_item_status_histories", ["order_item_id"])

    # ── 16. import_jobs ───────────────────────────────────────────
    op.create_table(
        "import_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("job_type", sa.String(50), nullable=False,
                  comment="google_sheet_import | excel_import | manual_input"),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending",
                  comment="pending | running | done | partial_error | failed"),
        sa.Column("source_url", sa.String(1000), nullable=True),
        sa.Column("source_filename", sa.String(300), nullable=True),
        sa.Column("target_domain", sa.String(50), nullable=False,
                  comment="place | order"),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_log", postgresql.JSONB(), nullable=True),
        sa.Column("extra_meta", postgresql.JSONB(), nullable=True),
        # Loose reference — FK 없음
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True,
                  comment="실행 운영자 UUID (loose reference, FK 없음)"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        comment="Google Sheet / Excel 임포트 작업 추적",
    )
    op.create_index("ix_import_jobs_status", "import_jobs", ["status"])

    # ── 17. audit_logs ────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        # Loose references — FK 없음 (탈퇴 후에도 로그 보존)
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True,
                  comment="액션 수행자 UUID (loose reference)"),
        sa.Column("actor_role", sa.String(50), nullable=True),
        sa.Column("actor_email_snapshot", sa.String(300), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("domain", sa.String(50), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True,
                  comment="대상 레코드 UUID (loose reference)"),
        sa.Column("target_type", sa.String(100), nullable=True),
        sa.Column("before_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("after_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(100), nullable=True),
        sa.Column("ip_address", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        comment="전 도메인 액션 불변 기록. INSERT 전용.",
    )
    op.create_index("ix_audit_logs_domain", "audit_logs", ["domain"])
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_target_id", "audit_logs", ["target_id"])


def downgrade() -> None:
    """역순으로 테이블 삭제 (FK 의존성 역방향)"""
    op.drop_table("audit_logs")
    op.drop_table("import_jobs")
    op.drop_table("order_item_status_histories")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("order_raw_inputs")
    op.drop_table("sellable_provider_mappings")
    op.drop_table("provider_offerings")
    op.drop_table("sellable_offerings")
    op.drop_table("standard_product_types")
    op.drop_table("providers")
    op.drop_table("place_review_logs")
    op.drop_table("place_raw_snapshots")
    op.drop_table("places")
    op.drop_table("brands")
    op.drop_table("agencies")
    op.drop_table("users")
