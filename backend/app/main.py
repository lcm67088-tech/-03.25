"""
PlaceOpt Backend — FastAPI Application Entry Point

Wave 1 라우터 목록:
  /api/v1/auth                    — 로그인·로그아웃·me
  /api/v1/users                   — 사용자 관리 (ADMIN 전용)
  /api/v1/places                  — Place CRUD + snapshot + review flow
  /api/v1/import-jobs             — GSheet/Excel import + retry
  /api/v1/orders                  — Order/OrderItem + from-raw + 상태전이 + 라우팅
  /api/v1/providers               — 실행처
  /api/v1/standard-product-types  — 표준 상품 유형
  /api/v1/sellable-offerings      — 판매 상품
  /api/v1/provider-offerings      — 실행처 상품
  /api/v1/mappings                — Sellable↔Provider 매핑
  /api/v1/agencies                — 대행사
  /api/v1/brands                  — 브랜드
  /api/v1/audit-logs              — 감사 로그
  /api/v1/dashboard               — 운영 요약 (Wave 1 호환 + Wave 2-A 확장)
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers.auth import router as auth_router
from app.routers.users import router as users_router
from app.routers.places import router as places_router
from app.routers.import_jobs import router as import_jobs_router
from app.routers.orders import router as orders_router
from app.routers.providers import (
    provider_router,
    spt_router,
    sellable_router,
    po_router,
    mapping_router,
    agency_router,
    brand_router,
)
from app.routers.order_items import router as order_items_router
from app.routers.audit import router as audit_router
from app.routers.dashboard import router as dashboard_router

settings = get_settings()

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="PlaceOpt Internal API",
    description=(
        "PlaceOpt 내부 운영 시스템 API\n\n"
        "**Wave 1 범위**: Place 파싱·검수, 주문 raw 저장, "
        "OrderItem 표준화, 기본 라우팅, 감사 로그\n\n"
        "**역할**: ADMIN | OPERATOR (Wave 1 확정)"
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 라우터 등록 ─────────────────────────────────────────────
# 인증
app.include_router(auth_router,         prefix=API_PREFIX,              tags=["auth"])
# 사용자
app.include_router(users_router,        prefix=f"{API_PREFIX}/users",   tags=["users"])
# Place
app.include_router(places_router,       prefix=f"{API_PREFIX}/places",  tags=["places"])
# Import jobs
app.include_router(import_jobs_router,  prefix=f"{API_PREFIX}/import-jobs", tags=["import-jobs"])
# Order 도메인
app.include_router(orders_router,       prefix=f"{API_PREFIX}/orders",  tags=["orders"])
app.include_router(order_items_router,  prefix=f"{API_PREFIX}/order-items", tags=["order-items"])
# Provider / Offering
app.include_router(provider_router,     prefix=API_PREFIX,              tags=["providers"])
app.include_router(spt_router,          prefix=API_PREFIX,              tags=["standard-product-types"])
app.include_router(sellable_router,     prefix=API_PREFIX,              tags=["sellable-offerings"])
app.include_router(po_router,           prefix=API_PREFIX,              tags=["provider-offerings"])
app.include_router(mapping_router,      prefix=API_PREFIX,              tags=["mappings"])
# Agency / Brand
app.include_router(agency_router,       prefix=API_PREFIX,              tags=["agencies"])
app.include_router(brand_router,        prefix=API_PREFIX,              tags=["brands"])
# Infra
app.include_router(audit_router,        prefix=API_PREFIX,              tags=["audit"])
app.include_router(dashboard_router,    prefix=f"{API_PREFIX}/dashboard", tags=["dashboard"])


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/", tags=["health"])
async def root():
    return {
        "app": "PlaceOpt Internal API",
        "version": "0.1.0",
        "docs": "/docs",
    }
