import redis.asyncio as redis
from app.core.config import settings
from typing import Optional

# Redis connection pool
redis_pool: Optional[redis.ConnectionPool] = None

async def init_redis():
    """Initialize Redis connection pool"""
    global redis_pool
    if redis_pool is None:
        redis_pool = redis.ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=20
        )

async def get_redis() -> redis.Redis:
    """Get Redis connection"""
    if redis_pool is None:
        await init_redis()
    return redis.Redis(connection_pool=redis_pool)

async def close_redis():
    """Close Redis connection pool"""
    global redis_pool
    if redis_pool:
        await redis_pool.disconnect()
        redis_pool = None