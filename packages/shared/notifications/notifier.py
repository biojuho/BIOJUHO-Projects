"""
shared.notifications.notifier — Telegram / Discord 알림 전송.

getdaytrends/alerts.py에서 추출한 공통 알림 로직을 모든 프로젝트에서
사용할 수 있도록 범용화한 모듈.

특징:
  - 환경 변수 기반 자동 설정 (DISCORD_WEBHOOK_URL, TELEGRAM_BOT_TOKEN 등)
  - 에러/성공/heartbeat/비용 경고 등 목적별 포맷터
  - 전송 실패 시 조용한 fallback (프로덕션 안전)
"""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from typing import Any


def send_telegram(
    message: str,
    bot_token: str,
    chat_id: str,
    *,
    timeout: int = 10,
) -> dict[str, Any]:
    """Telegram Bot API로 메시지 전송."""
    if not bot_token or not chat_id:
        return {"ok": False, "error": "Telegram 설정 없음"}

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": message[:4096],
        "parse_mode": "Markdown",
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"ok": False, "error": str(e)}


def send_discord(
    message: str,
    webhook_url: str,
    *,
    timeout: int = 10,
) -> dict[str, Any]:
    """Discord Webhook으로 메시지 전송."""
    if not webhook_url:
        return {"ok": False, "error": "Discord 설정 없음"}

    # Discord는 Markdown bold가 ** 형식
    discord_message = message.replace("*", "**")
    payload = json.dumps({"content": discord_message[:2000]}).encode("utf-8")

    try:
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "BIOJUHO-Notifier/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            _ = resp.read()  # Discord returns 204 No Content on success
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


class Notifier:
    """통합 알림 전송기.

    Usage::

        notifier = Notifier.from_env()
        notifier.send("✅ 작업 완료!")
        notifier.send_error("API 호출 실패", error=e, source="getdaytrends")
        notifier.send_heartbeat("getdaytrends")
    """

    def __init__(
        self,
        *,
        discord_webhook_url: str = "",
        telegram_bot_token: str = "",
        telegram_chat_id: str = "",
    ):
        self.discord_webhook_url = discord_webhook_url
        self.telegram_bot_token = telegram_bot_token
        self.telegram_chat_id = telegram_chat_id

    @classmethod
    def from_env(cls) -> "Notifier":
        """환경 변수에서 알림 채널 설정 자동 로드."""
        return cls(
            discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL", ""),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        )

    @property
    def has_channels(self) -> bool:
        """최소 1개 채널이 설정되어 있는지 확인."""
        return bool(self.discord_webhook_url) or bool(
            self.telegram_bot_token and self.telegram_chat_id
        )

    def send(self, message: str) -> dict[str, dict]:
        """모든 설정된 채널로 동시 전송."""
        results: dict[str, dict] = {}
        if self.telegram_bot_token and self.telegram_chat_id:
            results["telegram"] = send_telegram(
                message, self.telegram_bot_token, self.telegram_chat_id
            )
        if self.discord_webhook_url:
            results["discord"] = send_discord(message, self.discord_webhook_url)
        return results

    def send_error(
        self,
        error_message: str,
        *,
        error: Exception | None = None,
        source: str = "system",
    ) -> dict[str, dict]:
        """에러 알림 전송 (포맷팅 포함)."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines = [
            f"🔴 *에러 알림* [{source}]",
            f"🕐 {now}",
            f"📝 {error_message}",
        ]
        if error:
            lines.append(f"🔧 `{type(error).__name__}: {error!s}`")
        return self.send("\n".join(lines))

    def send_success(
        self,
        message: str,
        *,
        source: str = "system",
        details: str = "",
    ) -> dict[str, dict]:
        """성공 알림 전송."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines = [
            f"✅ *성공* [{source}]",
            f"🕐 {now}",
            f"📝 {message}",
        ]
        if details:
            lines.append(f"📊 {details}")
        return self.send("\n".join(lines))

    def send_heartbeat(
        self,
        service_name: str,
        *,
        status: str = "alive",
        details: str = "",
    ) -> dict[str, dict]:
        """서비스 heartbeat 전송 — 정기적 alive ping용."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        emoji = "💚" if status == "alive" else "💛"
        lines = [
            f"{emoji} *Heartbeat* [{service_name}]",
            f"🕐 {now}",
            f"📊 상태: {status}",
        ]
        if details:
            lines.append(f"📝 {details}")
        return self.send("\n".join(lines))

    def send_cost_alert(
        self,
        daily_cost: float,
        daily_budget: float,
        *,
        calls: int = 0,
    ) -> dict[str, dict]:
        """비용 경고 알림 — 예산 70% 이상 시 경고, 90% 이상 시 긴급."""
        if daily_budget <= 0:
            return {}

        pct = daily_cost / daily_budget * 100
        bar_len = min(int(pct / 10), 10)
        bar = "█" * bar_len + "░" * (10 - bar_len)

        if pct >= 90:
            emoji = "🔴"
            title = "일일 예산 임박!"
        elif pct >= 70:
            emoji = "🟡"
            title = "일일 비용 경고"
        else:
            return {}  # 70% 미만은 알림 불필요

        lines = [
            f"{emoji} *{title}*",
            f"💰 ${daily_cost:.4f} / ${daily_budget:.2f} ({pct:.0f}%)",
            f"📊 [{bar}]",
        ]
        if calls:
            lines.append(f"📞 API 호출: {calls}회")
        return self.send("\n".join(lines))
