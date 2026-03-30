"""
getdaytrends v2.0 - Alert System
Telegram + Discord 웹훅 알림. trend_monitor/webhook.py에서 포팅.
"""

import json
import urllib.parse
import urllib.request

from loguru import logger as log

from config import AppConfig
from models import ScoredTrend


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
    payload = json.dumps(
        {
            "chat_id": config.telegram_chat_id,
            "text": message[:4096],
            "parse_mode": "Markdown",
        }
    ).encode("utf-8")

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
            headers={
                "Content-Type": "application/json",
                "User-Agent": "BIOJUHO-Notifier/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            pass  # Discord returns 204 No Content on success
        log.info("Discord 알림 전송 완료")
        return {"ok": True}
    except Exception as e:
        log.error(f"Discord 전송 실패: {e}")
        return {"ok": False, "error": str(e)}


def send_slack_alert(message: str, config: AppConfig) -> dict:
    """[C-5] Slack Incoming Webhook으로 메시지 전송."""
    if not config.slack_webhook_url:
        return {"ok": False, "error": "Slack 설정 없음"}

    # Slack mrkdwn: *bold* 형식 그대로 사용 가능
    payload = json.dumps({"text": message[:3000]}).encode("utf-8")

    try:
        req = urllib.request.Request(
            config.slack_webhook_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "BIOJUHO-Notifier/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        # Slack returns "ok" on success
        log.info("Slack 알림 전송 완료")
        return {"ok": True, "body": body}
    except Exception as e:
        log.error(f"Slack 전송 실패: {e}")
        return {"ok": False, "error": str(e)}


def send_email_alert(message: str, config: AppConfig) -> dict:
    """[C-5] SMTP 기반 이메일 알림 전송."""
    if not config.smtp_host or not config.alert_email:
        return {"ok": False, "error": "SMTP/이메일 설정 없음"}

    import smtplib
    from email.mime.text import MIMEText

    # Markdown 제거하여 플레인텍스트 이메일 생성
    plain = message.replace("*", "").replace("`", "")

    msg = MIMEText(plain, "plain", "utf-8")
    msg["Subject"] = "[GetDayTrends] 트렌드 알림"
    msg["From"] = config.smtp_user or config.alert_email
    msg["To"] = config.alert_email

    try:
        if config.smtp_port == 465:
            server = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=10)
            server.starttls()

        if config.smtp_user and config.smtp_password:
            server.login(config.smtp_user, config.smtp_password)

        server.send_message(msg)
        server.quit()
        log.info(f"이메일 알림 전송 완료 → {config.alert_email}")
        return {"ok": True}
    except Exception as e:
        log.error(f"이메일 전송 실패: {e}")
        return {"ok": False, "error": str(e)}


def send_alert(message: str, config: AppConfig) -> dict:
    """모든 설정된 채널로 알림 전송."""
    results = {}
    if config.telegram_bot_token and config.telegram_chat_id:
        results["telegram"] = send_telegram_alert(message, config)
    if config.discord_webhook_url:
        results["discord"] = send_discord_alert(message, config)
    if config.slack_webhook_url:
        results["slack"] = send_slack_alert(message, config)
    if config.smtp_host and config.alert_email:
        results["email"] = send_email_alert(message, config)
    return results


def send_weekly_cost_report(config: AppConfig) -> bool:
    """
    주간 LLM 비용 리포트를 Telegram으로 전송.
    shared.llm.stats.CostTracker에서 7일 집계 데이터를 읽어 포맷.
    전송 성공 여부 반환.
    """
    try:
        from shared.llm.stats import _DB_PATH as llm_db_path
        from shared.llm.stats import CostTracker

        if not llm_db_path.exists():
            return False

        tracker = CostTracker(persist=True)
        daily = tracker.get_daily_stats(7)
        tracker.close()

        if not daily:
            return False

        # 일별 집계
        by_day: dict = {}
        for row in daily:
            d = row["date"]
            by_day.setdefault(d, {"cost": 0.0, "calls": 0})
            by_day[d]["cost"] += row["cost_usd"]
            by_day[d]["calls"] += row["calls"]

        total_7d = sum(v["cost"] for v in by_day.values())
        monthly_est = total_7d / 7 * 30

        lines = ["📊 *주간 LLM 비용 리포트*\n"]
        for day in sorted(by_day.keys(), reverse=True):
            v = by_day[day]
            bar = "█" * min(int(v["cost"] * 100), 10)
            lines.append(f"  `{day}` {bar} ${v['cost']:.4f} ({v['calls']}콜)")
        lines.append(f"\n💰 7일 합계: *${total_7d:.4f}*")
        lines.append(f"📈 월 추정: *${monthly_est:.2f}*")

        message = "\n".join(lines)
        result = send_telegram_alert(message, config)
        if result.get("ok"):
            log.info("주간 비용 리포트 Telegram 전송 완료")
            return True
        return False

    except Exception as e:
        log.warning(f"주간 비용 리포트 전송 실패: {e}")
        return False


def check_watchlist(
    trends: list[ScoredTrend],
    config: AppConfig,
    conn=None,
) -> int:
    """
    [v9.0] Watchlist 키워드가 트렌드에 등장하면 즉시 알림.
    conn이 주어지면 watchlist_hits 테이블에 기록.
    반환: 감지된 Watchlist 항목 수
    """
    if not config.watchlist_keywords or config.no_alerts:
        return 0

    detected: list[tuple[ScoredTrend, str]] = []
    for trend in trends:
        for wk in config.watchlist_keywords:
            if wk.lower() in trend.keyword.lower():
                detected.append((trend, wk))
                break

    if not detected:
        return 0

    # 알림 메시지
    lines = ["*[WATCHLIST] 관심 키워드 등장!*\n"]
    for trend, wk in detected:
        lines.append(
            f"  - *{trend.keyword}* (감지어: `{wk}`)"
            f" | 바이럴 {trend.viral_potential}점"
            f" | {trend.trend_acceleration}"
        )
    message = "\n".join(lines)
    send_alert(message, config)

    # DB 기록 (비동기 conn이므로 asyncio 없이 별도 코루틴으로 처리)
    if conn is not None:
        import asyncio

        from db import record_watchlist_hit

        for trend, wk in detected:
            try:
                asyncio.get_event_loop().run_until_complete(
                    record_watchlist_hit(conn, trend.keyword, wk, trend.viral_potential)
                )
            except Exception as _e:
                log.debug(f"watchlist_hit 기록 실패 (무시): {_e}")

    log.info(f"[Watchlist] {len(detected)}건 감지: {[t.keyword for t, _ in detected]}")
    return len(detected)


def check_and_alert(
    trends: list[ScoredTrend],
    config: AppConfig,
) -> int:
    """threshold 이상 트렌드에 대해 알림 전송. 전송 건수 반환."""
    if config.no_alerts:
        return 0

    has_channels = (config.telegram_bot_token and config.telegram_chat_id) or config.discord_webhook_url
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


def format_cost_summary(daily_cost: float, daily_budget: float) -> str:
    """[C3] 비용 요약 문자열 생성."""
    pct = (daily_cost / daily_budget * 100) if daily_budget > 0 else 0
    bar_len = min(int(pct / 10), 10)
    bar = "█" * bar_len + "░" * (10 - bar_len)
    status = "🟢" if pct < 70 else ("🟡" if pct < 90 else "🔴")
    return f"{status} ${daily_cost:.4f}/${daily_budget:.2f} ({pct:.0f}%) [{bar}]"


def send_daily_cost_alert(config: AppConfig) -> bool:
    """
    [C3] 일일 비용 알림 전송.
    오늘 누적 비용이 예산의 70% 이상이면 경고, 90% 이상이면 긴급 알림.
    """
    if config.daily_budget_usd <= 0:
        return False

    try:
        from datetime import date as _date

        from shared.llm.stats import _DB_PATH as llm_db_path
        from shared.llm.stats import CostTracker

        if not llm_db_path.exists():
            return False

        tracker = CostTracker(persist=True)
        daily = tracker.get_daily_stats(1)
        tracker.close()

        today = str(_date.today())
        today_cost = sum(r["cost_usd"] for r in daily if r.get("date") == today)

        pct = today_cost / config.daily_budget_usd * 100

        if pct < 70:
            return False  # 정상 범위 → 알림 불필요

        summary = format_cost_summary(today_cost, config.daily_budget_usd)
        today_calls = sum(r["calls"] for r in daily if r.get("date") == today)

        if pct >= 90:
            message = (
                f"🔴 *일일 예산 임박!*\n" f"{summary}\n" f"📞 호출: {today_calls}회\n" f"⚠️ Sonnet 비활성화 임계 도달"
            )
        else:
            message = f"🟡 *일일 비용 경고*\n" f"{summary}\n" f"📞 호출: {today_calls}회"

        result = send_alert(message, config)
        if any(r.get("ok") for r in result.values()):
            log.info(f"일일 비용 알림 전송: {summary}")
            return True
        return False

    except Exception as e:
        log.debug(f"일일 비용 알림 실패: {e}")
        return False


def send_heartbeat(
    config: AppConfig,
    *,
    trends_collected: int = 0,
    tweets_saved: int = 0,
    elapsed_sec: float = 0,
    cost_usd: float = 0,
) -> bool:
    """
    [v18.0] 파이프라인 완료 시 하트비트 전송.
    shared.notifications.Notifier가 없는 환경에서도 Telegram으로 직접 전송.
    """
    if not config.telegram_bot_token or not config.telegram_chat_id:
        return False

    from datetime import datetime as _dt

    now = _dt.now().strftime("%Y-%m-%d %H:%M")
    message = (
        f"💚 *GetDayTrends 하트비트*\n"
        f"⏰ {now}\n"
        f"📊 수집: {trends_collected}개\n"
        f"💾 저장: {tweets_saved}개\n"
        f"⏱️ 소요: {elapsed_sec:.0f}초\n"
        f"💰 비용: ${cost_usd:.4f}"
    )
    result = send_telegram_alert(message, config)
    return result.get("ok", False)
