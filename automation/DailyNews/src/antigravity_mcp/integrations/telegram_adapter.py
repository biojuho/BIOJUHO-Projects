from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx

from antigravity_mcp.config import get_settings

logger = logging.getLogger(__name__)


class TelegramAdapter:
    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.telegram_bot_token and self.settings.telegram_chat_id)

    async def send_message(self, message: str) -> bool:
        if not self.is_configured:
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

    async def send_error_alert(
        self,
        *,
        pipeline_stage: str,
        error_type: str,
        error_message: str,
        run_id: str = "",
        retryable: bool = False,
    ) -> bool:
        """Send an immediate error alert to Telegram when a pipeline stage fails."""
        now_kst = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
        retry_tag = " [RETRYABLE]" if retryable else ""
        text = (
            f"<b>[ALERT] Pipeline Error{retry_tag}</b>\n"
            f"<b>Stage:</b> {pipeline_stage}\n"
            f"<b>Error:</b> {error_type}\n"
            f"<b>Detail:</b> {error_message[:500]}\n"
            f"<b>Run ID:</b> {run_id or 'N/A'}\n"
            f"<b>Time:</b> {now_kst}"
        )
        try:
            return await self.send_message(text)
        except Exception as exc:
            logger.error("Failed to send Telegram error alert: %s", exc)
            return False

    async def send_daily_summary(
        self,
        *,
        total_runs: int,
        success_count: int,
        failure_count: int,
        error_rate: float,
        avg_latency: float | None,
    ) -> bool:
        """Send a daily pipeline health summary to Telegram."""
        latency_str = f"{avg_latency:.1f}s" if avg_latency is not None else "N/A"
        status_icon = "OK" if error_rate < 0.1 else "WARNING" if error_rate < 0.3 else "CRITICAL"
        text = (
            f"<b>[{status_icon}] Daily Pipeline Summary</b>\n"
            f"<b>Total runs:</b> {total_runs}\n"
            f"<b>Success:</b> {success_count} | <b>Failed:</b> {failure_count}\n"
            f"<b>Error rate:</b> {error_rate:.1%}\n"
            f"<b>Avg latency:</b> {latency_str}"
        )
        return await self.send_message(text)
