"""
backend/app/core/redis_client.py
Redis 连接管理
"""
import redis.asyncio as redis
from typing import Optional
from app.config import get_settings

settings = get_settings()
_redis: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis(
            host=settings.REDIS_HOST, port=settings.REDIS_PORT,
            db=settings.REDIS_DB, password=settings.REDIS_PASSWORD,
            decode_responses=True, max_connections=settings.REDIS_MAX_CONNECTIONS,
        )
    return _redis


async def close_redis():
    global _redis
    if _redis:
        await _redis.close()
        _redis = None
