"""001 Initial Schema — PlaceOpt Wave 1

Revision ID: 001_initial_schema
Revises: (none)
Create Date: 2026-03-25

Wave 1 테이블 목록:
  인증/역할:       users
  대행사/브랜드:   agencies, brands (FK Wave 2 강제 예정)
  Provider:        providers, standard_product_types, sellable_offerings,
                   provider_offerings, sellable_provider_mappings
  Place 도메인:    places, place_raw_snapshots (INSERT 전용), place_review_logs (INSERT 전용)
  Order 도메인:    order_raw_inputs (INSERT 전용), orders, order_items,
                   order_item_status_histories (INSERT 전용)
  인프라:          import_jobs, audit_logs (INSERT 전용)

설계 원칙:
  - raw 계열 테이블은 INSERT 전용 원칙 (application-level 강제)
  - raw FK: SET NULL (고아 보존)
  - 이력 FK: RESTRICT (삭제 방지)
  - loose reference: import_job_id, result_order_id — FK 없음
  - JSONB: raw_data, spec_data, contact_info, error_detail, extra_data
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # ── users ──────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("hashed_pw", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="OPERATOR",
                  comment="Wave 1 확정: ADMIN | OPERATOR"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
        comment="내부 운영자 계정",
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])

    # ── agencies ───────────────────────────────────────────
    op.create_table(
        "agencies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        comment="대행사. Wave 1: 테이블 생성만. FK 강제는 Wave 2.",
    )

    # ── brands ─────────────────────────────────────────────
    op.create_table(
        "brands",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("agency_id", UUID(as_uuid=True), nullable=True,
                  comment="FK to agencies (nullable)"),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="SET NULL"),
        comment="브랜드. Wave 1: 테이블 생성만.",
    )

    # ── providers ──────────────────────────────────────────
    op.create_table(
        "providers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("provider_type", sa.String(50), nullable=True),
        sa.Column("contact_info", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        comment="실행처 (매체사 등).",
    )

    # ── standard_product_types ─────────────────────────────
    op.create_table(
        "standard_product_types",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("channel", sa.String(50), nullable=True),
        sa.Column("requires_period", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("requires_daily_qty", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("supports_subtype", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("code", name="uq_spt_code"),
        comment="[초안/제안안] 표준 상품 유형.",
    )

    # ── sellable_offerings ─────────────────────────────────
    op.create_table(
        "sellable_offerings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("standard_product_type_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("base_price", sa.Integer, nullable=True),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("spec_data", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["standard_product_type_id"],
                                ["standard_product_types.id"]),
        comment="고객 판매 상품.",
    )

    # ── provider_offerings ─────────────────────────────────
    op.create_table(
        "provider_offerings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("standard_product_type_id", UUID(as_uuid=True), nullable=False),
        sa.Column("provider_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("cost_price", sa.Integer, nullable=True),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("spec_data", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["standard_product_type_id"],
                                ["standard_product_types.id"]),
        sa.ForeignKeyConstraint(["provider_id"], ["providers.id"]),
        comment="실행처 실행 상품.",
    )

    # ── sellable_provider_mappings ─────────────────────────
    op.create_table(
        "sellable_provider_mappings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("sellable_offering_id", UUID(as_uuid=True), nullable=False),
        sa.Column("provider_offering_id", UUID(as_uuid=True), nullable=False),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column("routing_conditions", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["sellable_offering_id"], ["sellable_offerings.id"]),
        sa.ForeignKeyConstraint(["provider_offering_id"], ["provider_offerings.id"]),
        sa.UniqueConstraint("sellable_offering_id", "provider_offering_id",
                            name="uq_sellable_provider"),
        comment="SellableOffering:ProviderOffering = 1:N",
    )

    # ── places ─────────────────────────────────────────────
    op.create_table(
        "places",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("naver_place_id", sa.String(100), nullable=True),
        sa.Column("naver_place_url", sa.String(500), nullable=True),
        sa.Column("confirmed_name", sa.String(200), nullable=True),
        sa.Column("confirmed_category", sa.String(100), nullable=True),
        sa.Column("confirmed_address", sa.String(300), nullable=True),
        sa.Column("confirmed_phone", sa.String(50), nullable=True),
        sa.Column("agency_id", UUID(as_uuid=True), nullable=True),
        sa.Column("brand_id", UUID(as_uuid=True), nullable=True),
        sa.Column("agency_name_snapshot", sa.String(200), nullable=True),
        sa.Column("brand_name_snapshot", sa.String(200), nullable=True),
        sa.Column("review_status", sa.String(50), nullable=False,
                  server_default="pending_review"),
        sa.Column("reviewed_by", UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", UUID(as_uuid=True), nullable=True),
        sa.Column("operator_note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["deleted_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("naver_place_id", name="uq_places_naver_place_id"),
        comment="네이버 플레이스 확정 레코드",
    )
    op.create_index("ix_places_review_status", "places", ["review_status"])

    # ── place_raw_snapshots (INSERT 전용) ──────────────────
    op.create_table(
        "place_raw_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("place_id", UUID(as_uuid=True), nullable=True,
                  comment="SET NULL — 고아 보존"),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_ref", sa.String(500), nullable=True),
        sa.Column("import_job_id", UUID(as_uuid=True), nullable=True,
                  comment="loose reference — FK 없음"),
        sa.Column("raw_data", JSONB, nullable=False),
        sa.Column("is_processed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"], ondelete="SET NULL"),
        comment="Place 원본 스냅샷. INSERT 전용.",
    )

    # ── place_review_logs (INSERT 전용) ────────────────────
    op.create_table(
        "place_review_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("place_id", UUID(as_uuid=True), nullable=False,
                  comment="RESTRICT — 로그 있으면 Place 삭제 불가"),
        sa.Column("snapshot_id", UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("field_name", sa.String(100), nullable=True),
        sa.Column("before_value", sa.Text, nullable=True),
        sa.Column("after_value", sa.Text, nullable=True),
        sa.Column("actor_id", UUID(as_uuid=True), nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["place_raw_snapshots.id"],
                                ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        comment="Place 검수 이력. INSERT 전용.",
    )

    # ── import_jobs ────────────────────────────────────────
    op.create_table(
        "import_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False,
                  comment="google_sheet_import(1차)|excel_import(보조)"),
        sa.Column("job_type", sa.String(50), nullable=False,
                  comment="order_sheet_import|place_sheet_import"),
        sa.Column("source_url", sa.String(1000), nullable=True),
        sa.Column("source_sheet_name", sa.String(200), nullable=True),
        sa.Column("source_file_name", sa.String(500), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("total_rows", sa.Integer, nullable=True),
        sa.Column("processed_rows", sa.Integer, nullable=True),
        sa.Column("failed_rows", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("error_detail", JSONB, nullable=True),
        sa.Column("requested_by", UUID(as_uuid=True), nullable=True,
                  comment="loose reference — FK 없음"),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("parent_job_id", UUID(as_uuid=True), nullable=True,
                  comment="재시도 원본 UUID (loose reference)"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        comment="Google Sheet / Excel import 작업 추적",
    )
    op.create_index("ix_import_jobs_status", "import_jobs", ["status"])

    # ── order_raw_inputs (INSERT 전용) ─────────────────────
    op.create_table(
        "order_raw_inputs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False,
                  comment="google_sheet_import(1차)|excel_import(보조)|manual_input"),
        sa.Column("source_ref", sa.String(1000), nullable=True),
        sa.Column("source_sheet_name", sa.String(200), nullable=True),
        sa.Column("source_row_index", sa.Integer, nullable=True),
        sa.Column("import_job_id", UUID(as_uuid=True), nullable=True,
                  comment="loose reference — FK 없음"),
        sa.Column("raw_data", JSONB, nullable=False),
        sa.Column("is_processed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("process_error", sa.Text, nullable=True),
        sa.Column("result_order_id", UUID(as_uuid=True), nullable=True,
                  comment="loose reference — FK 없음"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        comment="주문 원본 입력. INSERT 전용.",
    )

    # ── orders ─────────────────────────────────────────────
    op.create_table(
        "orders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("agency_id", UUID(as_uuid=True), nullable=True),
        sa.Column("agency_name_snapshot", sa.String(200), nullable=True),
        sa.Column("sales_rep_name", sa.String(100), nullable=True),
        sa.Column("estimator_name", sa.String(100), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft"),
        sa.Column("raw_input_id", UUID(as_uuid=True), nullable=True),
        sa.Column("source_type", sa.String(50), nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", UUID(as_uuid=True), nullable=True),
        sa.Column("operator_note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["raw_input_id"], ["order_raw_inputs.id"],
                                ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["deleted_by"], ["users.id"], ondelete="SET NULL"),
        comment="주문 헤더.",
    )
    op.create_index("ix_orders_status", "orders", ["status"])

    # ── order_items ────────────────────────────────────────
    op.create_table(
        "order_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("order_id", UUID(as_uuid=True), nullable=False),
        sa.Column("standard_product_type_id", UUID(as_uuid=True), nullable=True),
        sa.Column("product_type_code", sa.String(100), nullable=True),
        sa.Column("product_subtype", sa.String(100), nullable=True),
        sa.Column("sellable_offering_id", UUID(as_uuid=True), nullable=True),
        sa.Column("place_id", UUID(as_uuid=True), nullable=True),
        sa.Column("place_name_snapshot", sa.String(200), nullable=True),
        sa.Column("place_url_snapshot", sa.String(500), nullable=True),
        sa.Column("naver_place_id_snapshot", sa.String(100), nullable=True),
        sa.Column("main_keyword", sa.String(200), nullable=True),
        sa.Column("keywords_raw", sa.Text, nullable=True),
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("total_qty", sa.Integer, nullable=True),
        sa.Column("daily_qty", sa.Integer, nullable=True),
        sa.Column("working_days", sa.Integer, nullable=True),
        sa.Column("unit_price", sa.Integer, nullable=True),
        sa.Column("total_amount", sa.Integer, nullable=True),
        sa.Column("spec_data", JSONB, nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="received",
                  comment="received|on_hold|reviewing|ready_to_route|assigned|"
                          "in_progress|done|confirmed|settlement_ready|closed|cancelled"),
        sa.Column("provider_id", UUID(as_uuid=True), nullable=True),
        sa.Column("provider_offering_id", UUID(as_uuid=True), nullable=True),
        sa.Column("routed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("routed_by", UUID(as_uuid=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", UUID(as_uuid=True), nullable=True),
        sa.Column("operator_note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["standard_product_type_id"],
                                ["standard_product_types.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sellable_offering_id"],
                                ["sellable_offerings.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["provider_id"], ["providers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["provider_offering_id"],
                                ["provider_offerings.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["routed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["deleted_by"], ["users.id"], ondelete="SET NULL"),
        comment="표준화 작업 단위. Wave 1: raw row 1:1.",
    )
    op.create_index("ix_order_items_status", "order_items", ["status"])
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])

    # ── order_item_status_histories (INSERT 전용) ──────────
    op.create_table(
        "order_item_status_histories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("order_item_id", UUID(as_uuid=True), nullable=False,
                  comment="RESTRICT"),
        sa.Column("from_status", sa.String(50), nullable=True),
        sa.Column("to_status", sa.String(50), nullable=False),
        sa.Column("changed_by", UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["order_item_id"], ["order_items.id"],
                                ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"], ondelete="SET NULL"),
        comment="OrderItem 상태 이력. INSERT 전용.",
    )

    # ── audit_logs (INSERT 전용) ───────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("actor_id", UUID(as_uuid=True), nullable=True,
                  comment="loose reference — FK 없음"),
        sa.Column("actor_role", sa.String(50), nullable=True),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("field_name", sa.String(100), nullable=True),
        sa.Column("before_value", sa.Text, nullable=True),
        sa.Column("after_value", sa.Text, nullable=True),
        sa.Column("extra_data", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        comment="주요 변경 이력. INSERT 전용.",
    )
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"])
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"])

    # ── updated_at 자동 갱신 트리거 ───────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    for tbl in [
        "users", "agencies", "brands", "providers",
        "standard_product_types", "sellable_offerings", "provider_offerings",
        "sellable_provider_mappings", "places", "import_jobs", "orders", "order_items",
    ]:
        op.execute(f"""
            CREATE TRIGGER trg_{tbl}_updated_at
            BEFORE UPDATE ON {tbl}
            FOR EACH ROW EXECUTE FUNCTION update_updated_at();
        """)

    # ── 초기 StandardProductType 데이터 (초안/제안안) ─────
    op.execute("""
        INSERT INTO standard_product_types
            (id, code, display_name, description, channel,
             requires_period, requires_daily_qty, supports_subtype, sort_order)
        VALUES
            (gen_random_uuid(), 'TRAFFIC', '리워드 트래픽',
             '네이버 플레이스 리워드 트래픽. 취합시트: 트래픽 취합.',
             'naver_place', true, true, false, 1),
            (gen_random_uuid(), 'SAVE', '리워드 저장하기',
             '네이버 플레이스 리워드 저장하기. 취합시트: 저장 취합.',
             'naver_place', true, true, false, 2),
            (gen_random_uuid(), 'AI_REAL', 'AI 실계정 프리미엄 배포',
             'AI 실계정 프리미엄 배포. 취합시트: AI(실계정) 프리미엄 배포 취합.',
             'naver_place', true, true, false, 3),
            (gen_random_uuid(), 'AI_NONREAL', 'AI 비실계 프리미엄 배포',
             'AI 비실계정 프리미엄 배포. 취합시트: AI(비실계) 프리미엄 접수 취합.',
             'naver_place', true, true, false, 4),
            (gen_random_uuid(), 'BLOG_REPORTER', '실계정 기자단',
             '실계정 블로그 기자단. 취합시트: 실계정 실리뷰어 기자단 취합.',
             'blog', true, false, false, 5),
            (gen_random_uuid(), 'BLOG_DISPATCH', '블로그 배포 (최블/엔비블)',
             'CHOEBL(최블)+NBBL(엔비블) 통합. product_subtype으로 구분. 취합시트: 최블엔비블 취합.',
             'blog', true, false, true, 6),
            (gen_random_uuid(), 'XIAOHONGSHU', '샤오홍슈 체험단',
             '중국 샤오홍슈 체험단. 취합시트: 샤오홍슈(접수) 취합.',
             'xiaohongshu', true, false, false, 7),
            (gen_random_uuid(), 'DIANPING', '따종디엔핑 등록',
             '중국 따종디엔핑 등록. 취합시트: 따종디엔핑(접수) 취합.',
             'dianping', false, false, false, 8)
        ON CONFLICT (code) DO NOTHING;
    """)


def downgrade() -> None:
    tables_to_drop = [
        "audit_logs",
        "order_item_status_histories",
        "order_items",
        "orders",
        "order_raw_inputs",
        "import_jobs",
        "place_review_logs",
        "place_raw_snapshots",
        "places",
        "sellable_provider_mappings",
        "provider_offerings",
        "sellable_offerings",
        "standard_product_types",
        "providers",
        "brands",
        "agencies",
        "users",
    ]
    for tbl in tables_to_drop:
        op.drop_table(tbl)
    op.execute("DROP FUNCTION IF EXISTS update_updated_at CASCADE")
