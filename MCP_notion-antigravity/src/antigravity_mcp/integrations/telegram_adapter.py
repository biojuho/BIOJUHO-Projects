from __future__ import annotations

import httpx

from antigravity_mcp.config import get_settings


class TelegramAdapter:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def send_message(self, message: str) -> bool:
        if not self.settings.telegram_bot_token or not self.settings.telegram_chat_id:
            return False
        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                url,
                json={
                    "chat_id": self.settings.telegram_chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                },
            )
            return response.is_success
