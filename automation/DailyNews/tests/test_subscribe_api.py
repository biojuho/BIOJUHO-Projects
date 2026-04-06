"""Unit tests for subscribe_api handler and request boundary behavior."""

from __future__ import annotations

from pathlib import Path
import shutil
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from antigravity_mcp.integrations.subscriber_store import SubscriberStore


class _FakeRequest:
    def __init__(self, payload=None, *, side_effect: Exception | None = None) -> None:
        self._payload = payload
        self._side_effect = side_effect

    async def json(self):
        if self._side_effect is not None:
            raise self._side_effect
        return self._payload


@pytest.fixture
def tmp_path() -> Path:
    tmp_root = Path("D:/AI project/.test-tmp")
    tmp_root.mkdir(parents=True, exist_ok=True)
    path = tmp_root / f"subscribe-api-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def store(tmp_path: Path) -> SubscriberStore:
    return SubscriberStore(db_path=tmp_path / "test_subscribe_api.db")


@pytest.fixture(autouse=True)
def _patch_singletons(store: SubscriberStore):
    with patch(
        "antigravity_mcp.apps.subscribe_api._get_store",
        return_value=store,
    ), patch(
        "antigravity_mcp.apps.subscribe_api._get_adapter",
    ) as mock_adapter_fn:
        adapter = MagicMock()
        adapter.send_welcome = AsyncMock(return_value={"status": "dry_run"})
        mock_adapter_fn.return_value = adapter
        yield adapter


class TestHandleSubscribeHappyPath:
    @pytest.mark.asyncio
    async def test_new_subscriber_returns_ok(self, store: SubscriberStore) -> None:
        from antigravity_mcp.apps.subscribe_api import handle_subscribe

        result = await handle_subscribe("fresh@example.com")

        assert result["ok"] is True
        assert "구독" in result["message"]

        sub = store.get_subscriber_by_email("fresh@example.com")
        assert sub is not None
        assert sub.is_active

    @pytest.mark.asyncio
    async def test_email_is_normalized(self, store: SubscriberStore) -> None:
        from antigravity_mcp.apps.subscribe_api import handle_subscribe

        result = await handle_subscribe("  UPPER@Example.COM  ")

        assert result["ok"] is True
        assert store.get_subscriber_by_email("upper@example.com") is not None

    @pytest.mark.asyncio
    async def test_welcome_email_is_attempted(self, _patch_singletons) -> None:
        from antigravity_mcp.apps.subscribe_api import handle_subscribe

        adapter = _patch_singletons
        await handle_subscribe("welcome@example.com")

        adapter.send_welcome.assert_awaited_once()


class TestHandleSubscribeEdgeCases:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("email", ["", "   ", "not-an-email", "name@localhost", "user name@example.com"])
    async def test_invalid_email_strings_are_rejected(self, email: str) -> None:
        from antigravity_mcp.apps.subscribe_api import handle_subscribe

        result = await handle_subscribe(email)

        assert result["ok"] is False
        assert result["error"] == "invalid_email"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("email", [None, [], {}, 123])
    async def test_invalid_email_types_are_rejected(self, email: object) -> None:
        from antigravity_mcp.apps.subscribe_api import handle_subscribe

        result = await handle_subscribe(email)

        assert result["ok"] is False
        assert result["error"] == "invalid_email"

    @pytest.mark.asyncio
    async def test_already_active_returns_duplicate_error(self, store: SubscriberStore) -> None:
        from antigravity_mcp.apps.subscribe_api import handle_subscribe

        store.add_subscriber("dup@example.com")
        result = await handle_subscribe("dup@example.com")

        assert result["ok"] is False
        assert result["error"] == "already_subscribed"

    @pytest.mark.asyncio
    async def test_reactivation_of_unsubscribed_user(self, store: SubscriberStore) -> None:
        from antigravity_mcp.apps.subscribe_api import handle_subscribe

        store.add_subscriber("comeback@example.com")
        store.unsubscribe("comeback@example.com")

        result = await handle_subscribe("comeback@example.com")

        assert result["ok"] is True
        sub = store.get_subscriber_by_email("comeback@example.com")
        assert sub is not None and sub.is_active

    @pytest.mark.asyncio
    async def test_welcome_email_failure_does_not_break_subscribe(
        self,
        _patch_singletons,
        store: SubscriberStore,
    ) -> None:
        from antigravity_mcp.apps.subscribe_api import handle_subscribe

        adapter = _patch_singletons
        adapter.send_welcome = AsyncMock(side_effect=RuntimeError("SMTP down"))

        result = await handle_subscribe("resilient@example.com")

        assert result["ok"] is True
        sub = store.get_subscriber_by_email("resilient@example.com")
        assert sub is not None and sub.is_active

    @pytest.mark.asyncio
    async def test_store_returning_none_on_add_returns_server_error(self, store: SubscriberStore) -> None:
        from antigravity_mcp.apps.subscribe_api import handle_subscribe

        with patch.object(store, "add_subscriber", return_value=None), patch.object(
            store,
            "get_subscriber_by_email",
            return_value=None,
        ):
            result = await handle_subscribe("ghost@example.com")

        assert result["ok"] is False
        assert result["error"] == "server_error"


class TestHandleUnsubscribe:
    @pytest.mark.asyncio
    async def test_existing_subscriber_unsubscribes(self, store: SubscriberStore) -> None:
        from antigravity_mcp.apps.subscribe_api import handle_unsubscribe

        store.add_subscriber("bye@example.com")
        result = await handle_unsubscribe("bye@example.com")

        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_nonexistent_email_returns_not_found(self) -> None:
        from antigravity_mcp.apps.subscribe_api import handle_unsubscribe

        result = await handle_unsubscribe("nobody@example.com")

        assert result["ok"] is False
        assert result["error"] == "not_found"

    @pytest.mark.asyncio
    async def test_email_is_normalized_on_unsubscribe(self, store: SubscriberStore) -> None:
        from antigravity_mcp.apps.subscribe_api import handle_unsubscribe

        store.add_subscriber("norm@example.com")
        result = await handle_unsubscribe("  NORM@Example.COM  ")

        assert result["ok"] is True

    @pytest.mark.asyncio
    @pytest.mark.parametrize("email", [None, [], "bad-email"])
    async def test_invalid_unsubscribe_input_is_rejected(self, email: object) -> None:
        from antigravity_mcp.apps.subscribe_api import handle_unsubscribe

        result = await handle_unsubscribe(email)

        assert result["ok"] is False
        assert result["error"] == "invalid_email"

    @pytest.mark.asyncio
    async def test_double_unsubscribe_is_idempotent(self, store: SubscriberStore) -> None:
        from antigravity_mcp.apps.subscribe_api import handle_unsubscribe

        store.add_subscriber("twice@example.com")
        first = await handle_unsubscribe("twice@example.com")
        second = await handle_unsubscribe("twice@example.com")

        assert first["ok"] is True
        assert second["ok"] is True


class TestRequestBoundary:
    @pytest.mark.asyncio
    async def test_read_email_from_request_normalizes_valid_payload(self) -> None:
        from antigravity_mcp.apps.subscribe_api import _read_email_from_request

        email, error = await _read_email_from_request(_FakeRequest({"email": "  USER@Example.com  "}))

        assert email == "user@example.com"
        assert error is None

    @pytest.mark.asyncio
    async def test_read_email_from_request_rejects_malformed_json(self) -> None:
        from antigravity_mcp.apps.subscribe_api import _read_email_from_request

        email, error = await _read_email_from_request(_FakeRequest(side_effect=ValueError("bad json")))

        assert email == ""
        assert error is not None
        assert error["error"] == "invalid_request"

    @pytest.mark.asyncio
    async def test_read_email_from_request_rejects_non_object_json(self) -> None:
        from antigravity_mcp.apps.subscribe_api import _read_email_from_request

        email, error = await _read_email_from_request(_FakeRequest(["user@example.com"]))

        assert email == ""
        assert error is not None
        assert error["error"] == "invalid_request"

    @pytest.mark.asyncio
    async def test_read_email_from_request_rejects_null_email(self) -> None:
        from antigravity_mcp.apps.subscribe_api import _read_email_from_request

        email, error = await _read_email_from_request(_FakeRequest({"email": None}))

        assert email == ""
        assert error is not None
        assert error["error"] == "invalid_email"

    def test_result_status_code_maps_expected_errors(self) -> None:
        from antigravity_mcp.apps.subscribe_api import _result_status_code

        assert _result_status_code({"ok": True}) == 200
        assert _result_status_code({"ok": False, "error": "already_subscribed"}) == 409
        assert _result_status_code({"ok": False, "error": "invalid_request"}) == 400
        assert _result_status_code({"ok": False, "error": "not_found"}, not_found_status=404) == 404

    def test_build_signal_feed_serializes_history(self) -> None:
        from antigravity_mcp.apps.subscribe_api import build_signal_feed

        records = [
            {
                "keyword": "OpenAI agents",
                "composite_score": 0.91,
                "sources": '["reddit","x_trending"]',
                "source_count": 2,
                "arbitrage_type": "early_wave",
                "recommended_action": "draft_now",
                "velocity": 0.84,
                "category_hint": "tech",
                "detected_at": "2026-04-06T03:15:00+00:00",
            }
        ]

        with patch("antigravity_mcp.apps.subscribe_api._load_signal_history", return_value=records):
            payload = build_signal_feed()

        assert payload["ok"] is True
        assert payload["status"] == "live"
        assert payload["count"] == 1
        assert payload["signals"][0]["sources"] == ["reddit", "x_trending"]
        assert payload["signals"][0]["type"] == "early_wave"
        assert payload["updated_at"] == "2026-04-06T03:15:00+00:00"

    def test_build_signal_feed_degrades_gracefully(self) -> None:
        from antigravity_mcp.apps.subscribe_api import build_signal_feed

        with patch(
            "antigravity_mcp.apps.subscribe_api._load_signal_history",
            side_effect=RuntimeError("db unavailable"),
        ):
            payload = build_signal_feed()

        assert payload["ok"] is True
        assert payload["status"] == "degraded"
        assert payload["signals"] == []


class TestFastApiEndpoints:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        from antigravity_mcp.apps.subscribe_api import create_fastapi_app

        return TestClient(create_fastapi_app())

    def test_subscribe_endpoint_accepts_valid_email(self, client, store: SubscriberStore) -> None:
        response = client.post("/api/subscribe", json={"email": "  API@Example.com  "})

        assert response.status_code == 200
        assert response.json()["ok"] is True
        assert store.get_subscriber_by_email("api@example.com") is not None

    def test_subscribe_endpoint_rejects_malformed_json(self, client) -> None:
        response = client.post(
            "/api/subscribe",
            content=b"{",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 400
        assert response.json()["error"] == "invalid_request"

    def test_subscribe_endpoint_rejects_non_object_json(self, client) -> None:
        response = client.post("/api/subscribe", json=["api@example.com"])

        assert response.status_code == 400
        assert response.json()["error"] == "invalid_request"

    def test_subscribe_endpoint_rejects_null_email(self, client) -> None:
        response = client.post("/api/subscribe", json={"email": None})

        assert response.status_code == 400
        assert response.json()["error"] == "invalid_email"

    def test_unsubscribe_endpoint_returns_not_found_for_missing_subscriber(self, client) -> None:
        response = client.post("/api/unsubscribe", json={"email": "missing@example.com"})

        assert response.status_code == 404
        assert response.json()["error"] == "not_found"

    def test_unsubscribe_endpoint_accepts_existing_email(self, client, store: SubscriberStore) -> None:
        store.add_subscriber("leave@example.com")

        response = client.post("/api/unsubscribe", json={"email": "  leave@example.com  "})

        assert response.status_code == 200
        assert response.json()["ok"] is True

    def test_root_serves_landing_page(self, client) -> None:
        response = client.get("/")

        assert response.status_code == 200
        assert "Signal Desk" in response.text
        assert "data-form-mode=\"unsubscribe\"" in response.text
        assert "placeholder=\"keyword, category, source\"" in response.text

    def test_signals_endpoint_returns_serialized_feed(self, client) -> None:
        with patch(
            "antigravity_mcp.apps.subscribe_api._load_signal_history",
            return_value=[
                {
                    "keyword": "HBM supply chain",
                    "composite_score": 0.88,
                    "sources": '["google_trends","getdaytrends","x_trending"]',
                    "source_count": 3,
                    "arbitrage_type": "major",
                    "recommended_action": "series",
                    "velocity": 0.93,
                    "category_hint": "semiconductors",
                    "detected_at": "2026-04-06T04:00:00+00:00",
                }
            ],
        ):
            response = client.get("/api/signals?hours=24&limit=5&min_score=0.4")

        body = response.json()
        assert response.status_code == 200
        assert body["status"] == "live"
        assert body["count"] == 1
        assert body["signals"][0]["keyword"] == "HBM supply chain"
        assert body["signals"][0]["sources"] == ["google_trends", "getdaytrends", "x_trending"]


class TestSubscribeLifecycle:
    @pytest.mark.asyncio
    async def test_full_lifecycle(self, store: SubscriberStore) -> None:
        from antigravity_mcp.apps.subscribe_api import handle_subscribe, handle_unsubscribe

        r1 = await handle_subscribe("lifecycle@example.com")
        r2 = await handle_subscribe("lifecycle@example.com")
        r3 = await handle_unsubscribe("lifecycle@example.com")
        r4 = await handle_subscribe("lifecycle@example.com")

        assert r1["ok"] is True
        assert r2["ok"] is False
        assert r2["error"] == "already_subscribed"
        assert r3["ok"] is True
        assert r4["ok"] is True

        sub = store.get_subscriber_by_email("lifecycle@example.com")
        assert sub is not None and sub.is_active
