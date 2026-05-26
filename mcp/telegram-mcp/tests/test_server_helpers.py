from __future__ import annotations

import pytest
import server


def test_get_config_requires_token_and_chat(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    with pytest.raises(ValueError):
        server._get_config()


@pytest.mark.asyncio
async def test_send_returns_config_error_without_credentials(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    result = await server._send("hello")

    assert result["ok"] is False
    assert "TELEGRAM_BOT_TOKEN" in result["error"]


@pytest.mark.asyncio
async def test_send_alert_formats_level(monkeypatch):
    sent: dict[str, str] = {}

    async def fake_send(text: str, parse_mode: str = "Markdown", reply_markup: dict | None = None) -> dict:
        sent["text"] = text
        sent["parse_mode"] = parse_mode
        assert reply_markup is None
        return {"ok": True, "message_id": 1}

    monkeypatch.setattr(server, "_send", fake_send)

    result = await server.send_alert("Build", "Finished", level="warning")

    assert result == {"ok": True, "message_id": 1}
    assert "[WARNING]" in sent["text"]
    assert "Build" in sent["text"]


@pytest.mark.asyncio
async def test_get_updates_clamps_limit_and_normalizes_messages(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat")

    async def fake_call_api(method: str, payload: dict) -> dict:
        assert method == "getUpdates"
        assert payload["limit"] == 100
        return {
            "ok": True,
            "result": [
                {"update_id": 1, "message": {"from": {"first_name": "A"}, "text": "hi", "date": 1}},
                {"update_id": 2, "callback_query": {"from": {"first_name": "B"}, "data": "ok"}},
            ],
        }

    monkeypatch.setattr(server, "_call_api", fake_call_api)

    result = await server.get_updates(limit=999)

    assert result["ok"] is True
    assert result["updates"][0]["type"] == "message"
    assert result["updates"][1]["type"] == "callback_query"
