from __future__ import annotations

import asyncio
import json

import main as app_main  # noqa: E402
import pytest
import routers.jobs as jobs_router  # noqa: E402
import services.auth as auth_module  # noqa: E402
from httpx import ASGITransport, AsyncClient


async def wait_for_terminal_job(client: AsyncClient, job_id: str, timeout: float = 2.0) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        response = await client.get(f"/jobs/{job_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"succeeded", "failed"}:
            return payload
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"Job {job_id} did not complete within {timeout} seconds")
        await asyncio.sleep(0.02)


@pytest.mark.asyncio
async def test_notice_collection_job_completes_and_is_public(async_client: AsyncClient, monkeypatch):
    class StubScheduler:
        async def collect_all_notices(self):
            return [
                {"id": "n1", "title": "Notice 1", "source": "KDDF"},
                {"id": "n2", "title": "Notice 2", "source": "NTIS"},
            ]

    monkeypatch.setattr(jobs_router, "get_scheduler", lambda: StubScheduler())

    create_response = await async_client.post("/jobs/notices/collect")

    assert create_response.status_code == 200
    job = create_response.json()["job"]
    assert job["type"] == "notice_collection"
    assert job["status"] in {"queued", "running", "succeeded"}

    terminal = await wait_for_terminal_job(async_client, job["id"])
    assert terminal["status"] == "succeeded"
    assert terminal["partial"] is False
    assert terminal["result"]["collected"] == 2

    transport = ASGITransport(app=app_main.app)
    async with AsyncClient(transport=transport, base_url="http://test") as public_client:
        public_response = await public_client.get(f"/jobs/{job['id']}")

    assert public_response.status_code == 200
    assert public_response.json()["id"] == job["id"]


@pytest.mark.asyncio
async def test_notice_collection_job_streams_terminal_snapshot(async_client: AsyncClient, monkeypatch):
    class StubScheduler:
        async def collect_all_notices(self):
            return [{"id": "n1", "title": "Notice 1", "source": "KDDF"}]

    monkeypatch.setattr(jobs_router, "get_scheduler", lambda: StubScheduler())

    create_response = await async_client.post("/jobs/notices/collect")
    job_id = create_response.json()["job"]["id"]

    events = []
    async with async_client.stream("GET", f"/jobs/{job_id}/events") as response:
        assert response.status_code == 200
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

    assert any(event["status"] == "succeeded" for event in events)
    assert all(event["partial"] is True for event in events[:-1])
    assert events[-1]["partial"] is False
    assert events[-1]["result"]["collected"] == 1


@pytest.mark.asyncio
async def test_terminal_job_streams_snapshot_for_late_subscriber(async_client: AsyncClient, monkeypatch):
    class StubScheduler:
        async def collect_all_notices(self):
            return [{"id": "n1", "title": "Notice 1", "source": "KDDF"}]

    monkeypatch.setattr(jobs_router, "get_scheduler", lambda: StubScheduler())

    create_response = await async_client.post("/jobs/notices/collect")
    job_id = create_response.json()["job"]["id"]
    terminal = await wait_for_terminal_job(async_client, job_id)
    assert terminal["status"] == "succeeded"

    events = []
    async with async_client.stream("GET", f"/jobs/{job_id}/events") as response:
        assert response.status_code == 200
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

    assert [event["status"] for event in events] == ["succeeded"]
    assert [event["partial"] for event in events] == [False]
    assert events[0]["result"]["collected"] == 1


@pytest.mark.asyncio
async def test_paper_index_job_requires_auth(mock_external_services, monkeypatch):
    class StubAssetManager:
        def has_paper(self, paper_id: str) -> bool:  # noqa: ARG002
            return True

        def get_paper_owner_uid(self, paper_id: str) -> str | None:  # noqa: ARG002
            return "test-user-id"

    monkeypatch.setattr(jobs_router, "get_asset_manager", lambda: StubAssetManager())

    transport = ASGITransport(app=app_main.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/jobs/papers/index", json={"paper_id": "paper-1"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_paper_index_job_rejects_non_owner(async_client: AsyncClient, monkeypatch):
    class StubAssetManager:
        def has_paper(self, paper_id: str) -> bool:  # noqa: ARG002
            return True

        def get_paper_owner_uid(self, paper_id: str) -> str | None:  # noqa: ARG002
            return "another-user"

    monkeypatch.setattr(jobs_router, "get_asset_manager", lambda: StubAssetManager())

    response = await async_client.post("/jobs/papers/index", json={"paper_id": "paper-1"})

    assert response.status_code == 403
    assert response.json()["detail"] == "You do not have access to this paper"


@pytest.mark.asyncio
async def test_paper_match_job_validates_required_fields(async_client: AsyncClient):
    response = await async_client.post("/jobs/match/paper", json={})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_paper_match_job_completes_for_owned_paper(async_client: AsyncClient, monkeypatch):
    class StubAssetManager:
        def has_paper(self, paper_id: str) -> bool:  # noqa: ARG002
            return True

        def get_paper_owner_uid(self, paper_id: str) -> str | None:  # noqa: ARG002
            return "test-user-id"

    class StubVectorStore:
        def get_notice(self, notice_id: str):
            if notice_id == "paper-1":
                return {
                    "id": "paper-1",
                    "metadata": {"owner_uid": "test-user-id", "title": "Paper One"},
                    "document": "paper content",
                }
            return None

    class StubMatcher:
        async def match_paper(self, paper_id: str, limit: int = 5, target_trl=None, enrich: bool = False):  # noqa: ANN001, ARG002
            assert paper_id == "paper-1"
            assert limit == 3
            return [{"id": "rfp-1", "score": 0.91, "title": "Grant A"}]

    monkeypatch.setattr(jobs_router, "get_asset_manager", lambda: StubAssetManager())
    monkeypatch.setattr(jobs_router, "get_vector_store", lambda: StubVectorStore())
    monkeypatch.setattr(jobs_router, "get_rfp_matcher", lambda: StubMatcher())

    create_response = await async_client.post(
        "/jobs/match/paper",
        json={"paper_id": "paper-1", "limit": 3, "enrich": True},
    )

    assert create_response.status_code == 200
    job_id = create_response.json()["job"]["id"]
    terminal = await wait_for_terminal_job(async_client, job_id)
    assert terminal["status"] == "succeeded"
    assert terminal["result"]["matches"][0]["id"] == "rfp-1"


@pytest.mark.asyncio
async def test_private_job_status_forbids_other_users(async_client: AsyncClient, monkeypatch):
    class StubAssetManager:
        def has_paper(self, paper_id: str) -> bool:  # noqa: ARG002
            return True

        def get_paper_owner_uid(self, paper_id: str) -> str | None:  # noqa: ARG002
            return "test-user-id"

    class StubVectorStore:
        def get_notice(self, notice_id: str):
            if notice_id == "paper-1":
                return {
                    "id": "paper-1",
                    "metadata": {"owner_uid": "test-user-id", "title": "Paper One"},
                    "document": "paper content",
                }
            return None

    class StubMatcher:
        async def match_paper(self, paper_id: str, limit: int = 5, target_trl=None, enrich: bool = False):  # noqa: ANN001, ARG002
            return [{"id": "rfp-1"}]

    async def other_user():
        return {"uid": "other-user", "email": "other@example.com", "name": "Other User"}

    monkeypatch.setattr(jobs_router, "get_asset_manager", lambda: StubAssetManager())
    monkeypatch.setattr(jobs_router, "get_vector_store", lambda: StubVectorStore())
    monkeypatch.setattr(jobs_router, "get_rfp_matcher", lambda: StubMatcher())

    create_response = await async_client.post("/jobs/match/paper", json={"paper_id": "paper-1"})
    job_id = create_response.json()["job"]["id"]

    app_main.app.dependency_overrides[auth_module.get_optional_current_user] = other_user
    response = await async_client.get(f"/jobs/{job_id}")

    assert response.status_code == 403
    assert response.json()["detail"] == "You do not have access to this job"


@pytest.mark.asyncio
async def test_proposal_generation_job_returns_404_for_missing_rfp(async_client: AsyncClient, monkeypatch):
    class StubAssetManager:
        def has_paper(self, paper_id: str) -> bool:  # noqa: ARG002
            return True

        def get_paper_owner_uid(self, paper_id: str) -> str | None:  # noqa: ARG002
            return "test-user-id"

    class StubVectorStore:
        def get_notice(self, notice_id: str):
            if notice_id == "paper-1":
                return {
                    "id": "paper-1",
                    "metadata": {"owner_uid": "test-user-id", "title": "Paper One"},
                    "document": "paper content",
                }
            return None

    monkeypatch.setattr(jobs_router, "get_asset_manager", lambda: StubAssetManager())
    monkeypatch.setattr(jobs_router, "get_vector_store", lambda: StubVectorStore())

    response = await async_client.post(
        "/jobs/proposal/generate",
        json={"paper_id": "paper-1", "rfp_id": "missing-rfp"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "RFP not found"


@pytest.mark.asyncio
async def test_proposal_generation_job_completes(async_client: AsyncClient, monkeypatch):
    class StubAssetManager:
        def has_paper(self, paper_id: str) -> bool:  # noqa: ARG002
            return True

        def get_paper_owner_uid(self, paper_id: str) -> str | None:  # noqa: ARG002
            return "test-user-id"

    class StubVectorStore:
        def get_notice(self, notice_id: str):
            if notice_id == "paper-1":
                return {
                    "id": "paper-1",
                    "metadata": {"owner_uid": "test-user-id", "title": "Paper One", "abstract": "Summary"},
                    "document": "paper content",
                }
            if notice_id == "rfp-1":
                return {
                    "id": "rfp-1",
                    "title": "Grant A",
                    "metadata": {"title": "Grant A"},
                    "document": "rfp body",
                }
            return None

    class StubProposalGenerator:
        async def generate_draft(self, rfp_data: dict, paper_data: dict) -> str:
            return f"DRAFT::{rfp_data['id']}::{paper_data['id']}"

        async def review_draft(self, rfp_data: dict, paper_data: dict, draft: str) -> str:  # noqa: ARG002
            return "REVIEW_OK"

    monkeypatch.setattr(jobs_router, "get_asset_manager", lambda: StubAssetManager())
    monkeypatch.setattr(jobs_router, "get_vector_store", lambda: StubVectorStore())
    monkeypatch.setattr(jobs_router, "get_proposal_generator", lambda: StubProposalGenerator())

    create_response = await async_client.post(
        "/jobs/proposal/generate",
        json={"paper_id": "paper-1", "rfp_id": "rfp-1"},
    )

    assert create_response.status_code == 200
    terminal = await wait_for_terminal_job(async_client, create_response.json()["job"]["id"])
    assert terminal["status"] == "succeeded"
    assert terminal["result"]["draft"] == "DRAFT::rfp-1::paper-1"
    assert terminal["result"]["critique"] == "REVIEW_OK"
