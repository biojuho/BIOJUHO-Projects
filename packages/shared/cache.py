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
import time
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
    from redis.exceptions import ConnectionError as RedisConnectionError
    from redis.exceptions import RedisError, TimeoutError as RedisTimeoutError
    _REDIS_AVAILABLE = True
except ImportError:
    aioredis = None  # type: ignore[assignment]
    RedisConnectionError = ConnectionError  # type: ignore[assignment]
    RedisTimeoutError = TimeoutError  # type: ignore[assignment]
    RedisError = Exception  # type: ignore[assignment]
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
        self._disabled_until = 0.0
        self._suspend_seconds = int(os.getenv("REDIS_SUSPEND_SECONDS", "60"))

    def _is_suspended(self) -> bool:
        return time.monotonic() < self._disabled_until

    async def _close_conn(self) -> None:
        if not self._redis:
            return
        aclose = getattr(self._redis, "aclose", None)
        if aclose is not None:
            await aclose()
        else:
            await self._redis.close()
        self._redis = None

    async def _suspend_cache(self, operation: str, key: str, exc: Exception) -> None:
        was_suspended = self._is_suspended()
        self._disabled_until = time.monotonic() + self._suspend_seconds
        await self._close_conn()
        if not was_suspended:
            logger.warning(
                "Redis unavailable during %s for key=%s; disabling cache for %ss: %s",
                operation,
                key,
                self._suspend_seconds,
                exc,
            )

    @staticmethod
    def _is_connection_error(exc: Exception) -> bool:
        if isinstance(exc, RuntimeError) and "Event loop is closed" in str(exc):
            return True
        return isinstance(
            exc,
            (
                RedisConnectionError,
                RedisTimeoutError,
                RedisError,
                ConnectionError,
                TimeoutError,
                OSError,
            ),
        )

    async def _get_conn(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(
                self._url,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
                retry_on_timeout=True,
            )
        return self._redis

    async def get(self, key: str) -> Any:
        if self._is_suspended():
            return None
        try:
            r = await (await self._get_conn()).get(key)
            if r is not None:
                return json.loads(r)
        except Exception as e:
            if self._is_connection_error(e):
                await self._suspend_cache("GET", key, e)
            else:
                logger.warning("Redis GET error (key=%s): %s", key, e)
        return None

    async def set(self, key: str, value: Any, ttl: int = 60) -> None:
        if self._is_suspended():
            return
        try:
            data = json.dumps(value, ensure_ascii=False, default=str)
            await (await self._get_conn()).setex(key, ttl, data)
        except Exception as e:
            if self._is_connection_error(e):
                await self._suspend_cache("SET", key, e)
            else:
                logger.warning("Redis SET error (key=%s): %s", key, e)

    async def delete(self, key: str) -> None:
        if self._is_suspended():
            return
        try:
            await (await self._get_conn()).delete(key)
        except Exception as e:
            if self._is_connection_error(e):
                await self._suspend_cache("DELETE", key, e)
            else:
                logger.warning("Redis DELETE error (key=%s): %s", key, e)

    async def exists(self, key: str) -> bool:
        if self._is_suspended():
            return False
        try:
            return bool(await (await self._get_conn()).exists(key))
        except Exception as e:
            if self._is_connection_error(e):
                await self._suspend_cache("EXISTS", key, e)
            return False

    async def incr(self, key: str, ttl: int = 60) -> int:
        """Increment counter with TTL (for rate limiting)."""
        if self._is_suspended():
            return 1
        try:
            conn = await self._get_conn()
            async with conn.pipeline(transaction=True) as pipe:
                pipe.incr(key)
                pipe.expire(key, ttl)
                results = await pipe.execute()
            return results[0]
        except Exception as e:
            if self._is_connection_error(e):
                await self._suspend_cache("INCR", key, e)
            else:
                logger.warning("Redis INCR error (key=%s): %s - rate limit may be inaccurate", key, e)
            return 1

    async def close(self) -> None:
        await self._close_conn()

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
