"""
NotebookLM Health Check & Auth Refresh Utilities
=================================================
프로덕션 환경에서 NotebookLM 연동 상태를 모니터링하고
세션 자동 갱신을 지원하는 유틸리티 모듈.

Windows Task Scheduler 또는 cron에서 주기적으로 실행 가능.

갱신 전략 (하이브리드):
  1. 세션 나이 ≥ 20시간 → 자동 갱신 시도 (CLI reuse-session)
  2. 갱신 실패 → Telegram/Discord 알림 (수동 개입 요청)
  3. n8n에서 /auth/refresh → proactive_refresh() 호출
"""

import asyncio
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger as log

# 기본 경로
NOTEBOOKLM_HOME = Path.home() / ".notebooklm"
STORAGE_STATE_FILE = NOTEBOOKLM_HOME / "storage_state.json"
HEALTH_LOG_FILE = NOTEBOOKLM_HOME / "health_check.log"
REFRESH_HISTORY_FILE = NOTEBOOKLM_HOME / "refresh_history.json"

# 세션 갱신 기준 (시간)
SESSION_REFRESH_THRESHOLD_HOURS = 20  # 만료(24h) 전 여유 4시간


def check_auth_status() -> dict:
    """
    인증 상태를 확인.
    Returns:
        dict: {
            "authenticated": bool,
            "storage_file_exists": bool,
            "last_modified": str | None,
            "age_hours": float | None,
            "needs_refresh": bool,
        }
    """
    result = {
        "authenticated": False,
        "storage_file_exists": False,
        "last_modified": None,
        "age_hours": None,
        "needs_refresh": True,
    }

    if not STORAGE_STATE_FILE.exists():
        return result

    result["storage_file_exists"] = True

    # 파일 수정 시간으로 세션 나이 계산
    mtime = datetime.fromtimestamp(STORAGE_STATE_FILE.stat().st_mtime)
    result["last_modified"] = mtime.isoformat()
    age_hours = (datetime.now() - mtime).total_seconds() / 3600
    result["age_hours"] = round(age_hours, 1)

    # 임계값 이상이면 갱신 필요
    result["needs_refresh"] = age_hours >= SESSION_REFRESH_THRESHOLD_HOURS

    # CLI로 실제 인증 테스트 (선택적 — 느릴 수 있음)
    try:
        proc = subprocess.run(
            ["notebooklm", "auth", "check", "--test"],
            capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace",
            env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"},
        )
        result["authenticated"] = proc.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        result["authenticated"] = False

    return result


def get_session_cookies_count() -> int:
    """storage_state.json의 쿠키 수 확인 (간접적 인증 상태 체크)."""
    if not STORAGE_STATE_FILE.exists():
        return 0
    try:
        data = json.loads(STORAGE_STATE_FILE.read_text(encoding="utf-8"))
        return len(data.get("cookies", []))
    except Exception:
        return 0


# ──────────────────────────────────────────────────
#  Auth Refresh — 자동 갱신
# ──────────────────────────────────────────────────

def refresh_auth(timeout: int = 120) -> dict:
    """
    NotebookLM 인증 세션을 갱신 시도.

    전략:
      1차: `notebooklm auth login --reuse-session` (기존 쿠키 재사용)
      2차: 실패 시 `notebooklm auth login` (새 브라우저 세션)

    Args:
        timeout: CLI 실행 타임아웃 (초)

    Returns:
        {
            "success": bool,
            "method": str,  # "reuse_session" | "new_session" | "none"
            "message": str,
            "timestamp": str,
        }
    """
    result = {
        "success": False,
        "method": "none",
        "message": "",
        "timestamp": datetime.now().isoformat(),
    }

    env = {**__import__("os").environ, "PYTHONIOENCODING": "utf-8"}

    # 1차 시도: 기존 세션 재사용
    try:
        log.info("[Auth Refresh] 1차 시도: reuse-session")
        proc = subprocess.run(
            ["notebooklm", "auth", "login", "--reuse-session"],
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace", env=env,
        )
        if proc.returncode == 0:
            result["success"] = True
            result["method"] = "reuse_session"
            result["message"] = "기존 세션 재사용으로 갱신 성공"
            log.info("[Auth Refresh] ✅ reuse-session 성공")
            _record_refresh_history(result)
            return result
        log.warning(f"[Auth Refresh] reuse-session 실패: {proc.stderr[:200]}")
    except subprocess.TimeoutExpired:
        log.warning("[Auth Refresh] reuse-session 타임아웃")
    except FileNotFoundError:
        result["message"] = "notebooklm CLI가 설치되지 않았습니다"
        log.error("[Auth Refresh] notebooklm CLI 미설치")
        _record_refresh_history(result)
        return result

    # 2차 시도: 새 브라우저 세션 (headless)
    try:
        log.info("[Auth Refresh] 2차 시도: new session (headless)")
        proc = subprocess.run(
            ["notebooklm", "auth", "login"],
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace", env=env,
        )
        if proc.returncode == 0:
            result["success"] = True
            result["method"] = "new_session"
            result["message"] = "새 세션으로 갱신 성공"
            log.info("[Auth Refresh] ✅ new session 성공")
            _record_refresh_history(result)
            return result
        result["message"] = f"갱신 실패: {proc.stderr[:200]}"
        log.warning(f"[Auth Refresh] new session 실패: {proc.stderr[:200]}")
    except subprocess.TimeoutExpired:
        result["message"] = "갱신 타임아웃 (브라우저 응답 없음 — MFA/캡챠 필요할 수 있음)"
        log.warning("[Auth Refresh] new session 타임아웃")
    except Exception as e:
        result["message"] = f"갱신 예외: {e}"
        log.error(f"[Auth Refresh] 예외: {e}")

    _record_refresh_history(result)
    return result


def proactive_refresh() -> dict:
    """
    선제적 인증 갱신: 세션 나이를 확인하고 필요 시 자동 갱신.

    Returns:
        {
            "action": "skipped" | "refreshed" | "failed",
            "auth_status": dict,
            "refresh_result": dict | None,
            "alert_sent": bool,
        }
    """
    auth = check_auth_status()

    result = {
        "action": "skipped",
        "auth_status": auth,
        "refresh_result": None,
        "alert_sent": False,
    }

    # 갱신 불필요
    if not auth["needs_refresh"] and auth["authenticated"]:
        log.debug(
            f"[Proactive Refresh] 세션 정상 "
            f"(나이: {auth['age_hours']}h, 임계: {SESSION_REFRESH_THRESHOLD_HOURS}h)"
        )
        return result

    # 갱신 시도
    log.info(
        f"[Proactive Refresh] 갱신 필요 — "
        f"나이: {auth['age_hours']}h, 인증: {auth['authenticated']}"
    )
    refresh = refresh_auth()
    result["refresh_result"] = refresh

    if refresh["success"]:
        result["action"] = "refreshed"
        log.info("[Proactive Refresh] ✅ 세션 갱신 성공")
    else:
        result["action"] = "failed"
        log.error(f"[Proactive Refresh] ❌ 갱신 실패: {refresh['message']}")

        # 알림 발송
        try:
            alert_ok = send_auth_alert(refresh["message"])
            result["alert_sent"] = alert_ok
        except Exception as e:
            log.warning(f"[Proactive Refresh] 알림 발송 실패: {e}")

    return result


def send_auth_alert(error_message: str = "") -> bool:
    """
    인증 갱신 실패 시 Telegram/Discord 알림 발송.

    Returns:
        bool: 하나 이상의 채널에 성공적으로 발송되었으면 True
    """
    try:
        from config import AppConfig
        from alerts import send_alert

        config = AppConfig.from_env()

        age_info = ""
        auth = check_auth_status()
        if auth["age_hours"] is not None:
            age_info = f"\n⏱️ 세션 나이: {auth['age_hours']}시간"

        message = (
            f"🔴 *NotebookLM 인증 갱신 실패*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ 자동 갱신이 실패했습니다.\n"
            f"수동으로 인증을 갱신해주세요.\n"
            f"{age_info}\n"
            f"📝 오류: {error_message[:300]}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🔧 수동 갱신 명령:\n"
            f"`notebooklm auth login`"
        )

        results = send_alert(message, config)
        sent = any(r.get("ok") for r in results.values()) if results else False

        if sent:
            log.info("[Auth Alert] ✅ 알림 발송 완료")
        else:
            log.warning("[Auth Alert] 모든 알림 채널 실패")

        return sent

    except ImportError:
        log.warning("[Auth Alert] alerts 모듈 미사용 가능 — 알림 스킵")
        return False
    except Exception as e:
        log.error(f"[Auth Alert] 알림 발송 예외: {e}")
        return False


# ──────────────────────────────────────────────────
#  Refresh History — 이력 관리
# ──────────────────────────────────────────────────

def _record_refresh_history(result: dict):
    """갱신 이력을 JSON 파일에 추가 기록."""
    try:
        REFRESH_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

        history = []
        if REFRESH_HISTORY_FILE.exists():
            try:
                history = json.loads(
                    REFRESH_HISTORY_FILE.read_text(encoding="utf-8")
                )
                if not isinstance(history, list):
                    history = []
            except (json.JSONDecodeError, Exception):
                history = []

        history.append(result)

        # 최근 100건만 유지
        history = history[-100:]

        REFRESH_HISTORY_FILE.write_text(
            json.dumps(history, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        log.debug(f"갱신 이력 기록 실패 (무시): {e}")


def get_refresh_history(limit: int = 10) -> list[dict]:
    """최근 갱신 이력 조회."""
    if not REFRESH_HISTORY_FILE.exists():
        return []
    try:
        history = json.loads(
            REFRESH_HISTORY_FILE.read_text(encoding="utf-8")
        )
        return history[-limit:] if isinstance(history, list) else []
    except Exception:
        return []


# ──────────────────────────────────────────────────
#  Health Check — 종합 상태
# ──────────────────────────────────────────────────

async def health_check(verbose: bool = False) -> dict:
    """
    종합 헬스 체크 — 인증 + 기본 API 동작 확인.
    Returns:
        dict: {
            "timestamp": str,
            "auth": dict,
            "api_reachable": bool,
            "notebook_count": int | None,
            "status": "healthy" | "degraded" | "down",
        }
    """
    result = {
        "timestamp": datetime.now().isoformat(),
        "auth": check_auth_status(),
        "api_reachable": False,
        "notebook_count": None,
        "status": "down",
    }

    if not result["auth"]["authenticated"]:
        _log_health(result)
        return result

    # API 도달 가능성 테스트 — list 명령 실행
    try:
        proc = subprocess.run(
            ["notebooklm", "list", "--json"],
            capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace",
            env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"},
        )
        if proc.returncode == 0:
            result["api_reachable"] = True
            try:
                notebooks = json.loads(proc.stdout)
                result["notebook_count"] = len(notebooks) if isinstance(notebooks, list) else None
            except json.JSONDecodeError:
                # JSON 파싱 실패해도 API 도달은 성공
                result["notebook_count"] = None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # 상태 판정
    if result["api_reachable"] and result["auth"]["authenticated"]:
        if result["auth"]["needs_refresh"]:
            result["status"] = "degraded"  # 곧 만료 예정
        else:
            result["status"] = "healthy"
    elif result["auth"]["authenticated"]:
        result["status"] = "degraded"
    else:
        result["status"] = "down"

    _log_health(result)

    if verbose:
        print(f"\n{'='*50}")
        print(f"  NotebookLM Health Check")
        print(f"  Timestamp: {result['timestamp']}")
        print(f"  Auth: {'OK' if result['auth']['authenticated'] else 'FAIL'}")
        print(f"  Session Age: {result['auth']['age_hours']}h")
        print(f"  API: {'OK' if result['api_reachable'] else 'FAIL'}")
        print(f"  Status: {result['status'].upper()}")
        print(f"{'='*50}\n")

    return result


def _log_health(result: dict):
    """헬스 체크 결과를 로그 파일에 기록."""
    try:
        HEALTH_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(HEALTH_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ──────────────────────────────────────────────────
#  CLI Entry Point
# ──────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="NotebookLM Health Check & Auth Refresh")
    parser.add_argument("--verbose", "-v", action="store_true", help="상세 출력")
    parser.add_argument("--json", action="store_true", help="JSON 출력")
    parser.add_argument("--refresh", action="store_true", help="인증 갱신 시도")
    parser.add_argument("--proactive", action="store_true", help="선제적 인증 갱신 (필요 시만)")
    args = parser.parse_args()

    if args.refresh:
        result = refresh_auth()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.proactive:
        result = proactive_refresh()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        result = asyncio.run(health_check(verbose=args.verbose))
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif not args.verbose:
            status = result["status"]
            icon = {"healthy": "[OK]", "degraded": "[!!]", "down": "[XX]"}.get(status, "[??]")
            print(f"{icon} NotebookLM: {status}")
