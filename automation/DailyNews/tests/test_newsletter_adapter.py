"""Unit tests for newsletter composition, CTA injection, and delivery logic."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from antigravity_mcp.integrations.newsletter_adapter import (
    EmailPayload,
    NewsletterAdapter,
    NewsletterComposer,
)
from antigravity_mcp.integrations.subscriber_store import Subscriber, SubscriberStore
from antigravity_mcp.integrations.x_adapter import _inject_newsletter_cta


@pytest.fixture
def mock_subscriber() -> Subscriber:
    return Subscriber(
        id="sub-001",
        email="test@example.com",
        name="Alice",
        categories=["Economy_KR"],
        status="active",
    )


@pytest.fixture
def mock_report() -> MagicMock:
    report = MagicMock()
    report.report_id = "rpt-001"
    report.category = "Economy_KR"
    report.window_name = "morning"
    report.summary_lines = [
        "USD/KRW reaches a new local high",
        "Base rate remains unchanged",
        "Large-cap tech earnings arrive this week",
    ]
    report.insights = ["Rate pause keeps liquidity expectations steady."]
    report.channel_drafts = []
    return report


@pytest.fixture
def store(tmp_path: Path) -> SubscriberStore:
    return SubscriberStore(db_path=tmp_path / "test.db")


class TestNewsletterComposer:
    def test_compose_daily_brief_basic(self, mock_report: MagicMock) -> None:
        composer = NewsletterComposer()
        payload = composer.compose_daily_brief(
            reports=[mock_report],
            edition="morning",
        )
        assert isinstance(payload, EmailPayload)
        assert "DailyNews" in payload.subject
        assert payload.plain_text
        assert "Economy_KR" in payload.category

    def test_compose_daily_brief_filters_categories(self, mock_report: MagicMock) -> None:
        tech_report = MagicMock()
        tech_report.category = "Tech"
        tech_report.summary_lines = ["AI chip demand accelerates"]
        tech_report.insights = []
        tech_report.channel_drafts = []
        tech_report.report_id = "rpt-002"

        composer = NewsletterComposer()
        payload = composer.compose_daily_brief(
            reports=[mock_report, tech_report],
            subscriber_categories=["Tech"],
            edition="morning",
        )
        assert "Tech" in payload.category
        assert "rpt-002" in payload.report_ids

    def test_compose_daily_brief_falls_back_when_jinja_env_unavailable(
        self,
        mock_report: MagicMock,
    ) -> None:
        composer = NewsletterComposer()
        with patch.object(composer, "_get_jinja_env", side_effect=ImportError("jinja2 missing")):
            payload = composer.compose_daily_brief(
                reports=[mock_report],
                edition="morning",
            )

        assert payload.html_body.startswith("<pre>")
        assert payload.plain_text in payload.html_body

    def test_compose_welcome_email(self) -> None:
        composer = NewsletterComposer()
        payload = composer.compose_welcome_email("new@example.com")
        assert "환영" in payload.subject
        assert payload.html_body
        assert payload.plain_text

    def test_compose_welcome_email_falls_back_when_template_load_fails(self) -> None:
        composer = NewsletterComposer()
        env = MagicMock()
        env.get_template.side_effect = RuntimeError("template missing")

        with patch.object(composer, "_get_jinja_env", return_value=env):
            payload = composer.compose_welcome_email("new@example.com")

        assert "환영" in payload.subject
        assert "DailyNews" in payload.html_body
        assert payload.plain_text


class TestCTAInjection:
    def test_injects_when_space_allows(self) -> None:
        short_content = "Short tweet"
        with patch.dict("os.environ", {"NEWSLETTER_CTA_ENABLED": "1"}):
            result = _inject_newsletter_cta(short_content, signup_url="https://example.com/sub")
        assert "https://example.com/sub" in result
        assert len(result) <= 280

    def test_skips_when_too_long(self) -> None:
        long_content = "A" * 260
        result = _inject_newsletter_cta(long_content, signup_url="https://example.com/sub")
        assert result == long_content

    def test_skips_when_no_url(self) -> None:
        content = "Some tweet"
        with patch.dict("os.environ", {}, clear=True):
            result = _inject_newsletter_cta(content, signup_url="")
        assert result == content


class TestNewsletterAdapter:
    def test_is_configured_false_by_default(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            adapter = NewsletterAdapter()
            assert not adapter.is_configured

    def test_is_configured_true(self) -> None:
        env = {"RESEND_API_KEY": "re_123", "NEWSLETTER_FROM_EMAIL": "daily@example.com"}
        with patch.dict("os.environ", env, clear=False):
            adapter = NewsletterAdapter()
            assert adapter.is_configured

    @pytest.mark.asyncio
    async def test_send_single_dry_run(self) -> None:
        adapter = NewsletterAdapter()
        payload = EmailPayload(
            subject="Test",
            html_body="<h1>Hello</h1>",
            plain_text="Hello",
        )
        result = await adapter.send_single("test@example.com", payload, dry_run=True)
        assert result["status"] == "dry_run"

    @pytest.mark.asyncio
    async def test_send_daily_brief_dry_run(
        self,
        mock_report: MagicMock,
        mock_subscriber: Subscriber,
    ) -> None:
        adapter = NewsletterAdapter()
        result = await adapter.send_daily_brief(
            reports=[mock_report],
            subscribers=[mock_subscriber],
            edition="morning",
            dry_run=True,
        )
        assert result["sent"] == 1
        assert result["failed"] == 0
        assert result["warnings"] == []

    @pytest.mark.asyncio
    async def test_send_daily_brief_skips_inactive(
        self,
        mock_report: MagicMock,
    ) -> None:
        inactive = Subscriber(
            id="sub-002",
            email="inactive@example.com",
            status="unsubscribed",
        )
        adapter = NewsletterAdapter()
        result = await adapter.send_daily_brief(
            reports=[mock_report],
            subscribers=[inactive],
            dry_run=True,
        )
        assert result["sent"] == 0
        assert result["skipped"] == 1

    @pytest.mark.asyncio
    async def test_send_daily_brief_empty_reports(
        self,
        mock_subscriber: Subscriber,
    ) -> None:
        adapter = NewsletterAdapter()
        result = await adapter.send_daily_brief(
            reports=[],
            subscribers=[mock_subscriber],
            dry_run=True,
        )
        assert result["sent"] == 0

    @pytest.mark.asyncio
    async def test_send_welcome_dry_run(self, mock_subscriber: Subscriber) -> None:
        adapter = NewsletterAdapter()
        result = await adapter.send_welcome(mock_subscriber, dry_run=True)
        assert result["status"] == "dry_run"

    @pytest.mark.asyncio
    async def test_send_daily_brief_keeps_sent_when_audit_record_fails(
        self,
        mock_report: MagicMock,
        mock_subscriber: Subscriber,
        store: SubscriberStore,
    ) -> None:
        adapter = NewsletterAdapter(subscriber_store=store)

        with (
            patch.object(
                adapter,
                "send_single",
                new=AsyncMock(return_value={"status": "sent", "message_id": "msg-001"}),
            ),
            patch.object(store, "record_event", side_effect=RuntimeError("sqlite busy")),
            patch("antigravity_mcp.integrations.newsletter_adapter.asyncio.sleep", new=AsyncMock()),
        ):
            result = await adapter.send_daily_brief(
                reports=[mock_report],
                subscribers=[mock_subscriber],
                edition="morning",
                dry_run=False,
            )

        assert result["sent"] == 1
        assert result["failed"] == 0
        assert result["errors"] == []
        assert len(result["warnings"]) == 1
        assert "audit record failed" in result["warnings"][0]
