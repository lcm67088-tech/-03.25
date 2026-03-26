"""
애플리케이션 설정
pydantic-settings 기반 환경변수 로딩
"""
from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ─────────────────────────────────
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True

    # ── Security ────────────────────────────
    SECRET_KEY: str = "CHANGE_ME_32_CHARS_MINIMUM_FOR_PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24시간

    # ── Database ────────────────────────────
    DATABASE_URL: str = (
        "postgresql+asyncpg://placeopt:password@localhost:5432/placeopt_db"
    )
    DATABASE_URL_SYNC: str = (
        "postgresql+psycopg2://placeopt:password@localhost:5432/placeopt_db"
    )

    # ── Redis ───────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Google Sheets ────────────────────────
    GOOGLE_SERVICE_ACCOUNT_JSON_PATH: str = "./credentials/google_service_account.json"

    # ── CORS ─────────────────────────────────────────────────────────────────
    # 환경별로 .env 파일의 CORS_ORIGINS를 쉼표 구분 문자열로 설정
    #
    # 로컬 개발 (.env):
    #   CORS_ORIGINS=http://localhost:5173,http://localhost:3000
    #
    # 스테이징 (.env.staging 또는 서버 환경변수):
    #   CORS_ORIGINS=https://staging-ops.papainite.co.kr,http://localhost:5173
    #
    # 운영 (.env.production):
    #   CORS_ORIGINS=https://ops.papainite.co.kr
    # ─────────────────────────────────────────────────────────────────────────
    CORS_ORIGINS: str = (
        "http://localhost:3000,"
        "http://localhost:3001,"
        "http://localhost:8080,"
        "http://localhost:5173,"
        "http://localhost:5174,"
        # 스테이징 프론트엔드
        "https://staging-ops.papainite.co.kr,"
        # 운영 프론트엔드 (추후)
        "https://ops.papainite.co.kr"
    )

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_set(cls, v: str) -> str:
        if v.startswith("CHANGE_ME"):
            import warnings
            warnings.warn(
                "SECRET_KEY is using default value. "
                "Set a proper secret key in production.",
                stacklevel=2,
            )
        return v

    def get_cors_origins(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
