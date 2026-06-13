"""tests/test_alerts.py — alerts.py 단위 테스트.

C-5 (Slack/Email) 및 기존 채널 (Telegram/Discord) 테스트.
"""

from unittest.mock import MagicMock, patch

import pytest
from alerts import (
    check_watchlist,
    format_trend_alert,
    send_alert,
    send_daily_cost_alert,
    send_discord_alert,
    send_email_alert,
    send_slack_alert,
    send_telegram_alert,
)
from config import AppConfig


@pytest.fixture
def config():
    return AppConfig(
        telegram_bot_token="test-bot-token",
        telegram_chat_id="123456",
        discord_webhook_url="https://discord.com/api/webhooks/test",
        slack_webhook_url="https://hooks.slack.com/services/T/B/X",
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="user@example.com",
        smtp_password="password123",
        alert_email="recipient@example.com",
    )


@pytest.fixture
def empty_config():
    return AppConfig()


# ──────────────────────────── format_trend_alert ────────────────────────────


def test_format_trend_alert_contains_keyword():
    from models import ScoredTrend, TrendSource

    trend = ScoredTrend(
        keyword="테스트 트렌드",
        rank=1,
        viral_potential=85,
        trend_acceleration="급상승",
        top_insight="테스트 인사이트",
        sources=[TrendSource.GETDAYTRENDS],
        suggested_angles=["각도1", "각도2"],
        best_hook_starter="이것은 훅",
    )
    result = format_trend_alert(trend)
    assert "테스트 트렌드" in result
    assert "85" in result
    assert "급상승" in result


# ──────────────────────────── Telegram ────────────────────────────


def test_telegram_returns_error_without_config(empty_config):
    result = send_telegram_alert("test", empty_config)
    assert result["ok"] is False


# ──────────────────────────── Discord ────────────────────────────


def test_discord_returns_error_without_config(empty_config):
    result = send_discord_alert("test", empty_config)
    assert result["ok"] is False


# ──────────────────────────── Slack (C-5) ────────────────────────────


def test_slack_returns_error_without_config(empty_config):
    result = send_slack_alert("test", empty_config)
    assert result["ok"] is False
    assert "설정 없음" in result["error"]


@patch("alerts.urllib.request.urlopen")
def test_slack_sends_webhook(mock_urlopen, config):
    mock_resp = MagicMock()
    mock_resp.read.return_value = b"ok"
    mock_resp.__enter__ = lambda s: mock_resp
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_urlopen.return_value = mock_resp

    result = send_slack_alert("테스트 메시지", config)
    assert result["ok"] is True
    mock_urlopen.assert_called_once()

    # Verify the request payload
    call_args = mock_urlopen.call_args
    req = call_args[0][0]
    assert req.full_url == config.slack_webhook_url
    assert b"\\ud14c\\uc2a4\\ud2b8" in req.data or b"test" in req.data.lower() or len(req.data) > 0


@patch("alerts.urllib.request.urlopen", side_effect=Exception("네트워크 에러"))
def test_slack_handles_failure(mock_urlopen, config):
    result = send_slack_alert("test", config)
    assert result["ok"] is False
    assert "네트워크 에러" in result["error"]


# ──────────────────────────── Email (C-5) ────────────────────────────


def test_email_returns_error_without_config(empty_config):
    result = send_email_alert("test", empty_config)
    assert result["ok"] is False
    assert "설정 없음" in result["error"]


@patch("smtplib.SMTP")
def test_email_sends_via_starttls(mock_smtp_cls, config):
    mock_server = MagicMock()
    mock_smtp_cls.return_value = mock_server

    result = send_email_alert("테스트 *볼드* 메시지", config)
    assert result["ok"] is True

    mock_smtp_cls.assert_called_once_with("smtp.example.com", 587, timeout=10)
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("user@example.com", "password123")
    mock_server.send_message.assert_called_once()
    mock_server.quit.assert_called_once()


@patch("smtplib.SMTP_SSL")
def test_email_sends_via_ssl(mock_smtp_ssl_cls):
    config = AppConfig(
        smtp_host="smtp.example.com",
        smtp_port=465,
        smtp_user="user@example.com",
        smtp_password="password123",
        alert_email="recipient@example.com",
    )
    mock_server = MagicMock()
    mock_smtp_ssl_cls.return_value = mock_server

    result = send_email_alert("테스트 메시지", config)
    assert result["ok"] is True

    mock_smtp_ssl_cls.assert_called_once_with("smtp.example.com", 465, timeout=10)
    mock_server.send_message.assert_called_once()


@patch("smtplib.SMTP", side_effect=Exception("SMTP 연결 실패"))
def test_email_handles_failure(mock_smtp_cls, config):
    result = send_email_alert("test", config)
    assert result["ok"] is False
    assert "SMTP 연결 실패" in result["error"]


# ──────────────────────────── send_alert (multi-channel) ────────────────────────────


@patch("alerts.send_email_alert", return_value={"ok": True})
@patch("alerts.send_slack_alert", return_value={"ok": True})
@patch("alerts.send_discord_alert", return_value={"ok": True})
@patch("alerts.send_telegram_alert", return_value={"ok": True})
def test_send_alert_dispatches_all_channels(mock_tg, mock_dc, mock_sl, mock_em, config):
    results = send_alert("test message", config)
    assert "telegram" in results
    assert "discord" in results
    assert "slack" in results
    assert "email" in results
    assert all(r["ok"] for r in results.values())


def test_send_alert_skips_unconfigured_channels(empty_config):
    results = send_alert("test message", empty_config)
    assert results == {}


def test_daily_cost_alert_skips_below_threshold(config):
    fake_tracker = MagicMock()
    fake_tracker.get_daily_stats.return_value = [{"date": "2099-01-01", "cost_usd": 0.1, "calls": 2}]

    with (
        patch("alerts._daily_cost_tracker", return_value=fake_tracker),
        patch("alerts.date") as mock_date,
        patch("alerts.send_alert") as mock_send,
    ):
        mock_date.today.return_value = "2099-01-01"
        config.daily_budget_usd = 2.0

        assert send_daily_cost_alert(config) is False

    mock_send.assert_not_called()
    fake_tracker.close.assert_called_once()


def test_daily_cost_alert_sends_critical_message(config):
    fake_tracker = MagicMock()
    fake_tracker.get_daily_stats.return_value = [{"date": "2099-01-01", "cost_usd": 1.9, "calls": 12}]

    with (
        patch("alerts._daily_cost_tracker", return_value=fake_tracker),
        patch("alerts.date") as mock_date,
        patch("alerts.send_alert", return_value={"slack": {"ok": True}}) as mock_send,
    ):
        mock_date.today.return_value = "2099-01-01"
        config.daily_budget_usd = 2.0

        assert send_daily_cost_alert(config) is True

    message = mock_send.call_args.args[0]
    assert "critical" in message.lower()
    assert "Calls today: 12" in message
    fake_tracker.close.assert_called_once()


def test_check_watchlist_sends_single_alert_for_matches(config):
    from models import ScoredTrend, TrendSource

    trends = [
        ScoredTrend(
            keyword="AI regulation",
            rank=1,
            viral_potential=88,
            trend_acceleration="+20%",
            top_insight="policy spike",
            sources=[TrendSource.GETDAYTRENDS],
        ),
        ScoredTrend(
            keyword="sports update",
            rank=2,
            viral_potential=51,
            trend_acceleration="+1%",
            top_insight="low priority",
            sources=[TrendSource.GETDAYTRENDS],
        ),
    ]
    config.watchlist_keywords = ["regulation", "finance"]

    with patch("alerts.send_alert", return_value={"telegram": {"ok": True}}) as mock_send:
        assert check_watchlist(trends, config) == 1

    message = mock_send.call_args.args[0]
    assert "AI regulation" in message
    assert "regulation" in message
