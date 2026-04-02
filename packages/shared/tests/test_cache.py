"""
Tests for shared.cache module — Redis cache layer with NoOp fallback.
"""

import asyncio
import sys
import pytest

sys.path.insert(0, "packages")

from shared.cache import RedisCache, _NoOpCache, get_cache, close_cache


# ─── NoOpCache Tests ─────────────────────────────────────────


class TestNoOpCache:
    """NoOpCache should be a safe no-op for all operations."""

    @pytest.fixture
    def cache(self):
        return _NoOpCache()

    @pytest.mark.asyncio
    async def test_get_returns_none(self, cache):
        assert await cache.get("any_key") is None

    @pytest.mark.asyncio
    async def test_set_does_not_raise(self, cache):
        await cache.set("key", {"data": True}, ttl=60)

    @pytest.mark.asyncio
    async def test_delete_does_not_raise(self, cache):
        await cache.delete("key")

    @pytest.mark.asyncio
    async def test_exists_returns_false(self, cache):
        assert await cache.exists("key") is False

    @pytest.mark.asyncio
    async def test_incr_returns_1(self, cache):
        assert await cache.incr("key") == 1

    @pytest.mark.asyncio
    async def test_close_does_not_raise(self, cache):
        await cache.close()

    @pytest.mark.asyncio
    async def test_cached_decorator_passthrough(self, cache):
        call_count = 0

        @cache.cached(ttl=60, prefix="test")
        async def expensive_fn(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # Without real cache, function should execute every time
        assert await expensive_fn(5) == 10
        assert await expensive_fn(5) == 10
        assert call_count == 2  # No caching happened


# ─── RedisCache Tests (unit, no Redis required) ─────────────


class TestRedisCacheUnit:
    """Test RedisCache behavior when Redis is unreachable."""

    @pytest.fixture
    def cache(self):
        # Use a bogus URL so Redis connection fails gracefully
        return RedisCache(url="redis://localhost:19999/15")

    @pytest.mark.asyncio
    async def test_get_returns_none_on_connection_error(self, cache):
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_does_not_raise_on_connection_error(self, cache):
        # Should not raise even when Redis is unreachable
        await cache.set("key", {"value": 1}, ttl=10)

    @pytest.mark.asyncio
    async def test_exists_returns_false_on_connection_error(self, cache):
        assert await cache.exists("key") is False

    @pytest.mark.asyncio
    async def test_incr_returns_1_on_connection_error(self, cache):
        result = await cache.incr("key", ttl=60)
        assert result == 1

    @pytest.mark.asyncio
    async def test_close_does_not_raise(self, cache):
        await cache.close()

    @pytest.mark.asyncio
    async def test_cached_decorator_fallback(self, cache):
        """When Redis is down, @cached should still execute the function."""
        call_count = 0

        @cache.cached(ttl=30, prefix="test")
        async def compute(x):
            nonlocal call_count
            call_count += 1
            return x + 1

        assert await compute(10) == 11
        assert await compute(10) == 11
        assert call_count == 2  # Function ran twice (no cache)


# ─── get_cache singleton tests ───────────────────────────────


class TestGetCache:
    @pytest.mark.asyncio
    async def test_returns_cache_instance(self):
        await close_cache()  # Reset singleton
        cache = get_cache()
        assert cache is not None
        assert hasattr(cache, "get")
        assert hasattr(cache, "set")
        assert hasattr(cache, "incr")
        await close_cache()

    @pytest.mark.asyncio
    async def test_singleton_returns_same_instance(self):
        await close_cache()
        c1 = get_cache()
        c2 = get_cache()
        assert c1 is c2
        await close_cache()
