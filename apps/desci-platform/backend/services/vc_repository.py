"""
BioLinker - VC repository.

Provides a single accessor for VC firm data with two interchangeable
backends:

- ``MemoryVCRepository``: reads the curated JSON seed via ``VCCrawler``.
  Always available, used in smoke environments and as a Postgres
  fallback when no ``DATABASE_URL`` is configured.

- ``PostgresVCRepository``: reads from the ``vc_firms`` Supabase/Postgres
  table seeded by ``scripts/seed_vcs.py``. Used when ``DATABASE_URL`` is
  set and ``asyncpg`` is importable.

Selection rule (``get_vc_repository``):
    Postgres if (DATABASE_URL and asyncpg available) else Memory.

Both implementations expose the same async-friendly interface so callers
can switch without conditionals.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from typing import Protocol

from models import VCFirm

from services.logging_config import get_logger
from services.vc_crawler import get_vc_crawler

log = get_logger("biolinker.vc_repository")


class VCRepository(Protocol):
    """Async-friendly read interface for VC firm data."""

    backend: str

    async def list_vcs(
        self,
        *,
        country: str | None = None,
        stage: str | None = None,
        keyword: str | None = None,
        limit: int = 100,
    ) -> list[VCFirm]:
        ...

    async def get_vc(self, vc_id: str) -> VCFirm | None:
        ...


def _filter_in_memory(
    vcs: Iterable[VCFirm],
    *,
    country: str | None,
    stage: str | None,
    keyword: str | None,
) -> list[VCFirm]:
    country_norm = country.upper() if country else None
    stage_norm = stage.lower() if stage else None
    keyword_norm = keyword.lower() if keyword else None

    out: list[VCFirm] = []
    for vc in vcs:
        if country_norm and vc.country.upper() != country_norm:
            continue
        if stage_norm and not any(s.lower() == stage_norm for s in vc.preferred_stages):
            continue
        if keyword_norm:
            haystack = " ".join(
                [
                    vc.name,
                    vc.investment_thesis or "",
                    " ".join(vc.portfolio_keywords),
                ]
            ).lower()
            if keyword_norm not in haystack:
                continue
        out.append(vc)
    return out


class MemoryVCRepository:
    """In-memory backend reading from the curated JSON seed."""

    backend = "memory"

    def __init__(self) -> None:
        self._crawler = get_vc_crawler()

    async def list_vcs(
        self,
        *,
        country: str | None = None,
        stage: str | None = None,
        keyword: str | None = None,
        limit: int = 100,
    ) -> list[VCFirm]:
        vcs = self._crawler.fetch_vc_list()
        filtered = _filter_in_memory(vcs, country=country, stage=stage, keyword=keyword)
        return filtered[: max(0, limit)]

    async def get_vc(self, vc_id: str) -> VCFirm | None:
        for vc in self._crawler.fetch_vc_list():
            if vc.id == vc_id:
                return vc
        return None


class PostgresVCRepository:
    """Postgres-backed repository using asyncpg.

    The pool is created lazily on the first query. If the pool can't be
    built (database unreachable, missing table, etc.) the error is
    logged and a ``RuntimeError`` is raised so the caller can decide to
    fall back to the memory backend.
    """

    backend = "postgres"

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._pool = None

    async def _get_pool(self):
        if self._pool is None:
            import asyncpg

            self._pool = await asyncpg.create_pool(
                self._database_url,
                min_size=1,
                max_size=4,
                statement_cache_size=0,
            )
        return self._pool

    async def list_vcs(
        self,
        *,
        country: str | None = None,
        stage: str | None = None,
        keyword: str | None = None,
        limit: int = 100,
    ) -> list[VCFirm]:
        pool = await self._get_pool()
        clauses: list[str] = []
        params: list[object] = []

        if country:
            params.append(country.upper())
            clauses.append(f"country = ${len(params)}")
        if stage:
            params.append(stage)
            clauses.append(f"${len(params)} = ANY (preferred_stages)")
        if keyword:
            params.append(f"%{keyword.lower()}%")
            clauses.append(
                f"(lower(name) like ${len(params)} or lower(investment_thesis) like ${len(params)})"
            )

        where = ("where " + " and ".join(clauses)) if clauses else ""
        params.append(max(0, limit))
        sql = (
            "select id, name, country, website, investment_thesis, "
            "preferred_stages, portfolio_keywords, contact_email "
            f"from vc_firms {where} order by id limit ${len(params)}"
        )

        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
        return [VCFirm.model_validate(dict(row)) for row in rows]

    async def get_vc(self, vc_id: str) -> VCFirm | None:
        pool = await self._get_pool()
        sql = (
            "select id, name, country, website, investment_thesis, "
            "preferred_stages, portfolio_keywords, contact_email "
            "from vc_firms where id = $1"
        )
        async with pool.acquire() as conn:
            row = await conn.fetchrow(sql, vc_id)
        return VCFirm.model_validate(dict(row)) if row else None

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None


_repository: VCRepository | None = None


def _build_repository() -> VCRepository:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        try:
            import asyncpg  # noqa: F401  (probe only)
        except ImportError:
            log.warning(
                "vc_repository_pg_unavailable",
                detail="DATABASE_URL set but asyncpg not installed; falling back to memory",
            )
        else:
            log.info("vc_repository_backend", backend="postgres")
            return PostgresVCRepository(database_url)
    log.info("vc_repository_backend", backend="memory")
    return MemoryVCRepository()


def get_vc_repository() -> VCRepository:
    global _repository
    if _repository is None:
        _repository = _build_repository()
    return _repository


def reset_vc_repository() -> None:
    """Test hook — clears the cached repository so env changes take effect."""
    global _repository
    _repository = None
