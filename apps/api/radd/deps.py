from functools import lru_cache

import redis.asyncio as aioredis
from qdrant_client import AsyncQdrantClient

from radd.config import settings


@lru_cache
def get_redis() -> aioredis.Redis:
    return aioredis.from_url(settings.redis_url, decode_responses=True)


@lru_cache
def get_qdrant() -> AsyncQdrantClient:
    return AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
    )


async def check_db_health() -> bool:
    from sqlalchemy import text
    from radd.db.base import engine
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def check_redis_health() -> bool:
    try:
        r = get_redis()
        await r.ping()
        return True
    except Exception:
        return False


async def check_qdrant_health() -> bool:
    try:
        client = get_qdrant()
        await client.get_collections()
        return True
    except Exception:
        return False
