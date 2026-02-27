"""
=======================================================
  X(Twitter) 트렌드 자동 트윗 생성기 v2.0
  - 멀티소스 트렌드 수집 (getdaytrends + X API + Reddit + News)
  - Claude AI 바이럴 스코어링 + 5종 트윗/쓰레드 생성
  - Notion / Google Sheets / SQLite 자동 저장
  - Telegram / Discord 고바이럴 트렌드 알림
=======================================================
"""

import argparse
import io
import logging
import sys
import time
import uuid
from datetime import datetime

# Windows stdout UTF-8 설정
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import anthropic
import schedule

from alerts import check_and_alert
from analyzer import analyze_trends, detect_trend_patterns
from config import AppConfig
from db import get_connection, get_trend_stats, init_db, save_run, update_run
from generator import generate_for_trend
from models import RunResult
from scraper import collect_trends
from storage import save

log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="X 트렌드 자동 트윗 생성기 v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--country", default=None, help="국가 코드 (korea, us, japan 등)")
    parser.add_argument("--limit", type=int, default=None, help="처리할 트렌드 수")
    parser.add_argument("--one-shot", action="store_true", help="1회 실행 후 종료")
    parser.add_argument("--dry-run", action="store_true", help="수집+분석만 (저장 안 함)")
    parser.add_argument("--verbose", action="store_true", help="상세 로그 출력")
    parser.add_argument("--no-alerts", action="store_true", help="알림 전송 안 함")
    parser.add_argument("--schedule-min", type=int, default=None, help="스케줄 간격(분) 오버라이드")
    parser.add_argument("--stats", action="store_true", help="히스토리 통계만 출력 후 종료")
    return parser.parse_args()


# ══════════════════════════════════════════════════════
#  Logging
# ══════════════════════════════════════════════════════

def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("tweet_bot.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


# ══════════════════════════════════════════════════════
#  Banner
# ══════════════════════════════════════════════════════

def print_banner():
    print("""
╔═══════════════════════════════════════════════════════╗
║  X 트렌드 자동 트윗 생성기 v2.0                      ║
║  Multi-Source × Viral Scoring × Claude AI × Auto Save ║
╚═══════════════════════════════════════════════════════╝
""")


def print_config_summary(config: AppConfig):
    sources = ["getdaytrends.com"]
    if config.twitter_bearer_token:
        sources.append("X API")
    sources.extend(["Reddit", "Google News"])

    alerts_info = []
    if config.telegram_bot_token and config.telegram_chat_id:
        alerts_info.append("Telegram")
    if config.discord_webhook_url:
        alerts_info.append("Discord")

    print(f"""
  설정 요약
  ─────────────────────────────────
  국가         : {config.country}
  트렌드 수    : {config.limit}개
  저장 방식    : {config.storage_type.upper()}
  실행 간격    : {config.schedule_minutes}분
  톤앤매너     : {config.tone}
  데이터 소스  : {', '.join(sources)}
  알림 채널    : {', '.join(alerts_info) or '없음'}
  알림 임계값  : {config.alert_threshold}점
  스코어링 모델: {config.claude_model_scoring}
  생성 모델    : {config.claude_model}
""")


# ══════════════════════════════════════════════════════
#  Pipeline
# ══════════════════════════════════════════════════════

def run_pipeline(config: AppConfig, conn) -> RunResult:
    """전체 파이프라인: 수집 → 스코어링 → 알림 → 생성 → 저장."""
    run = RunResult(run_id=str(uuid.uuid4()), country=config.country)
    run_row_id = save_run(conn, run)

    separator = "=" * 55
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{separator}")
    print(f"  작업 시작: {now_str}")
    print(separator)

    # Step 1: 멀티소스 트렌드 수집
    print("\n[1/4] 멀티소스 트렌드 수집 중...")
    raw_trends, contexts = collect_trends(config)
    run.trends_collected = len(raw_trends)
    print(f"  수집 완료: {len(raw_trends)}개 트렌드")

    if not raw_trends:
        run.errors.append("트렌드 수집 실패")
        run.finished_at = datetime.now()
        update_run(conn, run, run_row_id)
        return run

    # Step 2: 바이럴 스코어링
    print("\n[2/4] 바이럴 스코어링 중...")
    scored_trends = analyze_trends(raw_trends, contexts, config)
    run.trends_scored = len(scored_trends)

    # 스코어 미리보기
    for st in scored_trends:
        score_bar = "█" * (st.viral_potential // 10) + "░" * (10 - st.viral_potential // 10)
        print(f"  #{st.rank} [{score_bar}] {st.viral_potential:3d}점 | {st.keyword}")

        # 히스토리 패턴 정보
        if config.verbose:
            pattern = detect_trend_patterns(conn, st.keyword)
            if pattern["seen_count"] > 0:
                print(f"       ↳ 히스토리: {pattern['seen_count']}회 등장, 평균 {pattern['avg_score']}점, 추세: {pattern['score_trend']}")

    # Step 3: 알림 전송 (스코어링 직후, 생성 전)
    if not config.no_alerts:
        alerts_sent = check_and_alert(scored_trends, config)
        run.alerts_sent = alerts_sent
        if alerts_sent:
            print(f"\n  알림 전송: {alerts_sent}건")

    # Step 4: 트윗/쓰레드 생성 + 저장
    print("\n[3/4] 트윗 생성 중...")
    client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    success_count = 0

    for i, trend in enumerate(scored_trends):
        print(f"\n  [{i + 1}/{len(scored_trends)}] '{trend.keyword}' (바이럴: {trend.viral_potential}점)")

        batch = generate_for_trend(trend, config, client)
        if not batch:
            run.errors.append(f"생성 실패: {trend.keyword}")
            continue

        run.tweets_generated += len(batch.tweets)

        # 미리보기
        for t in batch.tweets:
            preview = t.content[:50] + "..." if len(t.content) > 50 else t.content
            print(f"    [{t.tweet_type}] {preview}")
        if batch.thread:
            print(f"    [쓰레드] {len(batch.thread.tweets)}개 트윗")

        # 저장
        print(f"  [4/4] 저장 중...")
        ok = save(batch, trend, run_row_id, config, conn)
        if ok:
            success_count += 1
            run.tweets_saved += len(batch.tweets)

        # API rate limit 방지
        if i < len(scored_trends) - 1:
            time.sleep(3)

    run.finished_at = datetime.now()
    update_run(conn, run, run_row_id)

    elapsed = (run.finished_at - run.started_at).total_seconds()
    print(f"\n{separator}")
    print(f"  완료: {success_count}/{len(scored_trends)}개 저장")
    print(f"  소요: {elapsed:.1f}초")
    if not config.one_shot:
        print(f"  다음 실행: {config.schedule_minutes}분 후")
    print(separator)

    return run


# ══════════════════════════════════════════════════════
#  Stats
# ══════════════════════════════════════════════════════

def print_stats(conn):
    """히스토리 통계 출력."""
    stats = get_trend_stats(conn)
    print(f"""
  히스토리 통계
  ─────────────────────────────────
  총 실행 수      : {stats['total_runs']}회
  총 트렌드 수    : {stats['total_trends']}개
  평균 바이럴 점수: {stats['avg_viral_score']}점
  총 생성 트윗 수 : {stats['total_tweets']}개
""")


# ══════════════════════════════════════════════════════
#  Entry Point
# ══════════════════════════════════════════════════════

def main():
    args = parse_args()

    # 설정 로드
    config = AppConfig.from_env()

    # CLI 오버라이드
    if args.country:
        config.country = args.country
    if args.limit:
        config.limit = args.limit
    if args.one_shot:
        config.one_shot = True
    if args.dry_run:
        config.dry_run = True
    if args.verbose:
        config.verbose = True
    if args.no_alerts:
        config.no_alerts = True
    if args.schedule_min:
        config.schedule_minutes = args.schedule_min

    setup_logging(config.verbose)
    print_banner()

    # DB 초기화
    conn = get_connection(config.db_path)
    init_db(conn)

    # --stats 모드
    if args.stats:
        print_stats(conn)
        conn.close()
        return

    # 설정 검증 (dry-run이면 storage 키 없어도 허용)
    if config.dry_run:
        if not config.anthropic_api_key or "your_" in config.anthropic_api_key:
            print("\n  설정 오류:\n    ANTHROPIC_API_KEY가 설정되지 않았습니다.\n  → .env 파일을 확인해주세요\n")
            conn.close()
            return
    else:
        errors = config.validate()
        if errors:
            print("\n  설정 오류:")
            for e in errors:
                print(f"    {e}")
            print("\n  → .env 파일을 확인해주세요\n")
            conn.close()
            return

    print_config_summary(config)

    # 즉시 1회 실행
    run_pipeline(config, conn)

    # one-shot이면 여기서 종료
    if config.one_shot:
        conn.close()
        print("\n(one-shot 모드: 종료)")
        return

    # 스케줄 등록
    schedule.every(config.schedule_minutes).minutes.do(run_pipeline, config, conn)
    print(f"\n  스케줄러 가동 중... ({config.schedule_minutes}분마다)")
    print("  중단: Ctrl+C\n")

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        conn.close()
        print("\n\n  스케줄러 종료. 수고하셨습니다!")


if __name__ == "__main__":
    main()
