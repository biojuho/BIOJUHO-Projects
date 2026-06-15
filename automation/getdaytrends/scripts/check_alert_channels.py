"""getdaytrends — alert channel preflight (non-sending validation).

The product runs unattended on a scheduler and pages failures to Telegram /
Discord. If an alert token is revoked, failure notifications fail *silently* —
you stop hearing about breakages without knowing it. `--doctor` only checks that
channels are *configured*, not that the tokens still work.

This probes each configured channel with a read-only call that sends NO message
(Telegram getMe, Discord webhook GET) and reports valid / invalid / unconfigured,
exiting non-zero if any configured channel is dead, for launch/CI gating.

Run: python scripts/check_alert_channels.py
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# fetch(url) -> (status_code, body_text)
Fetcher = Callable[[str], "tuple[int, str]"]


def _default_fetch(url: str) -> tuple[int, str]:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return exc.code, body
    except Exception as exc:  # network/DNS/etc.
        return 0, str(exc)


def check_telegram(token: str, fetch: Fetcher) -> dict[str, Any]:
    status, body = fetch(f"https://api.telegram.org/bot{token}/getMe")
    if status == 200:
        try:
            ok = bool(json.loads(body).get("ok"))
        except Exception:
            ok = False
        return {"channel": "telegram", "ok": ok, "status": "valid" if ok else "invalid_response"}
    reason = "auth_failed" if status in (401, 403, 404) else ("error" if status else "unreachable")
    return {"channel": "telegram", "ok": False, "status": reason, "http": status}


def check_discord(webhook_url: str, fetch: Fetcher) -> dict[str, Any]:
    status, _body = fetch(webhook_url)
    if status == 200:
        return {"channel": "discord", "ok": True, "status": "valid"}
    reason = "auth_failed" if status in (401, 403, 404) else ("error" if status else "unreachable")
    return {"channel": "discord", "ok": False, "status": reason, "http": status}


def run(config: Any, fetch: Fetcher = _default_fetch) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    if getattr(config, "telegram_bot_token", "") and getattr(config, "telegram_chat_id", ""):
        results.append(check_telegram(config.telegram_bot_token, fetch))
    if getattr(config, "discord_webhook_url", ""):
        results.append(check_discord(config.discord_webhook_url, fetch))
    # Slack incoming webhooks have no safe non-sending validation endpoint; note it.
    if getattr(config, "slack_webhook_url", "") and not results:
        results.append({"channel": "slack", "ok": True, "status": "configured_unverified"})
    failed = [r for r in results if not r["ok"]]
    return {
        "status": "pass" if not failed else "fail",
        "channels": results,
        "failed_channels": [r["channel"] for r in failed],
        "configured": bool(results),
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate configured alert channels without sending a message.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON only.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    from config import AppConfig

    summary = run(AppConfig.from_env())
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        if not summary["configured"]:
            print("Alert channel preflight: no channels configured")
            return 0
        print(f"Alert channel preflight: {summary['status']}")
        for ch in summary["channels"]:
            mark = "OK " if ch["ok"] else "XX "
            print(f"  [{mark}] {ch['channel']}: {ch['status']}")
        if summary["failed_channels"]:
            print(f"  -> fix/rotate tokens for: {', '.join(summary['failed_channels'])}")
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
