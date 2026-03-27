"""Alert system — Slack, Email, and Discord notifications for pipeline events.

Usage:
    from notebooklm_automation.alerts import send_alert, AlertLevel

    await send_alert(AlertLevel.ERROR, "Pipeline failed", details={...})
"""

from __future__ import annotations

import os
from enum import Enum

import httpx
from loguru import logger as log

from .config import get_config


class AlertLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


_EMOJI_MAP = {
    AlertLevel.INFO: "✅",
    AlertLevel.WARNING: "⚠️",
    AlertLevel.ERROR: "🔴",
    AlertLevel.CRITICAL: "🚨",
}


async def send_alert(
    level: AlertLevel,
    title: str,
    *,
    details: dict | None = None,
    channels: list[str] | None = None,
) -> dict[str, bool]:
    """Send an alert to configured notification channels.

    Args:
        level: Alert severity level.
        title: Short alert title.
        details: Additional context (key-value pairs).
        channels: Override which channels to use. Defaults to all configured.

    Returns:
        ``{"slack": True/False, "email": True/False, "discord": True/False}``
    """
    cfg = get_config()
    results: dict[str, bool] = {}
    emoji = _EMOJI_MAP.get(level, "ℹ️")
    message = _format_message(emoji, level.value.upper(), title, details)

    # Determine which channels to use
    use_channels = channels or _detect_channels(cfg)

    if "slack" in use_channels:
        slack_url = os.getenv("SLACK_WEBHOOK_URL", "")
        if slack_url:
            results["slack"] = await _send_slack(slack_url, message)
        else:
            results["slack"] = False

    if "discord" in use_channels:
        discord_url = cfg.discord_webhook_url
        if discord_url:
            results["discord"] = await _send_discord(discord_url, message)
        else:
            results["discord"] = False

    if "email" in use_channels:
        results["email"] = await _send_email(title, message, level)

    log.info("[Alert] %s | %s | sent to: %s", level.value, title, results)
    return results


def _detect_channels(cfg) -> list[str]:
    """Auto-detect which channels are configured."""
    channels: list[str] = []
    if os.getenv("SLACK_WEBHOOK_URL"):
        channels.append("slack")
    if cfg.discord_webhook_url:
        channels.append("discord")
    if os.getenv("SMTP_HOST"):
        channels.append("email")
    return channels or ["slack"]  # default to slack


def _format_message(emoji: str, level: str, title: str, details: dict | None) -> str:
    """Format alert message."""
    lines = [f"{emoji} *[{level}] {title}*"]
    if details:
        for k, v in details.items():
            lines.append(f"  • {k}: {v}")
    return "\n".join(lines)


# ──────────────────────────────────────────────────
#  Channel Implementations
# ──────────────────────────────────────────────────

async def _send_slack(webhook_url: str, message: str) -> bool:
    """Send via Slack Incoming Webhook."""
    try:
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                webhook_url,
                json={"text": message},
                timeout=10,
            )
            resp.raise_for_status()
        return True
    except Exception as e:
        log.warning("[Alert/Slack] failed: %s", e)
        return False


async def _send_discord(webhook_url: str, message: str) -> bool:
    """Send via Discord Webhook."""
    try:
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                webhook_url,
                json={"content": message},
                timeout=10,
            )
            resp.raise_for_status()
        return True
    except Exception as e:
        log.warning("[Alert/Discord] failed: %s", e)
        return False


async def _send_email(subject: str, body: str, level: AlertLevel) -> bool:
    """Send via SMTP (if configured)."""
    smtp_host = os.getenv("SMTP_HOST", "")
    if not smtp_host:
        return False

    try:
        import smtplib
        from email.mime.text import MIMEText

        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER", "")
        smtp_pass = os.getenv("SMTP_PASS", "")
        to_email = os.getenv("ALERT_EMAIL", smtp_user)

        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = f"[{level.value.upper()}] {subject}"
        msg["From"] = smtp_user
        msg["To"] = to_email

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, [to_email], msg.as_string())

        return True
    except Exception as e:
        log.warning("[Alert/Email] failed: %s", e)
        return False
