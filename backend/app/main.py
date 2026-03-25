"""
PlaceOpt Backend — FastAPI Application Entry Point

Wave 1 엔드포인트 목록:
  POST   /api/v1/auth/login         — JWT 발급
  POST   /api/v1/auth/logout        — 로그아웃
  GET    /api/v1/auth/me            — 현재 사용자 정보
  CRUD   /api/v1/users              — 사용자 관리 (ADMIN 전용)
  CRUD   /api/v1/places             — Place CRUD + snapshot + review flow
  POST   /api/v1/import-jobs        — Google Sheet import 요청
  GET/POST /api/v1/orders           — 주문 관리
  POST   /api/v1/orders/from-raw    — raw → OrderItem 표준화 (핵심)
  GET    /api/v1/orders/raw-inputs  — 원본 입력 조회
  CRUD   /api/v1/order-items        — OrderItem CRUD + status + assign + history
  CRUD   /api/v1/providers          — 실행처 관리
  GET    /api/v1/offerings/*        — 상품 구조 (standard-types, sellable, provider, mappings)
  GET    /api/v1/audit              — 감사 로그 (ADMIN)
  GET    /api/v1/dashboard          — 운영 현황 요약
  GET    /health                    — 헬스체크
"""
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers

# ── 라우터 임포트 ─────────────────────────────────────────────
from app.routers.auth import router as auth_router
from app.routers.users import router as users_router
from app.routers.places import router as places_router
from app.routers.import_jobs import router as import_jobs_router
from app.routers.orders import router as orders_router
from app.routers.order_items import router as order_items_router
from app.routers.providers import router as providers_router
from app.routers.offerings import router as offerings_router
from app.routers.audit import router as audit_router
from app.routers.dashboard import router as dashboard_router

logger = logging.getLogger(__name__)
settings = get_settings()

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행"""
    logger.info("PlaceOpt API starting up... (Wave 1)")
    yield
    logger.info("PlaceOpt API shutting down...")


app = FastAPI(
    title="PlaceOpt Internal API",
    description=(
        "PlaceOpt 내부 운영 시스템 API\n\n"
        "**Wave 1 범위**: Place 파싱·검수, 주문 Google Sheet 임포트 및 raw 저장, "
        "OrderItem 표준화·상태 추적, 기본 라우팅, 감사 로그"
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 요청 ID 미들웨어 ─────────────────────────────────────────
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ── 예외 핸들러 ──────────────────────────────────────────────
register_exception_handlers(app)

# ── 라우터 등록 ──────────────────────────────────────────────
app.include_router(auth_router,         prefix=f"{API_PREFIX}/auth",         tags=["인증"])
app.include_router(users_router,        prefix=f"{API_PREFIX}/users",        tags=["사용자"])
app.include_router(places_router,       prefix=f"{API_PREFIX}/places",       tags=["플레이스"])
app.include_router(import_jobs_router,  prefix=f"{API_PREFIX}/import-jobs",  tags=["임포트"])
app.include_router(orders_router,       prefix=f"{API_PREFIX}/orders",       tags=["주문"])
app.include_router(order_items_router,  prefix=f"{API_PREFIX}/order-items",  tags=["주문아이템"])
app.include_router(providers_router,    prefix=f"{API_PREFIX}/providers",    tags=["실행처"])
app.include_router(offerings_router,    prefix=f"{API_PREFIX}/offerings",    tags=["상품"])
app.include_router(audit_router,        prefix=f"{API_PREFIX}/audit",        tags=["감사로그"])
app.include_router(dashboard_router,    prefix=f"{API_PREFIX}/dashboard",    tags=["대시보드"])


# ── 헬스체크 ─────────────────────────────────────────────────
@app.get("/health", tags=["시스템"])
async def health_check():
    return {"status": "ok", "version": "0.1.0", "env": settings.APP_ENV}


@app.get("/", tags=["시스템"])
async def root():
    return {
        "app": "PlaceOpt Internal API",
        "version": "0.1.0",
        "docs": "/docs",
    }
