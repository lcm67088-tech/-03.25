"""
초기 시드 데이터 — Wave 1 개발/테스트용

실행: python seed.py
(DB가 마이그레이션된 상태에서 실행)
"""
import asyncio
import sys
import os

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models import (
    User, Agency, Brand, Provider,
    StandardProductType, SellableOffering, ProviderOffering,
    SellableProviderMapping,
)


async def seed():
    async with AsyncSessionLocal() as db:
        # ── 1. 기본 사용자 생성 ────────────────────────────────
        admin = User(
            email="admin@placeopt.internal",
            name="시스템 관리자",
            hashed_pw=hash_password("Admin1234!"),
            role="ADMIN",
        )
        operator = User(
            email="operator@placeopt.internal",
            name="운영자1",
            hashed_pw=hash_password("Oper1234!"),
            role="OPERATOR",
        )
        db.add_all([admin, operator])
        await db.flush()
        print(f"✅ Users: admin={admin.id}, operator={operator.id}")

        # ── 2. 대행사 샘플 ────────────────────────────────────
        agencies = [
            Agency(name="스마트마케팅", note="샘플 대행사"),
            Agency(name="에그애드", note="샘플 대행사"),
            Agency(name="강원브리에이션", note="샘플 대행사"),
        ]
        db.add_all(agencies)
        await db.flush()
        print(f"✅ Agencies: {[a.name for a in agencies]}")

        # ── 3. 실행처 (매체사) 샘플 ───────────────────────────
        providers = [
            Provider(name="피크", provider_type="media_company"),
            Provider(name="NNW", provider_type="media_company"),
            Provider(name="더블유엔터", provider_type="media_company"),
            Provider(name="내부팀", provider_type="internal"),
        ]
        db.add_all(providers)
        await db.flush()
        print(f"✅ Providers: {[p.name for p in providers]}")

        # ── 4. StandardProductType [초안/제안안] ──────────────
        product_types_data = [
            dict(code="TRAFFIC", display_name="트래픽", channel="naver_place",
                 requires_period=True, requires_daily_qty=True, sort_order=1),
            dict(code="SAVE", display_name="저장", channel="naver_place",
                 requires_period=True, requires_daily_qty=True, sort_order=2),
            dict(code="AI_REAL", display_name="AI 실계정", channel="naver_place",
                 requires_period=True, requires_daily_qty=True, sort_order=3),
            dict(code="AI_NONREAL", display_name="AI 비실계", channel="naver_place",
                 requires_period=True, requires_daily_qty=True, sort_order=4),
            dict(code="BLOG_REPORTER", display_name="기자단/실리뷰어", channel="blog",
                 requires_period=False, requires_daily_qty=False, sort_order=5),
            dict(code="BLOG_DISPATCH", display_name="블로그배포(최블/엔비블)", channel="blog",
                 requires_period=False, requires_daily_qty=False,
                 supports_subtype=True, sort_order=6),
            dict(code="XIAOHONGSHU", display_name="샤오홍슈", channel="xiaohongshu",
                 requires_period=False, requires_daily_qty=False, sort_order=7),
            dict(code="DIANPING", display_name="따종디엔핑", channel="dianping",
                 requires_period=False, requires_daily_qty=False, sort_order=8),
        ]
        spt_list = [StandardProductType(**d) for d in product_types_data]
        db.add_all(spt_list)
        await db.flush()
        print(f"✅ StandardProductTypes: {[s.code for s in spt_list]}")

        # ── 5. SellableOffering 샘플 ──────────────────────────
        traffic_spt = next(s for s in spt_list if s.code == "TRAFFIC")
        save_spt = next(s for s in spt_list if s.code == "SAVE")

        sellable_list = [
            SellableOffering(
                standard_product_type_id=traffic_spt.id,
                name="트래픽 기본형",
                unit="일",
                spec_data={"channel": "naver_place"},
            ),
            SellableOffering(
                standard_product_type_id=save_spt.id,
                name="저장 기본형",
                unit="일",
                spec_data={"channel": "naver_place"},
            ),
        ]
        db.add_all(sellable_list)
        await db.flush()
        print(f"✅ SellableOfferings: {[s.name for s in sellable_list]}")

        # ── 6. ProviderOffering 샘플 ──────────────────────────
        peak = next(p for p in providers if p.name == "피크")

        provider_offering = ProviderOffering(
            standard_product_type_id=traffic_spt.id,
            provider_id=peak.id,
            name="피크 트래픽",
            spec_data={"provider": "피크"},
        )
        db.add(provider_offering)
        await db.flush()

        # 매핑
        mapping = SellableProviderMapping(
            sellable_offering_id=sellable_list[0].id,
            provider_offering_id=provider_offering.id,
            is_default=True,
            priority=0,
        )
        db.add(mapping)
        await db.flush()
        print("✅ SellableProviderMapping 생성 완료")

        await db.commit()
        print("\n🎉 시드 데이터 삽입 완료!")
        print(f"   admin: admin@placeopt.internal / Admin1234!")
        print(f"   operator: operator@placeopt.internal / Oper1234!")


if __name__ == "__main__":
    asyncio.run(seed())
