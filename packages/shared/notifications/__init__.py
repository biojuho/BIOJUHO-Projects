"""
shared.notifications — 통합 알림 모듈.

Telegram Bot API, Discord Webhook을 통해 에러 알림, heartbeat,
비용 경고 등을 전송합니다. 모든 프로젝트에서 공통으로 사용.

사용 예시::

    from shared.notifications import Notifier

    notifier = Notifier.from_env()
    notifier.send("✅ 파이프라인 완료!")
    notifier.send_error("API 호출 실패", error=e)
    notifier.send_heartbeat("getdaytrends")
"""

from shared.notifications.notifier import ErrorSpikeDetector, Notifier, send_discord, send_telegram

__all__ = ["ErrorSpikeDetector", "Notifier", "send_discord", "send_telegram"]
