"""Health check & auth refresh utilities.

Refactored from ``getdaytrends/notebooklm_health.py`` — all path constants
now come from :mod:`notebooklm_automation.config`.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from datetime import datetime

from loguru import logger as log

from .config import get_config

# ──────────────────────────────────────────────────
#  Auth Status
# ──────────────────────────────────────────────────


def check_auth_status() -> dict:
    """Return auth status dict with ``authenticated``, ``age_hours``, ``needs_refresh``."""
    cfg = get_config()
    result = {
        "authenticated": False,
        "storage_file_exists": False,
        "last_modified": None,
        "age_hours": None,
        "needs_refresh": True,
    }

    if not cfg.storage_state_file.exists():
        return result

    result["storage_file_exists"] = True
    mtime = datetime.fromtimestamp(cfg.storage_state_file.stat().st_mtime)
    result["last_modified"] = mtime.isoformat()
    age_hours = (datetime.now() - mtime).total_seconds() / 3600
    result["age_hours"] = round(age_hours, 1)
    result["needs_refresh"] = age_hours >= cfg.session_refresh_threshold_hours

    import os

    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    try:
        proc = subprocess.run(
            ["notebooklm", "auth", "check", "--test"],
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        result["authenticated"] = proc.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        result["authenticated"] = False

    return result


def get_session_cookies_count() -> int:
    """Return number of cookies in storage state (indirect auth check)."""
    cfg = get_config()
    if not cfg.storage_state_file.exists():
        return 0
    try:
        data = json.loads(cfg.storage_state_file.read_text(encoding="utf-8"))
        return len(data.get("cookies", []))
    except Exception:
        return 0


# ──────────────────────────────────────────────────
#  Auth Refresh
# ──────────────────────────────────────────────────


def refresh_auth(timeout: int = 120) -> dict:
    """Attempt to refresh the NotebookLM auth session.

    Strategy:
    1. ``notebooklm auth login --reuse-session`` (reuse cookies)
    2. ``notebooklm auth login`` (fresh browser session)
    """
    import os

    result = {
        "success": False,
        "method": "none",
        "message": "",
        "timestamp": datetime.now().isoformat(),
    }
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

    # Attempt 1: reuse-session
    try:
        log.info("[Auth Refresh] attempt 1: reuse-session")
        proc = subprocess.run(
            ["notebooklm", "auth", "login", "--reuse-session"],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        if proc.returncode == 0:
            result.update(success=True, method="reuse_session", message="기존 세션 재사용으로 갱신 성공")
            _record_refresh_history(result)
            return result
        log.warning("[Auth Refresh] reuse-session failed: %s", proc.stderr[:200])
    except subprocess.TimeoutExpired:
        log.warning("[Auth Refresh] reuse-session timeout")
    except FileNotFoundError:
        result["message"] = "notebooklm CLI is not installed"
        _record_refresh_history(result)
        return result

    # Attempt 2: fresh session
    try:
        log.info("[Auth Refresh] attempt 2: new session")
        proc = subprocess.run(
            ["notebooklm", "auth", "login"],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        if proc.returncode == 0:
            result.update(success=True, method="new_session", message="새 세션으로 갱신 성공")
            _record_refresh_history(result)
            return result
        result["message"] = f"갱신 실패: {proc.stderr[:200]}"
    except subprocess.TimeoutExpired:
        result["message"] = "갱신 타임아웃 (MFA/CAPTCHA 필요할 수 있음)"
    except Exception as e:
        result["message"] = f"갱신 예외: {e}"

    _record_refresh_history(result)
    return result


def proactive_refresh() -> dict:
    """Proactive refresh: check age, refresh only if needed."""
    auth = check_auth_status()
    result = {
        "action": "skipped",
        "auth_status": auth,
        "refresh_result": None,
        "alert_sent": False,
    }

    if not auth["needs_refresh"] and auth["authenticated"]:
        return result

    refresh = refresh_auth()
    result["refresh_result"] = refresh

    if refresh["success"]:
        result["action"] = "refreshed"
    else:
        result["action"] = "failed"
        try:
            result["alert_sent"] = send_auth_alert(refresh["message"])
        except Exception as e:
            log.warning("[Proactive Refresh] alert failed: %s", e)

    return result


def send_auth_alert(error_message: str = "") -> bool:
    """Send auth failure alert via Telegram / Discord / httpx webhook."""
    import httpx

    cfg = get_config()
    auth = check_auth_status()
    age_info = f"\n⏱️ 세션 나이: {auth['age_hours']}시간" if auth["age_hours"] is not None else ""

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

    sent = False

    # Telegram
    if cfg.telegram_bot_token and cfg.telegram_chat_id:
        try:
            resp = httpx.post(
                f"https://api.telegram.org/bot{cfg.telegram_bot_token}/sendMessage",
                json={"chat_id": cfg.telegram_chat_id, "text": message, "parse_mode": "Markdown"},
                timeout=10,
            )
            sent = sent or resp.status_code == 200
        except Exception as e:
            log.warning("[Alert] Telegram failed: %s", e)

    # Discord
    if cfg.discord_webhook_url:
        try:
            resp = httpx.post(
                cfg.discord_webhook_url,
                json={"content": message.replace("*", "**")},
                timeout=10,
            )
            sent = sent or resp.status_code in (200, 204)
        except Exception as e:
            log.warning("[Alert] Discord failed: %s", e)

    return sent


# ──────────────────────────────────────────────────
#  Refresh History
# ──────────────────────────────────────────────────


def _record_refresh_history(result: dict) -> None:
    cfg = get_config()
    try:
        cfg.refresh_history_file.parent.mkdir(parents=True, exist_ok=True)
        history: list = []
        if cfg.refresh_history_file.exists():
            try:
                history = json.loads(cfg.refresh_history_file.read_text(encoding="utf-8"))
                if not isinstance(history, list):
                    history = []
            except Exception:
                history = []
        history.append(result)
        history = history[-100:]
        cfg.refresh_history_file.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        log.debug("refresh history write failed: %s", e)


def get_refresh_history(limit: int = 10) -> list[dict]:
    cfg = get_config()
    if not cfg.refresh_history_file.exists():
        return []
    try:
        history = json.loads(cfg.refresh_history_file.read_text(encoding="utf-8"))
        return history[-limit:] if isinstance(history, list) else []
    except Exception:
        return []


# ──────────────────────────────────────────────────
#  Health Check
# ──────────────────────────────────────────────────


async def health_check(verbose: bool = False) -> dict:
    """Comprehensive health check — auth + basic API operation."""
    import os

    cfg = get_config()
    result = {
        "timestamp": datetime.now().isoformat(),
        "auth": check_auth_status(),
        "api_reachable": False,
        "notebook_count": None,
        "status": "down",
    }

    if not result["auth"]["authenticated"]:
        _log_health(result, cfg)
        return result

    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    try:
        proc = subprocess.run(
            ["notebooklm", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        if proc.returncode == 0:
            result["api_reachable"] = True
            try:
                notebooks = json.loads(proc.stdout)
                result["notebook_count"] = len(notebooks) if isinstance(notebooks, list) else None
            except json.JSONDecodeError:
                pass
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    if result["api_reachable"] and result["auth"]["authenticated"]:
        result["status"] = "degraded" if result["auth"]["needs_refresh"] else "healthy"
    elif result["auth"]["authenticated"]:
        result["status"] = "degraded"

    _log_health(result, cfg)

    if verbose:
        print(f"\n{'='*50}")
        print("  NotebookLM Health Check")
        print(f"  Auth: {'OK' if result['auth']['authenticated'] else 'FAIL'}")
        print(f"  Session Age: {result['auth']['age_hours']}h")
        print(f"  API: {'OK' if result['api_reachable'] else 'FAIL'}")
        print(f"  Status: {result['status'].upper()}")
        print(f"{'='*50}\n")

    return result


def _log_health(result: dict, cfg=None) -> None:
    if cfg is None:
        cfg = get_config()
    try:
        cfg.health_log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cfg.health_log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ──────────────────────────────────────────────────
#  CLI Entry Point
# ──────────────────────────────────────────────────


def _cli_main() -> None:
    """CLI entry point registered as ``notebooklm-health``."""
    import argparse

    parser = argparse.ArgumentParser(description="NotebookLM Health Check & Auth Refresh")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--proactive", action="store_true")
    args = parser.parse_args()

    if args.refresh:
        r = refresh_auth()
        print(json.dumps(r, ensure_ascii=False, indent=2))
    elif args.proactive:
        r = proactive_refresh()
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        r = asyncio.run(health_check(verbose=args.verbose))
        if args.json:
            print(json.dumps(r, ensure_ascii=False, indent=2))
        elif not args.verbose:
            icon = {"healthy": "[OK]", "degraded": "[!!]", "down": "[XX]"}.get(r["status"], "[??]")
            print(f"{icon} NotebookLM: {r['status']}")
