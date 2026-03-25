"""
데이터베이스 세션 관리
SQLAlchemy 2.0 async 방식 사용
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

# ── 비동기 엔진 ──────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,      # SQL 로그 (개발 환경)
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,       # 연결 유효성 체크
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ── 선언 기반 Base ───────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── 의존성 주입용 세션 제공자 ─────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── BackgroundTask용 세션 컨텍스트 매니저 ─────────────────────
@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    BackgroundTasks / 백그라운드 서비스에서 직접 사용하는 세션.
    FastAPI DI 외부에서 사용 시 이 함수 사용.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
