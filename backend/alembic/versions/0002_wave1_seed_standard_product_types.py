"""Wave 1 Seed — StandardProductType 초안 데이터 삽입

[초안/제안안] 취합 데이터 기반 제안. 확정본 아님.
코드: TRAFFIC | SAVE | AI_REAL | AI_NONREAL | BLOG_REPORTER | BLOG_DISPATCH | XIAOHONGSHU | DIANPING

BLOG_DISPATCH: CHOEBL(최블) + NBBL(엔비블) 통합. product_subtype으로 구분.
receipt 유형 제외 (현재 운영에서 제외).

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

SEED_TYPES = [
    {
        "code": "TRAFFIC",
        "display_name": "트래픽 (네이버 플레이스 검색)",
        "description": "네이버 플레이스 키워드 트래픽 유입. 일 수량 기반.",
        "channel": "naver_place",
        "requires_period": True,
        "requires_daily_qty": True,
        "supports_subtype": False,
        "sort_order": 10,
    },
    {
        "code": "SAVE",
        "display_name": "저장 (네이버 플레이스 저장)",
        "description": "네이버 플레이스 저장하기 유입. 일 수량 기반.",
        "channel": "naver_place",
        "requires_period": True,
        "requires_daily_qty": True,
        "supports_subtype": False,
        "sort_order": 20,
    },
    {
        "code": "AI_REAL",
        "display_name": "AI 실계정 프리미엄 배포",
        "description": "실 계정 기반 AI 블로그 프리미엄 배포.",
        "channel": "blog",
        "requires_period": False,
        "requires_daily_qty": False,
        "supports_subtype": False,
        "sort_order": 30,
    },
    {
        "code": "AI_NONREAL",
        "display_name": "AI 비실계정 프리미엄 배포",
        "description": "비실 계정 기반 AI 블로그 프리미엄 배포.",
        "channel": "blog",
        "requires_period": False,
        "requires_daily_qty": False,
        "supports_subtype": False,
        "sort_order": 40,
    },
    {
        "code": "BLOG_REPORTER",
        "display_name": "실리뷰어 기자단",
        "description": "실 리뷰어 기자단 블로그 리뷰 배포.",
        "channel": "blog",
        "requires_period": False,
        "requires_daily_qty": False,
        "supports_subtype": False,
        "sort_order": 50,
    },
    {
        "code": "BLOG_DISPATCH",
        "display_name": "블로그 배포 (최블/엔비블 통합)",
        "description": (
            "최블(CHOEBL)과 엔비블(NBBL)을 통합한 표준 유형. "
            "product_subtype 필드로 구분: choebl | nbbl. "
            "[가정: 운영 증거 없으면 통합 유지]"
        ),
        "channel": "blog",
        "requires_period": False,
        "requires_daily_qty": False,
        "supports_subtype": True,   # product_subtype: choebl | nbbl
        "sort_order": 60,
    },
    {
        "code": "XIAOHONGSHU",
        "display_name": "샤오홍슈 (小红书)",
        "description": "샤오홍슈 플랫폼 배포.",
        "channel": "xiaohongshu",
        "requires_period": False,
        "requires_daily_qty": False,
        "supports_subtype": False,
        "sort_order": 70,
    },
    {
        "code": "DIANPING",
        "display_name": "따종디엔핑 (大众点评)",
        "description": "따종디엔핑 플랫폼 배포.",
        "channel": "dianping",
        "requires_period": False,
        "requires_daily_qty": False,
        "supports_subtype": False,
        "sort_order": 80,
    },
]


def upgrade() -> None:
    bind = op.get_bind()
    for item in SEED_TYPES:
        bind.execute(
            sa.text(
                """
                INSERT INTO standard_product_types
                    (id, code, display_name, description, channel,
                     requires_period, requires_daily_qty, supports_subtype,
                     is_active, sort_order, created_at, updated_at)
                VALUES
                    (gen_random_uuid(), :code, :display_name, :description, :channel,
                     :requires_period, :requires_daily_qty, :supports_subtype,
                     true, :sort_order, now(), now())
                ON CONFLICT (code) DO NOTHING
                """
            ),
            item,
        )


def downgrade() -> None:
    bind = op.get_bind()
    codes = [item["code"] for item in SEED_TYPES]
    bind.execute(
        sa.text(
            "DELETE FROM standard_product_types WHERE code = ANY(:codes)"
        ),
        {"codes": codes},
    )
