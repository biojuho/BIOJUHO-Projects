"""End-to-end tests for the /vcs router."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_repo(monkeypatch):
    """Ensure the memory backend is used during router tests."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import services.vc_repository as vc_repo

    vc_repo.reset_vc_repository()
    yield
    vc_repo.reset_vc_repository()


def test_list_vcs_default_returns_full_dataset(sync_client):
    response = sync_client.get("/vcs")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) >= 50


def test_list_vcs_limit_truncates(sync_client):
    response = sync_client.get("/vcs", params={"limit": 5})
    assert response.status_code == 200
    assert len(response.json()) == 5


def test_list_vcs_country_filter(sync_client):
    response = sync_client.get("/vcs", params={"country": "US"})
    assert response.status_code == 200
    body = response.json()
    assert body, "expected non-empty result for US filter"
    assert all(vc["country"] == "US" for vc in body)


def test_list_vcs_stage_filter(sync_client):
    response = sync_client.get("/vcs", params={"stage": "Seed"})
    assert response.status_code == 200
    body = response.json()
    assert body
    assert all("Seed" in vc["preferred_stages"] for vc in body)


def test_list_vcs_keyword_filter(sync_client):
    response = sync_client.get("/vcs", params={"keyword": "oncology"})
    assert response.status_code == 200
    body = response.json()
    assert body
    for vc in body:
        haystack = " ".join(
            [vc["name"], vc.get("investment_thesis", ""), *vc.get("portfolio_keywords", [])]
        ).lower()
        assert "oncology" in haystack


def test_get_vc_by_id(sync_client):
    response = sync_client.get("/vcs/vc-kip-001")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "vc-kip-001"
    assert body["country"] == "KR"


def test_get_vc_unknown_returns_404(sync_client):
    response = sync_client.get("/vcs/does-not-exist")
    assert response.status_code == 404


def test_backend_meta(sync_client):
    response = sync_client.get("/vcs/meta/backend")
    assert response.status_code == 200
    assert response.json() == {"backend": "memory"}


def test_list_vcs_invalid_limit_rejected(sync_client):
    response = sync_client.get("/vcs", params={"limit": 999999})
    assert response.status_code == 422
