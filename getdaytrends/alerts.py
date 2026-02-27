"""
getdaytrends v2.0 - Alert System
Telegram + Discord 웹훅 알림. trend_monitor/webhook.py에서 포팅.
"""

import json
import logging
import urllib.parse
import urllib.request

from config import AppConfig
from models import ScoredTrend

log = logging.getLogger(__name__)


def format_trend_alert(trend: ScoredTrend) -> str:
    """고바이럴 트렌드를 읽기 쉬운 알림 메시지로 포맷."""
    angles = ", ".join(trend.suggested_angles[:3]) if trend.suggested_angles else "없음"
    sources = ", ".join(s.value for s in trend.sources)

    return (
        f"🔥 *고바이럴 트렌드 감지!*\n"
        f"📊 주제: *{trend.keyword}*\n"
        f"⚡ 바이럴 점수: {trend.viral_potential}/100\n"
        f"📈 가속도: {trend.trend_acceleration}\n"
        f"💡 핵심: {trend.top_insight}\n"
        f"🎯 앵글: {angles}\n"
        f"🌐 소스: {sources}\n"
        f"🚀 훅: {trend.best_hook_starter}"
    )


def send_telegram_alert(message: str, config: AppConfig) -> dict:
    """Telegram Bot API로 메시지 전송."""
    if not config.telegram_bot_token or not config.telegram_chat_id:
        return {"ok": False, "error": "Telegram 설정 없음"}

    url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage"
    payload = json.dumps({
        "chat_id": config.telegram_chat_id,
        "text": message[:4096],
        "parse_mode": "Markdown",
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        log.info("Telegram 알림 전송 완료")
        return result
    except Exception as e:
        log.error(f"Telegram 전송 실패: {e}")
        return {"ok": False, "error": str(e)}


def send_discord_alert(message: str, config: AppConfig) -> dict:
    """Discord Webhook으로 메시지 전송."""
    if not config.discord_webhook_url:
        return {"ok": False, "error": "Discord 설정 없음"}

    # Discord는 Markdown bold가 ** 형식
    discord_message = message.replace("*", "**")

    payload = json.dumps({"content": discord_message[:2000]}).encode("utf-8")

    try:
        req = urllib.request.Request(
            config.discord_webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            pass  # Discord returns 204 No Content on success
        log.info("Discord 알림 전송 완료")
        return {"ok": True}
    except Exception as e:
        log.error(f"Discord 전송 실패: {e}")
        return {"ok": False, "error": str(e)}


def send_alert(message: str, config: AppConfig) -> dict:
    """모든 설정된 채널로 알림 전송."""
    results = {}
    if config.telegram_bot_token and config.telegram_chat_id:
        results["telegram"] = send_telegram_alert(message, config)
    if config.discord_webhook_url:
        results["discord"] = send_discord_alert(message, config)
    return results


def check_and_alert(
    trends: list[ScoredTrend],
    config: AppConfig,
) -> int:
    """threshold 이상 트렌드에 대해 알림 전송. 전송 건수 반환."""
    if config.no_alerts:
        return 0

    has_channels = (
        (config.telegram_bot_token and config.telegram_chat_id)
        or config.discord_webhook_url
    )
    if not has_channels:
        return 0

    sent = 0
    for trend in trends:
        if trend.viral_potential >= config.alert_threshold:
            message = format_trend_alert(trend)
            result = send_alert(message, config)
            if any(r.get("ok") for r in result.values()):
                sent += 1
                log.info(f"알림 전송: '{trend.keyword}' (점수: {trend.viral_potential})")

    return sent
