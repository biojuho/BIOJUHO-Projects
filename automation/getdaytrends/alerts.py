"""
getdaytrends alert helpers.

This module intentionally keeps alert fan-out small and dependency-light so it
can be reused by the pipeline, TAP dispatch, and health checks.
"""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from datetime import date

from loguru import logger as log

try:
    from .config import AppConfig
    from .models import ScoredTrend
except ImportError:
    from config import AppConfig
    from models import ScoredTrend


def _escape_md(text: str) -> str:
    """Escape characters that break Telegram legacy Markdown parsing.

    Underscores in keywords like '버니즈는_언제나_다니편' otherwise trigger
    HTTP 400 from the Bot API.
    """
    if not text:
        return ""
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace("_", "\\_")
        .replace("*", "\\*")
        .replace("[", "\\[")
        .replace("`", "\\`")
    )


def format_trend_alert(trend: ScoredTrend) -> str:
    """Render one high-signal trend alert in a human-readable format."""

    angles = ", ".join(trend.suggested_angles[:3]) if trend.suggested_angles else "none"
    sources = ", ".join(getattr(source, "value", str(source)) for source in (trend.sources or [])) or "unknown"
    insight = trend.top_insight or "No summary available."
    acceleration = trend.trend_acceleration or "unknown"
    hook = trend.best_hook_starter or ""

    return (
        f"*High-viral trend detected!*\n"
        f"Topic: *{_escape_md(trend.keyword)}*\n"
        f"Viral score: {trend.viral_potential}/100\n"
        f"Acceleration: {_escape_md(acceleration)}\n"
        f"Insight: {_escape_md(insight)}\n"
        f"Angles: {_escape_md(angles)}\n"
        f"Sources: {_escape_md(sources)}\n"
        f"Hook: {_escape_md(hook)}"
    )


def send_telegram_alert(message: str, config: AppConfig) -> dict:
    """Send one message through the Telegram Bot API."""

    if not config.telegram_bot_token or not config.telegram_chat_id:
        return {"ok": False, "error": "Telegram 설정 없음"}

    url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage"
    payload = json.dumps(
        {
            "chat_id": config.telegram_chat_id,
            "text": message[:4096],
            "parse_mode": "Markdown",
        }
    ).encode("utf-8")

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        log.info("Telegram alert sent")
        return result
    except urllib.error.HTTPError as exc:  # pragma: no cover - network failure path
        # Capture the response body so 400/403 surface the real reason
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        log.error(f"Telegram send failed: HTTP {exc.code} {exc.reason} | body={body[:300]}")
        return {"ok": False, "error": f"HTTP {exc.code}: {body[:200]}"}
    except Exception as exc:  # pragma: no cover - network failure path
        log.error(f"Telegram send failed: {exc}")
        return {"ok": False, "error": str(exc)}


def send_discord_alert(message: str, config: AppConfig) -> dict:
    """Send one message through a Discord webhook."""

    if not config.discord_webhook_url:
        return {"ok": False, "error": "Discord 설정 없음"}

    payload = json.dumps({"content": message.replace("*", "**")[:2000]}).encode("utf-8")

    try:
        req = urllib.request.Request(
            config.discord_webhook_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "BIOJUHO-Notifier/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=10):
            pass
        log.info("Discord alert sent")
        return {"ok": True}
    except Exception as exc:  # pragma: no cover - network failure path
        log.error(f"Discord send failed: {exc}")
        return {"ok": False, "error": str(exc)}


def send_slack_alert(message: str, config: AppConfig) -> dict:
    """Send one message through a Slack incoming webhook."""

    if not config.slack_webhook_url:
        return {"ok": False, "error": "Slack 설정 없음"}

    payload = json.dumps({"text": message[:3000]}).encode("utf-8")

    try:
        req = urllib.request.Request(
            config.slack_webhook_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "BIOJUHO-Notifier/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        log.info("Slack alert sent")
        return {"ok": True, "body": body}
    except Exception as exc:  # pragma: no cover - network failure path
        log.error(f"Slack send failed: {exc}")
        return {"ok": False, "error": str(exc)}


def send_email_alert(message: str, config: AppConfig) -> dict:
    """Send one plain-text alert via SMTP."""

    if not config.smtp_host or not config.alert_email:
        return {"ok": False, "error": "SMTP/이메일 설정 없음"}

    import smtplib
    from email.mime.text import MIMEText

    plain = message.replace("*", "").replace("`", "")
    msg = MIMEText(plain, "plain", "utf-8")
    msg["Subject"] = "[GetDayTrends] Trend alert"
    msg["From"] = config.smtp_user or config.alert_email
    msg["To"] = config.alert_email

    try:
        if config.smtp_port == 465:
            server = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=10)
            server.starttls()

        if config.smtp_user and config.smtp_password:
            server.login(config.smtp_user, config.smtp_password)

        server.send_message(msg)
        server.quit()
        log.info(f"Email alert sent -> {config.alert_email}")
        return {"ok": True}
    except Exception as exc:  # pragma: no cover - network failure path
        log.error(f"Email send failed: {exc}")
        return {"ok": False, "error": str(exc)}


def send_alert(message: str, config: AppConfig) -> dict:
    """Send to every configured alert channel."""

    results: dict[str, dict] = {}
    if config.telegram_bot_token and config.telegram_chat_id:
        results["telegram"] = send_telegram_alert(message, config)
    if config.discord_webhook_url:
        results["discord"] = send_discord_alert(message, config)
    if config.slack_webhook_url:
        results["slack"] = send_slack_alert(message, config)
    if config.smtp_host and config.alert_email:
        results["email"] = send_email_alert(message, config)
    return results


def send_weekly_cost_report(config: AppConfig) -> bool:
    """Send a compact 7-day LLM cost report to Telegram when available."""

    if not config.telegram_bot_token or not config.telegram_chat_id:
        return False

    try:
        from shared.llm.stats import _DB_PATH as llm_db_path
        from shared.llm.stats import CostTracker
    except Exception:
        return False

    if not llm_db_path.exists():
        return False

    try:
        tracker = CostTracker(persist=True)
        daily = tracker.get_daily_stats(7)
        tracker.close()
    except Exception as exc:  # pragma: no cover - external dependency path
        log.warning(f"Weekly cost report unavailable: {exc}")
        return False

    if not daily:
        return False

    by_day: dict[str, dict[str, float | int]] = {}
    for row in daily:
        day_key = row["date"]
        by_day.setdefault(day_key, {"cost": 0.0, "calls": 0})
        by_day[day_key]["cost"] += row["cost_usd"]
        by_day[day_key]["calls"] += row["calls"]

    total_7d = sum(float(v["cost"]) for v in by_day.values())
    monthly_estimate = total_7d / 7 * 30

    lines = ["*Weekly LLM Cost Report*\n"]
    for day_key in sorted(by_day.keys(), reverse=True):
        stats = by_day[day_key]
        bar = "#" * min(int(float(stats["cost"]) * 100), 10)
        lines.append(f"  `{day_key}` {bar} ${float(stats['cost']):.4f} ({int(stats['calls'])} calls)")
    lines.append(f"\n7-day total: *${total_7d:.4f}*")
    lines.append(f"Monthly estimate: *${monthly_estimate:.2f}*")

    result = send_telegram_alert("\n".join(lines), config)
    return bool(result.get("ok"))


def check_watchlist(trends: list[ScoredTrend], config: AppConfig, conn=None) -> int:
    """Send an immediate alert when a watchlist keyword appears."""

    if not getattr(config, "watchlist_keywords", None) or config.no_alerts:
        return 0

    detected: list[tuple[ScoredTrend, str]] = []
    for trend in trends:
        for keyword in config.watchlist_keywords:
            if keyword.lower() in trend.keyword.lower():
                detected.append((trend, keyword))
                break

    if not detected:
        return 0

    lines = ["*[WATCHLIST] Keyword detected!*\n"]
    for trend, keyword in detected:
        lines.append(
            f"  - *{trend.keyword}* (matched `{keyword}`)"
            f" | viral {trend.viral_potential}"
            f" | {trend.trend_acceleration}"
        )

    send_alert("\n".join(lines), config)

    if conn is not None:
        try:
            try:
                from .db import record_watchlist_hit
            except ImportError:
                from db import record_watchlist_hit

            async def _persist_hits() -> None:
                for trend, keyword in detected:
                    await record_watchlist_hit(conn, trend.keyword, keyword, trend.viral_potential)

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                asyncio.run(_persist_hits())
            else:
                loop.create_task(_persist_hits())
        except Exception as exc:  # pragma: no cover - persistence is best effort
            log.debug(f"Watchlist persistence skipped: {exc}")

    return len(detected)


def check_and_alert(trends: list[ScoredTrend], config: AppConfig) -> int:
    """Send alerts for trends above the configured viral threshold."""

    if config.no_alerts:
        return 0

    sent = 0
    threshold = int(getattr(config, "alert_threshold", 70) or 70)
    for trend in trends:
        if trend.viral_potential < threshold:
            continue
        result = send_alert(format_trend_alert(trend), config)
        if any(channel_result.get("ok") for channel_result in result.values()):
            sent += 1
    return sent


def format_cost_summary(daily_cost: float, daily_budget: float) -> str:
    """Build one compact cost/budget summary line."""

    pct = (daily_cost / daily_budget * 100) if daily_budget > 0 else 0
    bar_len = min(int(pct / 10), 10)
    bar = "#" * bar_len + "-" * (10 - bar_len)
    status = "OK" if pct < 70 else ("WARN" if pct < 90 else "CRITICAL")
    return f"{status} ${daily_cost:.4f}/${daily_budget:.2f} ({pct:.0f}%) [{bar}]"


def send_daily_cost_alert(config: AppConfig) -> bool:
    """Send a daily budget alert when LLM usage crosses warning thresholds."""

    if config.daily_budget_usd <= 0 or config.no_alerts:
        return False

    try:
        from shared.llm.stats import _DB_PATH as llm_db_path
        from shared.llm.stats import CostTracker
    except Exception:
        return False

    if not llm_db_path.exists():
        return False

    try:
        tracker = CostTracker(persist=True)
        daily = tracker.get_daily_stats(1)
        tracker.close()
    except Exception as exc:  # pragma: no cover - external dependency path
        log.debug(f"Daily cost alert unavailable: {exc}")
        return False

    today = str(date.today())
    today_cost = sum(row["cost_usd"] for row in daily if row.get("date") == today)
    pct = today_cost / config.daily_budget_usd * 100 if config.daily_budget_usd > 0 else 0
    if pct < 70:
        return False

    summary = format_cost_summary(today_cost, config.daily_budget_usd)
    today_calls = sum(row["calls"] for row in daily if row.get("date") == today)
    if pct >= 90:
        message = (
            f"*Daily budget critical!*\n{summary}\n"
            f"Calls today: {today_calls}\n"
            "Consider disabling heavy Sonnet paths."
        )
    else:
        message = f"*Daily cost alert*\n{summary}\nCalls today: {today_calls}"

    results = send_alert(message, config)
    if any(result.get("ok") for result in results.values()):
        log.info(f"Daily cost alert sent: {summary}")
        return True
    return False
