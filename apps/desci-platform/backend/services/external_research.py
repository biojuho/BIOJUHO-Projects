"""
External research enrichment.

OpenAlex (200M+ scholarly works) and CrossRef (DOI authority) clients to
enrich BioLinker matching with citation/funding signals that internal
embeddings cannot derive. Both APIs are free; only a polite-pool email is
needed (per provider guidelines) — never a paid key.

Used as a passive enrichment layer alongside the existing vector matcher;
failures degrade silently to keep the matching path resilient.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import httpx

from .logging_config import get_logger

log = get_logger("biolinker.external_research")

_OPENALEX_BASE = "https://api.openalex.org"
_CROSSREF_BASE = "https://api.crossref.org"

# Polite-pool defaults — providers ask for an identifying email so they can
# contact maintainers instead of throttling the whole IP block.
_POLITE_EMAIL = os.getenv("EXTERNAL_RESEARCH_EMAIL", "biojuho@gmail.com")
_USER_AGENT = f"BioLinker/1.0 (mailto:{_POLITE_EMAIL})"

_DEFAULT_TIMEOUT = httpx.Timeout(8.0, connect=4.0)

# In-memory TTL cache shared across requests (single-process). 6h TTL chosen
# because OpenAlex/CrossRef metadata changes slowly (citation counts update
# nightly, abstracts almost never). The cap prevents unbounded growth in a
# long-running worker; eviction is FIFO via insertion order.
_CACHE_TTL_SECONDS = int(os.getenv("EXTERNAL_RESEARCH_CACHE_TTL", "21600"))
_CACHE_MAX_ENTRIES = int(os.getenv("EXTERNAL_RESEARCH_CACHE_MAX", "512"))
_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = asyncio.Lock()
_cache_metrics: dict[str, int] = {
    "hits": 0,
    "misses": 0,
    "expired": 0,
    "evictions": 0,
    "puts": 0,
}


def _cache_key(*parts: object) -> str:
    """Stable hash of arbitrary call arguments."""
    raw = "␟".join(str(p) for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


async def _cache_get(key: str) -> Any | None:
    async with _cache_lock:
        hit = _cache.get(key)
        if hit is None:
            _cache_metrics["misses"] += 1
            return None
        stored_at, value = hit
        if time.time() - stored_at > _CACHE_TTL_SECONDS:
            _cache.pop(key, None)
            _cache_metrics["expired"] += 1
            _cache_metrics["misses"] += 1
            return None
        _cache_metrics["hits"] += 1
        return value


async def _cache_put(key: str, value: Any) -> None:
    async with _cache_lock:
        if len(_cache) >= _CACHE_MAX_ENTRIES:
            # FIFO eviction: drop the oldest insertion.
            oldest_key = next(iter(_cache))
            _cache.pop(oldest_key, None)
            _cache_metrics["evictions"] += 1
        _cache[key] = (time.time(), value)
        _cache_metrics["puts"] += 1


def reset_cache() -> None:
    """Clear the in-memory cache. Intended for tests and operator tooling."""
    _cache.clear()
    for k in _cache_metrics:
        _cache_metrics[k] = 0


def cache_stats() -> dict[str, Any]:
    """Snapshot of cache utilization for /healthz and admin endpoints.

    Reports counters since process start (or the last ``reset_cache``). The
    snapshot is read-only and lock-free so it can be queried from health
    checks without contending with normal reads/writes.
    """
    hits = _cache_metrics["hits"]
    misses = _cache_metrics["misses"]
    total = hits + misses
    hit_rate = round(hits / total, 4) if total else 0.0
    return {
        "size": len(_cache),
        "max_entries": _CACHE_MAX_ENTRIES,
        "ttl_seconds": _CACHE_TTL_SECONDS,
        "hits": hits,
        "misses": misses,
        "expired": _cache_metrics["expired"],
        "evictions": _cache_metrics["evictions"],
        "puts": _cache_metrics["puts"],
        "hit_rate": hit_rate,
    }


@dataclass
class ScholarlyWork:
    """Normalized representation across OpenAlex / CrossRef."""

    source: str
    id: str
    title: str
    doi: str = ""
    year: int | None = None
    citation_count: int = 0
    authors: list[str] = field(default_factory=list)
    venue: str = ""
    abstract: str = ""
    concepts: list[str] = field(default_factory=list)
    open_access_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "id": self.id,
            "title": self.title,
            "doi": self.doi,
            "year": self.year,
            "citation_count": self.citation_count,
            "authors": self.authors,
            "venue": self.venue,
            "abstract": self.abstract,
            "concepts": self.concepts,
            "open_access_url": self.open_access_url,
        }


def _reconstruct_abstract(inverted_index: dict[str, list[int]] | None) -> str:
    """OpenAlex returns abstracts as inverted indices to dodge copyright; rebuild."""
    if not inverted_index:
        return ""
    positions: list[tuple[int, str]] = []
    for word, indices in inverted_index.items():
        for idx in indices:
            positions.append((idx, word))
    positions.sort(key=lambda item: item[0])
    return " ".join(word for _, word in positions)


class ExternalResearchClient:
    """Async client over OpenAlex + CrossRef with graceful degradation."""

    def __init__(self, session: httpx.AsyncClient | None = None) -> None:
        self._session = session
        self._owns_session = session is None

    async def __aenter__(self) -> ExternalResearchClient:
        if self._session is None:
            self._session = httpx.AsyncClient(
                timeout=_DEFAULT_TIMEOUT,
                headers={"User-Agent": _USER_AGENT},
            )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._owns_session and self._session is not None:
            await self._session.aclose()
            self._session = None

    async def search_openalex(self, query: str, per_page: int = 5) -> list[ScholarlyWork]:
        if not query.strip() or self._session is None:
            return []
        cache_key = _cache_key("openalex_search", query.strip(), per_page)
        cached = await _cache_get(cache_key)
        if cached is not None:
            log.debug("openalex_cache_hit", query=query)
            return cached  # type: ignore[no-any-return]

        url = f"{_OPENALEX_BASE}/works"
        params = {
            "search": query,
            "per-page": str(per_page),
            "mailto": _POLITE_EMAIL,
        }
        try:
            resp = await self._session.get(url, params=params)
            resp.raise_for_status()
            payload = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("openalex_search_failed", error=str(exc), query=query)
            return []

        results: list[ScholarlyWork] = []
        for item in payload.get("results", []):
            authorships = item.get("authorships", []) or []
            authors = [a.get("author", {}).get("display_name", "") for a in authorships if a.get("author")]
            concepts = [
                c.get("display_name", "")
                for c in (item.get("concepts", []) or [])
                if c.get("display_name") and c.get("score", 0) >= 0.3
            ]
            host = (item.get("primary_location") or {}).get("source") or {}
            oa_url = (item.get("open_access") or {}).get("oa_url") or ""

            results.append(
                ScholarlyWork(
                    source="openalex",
                    id=item.get("id", "").rsplit("/", 1)[-1],
                    title=item.get("title") or item.get("display_name", "") or "",
                    doi=(item.get("doi") or "").replace("https://doi.org/", ""),
                    year=item.get("publication_year"),
                    citation_count=int(item.get("cited_by_count") or 0),
                    authors=[a for a in authors if a],
                    venue=host.get("display_name", "") or "",
                    abstract=_reconstruct_abstract(item.get("abstract_inverted_index")),
                    concepts=concepts[:8],
                    open_access_url=oa_url,
                )
            )
        await _cache_put(cache_key, results)
        return results

    async def lookup_crossref_doi(self, doi: str) -> ScholarlyWork | None:
        if not doi.strip() or self._session is None:
            return None
        clean = doi.replace("https://doi.org/", "").strip()
        cache_key = _cache_key("crossref_doi", clean)
        cached = await _cache_get(cache_key)
        if cached is not None:
            log.debug("crossref_cache_hit", doi=clean)
            return cached  # type: ignore[no-any-return]

        url = f"{_CROSSREF_BASE}/works/{quote(clean, safe='/:')}"
        params = {"mailto": _POLITE_EMAIL}
        try:
            resp = await self._session.get(url, params=params)
            resp.raise_for_status()
            payload = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.info("crossref_lookup_failed", error=str(exc), doi=clean)
            return None

        message = payload.get("message") or {}
        title_list = message.get("title") or []
        authors_raw = message.get("author") or []
        authors = [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in authors_raw]
        issued = (message.get("issued") or {}).get("date-parts") or [[]]
        year = issued[0][0] if issued and issued[0] else None
        venue_list = message.get("container-title") or []

        work = ScholarlyWork(
            source="crossref",
            id=clean,
            title=(title_list[0] if title_list else "").strip(),
            doi=clean,
            year=year,
            citation_count=int(message.get("is-referenced-by-count") or 0),
            authors=[a for a in authors if a],
            venue=(venue_list[0] if venue_list else "") or "",
            abstract=(message.get("abstract") or "").strip(),
            concepts=list(message.get("subject") or [])[:8],
            open_access_url="",
        )
        await _cache_put(cache_key, work)
        return work

    async def enrich_query(
        self,
        query: str,
        per_page: int = 5,
        crossref_dois: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run OpenAlex search and CrossRef DOI lookups concurrently."""
        tasks: list[asyncio.Task[Any]] = [asyncio.create_task(self.search_openalex(query, per_page=per_page))]
        for doi in crossref_dois or []:
            tasks.append(asyncio.create_task(self.lookup_crossref_doi(doi)))

        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        works = gathered[0] if not isinstance(gathered[0], BaseException) else []
        crossref_hits: list[ScholarlyWork] = []
        for result in gathered[1:]:
            if isinstance(result, ScholarlyWork):
                crossref_hits.append(result)

        return {
            "query": query,
            "openalex": [w.to_dict() for w in works],
            "crossref": [w.to_dict() for w in crossref_hits],
            "total_citations": sum(w.citation_count for w in works) + sum(w.citation_count for w in crossref_hits),
        }


_client: ExternalResearchClient | None = None


def get_external_research_client() -> ExternalResearchClient:
    """Module-level accessor — callers should still use it as an async ctx mgr."""
    global _client
    if _client is None:
        _client = ExternalResearchClient()
    return _client
