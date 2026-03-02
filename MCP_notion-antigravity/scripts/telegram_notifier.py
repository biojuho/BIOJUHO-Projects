from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from antigravity_mcp.config import get_settings


def send_telegram_message(message: str, parse_mode: str = "HTML") -> bool:
    settings = get_settings()
    bot_token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id

    if not bot_token or not chat_id:
        print("[WARNING] Telegram credentials are missing. Skipping notification.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }

    try:
        response = httpx.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        print(f"[ERROR] Failed to send Telegram message: {exc}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send a message to the configured Telegram chat.")
    parser.add_argument("--test", required=True, help="Message to send")
    args = parser.parse_args()

    if not send_telegram_message(args.test):
        raise SystemExit(1)
