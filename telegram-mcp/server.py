"""Telegram Bot MCP Server — Claude Code integration for notifications, approvals, and monitoring."""

import os
import json
from datetime import datetime, timezone, timedelta

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("telegram-bot")

TELEGRAM_API = "https://api.telegram.org"
KST = timezone(timedelta(hours=9))


def _get_config() -> tuple[str, str]:
    """Return (bot_token, chat_id). Raises ValueError if not configured."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in environment variables"
        )
    return token, chat_id


async def _call_api(method: str, payload: dict) -> dict:
    """Call Telegram Bot API and return parsed response."""
    token, _ = _get_config()
    url = f"{TELEGRAM_API}/bot{token}/{method}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()


async def _send(text: str, parse_mode: str = "Markdown", reply_markup: dict | None = None) -> dict:
    """Send a message to the configured chat and return structured result."""
    try:
        _, chat_id = _get_config()
    except ValueError as e:
        return {"ok": False, "error": str(e)}

    payload: dict = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        result = await _call_api("sendMessage", payload)
        if result.get("ok"):
            return {"ok": True, "message_id": result["result"]["message_id"]}
        return {"ok": False, "error": result.get("description", "Unknown Telegram error")}
    except httpx.HTTPStatusError as e:
        return {"ok": False, "error": f"HTTP {e.response.status_code}: {e.response.text}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def send_message(text: str, parse_mode: str = "Markdown") -> dict:
    """Send a message to the configured Telegram chat.

    Args:
        text: Message text (supports Telegram Markdown).
        parse_mode: Parse mode — "Markdown", "MarkdownV2", or "HTML".

    Returns:
        Dict with ok, message_id (on success), or error (on failure).
    """
    return await _send(text, parse_mode=parse_mode)


@mcp.tool()
async def send_alert(title: str, body: str, level: str = "info") -> dict:
    """Send a formatted alert notification.

    Args:
        title: Alert title.
        body: Alert body text.
        level: Severity — "info", "warning", or "error".

    Returns:
        Dict with ok, message_id, or error.
    """
    icons = {"info": "[INFO]", "warning": "[WARNING]", "error": "[ERROR]"}
    icon = icons.get(level, "[INFO]")
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")

    msg = (
        f"*{icon} {title}*\n"
        f"\n"
        f"{body}\n"
        f"\n"
        f"_{now}_"
    )
    return await _send(msg)


@mcp.tool()
async def send_pipeline_report(
    pipeline_name: str, status: str, details: str, metrics: dict | None = None
) -> dict:
    """Send a pipeline execution report.

    Args:
        pipeline_name: Name of the pipeline (e.g. "GetDayTrends", "DailyNews").
        status: Execution result — "success", "partial", or "failed".
        details: Freeform description of what happened.
        metrics: Optional dict of key-value metrics (e.g. {"trends": 5, "duration_s": 42}).

    Returns:
        Dict with ok, message_id, or error.
    """
    status_label = {
        "success": "[OK] SUCCESS",
        "partial": "[!!] PARTIAL",
        "failed": "[FAIL] FAILED",
    }.get(status, status.upper())

    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    lines = [
        f"*Pipeline Report: {pipeline_name}*",
        f"Status: `{status_label}`",
        "",
        details,
    ]

    if metrics:
        lines.append("")
        lines.append("*Metrics:*")
        for k, v in metrics.items():
            lines.append(f"  - {k}: `{v}`")

    lines.append("")
    lines.append(f"_{now}_")

    return await _send("\n".join(lines))


@mcp.tool()
async def send_cost_report(daily_cost: float, budget: float, breakdown: dict | None = None) -> dict:
    """Send an LLM cost summary with a text progress bar.

    Args:
        daily_cost: Today's total cost in USD.
        budget: Daily budget cap in USD.
        breakdown: Optional dict mapping model/provider to cost (e.g. {"gemini-2.5-pro": 0.45}).

    Returns:
        Dict with ok, message_id, or error.
    """
    pct = min(daily_cost / budget, 1.0) if budget > 0 else 0.0
    filled = int(pct * 20)
    bar = "[" + "#" * filled + "-" * (20 - filled) + "]"

    now = datetime.now(KST).strftime("%Y-%m-%d")
    lines = [
        f"*LLM Cost Report — {now}*",
        "",
        f"Daily: `${daily_cost:.4f}` / `${budget:.2f}`",
        f"`{bar}` {pct * 100:.1f}%",
    ]

    if breakdown:
        lines.append("")
        lines.append("*Breakdown:*")
        for model, cost in sorted(breakdown.items(), key=lambda x: -x[1]):
            lines.append(f"  - {model}: `${cost:.4f}`")

    if pct >= 0.9:
        lines.append("")
        lines.append("*[WARNING] Budget usage >= 90%*")

    return await _send("\n".join(lines))


@mcp.tool()
async def send_approval_request(action: str, description: str) -> dict:
    """Request user approval via Telegram (sends inline keyboard placeholder text).

    The message includes an inline keyboard with Approve/Reject buttons.
    Use get_updates() to poll for the user's reply.

    Args:
        action: Short action label (e.g. "deploy-prod", "run-migration").
        description: Detailed explanation of what will happen.

    Returns:
        Dict with ok, message_id, or error.
    """
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    msg = (
        f"*[APPROVAL REQUIRED]*\n"
        f"\n"
        f"*Action:* `{action}`\n"
        f"{description}\n"
        f"\n"
        f"_{now}_"
    )

    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "Approve", "callback_data": json.dumps({"action": action, "decision": "approve"})},
                {"text": "Reject", "callback_data": json.dumps({"action": action, "decision": "reject"})},
            ]
        ]
    }

    return await _send(msg, reply_markup=reply_markup)


@mcp.tool()
async def get_updates(limit: int = 10) -> dict:
    """Get recent messages and callback responses from the user.

    Args:
        limit: Maximum number of updates to return (1-100).

    Returns:
        Dict with ok and updates list, or error.
    """
    try:
        _get_config()
    except ValueError as e:
        return {"ok": False, "error": str(e)}

    limit = max(1, min(limit, 100))

    try:
        result = await _call_api("getUpdates", {"limit": limit, "allowed_updates": ["message", "callback_query"]})
        if not result.get("ok"):
            return {"ok": False, "error": result.get("description", "Unknown error")}

        updates = []
        for u in result.get("result", []):
            entry: dict = {"update_id": u["update_id"]}
            if "message" in u:
                m = u["message"]
                entry["type"] = "message"
                entry["from"] = m.get("from", {}).get("first_name", "unknown")
                entry["text"] = m.get("text", "")
                entry["date"] = m.get("date")
            elif "callback_query" in u:
                cb = u["callback_query"]
                entry["type"] = "callback_query"
                entry["from"] = cb.get("from", {}).get("first_name", "unknown")
                entry["data"] = cb.get("data", "")
            updates.append(entry)

        return {"ok": True, "updates": updates}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@mcp.tool()
async def send_trend_alert(keyword: str, score: float, category: str, context: str) -> dict:
    """Send a trend watchlist match notification.

    Args:
        keyword: Trending keyword that matched the watchlist.
        score: Trend score (0-100).
        category: Category or tag (e.g. "crypto", "tech", "politics").
        context: Brief explanation of why this is trending now.

    Returns:
        Dict with ok, message_id, or error.
    """
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")

    if score >= 80:
        level = "[!!] HIGH"
    elif score >= 50:
        level = "[!] MEDIUM"
    else:
        level = "[-] LOW"

    msg = (
        f"*Trend Alert*\n"
        f"\n"
        f"*Keyword:* `{keyword}`\n"
        f"*Score:* `{score:.1f}` — {level}\n"
        f"*Category:* {category}\n"
        f"\n"
        f"*Context:*\n"
        f"{context}\n"
        f"\n"
        f"_{now}_"
    )
    return await _send(msg)


if __name__ == "__main__":
    mcp.run()
