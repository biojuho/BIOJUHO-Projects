"""Tests for the alert-channel preflight (injected fetcher; no network)."""

from types import SimpleNamespace

from scripts.check_alert_channels import check_discord, check_telegram, run


class TestCheckTelegram:
    def test_valid_token(self):
        res = check_telegram("tok", lambda url: (200, '{"ok": true, "result": {}}'))
        assert res["ok"] is True and res["status"] == "valid"

    def test_revoked_token(self):
        res = check_telegram("tok", lambda url: (401, '{"ok": false}'))
        assert res["ok"] is False and res["status"] == "auth_failed"

    def test_unreachable(self):
        res = check_telegram("tok", lambda url: (0, "dns error"))
        assert res["ok"] is False and res["status"] == "unreachable"

    def test_url_targets_getme_not_sendmessage(self):
        captured = {}

        def fetch(url):
            captured["url"] = url
            return 200, '{"ok": true}'

        check_telegram("tok", fetch)
        assert captured["url"].endswith("/getMe")
        assert "sendMessage" not in captured["url"]


class TestCheckDiscord:
    def test_valid_webhook(self):
        assert check_discord("https://discord/webhook", lambda url: (200, "{}"))["ok"] is True

    def test_dead_webhook(self):
        res = check_discord("https://discord/webhook", lambda url: (404, "not found"))
        assert res["ok"] is False and res["status"] == "auth_failed"


class TestRun:
    def test_passes_when_all_valid(self):
        cfg = SimpleNamespace(
            telegram_bot_token="t", telegram_chat_id="c", discord_webhook_url="https://d", slack_webhook_url=""
        )
        summary = run(cfg, fetch=lambda url: (200, '{"ok": true}'))
        assert summary["status"] == "pass"
        assert summary["configured"] is True

    def test_fails_when_a_channel_dead(self):
        cfg = SimpleNamespace(
            telegram_bot_token="t", telegram_chat_id="c", discord_webhook_url="https://d", slack_webhook_url=""
        )

        def fetch(url):
            return (401, "{}") if "telegram" in url else (200, "{}")

        summary = run(cfg, fetch=fetch)
        assert summary["status"] == "fail"
        assert "telegram" in summary["failed_channels"]

    def test_no_channels_configured(self):
        cfg = SimpleNamespace(telegram_bot_token="", telegram_chat_id="", discord_webhook_url="", slack_webhook_url="")
        summary = run(cfg, fetch=lambda url: (200, "{}"))
        assert summary["configured"] is False
        assert summary["status"] == "pass"
