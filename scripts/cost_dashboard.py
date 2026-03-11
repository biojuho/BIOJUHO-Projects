"""
scripts/cost_dashboard.py
주기적 비용 파수꾼 데몬(Daemon)
매일 오전 9시 (또는 주기적 실행 시점) 전일 발생한 'AI API 및 인프라 사용 비용 합계' 리포트를 요약하고
예산 스레스홀드 초과 시 차단/경고를 수행합니다.

사용법:
  python scripts/cost_dashboard.py               # 대시보드만 출력
  python scripts/cost_dashboard.py --notify       # 출력 + Discord/Telegram 알림
  python scripts/cost_dashboard.py --days 7       # 7일 데이터 요약
"""

import sys
import io
import argparse
from pathlib import Path
from datetime import datetime

# Windows cp949 환경에서 이모지 출력을 위한 UTF-8 강제 설정
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))

from shared.telemetry.cost_tracker import get_daily_cost_summary

DAILY_BUDGET_USD = 2.00
RATE_LIMIT_LOCK_FILE = WORKSPACE / "shared" / "llm" / "data" / "RATE_LIMIT.lock"


def run_cost_dashboard(*, days: int = 1, notify: bool = False):
    summary = get_daily_cost_summary(days=days)

    print("=" * 50)
    print(f"💰 AI Cost Dashboard [최근 {days}일 사용량 요약]")
    print(f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    if "error" in summary:
        print(f"오류: {summary['error']}")
        return

    print(f"총 LLM API 호출 수: {summary['total_calls']}건")
    print(f"총 발생 비용: ${summary['total_cost']:.4f}")

    print("\n[프로젝트별 사용 현황]")
    if not summary['projects']:
        print("  - 사용 이력 없음")
    for proj, stats in summary['projects'].items():
        print(f"  - {proj}: {stats['calls']}건 (${stats['cost_usd']:.4f})")

    print("-" * 50)

    # 예산 경고 Alarm 및 Rate Limiting 로직
    budget_exceeded = summary['total_cost'] > DAILY_BUDGET_USD
    if budget_exceeded:
        print(f"🚨 [경고] 일일 예산 스레스홀드(${DAILY_BUDGET_USD}) 초과! (현재 ${summary['total_cost']:.4f})")
        print("🚨 추가 API 요청 차단(Rate Limit) 방어 기동 발동.")
        RATE_LIMIT_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        RATE_LIMIT_LOCK_FILE.touch()
    else:
        print(f"✅ 예산 양호 (한도: ${DAILY_BUDGET_USD:.2f})")
        if RATE_LIMIT_LOCK_FILE.exists():
            RATE_LIMIT_LOCK_FILE.unlink()
            print("🟢 예산 내로 회복, 차단 해제 완료")

    # ── 알림 전송 (--notify 플래그) ──
    if notify:
        try:
            from shared.notifications import Notifier

            notifier = Notifier.from_env()
            if not notifier.has_channels:
                print("⚠️ 알림 채널 미설정 (DISCORD_WEBHOOK_URL / TELEGRAM_BOT_TOKEN)")
                return

            # 예산 경고 알림
            notifier.send_cost_alert(
                daily_cost=summary["total_cost"],
                daily_budget=DAILY_BUDGET_USD,
                calls=summary["total_calls"],
            )

            # 일일 리포트 알림 (항상 전송)
            project_lines = "\n".join(
                f"  `{proj}`: {s['calls']}건 (${s['cost_usd']:.4f})"
                for proj, s in summary["projects"].items()
            )
            report = (
                f"📊 *일일 비용 리포트*\n"
                f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"💰 합계: *${summary['total_cost']:.4f}* / "
                f"${DAILY_BUDGET_USD:.2f}\n"
                f"📞 호출: {summary['total_calls']}건\n"
                f"\n{project_lines}"
            )
            notifier.send(report)
            print("📤 알림 전송 완료")

        except Exception as e:
            print(f"⚠️ 알림 전송 실패: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Cost Dashboard")
    parser.add_argument("--days", type=int, default=1, help="조회 기간 (일)")
    parser.add_argument("--notify", action="store_true", help="Discord/Telegram 알림 전송")
    args = parser.parse_args()

    run_cost_dashboard(days=args.days, notify=args.notify)

