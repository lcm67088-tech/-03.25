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

    # ── CORS ────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001,http://localhost:8080,http://localhost:5173,http://localhost:5174"

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_set(cls, v: str) -> str:
        if v.startswith("CHANGE_ME") and True:
            # 개발 환경에서는 경고만 출력
            import warnings
            warnings.warn(
                "SECRET_KEY is using default value. "
                "Set a proper secret key in production.",
                stacklevel=2,
            )
        return v

    def get_cors_origins(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
