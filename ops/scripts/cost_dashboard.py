"""
scripts/cost_dashboard.py
二쇨린??鍮꾩슜 ?뚯닔袁??곕が(Daemon)
留ㅼ씪 ?ㅼ쟾 9??(?먮뒗 二쇨린???ㅽ뻾 ?쒖젏) ?꾩씪 諛쒖깮??'AI API 諛??명봽???ъ슜 鍮꾩슜 ?⑷퀎' 由ы룷?몃? ?붿빟?섍퀬
?덉궛 ?ㅻ젅?ㅽ???珥덇낵 ??李⑤떒/寃쎄퀬瑜??섑뻾?⑸땲??

?ъ슜踰?
  python scripts/cost_dashboard.py               # ?�?쒕낫?쒕쭔 異쒕젰
  python scripts/cost_dashboard.py --notify       # 異쒕젰 + Discord/Telegram ?뚮┝
  python scripts/cost_dashboard.py --days 7       # 7???곗씠???붿빟
"""

import sys
import io
import argparse
from pathlib import Path
from datetime import datetime

# Windows cp949 ?섍꼍?먯꽌 ?대え吏� 異쒕젰???꾪븳 UTF-8 媛뺤젣 ?ㅼ젙
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

WORKSPACE = Path(__file__).resolve().parents[1]

from shared.telemetry.cost_tracker import get_daily_cost_summary

DAILY_BUDGET_USD = 2.00
RATE_LIMIT_LOCK_FILE = WORKSPACE / "shared" / "llm" / "data" / "RATE_LIMIT.lock"


def run_cost_dashboard(*, days: int = 1, notify: bool = False):
    summary = get_daily_cost_summary(days=days)

    print("=" * 50)
    print(f"?뮥 AI Cost Dashboard [理쒓렐 {days}???ъ슜???붿빟]")
    print(f"?쒓컙: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    if "error" in summary:
        print(f"?ㅻ쪟: {summary['error']}")
        return

    print(f"珥?LLM API ?몄텧 ?? {summary['total_calls']}嫄?)
    print(f"珥?諛쒖깮 鍮꾩슜: ${summary['total_cost']:.4f}")

    print("\n[?꾨줈?앺듃蹂??ъ슜 ?꾪솴]")
    if not summary['projects']:
        print("  - ?ъ슜 ?대젰 ?놁쓬")
    for proj, stats in summary['projects'].items():
        print(f"  - {proj}: {stats['calls']}嫄?(${stats['cost_usd']:.4f})")

    print("-" * 50)

    # ?덉궛 寃쎄퀬 Alarm 諛?Rate Limiting 濡쒖쭅
    budget_exceeded = summary['total_cost'] > DAILY_BUDGET_USD
    if budget_exceeded:
        print(f"?슚 [寃쎄퀬] ?쇱씪 ?덉궛 ?ㅻ젅?ㅽ???${DAILY_BUDGET_USD}) 珥덇낵! (?꾩옱 ${summary['total_cost']:.4f})")
        print("?슚 異붽? API ?붿껌 李⑤떒(Rate Limit) 諛⑹뼱 湲곕룞 諛쒕룞.")
        RATE_LIMIT_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        RATE_LIMIT_LOCK_FILE.touch()
    else:
        print(f"???덉궛 ?묓샇 (?쒕룄: ${DAILY_BUDGET_USD:.2f})")
        if RATE_LIMIT_LOCK_FILE.exists():
            RATE_LIMIT_LOCK_FILE.unlink()
            print("?윟 ?덉궛 ?대줈 ?뚮났, 李⑤떒 ?댁젣 ?꾨즺")

    # ?�?� ?뚮┝ ?꾩넚 (--notify ?뚮옒洹? ?�?�
    if notify:
        try:
            from shared.notifications import Notifier

            notifier = Notifier.from_env()
            if not notifier.has_channels:
                print("?좑툘 ?뚮┝ 梨꾨꼸 誘몄꽕??(DISCORD_WEBHOOK_URL / TELEGRAM_BOT_TOKEN)")
                return

            # ?덉궛 寃쎄퀬 ?뚮┝
            notifier.send_cost_alert(
                daily_cost=summary["total_cost"],
                daily_budget=DAILY_BUDGET_USD,
                calls=summary["total_calls"],
            )

            # ?쇱씪 由ы룷???뚮┝ (??긽 ?꾩넚)
            project_lines = "\n".join(
                f"  `{proj}`: {s['calls']}嫄?(${s['cost_usd']:.4f})"
                for proj, s in summary["projects"].items()
            )
            report = (
                f"?뱤 *?쇱씪 鍮꾩슜 由ы룷??\n"
                f"?븧 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"?뮥 ?⑷퀎: *${summary['total_cost']:.4f}* / "
                f"${DAILY_BUDGET_USD:.2f}\n"
                f"?뱸 ?몄텧: {summary['total_calls']}嫄?n"
                f"\n{project_lines}"
            )
            notifier.send(report)
            print("?뱾 ?뚮┝ ?꾩넚 ?꾨즺")

        except Exception as e:
            print(f"?좑툘 ?뚮┝ ?꾩넚 ?ㅽ뙣: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Cost Dashboard")
    parser.add_argument("--days", type=int, default=1, help="議고쉶 湲곌컙 (??")
    parser.add_argument("--notify", action="store_true", help="Discord/Telegram ?뚮┝ ?꾩넚")
    args = parser.parse_args()

    run_cost_dashboard(days=args.days, notify=args.notify)
