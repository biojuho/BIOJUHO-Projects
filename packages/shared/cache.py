"""
Shared Redis Cache Layer — 100x Scale Infrastructure

Provides a unified caching interface for all projects (AgriGuard, DeSci, GetDayTrends).
Falls back gracefully to no-op when Redis is unavailable (local dev without Docker).

Usage:
    from shared.cache import get_cache

    cache = get_cache()

    # Simple key-value
    await cache.set("dashboard:summary", data, ttl=30)
    result = await cache.get("dashboard:summary")

    # Decorator
    @cache.cached(ttl=60, prefix="api")
    async def get_dashboard():
        ...
"""

from __future__ import annotations

import functools
import hashlib
import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Redis URL — defaults to Docker dev network
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Default TTLs (seconds)
TTL_API_RESPONSE = 30       # Dashboard, summary endpoints
TTL_TREND_SCORE = 21600     # 6 hours — trend scores
TTL_FINGERPRINT = 10800     # 3 hours — duplicate check sets
TTL_SENSOR_AGG = 60         # 1 minute — IoT aggregations
TTL_RATE_LIMIT = 60         # 1 minute — rate limit windows

try:
    import redis.asyncio as aioredis
    _REDIS_AVAILABLE = True
except ImportError:
    aioredis = None  # type: ignore[assignment]
    _REDIS_AVAILABLE = False


class _NoOpCache:
    """Fallback when Redis is unavailable. All operations are no-ops."""

    async def get(self, key: str) -> Any:
        return None

    async def set(self, key: str, value: Any, ttl: int = 60) -> None:
        pass

    async def delete(self, key: str) -> None:
        pass

    async def exists(self, key: str) -> bool:
        return False

    async def incr(self, key: str, ttl: int = 60) -> int:
        return 1

    async def close(self) -> None:
        pass

    def cached(self, ttl: int = 60, prefix: str = "cache"):
        """Decorator that passes through without caching."""
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                return await func(*args, **kwargs)
            wrapper.cache_clear = lambda: None
            return wrapper
        return decorator


class RedisCache:
    """Async Redis cache with JSON serialization and decorator support."""

    def __init__(self, url: str = REDIS_URL) -> None:
        self._url = url
        self._redis: aioredis.Redis | None = None

    async def _get_conn(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(
                self._url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                retry_on_timeout=True,
            )
        return self._redis

    async def get(self, key: str) -> Any:
        try:
            r = await (await self._get_conn()).get(key)
            if r is not None:
                return json.loads(r)
        except Exception as e:
            logger.debug("Redis GET error (key=%s): %s", key, e)
        return None

    async def set(self, key: str, value: Any, ttl: int = 60) -> None:
        try:
            data = json.dumps(value, ensure_ascii=False, default=str)
            await (await self._get_conn()).setex(key, ttl, data)
        except Exception as e:
            logger.debug("Redis SET error (key=%s): %s", key, e)

    async def delete(self, key: str) -> None:
        try:
            await (await self._get_conn()).delete(key)
        except Exception as e:
            logger.debug("Redis DELETE error (key=%s): %s", key, e)

    async def exists(self, key: str) -> bool:
        try:
            return bool(await (await self._get_conn()).exists(key))
        except Exception:
            return False

    async def incr(self, key: str, ttl: int = 60) -> int:
        """Increment counter with TTL (for rate limiting)."""
        try:
            conn = await self._get_conn()
            pipe = conn.pipeline()
            pipe.incr(key)
            pipe.expire(key, ttl)
            results = await pipe.execute()
            return results[0]
        except Exception:
            return 1

    async def close(self) -> None:
        if self._redis:
            await self._redis.close()
            self._redis = None

    def cached(self, ttl: int = 60, prefix: str = "cache"):
        """Decorator for async functions. Caches results by function args."""
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                # Build cache key from function name + args hash
                key_data = f"{func.__module__}.{func.__qualname__}:{args}:{kwargs}"
                key_hash = hashlib.md5(key_data.encode()).hexdigest()[:12]
                cache_key = f"{prefix}:{func.__name__}:{key_hash}"

                # Try cache first
                cached = await self.get(cache_key)
                if cached is not None:
                    return cached

                # Execute and cache
                result = await func(*args, **kwargs)
                if result is not None:
                    await self.set(cache_key, result, ttl=ttl)
                return result

            async def _clear():
                pass  # Individual key clearing not needed with TTL

            wrapper.cache_clear = _clear
            return wrapper
        return decorator


# Singleton
_CACHE: RedisCache | _NoOpCache | None = None


def get_cache() -> RedisCache | _NoOpCache:
    """Get the shared cache instance. Returns NoOpCache if Redis is unavailable."""
    global _CACHE
    if _CACHE is None:
        if _REDIS_AVAILABLE:
            _CACHE = RedisCache(REDIS_URL)
            logger.info("Redis cache initialized: %s", REDIS_URL.split("@")[-1])
        else:
            _CACHE = _NoOpCache()
            logger.info("Redis not available — using NoOpCache (pip install redis)")
    return _CACHE


async def close_cache() -> None:
    """Shutdown hook — close Redis connection."""
    global _CACHE
    if _CACHE:
        await _CACHE.close()
        _CACHE = None
