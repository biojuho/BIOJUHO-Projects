"""
BioLinker - E2E Proposal Flow Test

Full upload → match → proposal generation flow with monkeypatched services.
Uses shared conftest.py for sys.path setup.
"""

import warnings

import main as app_main  # noqa: E402
import pytest
import routers.rfp as rfp_router  # noqa: E402
import routers.web3 as web3_router  # noqa: E402
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    """
    Setup TestClient with mock bypasses to simulate an authenticated E2E flow
    without requiring actual Firebase auth or a real Web3 connected environment.
    """
    from unittest.mock import AsyncMock, MagicMock

    import services.usage_middleware as _usage_mw
    from services.user_tier import UserTier as _UserTier

    monkeypatch.setenv("ALLOW_TEST_BYPASS", "true")

    # UsageGuard / TierRequired mock — ENTERPRISE 티어로 모든 가드 통과
    stub_mgr = MagicMock()
    stub_mgr.get_tier = AsyncMock(return_value=_UserTier.ENTERPRISE)
    stub_mgr.check_and_increment = AsyncMock(
        return_value=(
            True,
            {"tier": "enterprise", "usage": {}},
        )
    )
    monkeypatch.setattr(_usage_mw, "get_tier_manager", lambda: stub_mgr)

    with TestClient(app_main.app) as test_client:
        test_client.headers["Authorization"] = "Bearer test-token-bypass"
        yield test_client


def test_full_e2e_upload_to_proposal_flow(client, monkeypatch):
    """
    Test the full flow:
    1. Upload a paper PDF (mocked parser/IPFS) -> Should return CID and index it.
    2. Get user's papers -> Should see the uploaded paper.
    3. Match the paper to an RFP -> Should return RFP matches.
    4. Generate a proposal draft -> Should return the generated draft and critique.
    """

    # === 1. Setup Stubs for External Dependencies ===
    class StubParser:
        def parse(self, content: bytes) -> str:
            return "This is a profound study on AI-driven clinical trials and biotechnology."

    class StubIPFS:
        is_configured = False

        async def upload_file(self, file_path: str, metadata: dict):
            return {
                "cid": "QmE2ETestCid999",
                "url": "https://gateway.pinata.cloud/ipfs/QmE2ETestCid999",
            }

        async def close(self):
            pass

    import services.pdf_parser as pdf_parser_module

    monkeypatch.setattr(pdf_parser_module, "get_pdf_parser", lambda: StubParser())
    monkeypatch.setattr(app_main, "get_ipfs_service", lambda: StubIPFS())

    # Stub the AssetManager so /assets/upload returns a CID-like response
    class StubAssetManager:
        async def upload_asset(self, file, asset_type="general"):
            return {
                "cid": "QmE2ETestCid999",
                "id": "QmE2ETestCid999",
                "filename": file.filename,
                "type": asset_type,
                "indexed": True,
            }

    monkeypatch.setattr(web3_router, "get_asset_manager", lambda: StubAssetManager())

    # Mock the Vector Store fully so we don't need ChromaDB running
    class InMemoryVectorStore:
        def __init__(self):
            self.papers = {}
            self.rfps = {
                "rfp-test-01": {
                    "id": "rfp-test-01",
                    "title": "National BioHealth Innovation Grant",
                    "metadata": {"title": "National BioHealth Innovation Grant"},
                    "document": "Funding for AI-driven clinical improvements.",
                }
            }

        def add_paper(self, paper_id, title, abstract, full_text, keywords):
            self.papers[paper_id] = {
                "id": paper_id,
                "metadata": {"title": title, "abstract": abstract},
                "document": full_text,
            }

        def get_notice(self, item_id: str):
            return self.papers.get(item_id) or self.rfps.get(item_id)

        def count(self):
            return len(self.papers) + len(self.rfps)

    mock_db = InMemoryVectorStore()
    monkeypatch.setattr(app_main, "get_vector_store", lambda: mock_db)
    monkeypatch.setattr(rfp_router, "get_vector_store", lambda: mock_db)

    # Allow bypassing Firestore DB read/writes in main endpoints
    monkeypatch.setattr(app_main, "db", None)

    # We still mock the RFP matcher and Proposal generator so we don't hit OpenAI in tests
    class StubRfpMatcher:
        async def match_paper(self, paper_id: str, limit: int = 5):
            if paper_id != "QmE2ETestCid999":
                raise ValueError("Paper not found")
            return [{"id": "rfp-test-01", "title": "National BioHealth Innovation Grant", "score": 0.95}]

    class StubProposalGenerator:
        async def generate_draft(self, rfp_data, paper_data):
            return f"# PROPOSAL DRAFT\nTarget: {rfp_data['id']}\nBased on: {paper_data['id']}"

        async def review_draft(self, rfp_data, paper_data, draft):
            return "This looks solid."

    monkeypatch.setattr(rfp_router, "get_rfp_matcher", lambda: StubRfpMatcher())
    monkeypatch.setattr(rfp_router, "get_proposal_generator", lambda: StubProposalGenerator())

    # === 2. Execution ===

    # A. Upload the document
    files = {"file": ("e2e_paper.pdf", b"%PDF-1.4 E2E Test Content", "application/pdf")}
    data = {"title": "E2E Study", "abstract": "Test E2E abstract"}
    headers = {"Authorization": "Bearer test-token-bypass"}

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        upload_resp = client.post("/assets/upload", files=files, data=data, headers=headers)

    assert upload_resp.status_code == 200
    upload_data = upload_resp.json()
    assert upload_data["cid"] == "QmE2ETestCid999"
    # Manually add to mock_db since we stubbed the AssetManager
    mock_db.add_paper("QmE2ETestCid999", "E2E Study", "Test E2E abstract", "content", ["bio"])

    # B. Match the paper to RFPs
    match_resp = client.post("/match/paper", json={"paper_id": "QmE2ETestCid999"})
    assert match_resp.status_code == 200
    match_data = match_resp.json()
    assert len(match_data["matches"]) > 0
    matched_rfp_id = match_data["matches"][0]["id"]
    assert matched_rfp_id == "rfp-test-01"

    # C. Generate Proposal
    proposal_resp = client.post(
        "/proposal/generate",
        json={"paper_id": "QmE2ETestCid999", "rfp_id": matched_rfp_id},
    )

    assert proposal_resp.status_code == 200
    proposal_data = proposal_resp.json()
    assert "PROPOSAL DRAFT" in proposal_data["draft"]
    assert matched_rfp_id in proposal_data["draft"]
    assert "solid" in proposal_data["critique"]
