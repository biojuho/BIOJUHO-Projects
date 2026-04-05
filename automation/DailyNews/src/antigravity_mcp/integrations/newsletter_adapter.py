"""Newsletter delivery adapter using Resend API.

Converts ContentReport objects into adaptive HTML emails via Jinja2 templates
and delivers them to subscribers based on their category preferences.

Rate limits (Resend free tier):
  - 100 emails/day
  - 3,000 emails/month
  - 1 email/second burst

Required env vars:
  RESEND_API_KEY          Resend API key
  NEWSLETTER_FROM_EMAIL   Verified sender (e.g., daily@yourdomain.com)
  NEWSLETTER_FROM_NAME    Display name (default: "DailyNews")
  NEWSLETTER_SIGNUP_URL   Landing page URL for CTA injection

Optional:
  NEWSLETTER_REPLY_TO     Reply-to email for engagement
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from antigravity_mcp.config import emit_metric, get_settings
from antigravity_mcp.domain.models import ContentReport
from antigravity_mcp.integrations.subscriber_store import Subscriber, SubscriberStore

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates" / "newsletter"

# ---------------------------------------------------------------------------
# Resend client (lazy import to avoid hard dependency)
# ---------------------------------------------------------------------------

_resend: Any = None
_RESEND_AVAILABLE = False

try:
    import resend as _resend_module  # type: ignore[import-untyped]

    _resend = _resend_module
    _RESEND_AVAILABLE = True
except ImportError:
    logger.debug("resend not installed; newsletter delivery disabled. Run: pip install resend")


# ---------------------------------------------------------------------------
# Email Payload
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EmailPayload:
    """Rendered email ready for delivery."""

    subject: str
    html_body: str
    plain_text: str
    category: str = ""
    report_ids: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Composer -> ContentReport -> EmailPayload
# ---------------------------------------------------------------------------


class NewsletterComposer:
    """Converts ContentReport(s) into deliverable email payloads."""

    def __init__(self) -> None:
        self._env: Any = None

    def _get_jinja_env(self) -> Any:  # noqa: ANN401
        """Lazy-load Jinja2 environment."""
        if self._env is None:
            from jinja2 import Environment, FileSystemLoader, select_autoescape

            self._env = Environment(
                loader=FileSystemLoader(str(TEMPLATE_DIR)),
                autoescape=select_autoescape(["html"]),
            )
        return self._env

    def _render_template(self, template_name: str, **context: Any) -> str | None:
        """Render a Jinja template and return None when template access fails."""
        try:
            env = self._get_jinja_env()
            template = env.get_template(template_name)
            return template.render(**context)
        except Exception as exc:
            logger.warning("Template rendering failed for %s, using fallback: %s", template_name, exc)
            return None

    @staticmethod
    def _html_fallback_from_plain_text(plain_text: str) -> str:
        """Wrap plain text in minimal HTML when templates are unavailable."""
        return f"<pre>{plain_text}</pre>"

    @staticmethod
    def _welcome_html_fallback() -> str:
        """Return a static fallback used when the welcome template is unavailable."""
        return (
            "<h1>DailyNews에 오신 것을 환영합니다</h1>"
            "<p>매일 아침 핵심 뉴스와 인사이트를 메일로 보내드립니다.</p>"
            "<p>첫 브리프에서 경제, 테크, AI 흐름을 빠르게 확인해 보세요.</p>"
        )

    def _plain_text_from_reports(self, reports: list[ContentReport], edition: str) -> str:
        """Generate plain-text fallback for email clients that don't render HTML."""
        lines = [
            f"DailyNews {edition.title()} Brief",
            f"Date: {datetime.now(UTC).strftime('%Y-%m-%d')}",
            f"{len(reports)} category report(s)",
            "",
        ]
        for report in reports:
            lines.append(f"## {report.category}")
            for line in report.summary_lines[:3]:
                lines.append(f"- {line}")
            if report.insights:
                lines.append(f"Insight: {report.insights[0]}")
            lines.append("")
        lines.append("Thanks for subscribing to DailyNews.")
        return "\n".join(lines)

    def compose_daily_brief(
        self,
        reports: list[ContentReport],
        *,
        subscriber_categories: list[str] | None = None,
        edition: str = "morning",
        signup_url: str = "",
        unsubscribe_url: str = "",
        subscriber_email: str = "",
    ) -> EmailPayload:
        """Compose a daily brief email from multiple category reports."""
        if subscriber_categories:
            cat_set = set(subscriber_categories)
            filtered = [report for report in reports if report.category in cat_set]
            if not filtered:
                filtered = reports[:3]
        else:
            filtered = reports

        today_str = datetime.now(UTC).strftime("%Y-%m-%d")

        top_headline = ""
        if filtered and filtered[0].summary_lines:
            top_headline = filtered[0].summary_lines[0][:60]
        if top_headline:
            subject = f"[DailyNews] {today_str} {edition.title()} Brief | {top_headline}"
        else:
            subject = f"[DailyNews] {today_str} {edition.title()} Brief"

        x_discussion_url = ""
        for report in filtered:
            for draft in getattr(report, "channel_drafts", []):
                if getattr(draft, "channel", "") == "x" and getattr(draft, "external_url", ""):
                    x_discussion_url = draft.external_url
                    break
            if x_discussion_url:
                break

        plain_text = self._plain_text_from_reports(filtered, edition)
        html_body = self._html_fallback_from_plain_text(plain_text)

        rendered = self._render_template(
            "daily_brief.html",
            edition=edition,
            date=today_str,
            report_count=len(filtered),
            reports=filtered,
            x_discussion_url=x_discussion_url,
            signup_url=signup_url,
            unsubscribe_url=unsubscribe_url or "#unsubscribe",
            subscriber_email=subscriber_email,
        )
        if rendered:
            html_body = rendered

        return EmailPayload(
            subject=subject,
            html_body=html_body,
            plain_text=plain_text,
            category=",".join(report.category for report in filtered),
            report_ids=[report.report_id for report in filtered],
        )

    def compose_welcome_email(self, subscriber_email: str, *, signup_url: str = "") -> EmailPayload:
        """Compose onboarding email for new subscribers."""
        html_body = self._welcome_html_fallback()
        rendered = self._render_template(
            "welcome.html",
            subscriber_email=subscriber_email,
            signup_url=signup_url,
        )
        if rendered:
            html_body = rendered

        return EmailPayload(
            subject="[DailyNews] 구독을 환영합니다",
            html_body=html_body,
            plain_text="DailyNews 구독을 환영합니다. 매일 아침 핵심 뉴스와 인사이트를 전해드립니다.",
        )


# ---------------------------------------------------------------------------
# Adapter -> Sends emails via Resend
# ---------------------------------------------------------------------------


class NewsletterAdapter:
    """Sends emails via Resend API with rate limiting and metric tracking."""

    def __init__(
        self,
        *,
        composer: NewsletterComposer | None = None,
        subscriber_store: SubscriberStore | None = None,
    ) -> None:
        self.settings = get_settings()
        self.composer = composer or NewsletterComposer()
        self._subscriber_store = subscriber_store
        self._api_key = os.getenv("RESEND_API_KEY", "")
        self._from_email = os.getenv("NEWSLETTER_FROM_EMAIL", "")
        self._from_name = os.getenv("NEWSLETTER_FROM_NAME", "DailyNews")
        self._reply_to = os.getenv("NEWSLETTER_REPLY_TO", "")
        self._signup_url = os.getenv("NEWSLETTER_SIGNUP_URL", "")

    @property
    def is_configured(self) -> bool:
        """Check if Resend API key and sender email are set."""
        return bool(self._api_key and self._from_email)

    def _init_resend(self) -> None:
        """Initialize Resend client with API key."""
        if _RESEND_AVAILABLE and self._api_key:
            _resend.api_key = self._api_key

    async def send_single(
        self,
        to_email: str,
        payload: EmailPayload,
        *,
        dry_run: bool = False,
    ) -> dict[str, str]:
        """Send a single email via Resend API."""
        if dry_run:
            logger.info("[DRY RUN] Would send '%s' to %s", payload.subject, to_email)
            return {"status": "dry_run", "message_id": "", "subject": payload.subject}

        if not _RESEND_AVAILABLE:
            return {"status": "error", "message_id": "", "message": "resend not installed"}

        if not self.is_configured:
            return {"status": "error", "message_id": "", "message": "Newsletter not configured"}

        self._init_resend()

        try:
            params: dict[str, Any] = {
                "from_": f"{self._from_name} <{self._from_email}>",
                "to": [to_email],
                "subject": payload.subject,
                "html": payload.html_body,
                "text": payload.plain_text,
            }
            if self._reply_to:
                params["reply_to"] = self._reply_to

            response = await asyncio.to_thread(_resend.Emails.send, params)
            message_id = response.get("id", "") if isinstance(response, dict) else str(response)

            logger.info("Newsletter sent to %s [%s]", to_email, message_id)
            return {"status": "sent", "message_id": message_id}

        except Exception as exc:
            logger.error("Newsletter send failed for %s: %s", to_email, exc)
            return {"status": "error", "message_id": "", "message": str(exc)}

    async def send_daily_brief(
        self,
        reports: list[ContentReport],
        subscribers: list[Subscriber],
        *,
        edition: str = "morning",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Send daily brief to all active subscribers with adaptive content."""
        result = {"sent": 0, "failed": 0, "skipped": 0, "errors": [], "warnings": []}

        if not reports:
            logger.info("No reports to send as newsletter")
            return result

        if not subscribers:
            logger.info("No subscribers to send to")
            return result

        send_delay = 1.0

        for subscriber in subscribers:
            if not subscriber.is_active:
                result["skipped"] += 1
                continue

            try:
                payload = self.composer.compose_daily_brief(
                    reports,
                    subscriber_categories=subscriber.categories or None,
                    edition=edition,
                    signup_url=self._signup_url,
                    unsubscribe_url=f"{self._signup_url}/unsubscribe?email={subscriber.email}" if self._signup_url else "",
                    subscriber_email=subscriber.email,
                )

                send_result = await self.send_single(subscriber.email, payload, dry_run=dry_run)

                if send_result["status"] in ("sent", "dry_run"):
                    result["sent"] += 1
                    if self._subscriber_store and not dry_run:
                        try:
                            self._subscriber_store.record_event(
                                subscriber.id,
                                "delivered",
                                newsletter_id=",".join(payload.report_ids),
                            )
                        except Exception as exc:
                            warning = f"{subscriber.email}: audit record failed: {exc}"
                            result["warnings"].append(warning)
                            logger.warning(
                                "Newsletter audit record failed for %s after successful send: %s",
                                subscriber.email,
                                exc,
                            )
                else:
                    result["failed"] += 1
                    result["errors"].append(f"{subscriber.email}: {send_result.get('message', 'unknown')}")

                if not dry_run:
                    await asyncio.sleep(send_delay)

            except Exception as exc:
                result["failed"] += 1
                result["errors"].append(f"{subscriber.email}: {exc}")
                logger.warning("Newsletter delivery failed for %s: %s", subscriber.email, exc)

        emit_metric(
            "newsletter_delivery",
            edition=edition,
            sent=result["sent"],
            failed=result["failed"],
            skipped=result["skipped"],
            warning_count=len(result["warnings"]),
            total_subscribers=len(subscribers),
            report_count=len(reports),
        )

        logger.info(
            "Newsletter delivery complete: sent=%d failed=%d skipped=%d warnings=%d",
            result["sent"],
            result["failed"],
            result["skipped"],
            len(result["warnings"]),
        )
        return result

    async def send_welcome(
        self,
        subscriber: Subscriber,
        *,
        dry_run: bool = False,
    ) -> dict[str, str]:
        """Send welcome email to a new subscriber."""
        payload = self.composer.compose_welcome_email(
            subscriber.email,
            signup_url=self._signup_url,
        )
        return await self.send_single(subscriber.email, payload, dry_run=dry_run)

    async def process_webhook(self, event: dict[str, Any]) -> None:
        """Process Resend webhook for open/click tracking."""
        if not self._subscriber_store:
            logger.debug("No subscriber store; webhook event ignored")
            return

        event_type = event.get("type", "")
        data = event.get("data", {})
        to_email = ""

        if isinstance(data.get("to"), list) and data["to"]:
            to_email = data["to"][0]
        elif isinstance(data.get("to"), str):
            to_email = data["to"]

        if not to_email:
            return

        subscriber = self._subscriber_store.get_subscriber_by_email(to_email)
        if not subscriber:
            return

        if event_type == "email.opened":
            self._subscriber_store.update_engagement_score(subscriber.id, opened=True)
            self._subscriber_store.record_event(subscriber.id, "opened")
        elif event_type == "email.clicked":
            self._subscriber_store.update_engagement_score(subscriber.id, clicked=True)
            self._subscriber_store.record_event(subscriber.id, "clicked")
        elif event_type in ("email.bounced", "email.complained"):
            self._subscriber_store.unsubscribe(to_email)
            self._subscriber_store.record_event(subscriber.id, event_type)
            logger.warning("Auto-unsubscribed %s due to %s", to_email, event_type)
