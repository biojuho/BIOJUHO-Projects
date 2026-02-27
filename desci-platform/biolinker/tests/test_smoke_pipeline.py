from pathlib import Path
import sys
import asyncio

from fastapi.testclient import TestClient


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

import main as app_main
import warnings


def test_me_endpoint_with_test_token(monkeypatch):
    monkeypatch.setenv("ALLOW_TEST_BYPASS", "true")
    with TestClient(app_main.app) as client:
        response = client.get(
            "/me",
            headers={"Authorization": "Bearer test-token-bypass"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is True
    assert data["uid"] == "test-user-id"
    assert data["email"] == "test@example.com"


def test_upload_returns_cid_and_index_status(monkeypatch):
    class StubParser:
        def parse(self, content: bytes) -> str:  # noqa: ARG002
            return "biotechnology platform discovery biomarker pipeline"

    class StubIPFS:
        is_configured = False

        async def upload_file(self, file_path: str, metadata: dict):  # noqa: ARG002
            return {
                "cid": "QmUnitTestCid123",
                "url": "https://gateway.pinata.cloud/ipfs/QmUnitTestCid123",
            }

        async def close(self):
            return None

    class StubVectorStore:
        def __init__(self):
            self.saved = []

        def add_paper(self, paper_id, title, abstract, full_text, keywords):
            self.saved.append(
                {
                    "paper_id": paper_id,
                    "title": title,
                    "abstract": abstract,
                    "full_text": full_text,
                    "keywords": keywords,
                }
            )

    stub_store = StubVectorStore()

    import services.pdf_parser as pdf_parser_module

    monkeypatch.setattr(pdf_parser_module, "get_pdf_parser", lambda: StubParser())
    monkeypatch.setattr(app_main, "get_ipfs_service", lambda: StubIPFS())
    monkeypatch.setattr(app_main, "get_vector_store", lambda: stub_store)

    files = {"file": ("paper.pdf", b"%PDF-1.4 test", "application/pdf")}
    data = {"title": "Unit Test Paper", "abstract": "Test abstract"}
    headers = {"Authorization": "Bearer test-token-bypass"}

    with TestClient(app_main.app) as client:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            response = client.post("/upload", files=files, data=data, headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["cid"] == "QmUnitTestCid123"
    assert payload["analysis"]["status"] == "indexed"
    assert len(stub_store.saved) == 1
    assert stub_store.saved[0]["paper_id"] == "QmUnitTestCid123"


def test_match_to_proposal_flow(monkeypatch):
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

    monkeypatch.setattr(app_main, "get_rfp_matcher", lambda: StubMatcher())
    monkeypatch.setattr(app_main, "get_vector_store", lambda: StubVectorStore())
    monkeypatch.setattr(app_main, "get_proposal_generator", lambda: StubProposalGenerator())

    with TestClient(app_main.app) as client:
        match_res = client.post("/match/paper", json={"paper_id": "paper-1"})
        proposal_res = client.post(
            "/proposal/generate",
            json={"paper_id": "paper-1", "rfp_id": "rfp-1"},
        )

    assert match_res.status_code == 200
    assert match_res.json()["matches"][0]["id"] == "rfp-1"
    assert proposal_res.status_code == 200
    assert proposal_res.json()["draft"] == "DRAFT::rfp-1::paper-1"


def test_health_degraded_when_vector_store_fails(monkeypatch):
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


def test_proposal_generator_fallback_without_llm():
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


def test_papers_me_returns_empty_when_mock_mode_off_and_db_unavailable(monkeypatch):
    monkeypatch.setenv("ALLOW_TEST_BYPASS", "true")
    monkeypatch.setattr(app_main, "MOCK_MODE", False)
    monkeypatch.setattr(app_main, "db", None)

    with TestClient(app_main.app) as client:
        response = client.get(
            "/papers/me",
            headers={"Authorization": "Bearer test-token-bypass"},
        )

    assert response.status_code == 200
    assert response.json() == []


def test_papers_me_returns_mock_seed_when_mock_mode_on(monkeypatch):
    monkeypatch.setenv("ALLOW_TEST_BYPASS", "true")
    monkeypatch.setattr(app_main, "MOCK_MODE", True)
    monkeypatch.setattr(app_main, "db", None)

    with TestClient(app_main.app) as client:
        response = client.get(
            "/papers/me",
            headers={"Authorization": "Bearer test-token-bypass"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert any(item.get("title") == "AI-Driven Drug Discovery Framework" for item in payload)
    assert any(item.get("cid") == "QmXyZ..." for item in payload)


def test_transactions_returns_empty_when_mock_mode_off_and_db_unavailable(monkeypatch):
    address = "0x1111111111111111111111111111111111111111"
    monkeypatch.setattr(app_main, "MOCK_MODE", False)
    monkeypatch.setattr(app_main, "db", None)

    with TestClient(app_main.app) as client:
        response = client.get(f"/transactions/{address}")

    assert response.status_code == 200
    assert response.json() == []


def test_transactions_returns_mock_seed_when_mock_mode_on(monkeypatch):
    address = "0x2222222222222222222222222222222222222222"
    monkeypatch.setattr(app_main, "MOCK_MODE", True)
    monkeypatch.setattr(app_main, "db", None)

    with TestClient(app_main.app) as client:
        response = client.get(f"/transactions/{address}")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 3
    assert all(item.get("address") == address for item in payload)


def test_wallet_balance_contract_when_mock_mode_off_returns_error_payload(monkeypatch):
    class StubWeb3:
        async def get_balance(self, address: str):  # noqa: ARG002
            return {"error": "Web3 service not available or token contract not configured"}

    monkeypatch.setattr(app_main, "MOCK_MODE", False)
    monkeypatch.setattr(app_main, "get_web3_service", lambda: StubWeb3())

    with TestClient(app_main.app) as client:
        response = client.get("/wallet/0x3333333333333333333333333333333333333333")

    assert response.status_code == 200
    payload = response.json()
    assert "error" in payload


def test_wallet_balance_contract_when_mock_mode_on_returns_mock_payload(monkeypatch):
    class StubWeb3:
        async def get_balance(self, address: str):
            return {
                "address": address,
                "balance": "123",
                "balance_wei": str(123 * 10**18),
                "symbol": "DSCI",
                "_mock": True,
            }

    monkeypatch.setattr(app_main, "MOCK_MODE", True)
    monkeypatch.setattr(app_main, "get_web3_service", lambda: StubWeb3())

    with TestClient(app_main.app) as client:
        response = client.get("/wallet/0x4444444444444444444444444444444444444444")

    assert response.status_code == 200
    payload = response.json()
    assert payload.get("_mock") is True


def test_web3_service_reward_amounts_returns_error_when_mock_mode_off(monkeypatch):
    import services.web3_service as web3_module

    monkeypatch.setattr(web3_module, "MOCK_MODE", False)
    service = web3_module.Web3Service()
    service.token_contract = None

    result = asyncio.run(service.get_reward_amounts())
    assert "error" in result
