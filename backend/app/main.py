"""
PlaceOpt Backend — FastAPI Application Entry Point

Wave 1 엔드포인트 목록:
  POST   /api/v1/auth/login
  POST   /api/v1/auth/logout
  GET    /api/v1/auth/me
  CRUD   /api/v1/users              (ADMIN 전용)
  CRUD   /api/v1/places             (+ snapshot, review flow)
  POST   /api/v1/import-jobs        (Google Sheet import)
  GET/POST/PATCH/DELETE /api/v1/orders
  POST   /api/v1/orders/from-raw    (raw → OrderItem 표준화)
  CRUD   /api/v1/order-items        (+ status, assign, history)
  CRUD   /api/v1/providers
  GET    /api/v1/offerings/*        (standard-types, sellable, provider, mappings)
  GET    /api/v1/audit
  GET    /api/v1/dashboard
"""
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers

from app.routers import auth
from app.routers import users
from app.routers import places
from app.routers import import_jobs
from app.routers import orders
from app.routers import order_items
from app.routers import providers
from app.routers import offerings
from app.routers import audit
from app.routers import dashboard

logger = logging.getLogger(__name__)
settings = get_settings()

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행"""
    logger.info("PlaceOpt API starting up...")
    yield
    logger.info("PlaceOpt API shutting down...")


app = FastAPI(
    title="PlaceOpt Internal API",
    description=(
        "PlaceOpt 내부 운영 시스템 API\n\n"
        "**Wave 1 범위**: Place 파싱·검수, 주문 raw 저장, "
        "OrderItem 표준화, 기본 라우팅, 감사 로그"
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
app.include_router(auth.router, prefix=f"{API_PREFIX}/auth", tags=["인증"])
app.include_router(users.router, prefix=f"{API_PREFIX}/users", tags=["사용자"])
app.include_router(places.router, prefix=f"{API_PREFIX}/places", tags=["플레이스"])
app.include_router(import_jobs.router, prefix=f"{API_PREFIX}/import-jobs", tags=["임포트"])
app.include_router(orders.router, prefix=f"{API_PREFIX}/orders", tags=["주문"])
app.include_router(order_items.router, prefix=f"{API_PREFIX}/order-items", tags=["주문아이템"])
app.include_router(providers.router, prefix=f"{API_PREFIX}/providers", tags=["실행처"])
app.include_router(offerings.router, prefix=f"{API_PREFIX}/offerings", tags=["상품"])
app.include_router(audit.router, prefix=f"{API_PREFIX}/audit", tags=["감사로그"])
app.include_router(dashboard.router, prefix=f"{API_PREFIX}/dashboard", tags=["대시보드"])


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
