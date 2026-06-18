"""Tests for the in-memory TTL cache layer over OpenAlex / CrossRef."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

BIOLINKER_DIR = Path(__file__).resolve().parent.parent
if str(BIOLINKER_DIR) not in sys.path:
    sys.path.insert(0, str(BIOLINKER_DIR))

from services import external_research as er  # noqa: E402
from services.external_research import (  # noqa: E402
    ExternalResearchClient,
    _cache_get,
    _cache_key,
    _cache_put,
    reset_cache,
)


@pytest.fixture(autouse=True)
def _clean_cache():
    reset_cache()
    yield
    reset_cache()


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _CountingSession:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.call_count = 0

    async def get(self, url, params=None) -> _FakeResponse:
        self.call_count += 1
        return _FakeResponse(self.payload)

    async def aclose(self) -> None:
        return None


def test_cache_key_is_stable_for_same_args() -> None:
    assert _cache_key("a", 1, "b") == _cache_key("a", 1, "b")
    assert _cache_key("a", 1) != _cache_key("a", 2)


@pytest.mark.asyncio
async def test_cache_get_returns_none_when_expired() -> None:
    await _cache_put("k1", "value")
    # Force expiry by mocking time
    with patch.object(er, "_CACHE_TTL_SECONDS", -1):
        assert await _cache_get("k1") is None


@pytest.mark.asyncio
async def test_cache_get_returns_value_within_ttl() -> None:
    await _cache_put("k2", "fresh")
    assert await _cache_get("k2") == "fresh"


@pytest.mark.asyncio
async def test_cache_evicts_oldest_when_full() -> None:
    with patch.object(er, "_CACHE_MAX_ENTRIES", 2):
        await _cache_put("a", 1)
        await _cache_put("b", 2)
        await _cache_put("c", 3)
        # "a" should have been evicted
        assert await _cache_get("a") is None
        assert await _cache_get("b") == 2
        assert await _cache_get("c") == 3


@pytest.mark.asyncio
async def test_search_openalex_uses_cache_on_repeat_call() -> None:
    payload = {
        "results": [
            {
                "id": "https://openalex.org/W1",
                "title": "Cached title",
                "cited_by_count": 5,
            }
        ]
    }
    session = _CountingSession(payload)
    client = ExternalResearchClient(session=session)  # type: ignore[arg-type]

    first = await client.search_openalex("ai drug", per_page=5)
    second = await client.search_openalex("ai drug", per_page=5)

    assert session.call_count == 1, "second call should be served from cache"
    assert first == second
    assert first[0].title == "Cached title"


@pytest.mark.asyncio
async def test_search_openalex_cache_miss_for_different_query() -> None:
    session = _CountingSession({"results": []})
    client = ExternalResearchClient(session=session)  # type: ignore[arg-type]

    await client.search_openalex("query A", per_page=5)
    await client.search_openalex("query B", per_page=5)

    assert session.call_count == 2


@pytest.mark.asyncio
async def test_lookup_crossref_doi_caches_result() -> None:
    payload = {
        "message": {
            "title": ["t"],
            "is-referenced-by-count": 1,
            "issued": {"date-parts": [[2024]]},
        }
    }
    session = _CountingSession(payload)
    client = ExternalResearchClient(session=session)  # type: ignore[arg-type]

    a = await client.lookup_crossref_doi("10.1/abc")
    b = await client.lookup_crossref_doi("10.1/abc")

    assert session.call_count == 1
    assert a is b or (a is not None and b is not None and a.title == b.title)


@pytest.mark.asyncio
async def test_search_openalex_does_not_cache_on_failure() -> None:
    """Failures should not poison the cache."""
    import httpx

    class _BoomSession:
        def __init__(self) -> None:
            self.call_count = 0

        async def get(self, url, params=None):
            self.call_count += 1
            raise httpx.RequestError("boom")  # type: ignore[arg-type]

        async def aclose(self) -> None:
            return None

    session = _BoomSession()
    client = ExternalResearchClient(session=session)  # type: ignore[arg-type]

    a = await client.search_openalex("topic", per_page=5)
    b = await client.search_openalex("topic", per_page=5)

    assert a == [] and b == []
    assert session.call_count == 2, "failed responses must not be cached"


@pytest.mark.asyncio
async def test_reset_cache_clears_all_entries() -> None:
    await _cache_put("k", "v")
    assert await _cache_get("k") == "v"
    reset_cache()
    assert await _cache_get("k") is None


@pytest.mark.asyncio
async def test_cache_respects_ttl_with_real_clock() -> None:
    """End-to-end: a tiny TTL should evict naturally without mocking."""
    with patch.object(er, "_CACHE_TTL_SECONDS", 0):
        await _cache_put("k", "v")
        # any nonzero elapsed time should miss
        time.sleep(0.01)
        assert await _cache_get("k") is None


@pytest.mark.asyncio
async def test_cache_stats_tracks_hits_misses_and_rate() -> None:
    from services.external_research import cache_stats

    initial = cache_stats()
    assert initial["hits"] == 0
    assert initial["misses"] == 0
    assert initial["hit_rate"] == 0.0

    await _cache_put("k", "v")
    await _cache_get("k")  # hit
    await _cache_get("k")  # hit
    await _cache_get("missing")  # miss

    stats = cache_stats()
    assert stats["hits"] == 2
    assert stats["misses"] == 1
    assert stats["puts"] == 1
    assert stats["size"] == 1
    assert stats["hit_rate"] == round(2 / 3, 4)
    assert stats["ttl_seconds"] == er._CACHE_TTL_SECONDS
    assert stats["max_entries"] == er._CACHE_MAX_ENTRIES


@pytest.mark.asyncio
async def test_cache_stats_increments_expired_and_evictions() -> None:
    from services.external_research import cache_stats

    # Force expiry on the first read
    await _cache_put("k", "v")
    with patch.object(er, "_CACHE_TTL_SECONDS", -1):
        await _cache_get("k")
    assert cache_stats()["expired"] == 1

    # Force eviction by exceeding max entries
    reset_cache()
    with patch.object(er, "_CACHE_MAX_ENTRIES", 1):
        await _cache_put("a", 1)
        await _cache_put("b", 2)  # evicts "a"
    assert cache_stats()["evictions"] == 1


def test_reset_cache_zeroes_metric_counters() -> None:
    from services.external_research import _cache_metrics, cache_stats

    _cache_metrics["hits"] = 99
    _cache_metrics["misses"] = 33
    reset_cache()
    snap = cache_stats()
    assert snap["hits"] == 0 and snap["misses"] == 0
