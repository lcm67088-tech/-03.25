"""
Redis 클라이언트
JWT 블랙리스트, 캐시 용도
"""
from typing import Optional

import redis.asyncio as aioredis

from app.core.config import get_settings

settings = get_settings()

_redis_client: Optional[aioredis.Redis] = None


def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def blacklist_token(token: str, expire_seconds: int = 86400) -> None:
    """토큰을 블랙리스트에 추가 (로그아웃 처리)"""
    r = get_redis()
    await r.setex(f"blacklist:{token}", expire_seconds, "1")


async def is_token_blacklisted(token: str) -> bool:
    r = get_redis()
    result = await r.get(f"blacklist:{token}")
    return result is not None
