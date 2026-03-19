"""
BioLinker - Smoke / Integration Pipeline Tests

Uses shared conftest.py fixtures for external service stubs.
sync_client provides a TestClient with all services pre-mocked.
"""
import asyncio
import warnings

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

import main as app_main  # noqa: E402
import routers.rfp as rfp_router  # noqa: E402
import routers.web3 as web3_router  # noqa: E402


# ─── Auth / basic endpoint tests ────────────────────────────────────────────


def test_me_endpoint_with_test_token(sync_client):
    """GET /me with test-bypass token should return authenticated user."""
    response = sync_client.get(
        "/me",
        headers={"Authorization": "Bearer test-token-bypass"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is True
    assert data["uid"] == "test-user-id"
    assert data["email"] == "test@example.com"


# ─── Asset upload ────────────────────────────────────────────────────────────


def test_upload_returns_cid_and_index_status(sync_client, monkeypatch):
    """POST /assets/upload should return CID and analysis status."""

    class StubAssetManager:
        async def upload_asset(self, file, asset_type):
            return {"cid": "QmUnitTestCid123", "analysis": {"status": "indexed"}}

    monkeypatch.setattr(web3_router, "get_asset_manager", lambda: StubAssetManager())

    files = {"file": ("paper.pdf", b"%PDF-1.4 test", "application/pdf")}
    data = {"asset_type": "general", "title": "Unit Test Paper", "abstract": "Test abstract"}
    headers = {"Authorization": "Bearer test-token-bypass"}

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        response = sync_client.post("/assets/upload", files=files, data=data, headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["analysis"]["status"] == "indexed"


# ─── Match → Proposal flow ──────────────────────────────────────────────────


def test_match_to_proposal_flow(sync_client, monkeypatch):
    """POST /match/paper → /proposal/generate should chain correctly."""

    class StubMatcher:
        async def match_paper(self, paper_id: str, limit: int = 5):  # noqa: ARG002
            if paper_id != "paper-1":
                raise ValueError("Paper not found")
            return [
                {
                    "id": "rfp-1",
                    "title": "KR Bio Grant",
                    "source": "KDDF",
                    "score": 0.92,
                    "keywords": ["bio"],
                    "body_text": "funding notice",
                }
            ]

    class StubVectorStore:
        def get_notice(self, notice_id: str):
            if notice_id == "paper-1":
                return {
                    "id": "paper-1",
                    "metadata": {"title": "Paper One", "abstract": "Abstract"},
                    "document": "paper body",
                }
            if notice_id == "rfp-1":
                return {
                    "id": "rfp-1",
                    "title": "KR Bio Grant",
                    "metadata": {"title": "KR Bio Grant"},
                    "document": "rfp body",
                }
            return None

    class StubProposalGenerator:
        async def generate_draft(self, rfp_data: dict, paper_data: dict) -> str:
            return f"DRAFT::{rfp_data.get('id')}::{paper_data.get('id')}"

        async def review_draft(self, rfp_data: dict, paper_data: dict, draft: str) -> str:  # noqa: ARG002
            return "REVIEW_OK"

    monkeypatch.setattr(rfp_router, "get_rfp_matcher", lambda: StubMatcher())
    monkeypatch.setattr(rfp_router, "get_vector_store", lambda: StubVectorStore())
    monkeypatch.setattr(rfp_router, "get_proposal_generator", lambda: StubProposalGenerator())

    # [QA 수정] Tier manager mock — ENTERPRISE 티어로 모든 가드 통과
    from unittest.mock import AsyncMock as _AsyncMock
    import services.usage_middleware as _usage_mw
    from services.user_tier import UserTier as _UserTier

    stub_mgr = MagicMock()
    stub_mgr.get_tier = _AsyncMock(return_value=_UserTier.ENTERPRISE)
    stub_mgr.check_and_increment = _AsyncMock(return_value=(
        True,
        {"tier": "enterprise", "usage": {"proposal_generation": {"used": 1, "limit": 999999, "remaining": 999998}}},
    ))
    monkeypatch.setattr(_usage_mw, "get_tier_manager", lambda: stub_mgr)

    auth_headers = {"Authorization": "Bearer test-token-bypass"}

    match_res = sync_client.post("/match/paper", json={"paper_id": "paper-1"})
    proposal_res = sync_client.post(
        "/proposal/generate",
        json={"paper_id": "paper-1", "rfp_id": "rfp-1"},
        headers=auth_headers,
    )

    assert match_res.status_code == 200
    assert match_res.json()["matches"][0]["id"] == "rfp-1"
    assert proposal_res.status_code == 200
    assert proposal_res.json()["draft"] == "DRAFT::rfp-1::paper-1"


# ─── Health degraded scenario ───────────────────────────────────────────────


def test_health_degraded_when_vector_store_fails(monkeypatch):
    """Health should report 'degraded' when vector store raises."""

    class BrokenVectorStore:
        def count(self):
            raise RuntimeError("simulated failure")

    class StubWeb3:
        is_connected = False

    class StubIPFS:
        is_configured = False

        async def close(self):
            return None

    monkeypatch.setattr(app_main, "get_vector_store", lambda: BrokenVectorStore())
    monkeypatch.setattr(app_main, "get_web3_service", lambda: StubWeb3())
    monkeypatch.setattr(app_main, "get_ipfs_service", lambda: StubIPFS())

    with TestClient(app_main.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["chromadb_ok"] is False


# ─── Proposal generator fallback ────────────────────────────────────────────


def test_proposal_generator_fallback_without_llm():
    """ProposalGenerator should produce a template draft when LLM is None."""
    import services.proposal_generator as proposal_module

    generator = proposal_module.ProposalGenerator()
    generator.llm = None

    draft = asyncio.run(
        generator.generate_draft(
            {"id": "rfp-1", "title": "KR Bio Grant", "document": "rfp body"},
            {
                "id": "paper-1",
                "metadata": {"title": "Paper One", "abstract": "Abstract"},
                "document": "paper body",
            },
        )
    )

    assert draft.startswith("# Proposal:")


# ─── Wallet / Web3 contract tests ───────────────────────────────────────────


def test_wallet_balance_contract_when_mock_mode_off_returns_error_payload(monkeypatch):
    """get_balance should return error payload when service is not available."""

    class StubWeb3:
        async def get_balance(self, address: str):  # noqa: ARG002
            return {"error": "Web3 service not available or token contract not configured"}

    monkeypatch.setattr(web3_router, "get_web3_service", lambda: StubWeb3())

    with TestClient(app_main.app) as client:
        response = client.get("/wallet/0x3333333333333333333333333333333333333333")

    assert response.status_code == 200
    payload = response.json()
    assert "error" in payload


def test_wallet_balance_contract_when_mock_mode_on_returns_mock_payload(monkeypatch):
    """get_balance should return mock data when mock mode is on."""

    class StubWeb3:
        async def get_balance(self, address: str):
            return {
                "address": address,
                "balance": "123",
                "balance_wei": str(123 * 10**18),
                "symbol": "DSCI",
                "_mock": True,
            }

    monkeypatch.setattr(web3_router, "get_web3_service", lambda: StubWeb3())

    with TestClient(app_main.app) as client:
        response = client.get("/wallet/0x4444444444444444444444444444444444444444")

    assert response.status_code == 200
    payload = response.json()
    assert payload.get("_mock") is True


def test_web3_service_reward_amounts_returns_error_when_mock_mode_off(monkeypatch):
    """Reward amounts should return error when mock mode is off and no contract."""
    import services.web3_service as web3_module

    monkeypatch.setattr(web3_module, "MOCK_MODE", False)
    service = web3_module.Web3Service()
    service.token_contract = None

    result = asyncio.run(service.get_reward_amounts())
    assert "error" in result
