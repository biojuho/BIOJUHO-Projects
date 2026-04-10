"""
=======================================================
  X(Twitter) 트렌드 자동 트윗 생성기 v4.1
  - 멀티소스 트렌드 병렬 수집 + 클러스터링
  - Claude AI 바이럴 스코어링 (배치 + 캐시 + 재시도)
  - 5종 단문 + Premium+ 장문 + Threads + 강화 쓰레드
  - 감성 필터(safety_flag) + A/B 변형 + 멀티언어
  - Notion / Google Sheets / SQLite 원자적 트랜잭션 저장
  - 스마트 스케줄링 + 야간 슬립 + SIGTERM 우아한 종료
=======================================================
"""

import argparse
import asyncio
import dataclasses
import io
import os
import signal
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

# ══════════════════════════════════════════════════════
#  자동 PYTHONPATH 설정 (프로젝트 루트 추가)
# ══════════════════════════════════════════════════════
# getdaytrends 디렉토리에서 직접 실행해도 shared 모듈을 찾을 수 있도록
# 프로젝트 루트를 sys.path에 추가
_current_file = Path(__file__).resolve()
_getdaytrends_dir = _current_file.parent
_workspace_root = _getdaytrends_dir.parent  # BUG-019 fix: parent (not parents[1])

for candidate in (_workspace_root, _workspace_root / "packages"):
    candidate_text = str(candidate)
    if candidate_text not in sys.path:
        sys.path.insert(0, candidate_text)

# pytest 실행 중에는 이미 경로가 설정되어 있으므로 중복 추가 방지
if "pytest" not in sys.modules and str(_getdaytrends_dir) not in sys.path:
    sys.path.insert(0, str(_getdaytrends_dir))

# Windows stdout UTF-8 설정 (pytest 실행 중에는 건너뜀: capture 충돌 방지)
if sys.platform == "win32" and "pytest" not in sys.modules and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


import schedule
from loguru import logger as log

try:
    from .config import VERSION, AppConfig
    from .core.pipeline import maybe_cleanup, maybe_send_weekly_cost_report, run_pipeline
    from .db import close_pg_pool, get_connection, get_trend_stats, init_db
    from .utils import run_async
except ImportError:
    from config import VERSION, AppConfig
    from core.pipeline import maybe_cleanup, maybe_send_weekly_cost_report, run_pipeline
    from db import close_pg_pool, get_connection, get_trend_stats, init_db
    from utils import run_async

# ══════════════════════════════════════════════════════
#  프로세스 Lockfile (동시 실행 방지)
# ══════════════════════════════════════════════════════

_LOCK_FILE = Path(__file__).parent / "data" / "getdaytrends.lock"


def _is_pid_alive(pid: int) -> bool:
    """PID가 현재 실행 중인지 확인 (크로스 플랫폼)."""
    if sys.platform == "win32":
        try:
            import ctypes

            SYNCHRONIZE = 0x00100000
            handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False
        except (OSError, PermissionError):
            return False
    # POSIX
    try:
        os.kill(pid, 0)
        return True
    except (OSError, PermissionError):
        return False


def _acquire_lock() -> bool:
    """Lockfile을 획득해 중복 실행을 방지. 이미 실행 중이면 False 반환."""
    _LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)

    def _try_create_lockfile() -> bool:
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        try:
            fd = os.open(_LOCK_FILE, flags)
        except FileExistsError:
            return False

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(str(os.getpid()))
                handle.flush()
            return True
        except Exception:
            _LOCK_FILE.unlink(missing_ok=True)
            raise

    if _LOCK_FILE.exists():
        try:
            pid = int(_LOCK_FILE.read_text().strip())
            if _is_pid_alive(pid):
                print(f"\n  [오류] GetDayTrends가 이미 실행 중입니다 (PID {pid}).")
                print("  중복 실행을 방지하기 위해 종료합니다.\n")
                return False
            # 스테일 lockfile (이전 프로세스가 비정상 종료)
            _LOCK_FILE.unlink(missing_ok=True)
        except (ValueError, OSError):
            _LOCK_FILE.unlink(missing_ok=True)

    return _try_create_lockfile()


def _release_lock() -> None:
    """Lockfile 해제. 자신이 생성한 lockfile만 삭제."""
    try:
        if _LOCK_FILE.exists():
            pid = int(_LOCK_FILE.read_text().strip())
            if pid == os.getpid():
                _LOCK_FILE.unlink(missing_ok=True)
    except (ValueError, OSError):
        pass


# ══════════════════════════════════════════════════════
#  우아한 종료 (SIGTERM / SIGINT)
# ══════════════════════════════════════════════════════

_SHUTDOWN_FLAG = threading.Event()


def _install_signal_handlers() -> None:
    """SIGTERM·SIGINT 수신 시 종료 플래그 설정."""

    def _handler(signum: int, _frame: object) -> None:
        log.warning(f"종료 신호 수신 (signal {signum}) — 현재 파이프라인 완료 후 종료합니다.")
        _SHUTDOWN_FLAG.set()

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)


# ══════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="X 트렌드 자동 트윗 생성기 v4.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--country", default=None, help="국가 코드 (korea, us, japan 등)")
    parser.add_argument("--countries", default=None, help="쉼표 구분 다국가 (korea,us,japan) — 순차 실행")
    parser.add_argument("--limit", type=int, default=None, help="처리할 트렌드 수")
    parser.add_argument("--one-shot", action="store_true", help="1회 실행 후 종료")
    parser.add_argument("--dry-run", action="store_true", help="수집+분석만 (저장 안 함)")
    parser.add_argument("--verbose", action="store_true", help="상세 로그 출력")
    parser.add_argument("--no-alerts", action="store_true", help="알림 전송 안 함")
    parser.add_argument("--schedule-min", type=int, default=None, help="스케줄 간격(분) 오버라이드")
    parser.add_argument("--stats", action="store_true", help="히스토리 통계만 출력 후 종료")
    parser.add_argument("--serve", action="store_true", help="대시보드 웹 서버 실행 (포트 8080)")
    return parser.parse_args()


# ══════════════════════════════════════════════════════
#  Logging
# ══════════════════════════════════════════════════════


def setup_logging(verbose: bool = False) -> None:
    from loguru import logger

    logger.remove()
    level = "DEBUG" if verbose else "INFO"

    logger.add(
        sys.stderr,
        level=level,
        colorize=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )

    logger.add(
        Path(__file__).parent / "data" / "tweet_bot.log",  # B-014 fix: 절대 경로 고정
        rotation="10 MB",
        retention=5,
        encoding="utf-8",
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )


# ══════════════════════════════════════════════════════
#  Banner
# ══════════════════════════════════════════════════════


def print_banner():
    print(
        f"""
╔═══════════════════════════════════════════════════════════╗
║  X 트렌드 자동 트윗 생성기 v{VERSION}                          ║
║  Cache × Retry × Multi-Country × Cost Tracking            ║
╚═══════════════════════════════════════════════════════════╝
"""
    )


def print_config_summary(config: AppConfig):
    country_label = ", ".join(config.countries) if len(config.countries) > 1 else config.country
    country_mode = "parallel" if len(config.countries) > 1 and config.enable_parallel_countries else "single"

    sources = ["getdaytrends.com"]
    if config.twitter_bearer_token:
        sources.append("X API")
    sources.extend(["Reddit", "Google News"])

    alerts_info = []
    if config.telegram_bot_token and config.telegram_chat_id:
        alerts_info.append("Telegram")
    if config.discord_webhook_url:
        alerts_info.append("Discord")

    features = []
    if config.enable_clustering:
        features.append("클러스터링")
    if config.enable_long_form:
        features.append(f"Premium+ 장문(≥{config.long_form_min_score}점)")
    if config.enable_threads:
        features.append("Threads")
    if config.smart_schedule:
        features.append("스마트 스케줄")
    if config.night_mode:
        features.append("야간 슬립(02-07시)")

    print(
        f"""
  설정 요약
  ─────────────────────────────────
  국가         : {country_label}
  국가 실행    : {country_mode}
  트렌드 수    : {config.limit}개
  중복 제외    : {config.dedupe_window_hours}시간 이내 처리 키워드
  저장 방식    : {config.storage_type.upper()}
  실행 간격    : {config.schedule_minutes}분
  톤앤매너     : {config.tone}
  데이터 소스  : {', '.join(sources)}
  병렬 워커    : {config.max_workers}개
  알림 채널    : {', '.join(alerts_info) or '없음'}
  알림 임계값  : {config.alert_threshold}점
  LLM 라우팅   : shared.llm (티어 기반 자동 폴백)
  v2.1 기능    : {', '.join(features) or '없음'}
"""
    )


# ══════════════════════════════════════════════════════
#  Stats
# ══════════════════════════════════════════════════════


async def print_stats(config: AppConfig):
    """히스토리 통계 + LLM 비용 통계 출력."""
    conn = await get_connection(config.db_path, config.database_url)
    try:
        stats = await get_trend_stats(conn)
        print(
            f"""
  히스토리 통계
  ─────────────────────────────────
  총 실행 수      : {stats['total_runs']}회
  총 트렌드 수    : {stats['total_trends']}개
  평균 바이럴 점수: {stats['avg_viral_score']}점
  총 생성 트윗 수 : {stats['total_tweets']}개
"""
        )
    finally:
        await conn.close()

    # LLM 비용 통계 (최근 7일)
    try:
        from shared.llm.stats import _DB_PATH as llm_db_path
        from shared.llm.stats import CostTracker

        if llm_db_path.exists():
            tracker = CostTracker(persist=True)
            daily = tracker.get_daily_stats(7)
            tracker.close()

            if daily:
                print("  LLM 비용 (최근 7일)")
                print("  ─────────────────────────────────")
                by_day: dict = {}
                for row in daily:
                    d = row["date"]
                    by_day.setdefault(d, {"cost": 0.0, "calls": 0})
                    by_day[d]["cost"] += row["cost_usd"]
                    by_day[d]["calls"] += row["calls"]
                total_cost = sum(v["cost"] for v in by_day.values())
                for day in sorted(by_day.keys(), reverse=True)[:7]:
                    v = by_day[day]
                    print(f"  {day} : ${v['cost']:.4f}  ({v['calls']}콜)")
                print("  ─────────────────────────────────")
                print(f"  7일 합계       : ${total_cost:.4f}")
                print(f"  월 추정 비용   : ${total_cost / 7 * 30:.2f}")
                print()
    except (ValueError, KeyError, OSError) as e:
        log.debug(f"LLM 비용 통계 조회 실패: {type(e).__name__}: {e}")


def _normalize_countries(countries: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()

    for country in countries:
        code = (country or "").strip().lower()
        if not code or code in seen:
            continue
        seen.add(code)
        normalized.append(code)

    return normalized


async def _refresh_tap_products_after_parallel_runs(config: AppConfig, countries: list[str]) -> dict:
    """Refresh TAP snapshots after parallel country runs complete."""

    normalized_countries = _normalize_countries(countries)
    if not config.enable_tap or len(normalized_countries) < 2:
        return {}

    try:
        try:
            from .tap import dispatch_tap_alert_queue, refresh_tap_market_surfaces
        except ImportError:
            from tap import dispatch_tap_alert_queue, refresh_tap_market_surfaces

        tap_config = dataclasses.replace(
            config,
            country=normalized_countries[0],
            countries=normalized_countries,
        )
        conn = await get_connection(config.db_path, database_url=config.database_url)
        try:
            await init_db(conn)
            summary = await refresh_tap_market_surfaces(conn, tap_config, snapshot_source="parallel_batch")
            payload = summary.to_dict()
            if payload.get("alerts_queued") and getattr(config, "enable_tap_alert_dispatch", False):
                dispatch_summary = await dispatch_tap_alert_queue(
                    conn,
                    tap_config,
                    limit=max(1, int(getattr(config, "tap_alert_dispatch_batch_size", 5) or 5)),
                )
                payload["dispatch"] = dispatch_summary.to_dict()
        finally:
            await conn.close()

        if payload.get("snapshots_built"):
            print(
                "  TAP refresh       : "
                f"{payload['snapshots_built']} snapshots / {payload['alerts_queued']} alerts queued"
            )
        if payload.get("dispatch"):
            dispatch = payload["dispatch"]
            print(
                "  TAP dispatch      : "
                f"{dispatch['dispatched']} sent / {dispatch['failed']} failed / {dispatch['skipped']} skipped"
            )
        return payload
    except Exception as exc:
        log.warning(f"TAP parallel refresh failed (ignored): {type(exc).__name__}: {exc}")
        return {}


async def _run_countries_parallel_job(config: AppConfig) -> list:
    countries = _normalize_countries(config.countries)
    if not countries:
        return []

    parallel_limit = min(config.country_parallel_limit, len(countries))
    print(f"\n  Parallel countries: {', '.join(country.upper() for country in countries)}")
    print(f"  Concurrency limit : {parallel_limit}")

    if config.smart_schedule and not config.one_shot:
        print("  Smart reschedule stays on the base interval " f"({config.schedule_minutes} min) in parallel mode.")

    semaphore = asyncio.Semaphore(parallel_limit)

    async def _run_single(country: str):
        country_config = config.for_country(country)
        country_config.smart_schedule = False

        async with semaphore:
            started_at = time.perf_counter()
            try:
                result = await asyncio.to_thread(run_pipeline, country_config)
                elapsed = time.perf_counter() - started_at
                return country, result, elapsed, None
            except Exception as exc:  # pragma: no cover - exercised via tests
                elapsed = time.perf_counter() - started_at
                return country, None, elapsed, exc

    # B-004 fix: return_exceptions=True로 단일 국가 실패 시 전체 gather 중단 방지
    # _run_single은 내부 try/except로 Exception을 처리하나,
    # BaseException이 빠져나올 경우 다른 국가 결과 유실 방지
    raw_results = await asyncio.gather(
        *[_run_single(country) for country in countries],
        return_exceptions=True,
    )
    # gather 자체가 예외를 반환한 경우 (BaseException 계열) 폴백 처리
    country_results = []
    for i, res in enumerate(raw_results):
        if isinstance(res, BaseException):
            country = countries[i]
            log.error(f"  [gather] {country.upper()} 예외 탈출: {type(res).__name__}: {res}")
            country_results.append((country, None, 0.0, res))
        else:
            country_results.append(res)

    failures: list[tuple[str, Exception]] = []

    for country, result, elapsed, error in country_results:
        if error is not None:
            failures.append((country, error))
            print(f"  FAIL {country.upper()} ({elapsed:.1f}s): {error}")
            continue

        print(
            f"  OK   {country.upper()} ({elapsed:.1f}s) "
            f"collected={result.trends_collected} "
            f"saved={result.tweets_saved} "
            f"errors={len(result.errors)}"
        )

    if failures:
        failed_countries = ", ".join(country.upper() for country, _ in failures)
        log.error(f"Parallel country run failed: {failed_countries}")
        try:
            from shared.notifications import Notifier
            _notifier = Notifier.from_env()
            if _notifier.has_channels:
                _notifier.send_error(
                    f"병렬 파이프라인 실패 ({failed_countries}): {failures[0][1]}",
                    error=failures[0][1],
                    source="GetDayTrends",
                )
        except Exception as e:
            log.warning(f"Failed to send error notification: {e}")
            
        if len(failures) == len(countries):
            raise RuntimeError(f"All parallel country runs failed: {failed_countries}") from failures[0][1]

    successful_countries = [country for country, _, _, error in country_results if error is None]
    
    try:
        if successful_countries:
            from shared.notifications import Notifier
            _notifier = Notifier.from_env()
            if _notifier.has_channels:
                _notifier.send_heartbeat(
                    "GetDayTrends",
                    status="alive",
                    details=f"병렬 완료: {', '.join(successful_countries)} / 전체: {len(countries)}"
                )
    except Exception as e:
        log.warning(f"Failed to send heartbeat notification: {e}")

    await _refresh_tap_products_after_parallel_runs(config, successful_countries)

    return [result for _, result, _, error in country_results if error is None]


# ══════════════════════════════════════════════════════
#  Entry Point
# ══════════════════════════════════════════════════════


def main():
    # 중복 실행 방지 (--stats, --serve 는 lockfile 불필요)
    _pre_args = sys.argv[1:]
    _skip_lock = any(a in _pre_args for a in ("--stats", "--serve"))
    if not _skip_lock and not _acquire_lock():
        sys.exit(1)

    try:
        _main_body()
    except Exception as exc:
        try:
            from shared.notifications import Notifier
            _notifier = Notifier.from_env()
            if _notifier.has_channels:
                _notifier.send_error(f"GetDayTrends 파이프라인 가동 중단 (main): {exc}", error=exc, source="GetDayTrends")
        except Exception:
            pass
        raise
    finally:
        if not _skip_lock:
            _release_lock()


def _main_body():
    args = parse_args()

    # 설정 로드
    config = AppConfig.from_env()

    # CLI 오버라이드
    if args.countries:
        countries = _normalize_countries(args.countries.split(","))
        config.country = countries[0]
        config.countries = countries
    elif args.country:
        config.country = args.country
        config.countries = [args.country]
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

    # SIGTERM / SIGINT 핸들러 등록
    _install_signal_handlers()

    # DB 초기화 등 앱 레벨 초기 설정
    async def _app_init():
        _conn = await get_connection(config.db_path, database_url=config.database_url)
        await init_db(_conn)
        await maybe_cleanup(_conn, days=config.data_retention_days)
        await maybe_send_weekly_cost_report(_conn, config)
        await _conn.close()

    run_async(_app_init())

    # --serve 모드: 대시보드 웹 서버
    if args.serve:
        try:
            import uvicorn

            try:
                from .dashboard import app as _dashboard_app
            except ImportError:
                from dashboard import app as _dashboard_app

            print("\n  대시보드 서버 시작: http://localhost:8080\n")
            uvicorn.run(_dashboard_app, host="0.0.0.0", port=8080)
        except ImportError as e:
            print(f"\n  서버 실행 실패: {e}")
            print("  → pip install uvicorn 후 재시도\n")
        return

    # --stats 모드
    if args.stats:
        run_async(print_stats(config))
        return

    # 설정 검증 (dry-run이면 storage 키 없어도 허용)
    if config.dry_run:
        from shared.llm.config import load_keys

        keys = load_keys()
        if not any(keys.values()):
            print("\n  설정 오류:\n    LLM API 키가 설정되지 않았습니다.\n  → 루트 .env 파일을 확인해주세요\n")
            return
    else:
        errors = config.validate()
        if errors:
            print("\n  설정 오류:")
            for e in errors:
                print(f"    {e}")
            print("\n  → .env 파일을 확인해주세요\n")
            return

    config.countries = _normalize_countries(config.countries or [config.country])
    config.country = config.countries[0]

    print_config_summary(config)

    # 즉시 1회 실행 (다국가 지원 — 병렬/순차 자동 선택)
    def _run_all_countries():
        try:
            if len(config.countries) > 1 and config.enable_parallel_countries:
                run_async(_run_countries_parallel_job(config))
            else:
                for country in config.countries:
                    country_config = config.for_country(country) if country != config.country else config
                    if len(config.countries) > 1:
                        print(f"\n  ═══ 국가: {country.upper()} ═══")
                    
                    try:
                        result = run_pipeline(country_config, schedule_callback=_run_all_countries)
                        # 단일 실행 시 Heartbeat 연결
                        from shared.notifications import Notifier
                        _notifier = Notifier.from_env()
                        if _notifier.has_channels and result:
                            _notifier.send_heartbeat(
                                "GetDayTrends",
                                status="alive",
                                details=f"국가: {country_config.country} 완료 (수집: {result.trends_collected})"
                            )
                    except Exception as pipe_err:
                        # 단일 실행 시 에러 알림
                        from shared.notifications import Notifier
                        _notifier = Notifier.from_env()
                        if _notifier.has_channels:
                            _notifier.send_error(
                                f"파이프라인 실패 ({country_config.country}): {pipe_err}",
                                error=pipe_err,
                                source="GetDayTrends",
                            )
                        raise
        except Exception as run_err:
            from loguru import logger as log
            log.error(f"스케줄 파이프라인 실행 중 오류: {run_err}")

    _run_all_countries()

    # one-shot이면 여기서 종료
    if config.one_shot:
        print("\n(one-shot 모드: 종료)")
        return

    # 스케줄 등록
    schedule.every(config.schedule_minutes).minutes.do(_run_all_countries)
    print(f"\n  스케줄러 가동 중... ({config.schedule_minutes}분마다)")
    if config.night_mode:
        print("  야간 슬립: 02:00~07:00 자동 대기")
    print("  중단: Ctrl+C\n")

    try:
        while not _SHUTDOWN_FLAG.is_set():
            # 야간 슬립: 02:00~07:00 사이 실행 건너뜀
            if config.night_mode:
                now_hour = datetime.now().hour
                if 2 <= now_hour < 7:
                    wake_at = datetime.now().replace(hour=7, minute=0, second=0, microsecond=0)
                    sleep_seconds = max(0, (wake_at - datetime.now()).total_seconds())  # BUG-013 fix: guard against negative
                    if sleep_seconds > 0:
                        log.info(f"야간 슬립: 07:00까지 {sleep_seconds/60:.0f}분 대기")
                        print(f"  야간 슬립 중... (07:00 기상, {sleep_seconds/60:.0f}분 후)")
                        for _ in range(int(sleep_seconds)):
                            if _SHUTDOWN_FLAG.is_set():
                                break
                            time.sleep(1)
                        continue

            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        _SHUTDOWN_FLAG.set()
    finally:

        async def _cleanup():
            await close_pg_pool()

        run_async(_cleanup())
        print("\n\n  스케줄러 종료. 수고하셨습니다!")


if __name__ == "__main__":
    main()
