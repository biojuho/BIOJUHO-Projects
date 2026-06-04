from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REQUIRED_ENV = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
DEFAULT_MESSAGE = "AutoResearch live Telegram notification verification."
TELEGRAM_API = "https://api.telegram.org"


def run(
    *,
    execute: bool = False,
    message: str = DEFAULT_MESSAGE,
    timeout_seconds: float = 15.0,
    env: Mapping[str, str] | None = None,
    sender: Callable[[str, str, str, float], dict[str, Any]] | None = None,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
) -> dict[str, Any]:
    env_map = env if env is not None else os.environ
    missing_env = [name for name in REQUIRED_ENV if not env_map.get(name)]
    ready = not missing_env
    errors: list[str] = []
    delivery = {
        "attempted": False,
        "ok": False,
        "message_id": None,
        "error": "",
    }
    started = time.perf_counter()

    if execute:
        if not ready:
            errors.append("missing required env: " + ", ".join(missing_env))
        else:
            delivery["attempted"] = True
            send = sender or send_telegram_message
            result = send(env_map["TELEGRAM_BOT_TOKEN"], env_map["TELEGRAM_CHAT_ID"], message, timeout_seconds)
            delivery.update(_redact_payload(result, env_map))
            if not delivery["ok"]:
                errors.append(delivery["error"] or "Telegram sendMessage returned ok=false")

    report = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "execute" if execute else "dry_run",
        "status": "pass" if not errors else "fail",
        "live_status": "ready_for_execution" if ready else "blocked_missing_required_env",
        "required_env": [
            {"name": name, "present": bool(env_map.get(name))}
            for name in REQUIRED_ENV
        ],
        "missing_required_env": missing_env,
        "summary": {
            "required_env_count": len(REQUIRED_ENV),
            "missing_required_env_count": len(missing_env),
            "message_attempted": delivery["attempted"],
            "message_sent": bool(delivery["ok"]),
            "elapsed_seconds": round(max(time.perf_counter() - started, 0.0), 3),
        },
        "delivery": delivery,
        "errors": errors,
    }
    if json_out is not None:
        _write_json_atomic(json_out, report)
    if markdown_out is not None:
        _write_text_atomic(markdown_out, render_markdown(report))
    return report


def send_telegram_message(token: str, chat_id: str, message: str, timeout_seconds: float) -> dict[str, Any]:
    payload = json.dumps(
        {
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": True,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{TELEGRAM_API}/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "message_id": None, "error": f"HTTP {exc.code}: {_tail_text(body)}"}
    except OSError as exc:
        return {"ok": False, "message_id": None, "error": str(exc)}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {"ok": False, "message_id": None, "error": f"invalid JSON response: {exc}"}

    if not data.get("ok"):
        return {"ok": False, "message_id": None, "error": str(data.get("description", "unknown Telegram error"))}
    result = data.get("result", {})
    message_id = result.get("message_id") if isinstance(result, dict) else None
    return {"ok": True, "message_id": message_id, "error": ""}


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Telegram Notification Live Verify",
        "",
        f"- Status: `{report['status']}`",
        f"- Mode: `{report['mode']}`",
        f"- Live status: `{report['live_status']}`",
        f"- Missing required env names: `{report['summary']['missing_required_env_count']}`",
        f"- Message attempted: `{str(report['summary']['message_attempted']).lower()}`",
        f"- Message sent: `{str(report['summary']['message_sent']).lower()}`",
        "- Secret values: not emitted; this verifier records env names and delivery status only.",
        "",
        "## Required Env",
        "",
    ]
    for item in report["required_env"]:
        lines.append(f"- `{item['name']}` present: `{str(item['present']).lower()}`")
    lines.extend(["", "## Delivery", ""])
    lines.extend(
        [
            f"- Attempted: `{str(report['delivery']['attempted']).lower()}`",
            f"- OK: `{str(report['delivery']['ok']).lower()}`",
            f"- Message id: `{report['delivery']['message_id']}`",
        ]
    )
    if report["delivery"]["error"]:
        lines.append(f"- Error: {report['delivery']['error']}")
    lines.extend(["", "## Errors", ""])
    if report["errors"]:
        lines.extend(f"- {error}" for error in report["errors"])
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dry-run or execute a live Telegram notification delivery check.")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--message", default=DEFAULT_MESSAGE)
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args(argv)
    report = run(
        execute=args.execute,
        message=args.message,
        timeout_seconds=args.timeout_seconds,
        json_out=args.json_out,
        markdown_out=args.markdown_out,
    )
    print(
        "telegram notification live verify: "
        f"mode={report['mode']}, "
        f"status={report['status']}, "
        f"live_status={report['live_status']}, "
        f"message_sent={str(report['summary']['message_sent']).lower()}"
    )
    return 0 if report["status"] == "pass" else 1


def _redact_payload(value: Any, env_map: Mapping[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _redact_payload(item, env_map) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_payload(item, env_map) for item in value]
    if isinstance(value, str):
        redacted = value
        for name in REQUIRED_ENV:
            secret = env_map.get(name)
            if secret and len(secret) >= 4:
                redacted = redacted.replace(secret, f"<redacted:{name}>")
        return redacted
    return value


def _tail_text(value: str, *, max_chars: int = 500) -> str:
    return value.strip()[-max_chars:]


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    _write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
