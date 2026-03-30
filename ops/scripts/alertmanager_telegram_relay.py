"""
Minimal AlertManager → Telegram relay.

Receives AlertManager webhook POST at /alertmanager-telegram-relay,
formats the alert, and sends it to a Telegram chat via the Bot API.

Usage:
    TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... python alertmanager_telegram_relay.py

Listens on port 9095 by default.
"""
from __future__ import annotations

import json
import logging
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.request import Request, urlopen

log = logging.getLogger("telegram-relay")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
PORT = int(os.environ.get("RELAY_PORT", "9095"))


def format_alert(alert: dict) -> str:
    status = alert.get("status", "unknown").upper()
    labels = alert.get("labels", {})
    annotations = alert.get("annotations", {})
    name = labels.get("alertname", "?")
    service = labels.get("service", labels.get("job", "?"))
    summary = annotations.get("summary", "")
    description = annotations.get("description", "")

    icon = "\u26a0\ufe0f" if status == "FIRING" else "\u2705"
    lines = [
        f"{icon} *{status}*: {name}",
        f"Service: `{service}`",
    ]
    if summary:
        lines.append(f"{summary}")
    if description:
        lines.append(f"_{description}_")
    return "\n".join(lines)


def send_telegram(text: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        log.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set, skipping")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }).encode()
    req = Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=10) as resp:
            log.info("Telegram sent: %s", resp.status)
    except Exception as exc:
        log.error("Telegram send failed: %s", exc)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        alerts = data.get("alerts", [])
        for alert in alerts:
            text = format_alert(alert)
            send_telegram(text)

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, fmt, *args):
        log.info(fmt, *args)


if __name__ == "__main__":
    log.info("Telegram relay listening on :%d", PORT)
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down")
