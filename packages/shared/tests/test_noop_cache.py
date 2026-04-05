"""Unit tests for shared.cache._NoOpCache — the Redis fallback.

When Redis is unavailable (local dev, CI without Docker), the entire
caching layer silently falls back to _NoOpCache. If this fallback
is broken, every cache.get() call would throw instead of returning None,
crashing all projects in local dev.

Run:
  python -m pytest shared/tests/test_noop_cache.py -v
"""

from __future__ import annotations

import pytest

from shared.cache import _NoOpCache


@pytest.fixture
def cache() -> _NoOpCache:
    return _NoOpCache()


# ===========================================================================
# Basic CRUD Operations
# ===========================================================================


class TestNoOpCacheCRUD:
    """All CRUD ops must succeed silently and return sensible defaults."""

    @pytest.mark.asyncio
    async def test_get_returns_none(self, cache: _NoOpCache):
        result = await cache.get("any:key")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_does_not_raise(self, cache: _NoOpCache):
        # Must not throw, even with complex values
        await cache.set("key", {"complex": [1, 2, 3]}, ttl=60)

    @pytest.mark.asyncio
    async def test_delete_does_not_raise(self, cache: _NoOpCache):
        await cache.delete("nonexistent:key")

    @pytest.mark.asyncio
    async def test_exists_returns_false(self, cache: _NoOpCache):
        result = await cache.exists("any:key")
        assert result is False

    @pytest.mark.asyncio
    async def test_incr_returns_one(self, cache: _NoOpCache):
        """Rate limiter depends on incr returning 1, not crashing."""
        result = await cache.incr("rate:limit:key", ttl=60)
        assert result == 1

    @pytest.mark.asyncio
    async def test_close_does_not_raise(self, cache: _NoOpCache):
        await cache.close()


# ===========================================================================
# Set-then-Get (no persistence guarantee)
# ===========================================================================


class TestNoOpCacheNoPersistence:
    """NoOpCache is deliberately forgetful. Set → Get should return None."""

    @pytest.mark.asyncio
    async def test_set_then_get_returns_none(self, cache: _NoOpCache):
        await cache.set("ephemeral", "value", ttl=3600)
        result = await cache.get("ephemeral")
        assert result is None

    @pytest.mark.asyncio
    async def test_multiple_incr_always_returns_one(self, cache: _NoOpCache):
        """Each incr call is stateless — always returns 1."""
        r1 = await cache.incr("counter")
        r2 = await cache.incr("counter")
        r3 = await cache.incr("counter")
        assert r1 == r2 == r3 == 1


# ===========================================================================
# Decorator: @cache.cached
# ===========================================================================


class TestNoOpCachedDecorator:
    """The @cached decorator must pass-through without caching."""

    @pytest.mark.asyncio
    async def test_cached_function_executes_every_time(self, cache: _NoOpCache):
        call_count = 0

        @cache.cached(ttl=60, prefix="test")
        async def expensive_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        # Call twice with same args — both should execute (no caching)
        r1 = await expensive_function(5)
        r2 = await expensive_function(5)
        assert r1 == 10
        assert r2 == 10
        assert call_count == 2, "NoOpCache decorator should NOT cache results"

    @pytest.mark.asyncio
    async def test_cached_function_preserves_return_value(self, cache: _NoOpCache):
        @cache.cached(ttl=30, prefix="api")
        async def get_data() -> dict:
            return {"status": "ok", "count": 42}

        result = await get_data()
        assert result == {"status": "ok", "count": 42}

    @pytest.mark.asyncio
    async def test_cached_function_preserves_name(self, cache: _NoOpCache):
        @cache.cached(ttl=60)
        async def my_function():
            return True

        assert my_function.__name__ == "my_function"

    @pytest.mark.asyncio
    async def test_cache_clear_is_callable(self, cache: _NoOpCache):
        @cache.cached(ttl=60)
        async def something():
            return 1

        # cache_clear must be a no-op lambda, not throw
        something.cache_clear()

    @pytest.mark.asyncio
    async def test_cached_with_kwargs(self, cache: _NoOpCache):
        @cache.cached(ttl=60, prefix="kw")
        async def lookup(name: str, *, detailed: bool = False) -> str:
            return f"{name}:{'full' if detailed else 'brief'}"

        r = await lookup("trend", detailed=True)
        assert r == "trend:full"

    @pytest.mark.asyncio
    async def test_cached_with_none_return(self, cache: _NoOpCache):
        """Functions returning None should not cause issues."""
        @cache.cached(ttl=60)
        async def returns_none():
            return None

        result = await returns_none()
        assert result is None
