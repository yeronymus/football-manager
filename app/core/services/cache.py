import json
import logging
from typing import Any, Optional
import redis.asyncio as aioredis
from app.config import settings

logger = logging.getLogger(__name__)


class RedisCacheService:
    """
    Look-aside Passive Caching Service isolated onto dedicated Redis logical DB (REDIS_CACHE_DB).
    Ensures cache operations can never interfere with FSM states or scheduled jobs.
    """

    def __init__(self):
        self.redis_url = settings.REDIS_CACHE_URL
        self._client: Optional[aioredis.Redis] = None
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def _get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client

    async def ping(self) -> bool:
        client = self._get_client()
        return bool(await client.ping())

    async def get(self, key: str) -> Optional[Any]:
        """Passive Cache: retrieve deserialized JSON value."""
        try:
            client = self._get_client()
            data = await client.get(key)
            if data:
                self.hits += 1
                logger.debug(f"Cache Hit for key: {key}")
                return json.loads(data)
            self.misses += 1
            logger.debug(f"Cache Miss for key: {key}")
            return None
        except Exception as e:
            logger.warning(f"Failed to read from cache for key {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Passive Cache: save serialized JSON value with a TTL."""
        try:
            client = self._get_client()
            serialized = json.dumps(value)
            await client.set(key, serialized, ex=ttl)
            logger.debug(f"Cache Set for key: {key} (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.warning(f"Failed to write to cache for key {key}: {e}")
            return False

    async def evict(self, key: str) -> bool:
        """Eviction / Invalidation: remove key from cache."""
        try:
            client = self._get_client()
            deleted = await client.delete(key)
            if deleted:
                self.evictions += 1
                logger.debug(f"Cache Evicted key: {key}")
                return True
            return False
        except Exception as e:
            logger.warning(f"Failed to evict key {key}: {e}")
            return False

    async def evict_all(self) -> bool:
        """Flushes ONLY the dedicated cache logical DB (REDIS_CACHE_DB)."""
        try:
            client = self._get_client()
            await client.flushdb()
            logger.info("Cache logical DB flushed.")
            return True
        except Exception as e:
            logger.warning(f"Failed to flush cache DB: {e}")
            return False

    def get_status(self) -> dict:
        return {
            "status": "active",
            "provider": "Redis 7",
            "logical_db": settings.redis_cache_db,
            "eviction_policy": "volatile-lru",
            "default_ttl_seconds": 300,
            "metrics": {
                "hits": self.hits,
                "misses": self.misses,
                "evictions": self.evictions,
            },
        }


cache_service = RedisCacheService()
