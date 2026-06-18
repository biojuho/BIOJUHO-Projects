"""Unit tests for the in-memory VC repository (backend selection + filters)."""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture(autouse=True)
def _reset_repo(monkeypatch):
    """Force a fresh repository selection per test."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import services.vc_repository as vc_repo

    vc_repo.reset_vc_repository()
    yield
    vc_repo.reset_vc_repository()


def test_memory_backend_selected_when_no_database_url():
    import services.vc_repository as vc_repo

    repo = vc_repo.get_vc_repository()
    assert repo.backend == "memory"


def test_pg_backend_selected_when_database_url_set(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://example:example@localhost/example")
    import services.vc_repository as vc_repo

    vc_repo.reset_vc_repository()
    repo = vc_repo.get_vc_repository()
    assert repo.backend == "postgres"


def test_pg_backend_falls_back_when_asyncpg_missing(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://example:example@localhost/example")
    import services.vc_repository as vc_repo

    vc_repo.reset_vc_repository()

    real_import = importlib.import_module

    def fake_import(name, *args, **kwargs):
        if name == "asyncpg":
            raise ImportError("no asyncpg in this env")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", fake_import)
    monkeypatch.setattr("builtins.__import__", lambda name, *a, **k: (_ for _ in ()).throw(ImportError("blocked")) if name == "asyncpg" else __import__(name, *a, **k))

    repo = vc_repo.get_vc_repository()
    assert repo.backend == "memory"


@pytest.mark.asyncio
async def test_list_vcs_returns_full_dataset():
    import services.vc_repository as vc_repo

    repo = vc_repo.get_vc_repository()
    rows = await repo.list_vcs(limit=200)
    assert len(rows) >= 50, "expected at least 50 curated KR VCs in the seed"
    assert all(vc.id for vc in rows)


@pytest.mark.asyncio
async def test_list_vcs_filters_by_country():
    import services.vc_repository as vc_repo

    repo = vc_repo.get_vc_repository()
    kr_only = await repo.list_vcs(country="KR", limit=200)
    non_kr = await repo.list_vcs(country="US", limit=200)
    assert all(vc.country == "KR" for vc in kr_only)
    assert all(vc.country == "US" for vc in non_kr)


@pytest.mark.asyncio
async def test_list_vcs_filters_by_stage_and_keyword():
    import services.vc_repository as vc_repo

    repo = vc_repo.get_vc_repository()
    seeds = await repo.list_vcs(stage="Seed", limit=200)
    assert seeds, "expected at least one seed-stage VC in the seed dataset"
    assert all("Seed" in vc.preferred_stages for vc in seeds)

    oncology = await repo.list_vcs(keyword="oncology", limit=200)
    assert oncology, "expected oncology-related VCs in the seed"


@pytest.mark.asyncio
async def test_list_vcs_respects_limit():
    import services.vc_repository as vc_repo

    repo = vc_repo.get_vc_repository()
    small = await repo.list_vcs(limit=3)
    assert len(small) == 3


@pytest.mark.asyncio
async def test_get_vc_known_and_unknown():
    import services.vc_repository as vc_repo

    repo = vc_repo.get_vc_repository()
    hit = await repo.get_vc("vc-kip-001")
    assert hit is not None
    assert hit.country == "KR"

    miss = await repo.get_vc("does-not-exist")
    assert miss is None
