"""
=======================================================
  getdaytrends v4.1
  - Twitter (X) integrations
  - Claude AI + fallback routing + adaptive behavior
  - Reddit, Premium+, Threads, Telegram sources
  - Safety checks (A/B) and stability hardening
  - Notion / Google Sheets / SQLite output support
  - Graceful process shutdown with SIGTERM handling
=======================================================
"""

# ruff: noqa: E402
# This script adjusts sys.path before local imports so it can run directly
# from the workspace root or from automation/getdaytrends.

import argparse
import asyncio
import dataclasses
import hashlib
import importlib.util
import io
import os
import re
import signal
import socket
import sys
import threading
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import unquote, urlparse

# --------------------------------------------------
#  PYTHONPATH setup (workspace and package roots)
# --------------------------------------------------
# This script runs from source checkout and resolves shared imports.
# Ensure both workspace root and package root are in sys.path for direct execution.
_current_file = Path(__file__).resolve()
_getdaytrends_dir = _current_file.parent
# Workspace root is one level above automation/getdaytrends.
# This keeps packages/shared imports working.
# Parent[1] resolves to the repository root.
_workspace_root = _getdaytrends_dir.parents[1]

for candidate in (_workspace_root, _workspace_root / "packages"):
    candidate_text = str(candidate)
    if candidate_text not in sys.path:
        sys.path.insert(0, candidate_text)

# Skip duplicate path injection while running tests.
if "pytest" not in sys.modules and str(_getdaytrends_dir) not in sys.path:
    sys.path.insert(0, str(_getdaytrends_dir))

# Windows stdout UTF-8: keep stream stable (skip reconfiguration in pytest capture mode).
if sys.platform == "win32" and "pytest" not in sys.modules and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# asyncpg + SSL can trigger event-loop errors with Windows ProactorEventLoop.
# Force SelectorEventLoop on Windows to avoid closed-loop / send errors.
# Python 3.16 removed set_event_loop_policy; call set_event_loop directly.
if sys.platform == "win32":
    asyncio.set_event_loop(asyncio.SelectorEventLoop())


def _read_fast_version() -> str:
    """Read VERSION without importing the full runtime stack."""
    config_path = _getdaytrends_dir / "config.py"
    try:
        match = re.search(
            r"^VERSION\s*=\s*[\"']([^\"']+)[\"']",
            config_path.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
    except OSError:
        return "unknown"
    return match.group(1) if match else "unknown"


def _maybe_exit_fast_version(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    if "--version" in args:
        print(f"getdaytrends {_read_fast_version()}")
        raise SystemExit(0)


_maybe_exit_fast_version()


import schedule
from loguru import logger as log

from getdaytrends.config import VERSION, AppConfig
from getdaytrends.core.pipeline import maybe_cleanup, maybe_send_weekly_cost_report, run_pipeline
from getdaytrends.db import close_pg_pool, get_connection, get_trend_stats, init_db
from getdaytrends.utils import run_async

# --------------------------------------------------
#  Lockfile (single-run protection)
# --------------------------------------------------

_LOCK_FILE = Path(__file__).parent / "data" / "getdaytrends.lock"
SUPABASE_CONNECTION_DOC_URL = "https://supabase.com/docs/reference/postgres/connection-strings"


def _is_pid_alive(pid: int) -> bool:
    """Return True if the PID is still running."""
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


def _remove_lockfile_if_possible(lock_path: Path) -> bool:
    for attempt in range(3):
        try:
            lock_path.unlink(missing_ok=True)
            return True
        except PermissionError:
            if attempt == 2:
                return False
            time.sleep(0.01)
        except OSError:
            return False
    return False


def _try_create_lockfile(lock_path: Path) -> bool:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(lock_path, flags)
    except FileExistsError:
        return False

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(str(os.getpid()))
            handle.flush()
        return True
    except Exception:
        _remove_lockfile_if_possible(lock_path)
        raise


def _acquire_lock() -> bool:
    """Create the lockfile and block duplicate process starts."""
    _LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)

    if _LOCK_FILE.exists():
        try:
            pid = int(_LOCK_FILE.read_text().strip())
            if _is_pid_alive(pid):
                print(f"\n  [ERROR] GetDayTrends is already running (PID {pid}).")
                print("  Duplicate execution prevented. Exiting.\n")
                return False
            # Remove stale lockfile (previous process ended unexpectedly).
            if not _remove_lockfile_if_possible(_LOCK_FILE):
                return False
        except (ValueError, OSError):
            if not _remove_lockfile_if_possible(_LOCK_FILE):
                return False

    return _try_create_lockfile(_LOCK_FILE)


def _release_lock() -> None:
    """Release lockfile on process shutdown."""
    for attempt in range(3):
        try:
            if _LOCK_FILE.exists():
                pid = int(_LOCK_FILE.read_text().strip())
                if pid == os.getpid():
                    _LOCK_FILE.unlink(missing_ok=True)
            return
        except (ValueError, OSError):
            if attempt == 2:
                return
            time.sleep(0.01)


# =======================================================
#  Graceful shutdown (SIGTERM / SIGINT)
# =======================================================

_SHUTDOWN_FLAG = threading.Event()


def _install_signal_handlers() -> None:
    """Register SIGTERM / SIGINT handlers for graceful shutdown."""

    def _handler(signum: int, _frame: object) -> None:
        log.warning(f"Shutdown signal received (signal {signum}); stopping.")
        _SHUTDOWN_FLAG.set()

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)


#  CLI
# --------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="getdaytrends CLI runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"getdaytrends {VERSION}")
    parser.add_argument("--country", default=None, help="Run only one country (korea, us, japan, uk, india, global)")
    parser.add_argument("--countries", default=None, help="Comma-separated countries (korea,us,japan) for multi-country runs")
    parser.add_argument("--limit", type=int, default=None, help="Max trends to process")
    parser.add_argument("--one-shot", action="store_true", help="Run once and exit")
    parser.add_argument("--dry-run", action="store_true", help="Collect/analyze only, skip storage")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logs")
    parser.add_argument("--no-alerts", action="store_true", help="Disable alert sending")
    parser.add_argument("--doctor", action="store_true", help="Run environment and dependency checks only")
    parser.add_argument(
        "--require-live-db",
        action="store_true",
        help="With --doctor/--health-check, run a non-destructive live PostgreSQL SELECT 1 probe.",
    )
    parser.add_argument(
        "--health-check",
        action="store_true",
        help="Alias for --doctor; intended for schedulers and monitor probes",
    )
    parser.add_argument("--schedule-min", type=int, default=None, help="Override schedule interval (minutes)")
    parser.add_argument("--stats", action="store_true", help="Print stats and exit")
    parser.add_argument("--serve", action="store_true", help="Run dashboard server at port 8080")
    return parser.parse_args()


# --------------------------------------------------
#  Logging
# --------------------------------------------------

_LOG_TOKEN_PATTERNS = re.compile(
    r"(ntn_[A-Za-z0-9]{6})[A-Za-z0-9]*"  # Notion
    r"|(sk-[A-Za-z0-9]{6})[A-Za-z0-9]*"  # OpenAI
    r"|(ghp_[A-Za-z0-9]{6})[A-Za-z0-9]*"  # GitHub PAT
    r"|(xai-[A-Za-z0-9]{6})[A-Za-z0-9]*"  # X.AI
    r"|(AIza[A-Za-z0-9_-]{6})[A-Za-z0-9_-]*"  # Google API Key
)


def _mask_log_tokens(message: str) -> str:
    def _replacer(match: re.Match[str]) -> str:
        for group in match.groups():
            if group:
                return group + "***"
        return match.group(0)

    return _LOG_TOKEN_PATTERNS.sub(_replacer, message)


def setup_logging(verbose: bool = False) -> None:
    from loguru import logger

    logger.remove()
    level = "DEBUG" if verbose else "INFO"

    def _patched_format(record: Any) -> str:
        record["extra"]["masked_message"] = _mask_log_tokens(str(record["message"]))
        return (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{extra[masked_message]}</level>\n{exception}"
        )

    logger.add(
        sys.stderr,
        level=level,
        colorize=True,
        format=_patched_format,
    )

    def _file_format(record: Any) -> str:
        record["extra"]["masked_message"] = _mask_log_tokens(str(record["message"]))
        return (
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {extra[masked_message]}\n{exception}"
        )

    logger.add(
        Path(__file__).parent / "data" / "tweet_bot.log",  # B-014 fix: fixed absolute path
        rotation="10 MB",
        retention=5,
        encoding="utf-8",
        level=level,
        format=_file_format,
    )


def _module_available(module_name: str) -> bool:
    """Return True when a module spec is importable."""

    return importlib.util.find_spec(module_name) is not None


def _mask_sensitive_value(value: str | None) -> str:
    """Mask credentials in values printed to operator terminals."""

    if not value:
        return ""

    text = str(value)
    if "://" in text and "@" in text:
        scheme, rest = text.split("://", 1)
        if "@" in rest:
            host_part = rest.rsplit("@", 1)[-1]
            return f"{scheme}://***:***@{host_part}"

    secret_markers = ("token", "secret", "password", "apikey", "api_key")
    lowered = text.lower()
    if any(marker in lowered for marker in secret_markers):
        return text[:6] + "***" if len(text) > 6 else "***"

    return text


def _mask_database_error(value: object) -> str:
    text = str(value)
    text = re.sub(r"((?:postgresql|postgres)://)[^@\s]+@", r"\1***:***@", text)
    text = re.sub(r"(tenant/user\s+)[^\s)]+", r"\1***", text, flags=re.IGNORECASE)
    text = re.sub(r"\bpostgres\.[A-Za-z0-9_.-]+", "postgres.***", text)
    return text


def _read_env_key(env_path: Path, key: str) -> str | None:
    try:
        lines = env_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() != key:
            continue
        parsed = value.strip()
        if len(parsed) >= 2 and parsed[0] == parsed[-1] and parsed[0] in {"'", '"'}:
            parsed = parsed[1:-1]
        return parsed
    return None


def _env_key_with_source(key: str, *, project_root: Path, workspace_root: Path) -> tuple[str, str]:
    process_value = os.getenv(key)
    if process_value:
        return "process environment", process_value

    for label, path in (("project .env", project_root / ".env"), ("workspace root .env", workspace_root / ".env")):
        value = _read_env_key(path, key)
        if value:
            return label, value
    return "unset", ""


def _database_url_source(database_url: str, *, project_root: Path, workspace_root: Path) -> tuple[str, str]:
    if not database_url:
        return "unset", "DATABASE_URL is not set."

    candidates = [
        ("workspace root .env", workspace_root / ".env"),
        ("project .env", project_root / ".env"),
    ]
    matches = [label for label, path in candidates if _read_env_key(path, "DATABASE_URL") == database_url]
    project_value = _read_env_key(project_root / ".env", "DATABASE_URL")

    if matches:
        source = " and ".join(matches)
        if "workspace root .env" in matches and project_value and project_value != database_url:
            return (
                source,
                "Project .env also defines DATABASE_URL, but workspace root/process precedence is providing the effective value.",
            )
        return source, f"Effective DATABASE_URL appears to come from {source}."

    if project_value and project_value != database_url:
        return (
            "process environment or workspace loader",
            "Project .env defines a different DATABASE_URL; inspect process env and workspace root .env precedence.",
        )
    return "process environment or another env loader", "DATABASE_URL does not exactly match tracked root/project .env files."


def _supabase_pooler_url_shape(host: str, port: int | None, path: str, *, uses_project_user: bool) -> dict[str, str]:
    if not uses_project_user:
        return _doctor_item(
            "ERROR",
            "db.supabase_user_shape",
            "Supabase pooler URL is missing the project-qualified postgres.<project_ref> user shape",
            "Copy the pooler connection string from the Supabase dashboard and keep the postgres.<project_ref> user.",
        )

    if port != 6543:
        return _doctor_item(
            "ERROR",
            "db.supabase_pooler_mode",
            (
                "Supabase pooler URL must use the Shared Pooler transaction mode for production launch "
                f"readiness: host={host}, port={port or '(default)'}, expected_port=6543, "
                f"user=postgres.<project_ref>, database={path}"
            ),
            (
                "Copy the Transaction pooler connection string from the Supabase dashboard Connect panel "
                "and keep port 6543."
            ),
        )

    return _doctor_item(
        "OK",
        "db.supabase_url_shape",
        f"Supabase transaction pooler shape detected: host={host}, port={port or '(default)'}, user=postgres.<project_ref>, database={path}",
    )


def _database_url_shape(database_url: str) -> dict[str, str]:
    parsed = urlparse(database_url)
    username = unquote(parsed.username or "")
    host = parsed.hostname or ""
    try:
        port = parsed.port
    except ValueError as exc:
        return _doctor_item(
            "WARN",
            "db.url_shape",
            f"DATABASE_URL has an invalid port: {_mask_database_error(exc)}",
            "Copy a complete PostgreSQL connection string from the database provider and rerun --doctor.",
        )
    path = (parsed.path or "").lstrip("/") or "(none)"
    is_supabase_pooler = host.endswith(".pooler.supabase.com")
    uses_project_user = username.startswith("postgres.")

    if not parsed.scheme:
        return _doctor_item(
            "WARN",
            "db.url_shape",
            "DATABASE_URL cannot be parsed as a URL",
            "Replace DATABASE_URL with a complete PostgreSQL connection string.",
        )

    if is_supabase_pooler:
        return _supabase_pooler_url_shape(host, port, path, uses_project_user=uses_project_user)

    return _doctor_item(
        "OK",
        "db.url_shape",
        f"PostgreSQL URL shape detected: host={host or '(none)'}, port={port or '(default)'}, database={path}",
    )


def _short_ref_fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]


def _supabase_pooler_project_ref(database_url: str) -> str:
    try:
        parsed = urlparse(database_url)
    except ValueError:
        return ""
    host = parsed.hostname or ""
    if not host.endswith(".pooler.supabase.com"):
        return ""
    username = unquote(parsed.username or "")
    if not username.startswith("postgres."):
        return ""
    return username.split(".", 1)[1].strip()


def _supabase_api_project_ref(supabase_url: str) -> str:
    if not supabase_url:
        return ""
    candidate = supabase_url if "://" in supabase_url else f"https://{supabase_url}"
    try:
        parsed = urlparse(candidate)
    except ValueError:
        return ""
    host = parsed.hostname or ""
    if not host.endswith(".supabase.co"):
        return ""
    project_ref = host.removesuffix(".supabase.co").split(".")[0].strip()
    return project_ref


def _supabase_ref_match_item(database_ref: str, api_ref: str, *, supabase_url_source: str) -> dict[str, str]:
    database_fp = _short_ref_fingerprint(database_ref)
    api_fp = _short_ref_fingerprint(api_ref)
    if database_ref != api_ref:
        return _doctor_item(
            "ERROR",
            "db.supabase_project_ref_crosscheck",
            (
                "DATABASE_URL pooler project ref does not match SUPABASE_URL "
                f"(database_ref_fp={database_fp}, supabase_url_ref_fp={api_fp})"
            ),
            "Copy DATABASE_URL and SUPABASE_URL from the same Supabase project, then rerun --doctor --require-live-db.",
        )

    return _doctor_item(
        "OK",
        "db.supabase_project_ref_crosscheck",
        f"DATABASE_URL and SUPABASE_URL project refs match (ref_fp={database_fp}, source={supabase_url_source})",
        "",
    )


def _supabase_project_ref_crosscheck(
    database_url: str,
    supabase_url: str,
    *,
    supabase_url_source: str,
) -> dict[str, str] | None:
    database_ref = _supabase_pooler_project_ref(database_url)
    if not database_ref:
        return None

    if not supabase_url:
        return _doctor_item(
            "WARN",
            "db.supabase_project_ref_crosscheck",
            "SUPABASE_URL is not set; cannot cross-check DATABASE_URL project ref",
            "Set SUPABASE_URL from the same Supabase project, or manually verify the pooler user in the dashboard Connect panel.",
        )

    api_ref = _supabase_api_project_ref(supabase_url)
    if not api_ref:
        return _doctor_item(
            "WARN",
            "db.supabase_project_ref_crosscheck",
            f"SUPABASE_URL from {supabase_url_source} does not expose a standard project ref hostname",
            "Use the project API URL shaped like https://<project_ref>.supabase.co for automatic cross-checking.",
        )

    return _supabase_ref_match_item(database_ref, api_ref, supabase_url_source=supabase_url_source)


def _doctor_item(level: str, check_id: str, message: str, remediation: str = "") -> dict[str, str]:
    return {
        "level": level,
        "id": check_id,
        "message": message,
        "remediation": remediation,
    }


def _print_doctor_report(config: AppConfig, checks: list[dict[str, str]]) -> None:
    print("\n  [doctor] getdaytrends health check")
    print("  " + "=" * 62)
    print(f"  VERSION      : {VERSION}")
    print(f"  COUNTRY      : {config.country}")
    print(f"  LIMIT        : {config.limit}")
    print(f"  SCHEDULE_MIN : {config.schedule_minutes}")
    print(f"  STORAGE      : {config.storage_type}")
    print(f"  DATABASE     : {_mask_sensitive_value(config.database_url or config.db_path)}")
    print("  " + "=" * 62)
    for entry in checks:
        print(f"  [{entry['level']}] {entry['id']}: {entry['message']}")
        if entry["remediation"]:
            print(f"       fix: {entry['remediation']}")
    print("  " + "=" * 62)


def _doctor_result(checks: list[dict[str, str]]) -> tuple[int, str]:
    counts = Counter(entry["level"] for entry in checks)
    errors = counts["ERROR"]
    warnings = counts["WARN"]
    if errors:
        return 2, f"FAIL (errors={errors}, warnings={warnings})"
    if warnings:
        return 0, f"PASS WITH WARNINGS (warnings={warnings})"
    return 0, "PASS"


def _append_doctor_module_checks(checks: list[dict[str, str]]) -> None:
    for module_name in ("schedule", "loguru"):
        if _module_available(module_name):
            checks.append(_doctor_item("OK", f"module.{module_name}", f"Required module available: {module_name}"))
        else:
            checks.append(
                _doctor_item(
                    "ERROR",
                    f"module.{module_name}",
                    f"Missing required module: {module_name}",
                    "Run dependency sync from the workspace root: uv sync --package getdaytrends --extra dev.",
                )
            )

    for module_name in ("uvicorn", "asyncpg", "httpx", "aiosqlite", "playwright", "sqlalchemy"):
        if _module_available(module_name):
            checks.append(_doctor_item("OK", f"module.{module_name}", f"Optional module available: {module_name}"))
        else:
            checks.append(
                _doctor_item(
                    "WARN",
                    f"module.{module_name}",
                    f"Optional module missing: {module_name}",
                    "Install it only if you use the related dashboard, browser, or database feature.",
                )
            )


def _append_doctor_config_validation_checks(checks: list[dict[str, str]], config: AppConfig) -> None:
    try:
        for message in config.validate():
            if message.startswith("LLM API keys are not configured"):
                checks.append(
                    _doctor_item(
                        "WARN",
                        "config.llm_keys",
                        message,
                        "Set at least one LLM provider key in .env before production runs.",
                    )
                )
            else:
                checks.append(
                    _doctor_item(
                        "ERROR",
                        "config.validation",
                        message,
                        "Fix the reported .env/config value and rerun --doctor.",
                    )
                )
    except Exception as exc:  # pragma: no cover - defensive
        checks.append(
            _doctor_item(
                "ERROR",
                "config.validation_crash",
                f"Config validation crashed: {type(exc).__name__}: {exc}",
                "Inspect AppConfig.from_env and recent config changes.",
            )
        )


def _append_doctor_env_file_check(checks: list[dict[str, str]], env_path: Path) -> None:
    if env_path.exists():
        if env_path.stat().st_size == 0:
            checks.append(
                _doctor_item("WARN", "env.empty", f"Environment file exists but is empty: {env_path}", "Populate .env from .env.example.")
            )
        else:
            checks.append(_doctor_item("OK", "env.file", f".env found and readable ({env_path})"))
    else:
        checks.append(_doctor_item("WARN", "env.missing", f".env not found: {env_path}", "Copy .env.example to .env and set provider keys."))


def _append_doctor_data_dir_check(checks: list[dict[str, str]], data_dir: Path) -> None:
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        checks.append(_doctor_item("OK", "path.data_dir", f"Data directory ready ({data_dir})"))
    except Exception as exc:
        checks.append(
            _doctor_item(
                "ERROR",
                "path.data_dir",
                f"Cannot access data directory ({data_dir}): {exc}",
                "Fix permissions or create the directory.",
            )
        )


def _append_doctor_lock_check(checks: list[dict[str, str]], lock_path: Path) -> None:
    if not lock_path.exists():
        return
    try:
        lock_pid = int(lock_path.read_text().strip())
        if _is_pid_alive(lock_pid):
            checks.append(
                _doctor_item(
                    "WARN",
                    "lock.running",
                    f"Existing lockfile for running PID {lock_pid}",
                    "Wait for the run to finish before starting another pipeline run.",
                )
            )
        else:
            checks.append(
                _doctor_item(
                    "OK",
                    "lock.stale",
                    f"Stale lockfile found for PID {lock_pid}",
                    "The next pipeline run will clean this stale lock automatically.",
                )
            )
    except Exception as exc:
        checks.append(
            _doctor_item(
                "WARN",
                "lock.unreadable",
                f"Cannot read lockfile ({lock_path}): {exc}",
                "Inspect or remove the lockfile if no pipeline process is running.",
            )
        )


def _doctor_alert_channels(config: AppConfig) -> list[str]:
    channels = []
    if config.telegram_bot_token and config.telegram_chat_id:
        channels.append("telegram")
    if config.discord_webhook_url:
        channels.append("discord")
    if config.slack_webhook_url:
        channels.append("slack")
    if config.smtp_host and config.alert_email:
        channels.append("email")
    return [] if config.no_alerts else channels


def _append_doctor_alert_checks(checks: list[dict[str, str]], config: AppConfig) -> None:
    alert_channels = _doctor_alert_channels(config)
    if alert_channels:
        checks.append(_doctor_item("OK", "alerts.channels", "Alert channels: " + ", ".join(alert_channels)))
    elif config.no_alerts:
        checks.append(_doctor_item("OK", "alerts.disabled", "Alerting intentionally disabled by --no-alerts"))
    else:
        checks.append(
            _doctor_item(
                "WARN",
                "alerts.channels",
                "No active alert channel configured",
                "Configure Telegram, Discord, Slack, or SMTP for unattended operations.",
            )
        )

    if config.watchlist_keywords and not alert_channels and not config.no_alerts:
        checks.append(
            _doctor_item(
                "WARN",
                "alerts.watchlist",
                "Watchlist is configured but alerts are off",
                "Enable an alert channel or remove watchlist keywords.",
            )
        )


def _doctor_active_features(config: AppConfig) -> list[str]:
    active_features = []
    if config.enable_tap:
        active_features.append("tap")
    if config.enable_quality_feedback:
        active_features.append("quality_feedback")
    if config.enable_adaptive_voice:
        active_features.append("adaptive_voice")
    if config.enable_edape:
        active_features.append("edape")
    return active_features


def _append_doctor_feature_checks(checks: list[dict[str, str]], config: AppConfig) -> None:
    active_features = _doctor_active_features(config)
    if active_features:
        checks.append(_doctor_item("OK", "features.enabled", "Feature flags: " + ", ".join(active_features)))


def _append_doctor_database_url_source_check(
    checks: list[dict[str, str]],
    database_url: str,
    *,
    project_root: Path,
    workspace_root: Path,
) -> None:
    source, source_message = _database_url_source(
        database_url,
        project_root=project_root,
        workspace_root=workspace_root,
    )
    checks.append(_doctor_item("OK", "db.database_url_source", f"DATABASE_URL source: {source}. {source_message}"))


def _append_doctor_database_shape_check(checks: list[dict[str, str]], database_url: str) -> bool:
    shape = _database_url_shape(database_url)
    checks.append(_doctor_item(shape["level"], shape["id"], shape["message"], shape["remediation"]))
    return shape["level"] == "ERROR"


def _append_doctor_supabase_crosscheck(
    checks: list[dict[str, str]],
    database_url: str,
    *,
    project_root: Path,
    workspace_root: Path,
) -> bool:
    supabase_url_source, supabase_url = _env_key_with_source(
        "SUPABASE_URL",
        project_root=project_root,
        workspace_root=workspace_root,
    )
    crosscheck = _supabase_project_ref_crosscheck(
        database_url,
        supabase_url,
        supabase_url_source=supabase_url_source,
    )
    if crosscheck is None:
        return False
    checks.append(_doctor_item(crosscheck["level"], crosscheck["id"], crosscheck["message"], crosscheck["remediation"]))
    return crosscheck["level"] == "ERROR"


def _append_doctor_database_preflight_checks(
    checks: list[dict[str, str]],
    database_url: str,
    *,
    project_root: Path,
    workspace_root: Path,
    require_live_db: bool,
) -> tuple[bool, bool]:
    _append_doctor_database_url_source_check(
        checks,
        database_url,
        project_root=project_root,
        workspace_root=workspace_root,
    )
    database_shape_failed = _append_doctor_database_shape_check(checks, database_url)

    supabase_crosscheck_failed = False
    if require_live_db:
        supabase_crosscheck_failed = _append_doctor_supabase_crosscheck(
            checks,
            database_url,
            project_root=project_root,
            workspace_root=workspace_root,
        )
    return database_shape_failed, supabase_crosscheck_failed


def _append_doctor_endpoint_dns_check(checks: list[dict[str, str]], host: str) -> bool:
    try:
        address_count = _probe_endpoint_dns(host)
        checks.append(_doctor_item("OK", "db.endpoint_dns", f"Database endpoint DNS resolved: host={host}, addresses={address_count}"))
        return True
    except Exception as exc:
        checks.append(
            _doctor_item(
                "ERROR",
                "db.endpoint_dns",
                f"Database endpoint DNS failed: host={host}: {type(exc).__name__}: {_mask_database_error(exc)}",
                (
                    "Confirm the Supabase pooler host copied from the project dashboard "
                    f"and compare it with {SUPABASE_CONNECTION_DOC_URL}."
                ),
            )
        )
        return False


def _append_doctor_endpoint_tcp_check(checks: list[dict[str, str]], host: str, port: int) -> bool:
    try:
        _probe_endpoint_tcp(host, port)
        checks.append(_doctor_item("OK", "db.endpoint_tcp", f"Database endpoint TCP connect succeeded: host={host}, port={port}"))
        return True
    except Exception as exc:
        checks.append(
            _doctor_item(
                "ERROR",
                "db.endpoint_tcp",
                f"Database endpoint TCP connect failed: host={host}, port={port}: {type(exc).__name__}: {_mask_database_error(exc)}",
                "Verify local network/firewall access to the Supabase pooler and rerun --doctor --require-live-db.",
            )
        )
        return False


def _append_doctor_database_endpoint_probe_checks(
    checks: list[dict[str, str]],
    database_url: str,
    *,
    endpoint_ready: bool,
    require_live_db: bool,
) -> bool:
    endpoint = _database_endpoint(database_url)
    if not (require_live_db and endpoint_ready and endpoint):
        return endpoint_ready

    host, port = endpoint
    if not _append_doctor_endpoint_dns_check(checks, host):
        return False

    return _append_doctor_endpoint_tcp_check(checks, host, port)


def _append_doctor_live_postgres_check(
    checks: list[dict[str, str]],
    database_url: str,
    *,
    endpoint_ready: bool,
    require_live_db: bool,
) -> None:
    if not (require_live_db and endpoint_ready):
        return
    try:
        run_async(_probe_live_postgres(database_url))
        checks.append(_doctor_item("OK", "db.live_postgres", "Live PostgreSQL SELECT 1 succeeded"))
    except Exception as exc:
        checks.append(
            _doctor_item(
                "ERROR",
                "db.live_postgres",
                f"Live PostgreSQL probe failed: {type(exc).__name__}: {_mask_database_error(exc)}",
                (
                    "Fix DATABASE_URL / Supabase pooler credentials, verify the project ref and database password "
                    f"against the Supabase dashboard Connect panel, then rerun --doctor --require-live-db. See {SUPABASE_CONNECTION_DOC_URL}."
                ),
            )
        )


async def _probe_live_postgres(database_url: str) -> None:
    import asyncpg

    conn = await asyncpg.connect(database_url, statement_cache_size=0, timeout=10)
    try:
        await conn.fetchval("select 1")
    finally:
        await conn.close()


def _database_endpoint(database_url: str) -> tuple[str, int] | None:
    try:
        parsed = urlparse(database_url)
        host = parsed.hostname or ""
        port = parsed.port or 5432
    except ValueError:
        return None
    if not host:
        return None
    return host, port


def _probe_endpoint_dns(host: str) -> int:
    infos = socket.getaddrinfo(host, None)
    addresses = {info[4][0] for info in infos if len(info) >= 5 and info[4]}
    return len(addresses) or len(infos)


def _probe_endpoint_tcp(host: str, port: int, *, timeout_seconds: float = 5.0) -> None:
    with socket.create_connection((host, port), timeout=timeout_seconds):
        return


def _load_notion_storage_helpers() -> tuple[Any, Any, Any, Any]:
    try:
        from .storage_notion import (
            NOTION_AVAILABLE,
            NotionClient,
            _missing_legacy_notion_properties,
            _resolve_notion_write_target,
        )
    except ImportError:
        from storage_notion import (
            NOTION_AVAILABLE,
            NotionClient,
            _missing_legacy_notion_properties,
            _resolve_notion_write_target,
        )
    return NOTION_AVAILABLE, NotionClient, _missing_legacy_notion_properties, _resolve_notion_write_target


def _notion_target_schema_check(target: Any, missing_legacy_properties: Any) -> dict[str, str]:
    missing = missing_legacy_properties(target.schema)
    if missing:
        return _doctor_item(
            "ERROR",
            "notion.schema",
            "Notion target is missing required properties: " + ", ".join(missing),
            "Use the Getdaytrends Notion database schema or update the configured NOTION_DATABASE_ID.",
        )
    target_kind = "data source" if target.uses_data_source else "database"
    return _doctor_item(
        "OK",
        "notion.schema",
        f"Notion {target_kind} schema ready ({len(target.schema)} properties)",
        "",
    )


def _check_notion_storage_target(config: AppConfig) -> dict[str, str] | None:
    if config.storage_type not in ("notion", "both"):
        return None
    if not config.notion_token or not config.notion_database_id:
        return None

    try:
        (
            NOTION_AVAILABLE,
            NotionClient,
            _missing_legacy_notion_properties,
            _resolve_notion_write_target,
        ) = _load_notion_storage_helpers()
        if not NOTION_AVAILABLE or NotionClient is None:
            return _doctor_item(
                "ERROR",
                "notion.client",
                "notion-client package is not available for Notion storage",
                "Run dependency sync from the workspace root: uv sync --package getdaytrends --extra dev.",
            )
        notion = NotionClient(auth=config.notion_token)
        target = _resolve_notion_write_target(notion, config.notion_database_id)
        if target is None:
            return _doctor_item(
                "ERROR",
                "notion.target",
                "Configured Notion database/data source could not be resolved",
                "Share the Getdaytrends database with the integration and verify NOTION_DATABASE_ID.",
            )
        return _notion_target_schema_check(target, _missing_legacy_notion_properties)
    except Exception as exc:
        return _doctor_item(
            "ERROR",
            "notion.schema",
            f"Notion schema check failed: {type(exc).__name__}: {exc}",
            "Verify Notion integration access and rerun --doctor.",
        )


def _append_doctor_sqlite_checks(checks: list[dict[str, str]], db_path: Path, *, require_live_db: bool) -> None:
    if require_live_db:
        checks.append(
            _doctor_item(
                "ERROR",
                "db.live_postgres",
                "Live PostgreSQL probe requested but DATABASE_URL is not set",
                "Set DATABASE_URL or rerun --doctor without --require-live-db for SQLite-only development checks.",
            )
        )
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with db_path.open("a", encoding="utf-8"):
            pass
        checks.append(_doctor_item("OK", "db.sqlite_path", f"SQLite DB path writable ({db_path})"))
    except Exception as exc:
        checks.append(
            _doctor_item(
                "ERROR",
                "db.sqlite_path",
                f"SQLite DB path not writable ({db_path}): {exc}",
                "Fix the DB path or directory permissions.",
            )
        )


def _append_doctor_postgres_compatibility_check(checks: list[dict[str, str]], database_url: str) -> bool:
    if not database_url.startswith("postgresql://"):
        checks.append(
            _doctor_item(
                "WARN",
                "db.url_scheme",
                "DATABASE_URL is set but does not use postgresql://",
                "Use a PostgreSQL URL or unset DATABASE_URL for SQLite.",
            )
        )
        return False

    if not _module_available("asyncpg"):
        checks.append(
            _doctor_item(
                "WARN",
                "db.asyncpg",
                "DATABASE_URL configured, but asyncpg module is missing",
                "Install asyncpg or unset DATABASE_URL for SQLite.",
            )
        )
        return False

    checks.append(_doctor_item("OK", "db.postgres_config", "PostgreSQL settings and asyncpg module detected"))
    return True


def _append_doctor_postgres_endpoint_checks(
    checks: list[dict[str, str]],
    database_url: str,
    *,
    supabase_crosscheck_failed: bool,
    database_shape_failed: bool,
    require_live_db: bool,
) -> None:
    endpoint_ready = not supabase_crosscheck_failed and not database_shape_failed
    endpoint_ready = _append_doctor_database_endpoint_probe_checks(
        checks,
        database_url,
        endpoint_ready=endpoint_ready,
        require_live_db=require_live_db,
    )
    _append_doctor_live_postgres_check(
        checks,
        database_url,
        endpoint_ready=endpoint_ready,
        require_live_db=require_live_db,
    )


def _append_doctor_database_checks(
    checks: list[dict[str, str]],
    config: AppConfig,
    *,
    project_root: Path,
    workspace_root: Path,
    db_path: Path,
    require_live_db: bool,
) -> None:
    if config.database_url:
        database_shape_failed, supabase_crosscheck_failed = _append_doctor_database_preflight_checks(
            checks,
            config.database_url,
            project_root=project_root,
            workspace_root=workspace_root,
            require_live_db=require_live_db,
        )

        if _append_doctor_postgres_compatibility_check(checks, config.database_url):
            _append_doctor_postgres_endpoint_checks(
                checks,
                config.database_url,
                supabase_crosscheck_failed=supabase_crosscheck_failed,
                database_shape_failed=database_shape_failed,
                require_live_db=require_live_db,
            )
        if config.allow_sqlite_fallback:
            checks.append(_doctor_item("OK", "db.sqlite_fallback", "SQLite fallback enabled if PostgreSQL is unavailable"))
        return

    _append_doctor_sqlite_checks(checks, db_path, require_live_db=require_live_db)


def _run_doctor_check(config: AppConfig, *, require_live_db: bool = False) -> int:
    """Run non-destructive runtime and configuration checks."""

    project_root = Path(__file__).resolve().parent
    env_path = project_root / ".env"
    workspace_root = project_root.parents[1]
    data_dir = project_root / "data"
    lock_path = _LOCK_FILE
    db_path = Path(config.db_path).expanduser()

    checks: list[dict[str, str]] = []

    _append_doctor_env_file_check(checks, env_path)
    _append_doctor_module_checks(checks)
    _append_doctor_config_validation_checks(checks, config)

    notion_check = _check_notion_storage_target(config)
    if notion_check is not None:
        checks.append(notion_check)

    _append_doctor_data_dir_check(checks, data_dir)

    _append_doctor_database_checks(
        checks,
        config,
        project_root=project_root,
        workspace_root=workspace_root,
        db_path=db_path,
        require_live_db=require_live_db,
    )

    _append_doctor_lock_check(checks, lock_path)

    _append_doctor_alert_checks(checks, config)
    _append_doctor_feature_checks(checks, config)

    _print_doctor_report(config, checks)
    status_code, result = _doctor_result(checks)
    print(f"  result: {result}")
    return status_code



# --------------------------------------------------
#  Banner
# --------------------------------------------------


def print_banner():
    print(
        f"""
========================================================
 getdaytrends v{VERSION}
 Cache + Retry + Multi-Country + Cost Tracking
========================================================
"""
    )


def _config_summary_sources(config: AppConfig) -> list[str]:
    sources = ["getdaytrends.com"]
    if config.twitter_bearer_token:
        sources.append("X API")
    sources.extend(["Reddit", "Google News"])
    return sources


def _config_summary_alert_channels(config: AppConfig) -> list[str]:
    alerts_info = []
    if config.telegram_bot_token and config.telegram_chat_id:
        alerts_info.append("Telegram")
    if config.discord_webhook_url:
        alerts_info.append("Discord")
    if config.slack_webhook_url:
        alerts_info.append("Slack")
    if config.smtp_host and config.alert_email:
        alerts_info.append("SMTP")
    return alerts_info


def _config_summary_features(config: AppConfig) -> list[str]:
    features = []
    if config.enable_clustering:
        features.append("Clustering")
    if config.enable_long_form:
        features.append(f"Premium+ Long Form (min score: {config.long_form_min_score})")
    if config.enable_threads:
        features.append("Threads")
    if config.smart_schedule:
        features.append("Smart schedule")
    if config.night_mode:
        features.append("Night mode (02:00~07:00)")
    return features


def print_config_summary(config: AppConfig):
    country_label = ", ".join(config.countries) if len(config.countries) > 1 else config.country
    country_mode = "parallel" if len(config.countries) > 1 and config.enable_parallel_countries else "single"

    sources = _config_summary_sources(config)
    alerts_info = _config_summary_alert_channels(config)
    features = _config_summary_features(config)

    print(
        f"""
  Configuration
  ----------------------------------------
  Countries        : {country_label}
  Mode             : {country_mode}
  Limit            : {config.limit}
  Dedup window     : {config.dedupe_window_hours}h
  Storage          : {config.storage_type.upper()}
  Schedule         : {config.schedule_minutes}m
  Tone             : {config.tone}
  Sources          : {", ".join(sources)}
  Max workers      : {config.max_workers}
  Alert channels   : {", ".join(alerts_info) or "none"}
  Alert threshold  : {config.alert_threshold}%
  LLM provider     : shared.llm (auto-selected)
  v2.1 features    : {", ".join(features) or "none"}
"""
    )


def _daily_llm_cost_totals(daily: list[dict[str, Any]]) -> tuple[list[tuple[str, Any, Any]], Any]:
    by_day: dict[str, dict[str, Any]] = {}
    for row in daily:
        day = row["date"]
        by_day.setdefault(day, {"cost": 0.0, "calls": 0})
        by_day[day]["cost"] += row["cost_usd"]
        by_day[day]["calls"] += row["calls"]

    total_cost = sum(values["cost"] for values in by_day.values())
    rows = [(day, by_day[day]["cost"], by_day[day]["calls"]) for day in sorted(by_day.keys(), reverse=True)[:7]]
    return rows, total_cost


def _print_llm_cost_summary(daily: list[dict[str, Any]]) -> None:
    if not daily:
        return

    rows, total_cost = _daily_llm_cost_totals(daily)
    print("  LLM cost (last 7 days)")
    print("  ----------------------------------------")
    for day, cost, calls in rows:
        print(f"  {day} : ${cost:.4f}  ({calls} calls)")
    print("  ----------------------------------------")
    print(f"  7-day total     : ${total_cost:.4f}")
    print(f"  30-day forecast : ${total_cost / 7 * 30:.2f}")
    print()


async def print_stats(config: AppConfig):
    """Print runtime stats and recent LLM cost totals."""
    local_stats_database_url = f"sqlite:///{config.db_path}"
    conn = await get_connection(
        config.db_path,
        local_stats_database_url,
        allow_sqlite_fallback=False,
    )
    try:
        stats = await get_trend_stats(conn)
        print(
            f"""
  Runtime stats
  ----------------------------------------
  Total runs      : {stats["total_runs"]}
  Total trends    : {stats["total_trends"]}
  Avg viral score : {stats["avg_viral_score"]}
  Total tweets    : {stats["total_tweets"]}
"""
        )
    finally:
        await conn.close()

    # LLM cost summary (last 7 days)
    try:
        from shared.llm.stats import CostTracker

        tracker = CostTracker(persist=True)
        daily = tracker.get_daily_stats(7)
        tracker.close()

        _print_llm_cost_summary(daily)
    except (ValueError, KeyError, OSError) as e:
        log.debug(f"LLM cost query failed: {type(e).__name__}: {e}")
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


def _load_tap_refresh_helpers() -> tuple[Any, Any]:
    try:
        from .tap import dispatch_tap_alert_queue, refresh_tap_market_surfaces
    except ImportError:
        from tap import dispatch_tap_alert_queue, refresh_tap_market_surfaces
    return refresh_tap_market_surfaces, dispatch_tap_alert_queue


def _parallel_tap_config(config: AppConfig, countries: list[str]) -> AppConfig:
    return dataclasses.replace(
        config,
        country=countries[0],
        countries=countries,
    )


def _print_tap_refresh_summary(payload: dict[str, Any]) -> None:
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


async def _refresh_tap_products_after_parallel_runs(config: AppConfig, countries: list[str]) -> dict[str, Any]:
    """Refresh TAP snapshots after parallel country runs complete."""

    normalized_countries = _normalize_countries(countries)
    if not config.enable_tap or len(normalized_countries) < 2:
        return {}

    try:
        refresh_tap_market_surfaces, dispatch_tap_alert_queue = _load_tap_refresh_helpers()
        tap_config = _parallel_tap_config(config, normalized_countries)
        conn = await get_connection(config.db_path, database_url=config.database_url)
        try:
            await init_db(conn)
            summary = await refresh_tap_market_surfaces(conn, tap_config, snapshot_source="parallel_batch")
            payload = cast("dict[str, Any]", summary.to_dict())
            if payload.get("alerts_queued") and getattr(config, "enable_tap_alert_dispatch", False):
                dispatch_summary = await dispatch_tap_alert_queue(
                    conn,
                    tap_config,
                    limit=max(1, int(getattr(config, "tap_alert_dispatch_batch_size", 5) or 5)),
                )
                payload["dispatch"] = dispatch_summary.to_dict()
        finally:
            await conn.close()

        _print_tap_refresh_summary(payload)
        return payload
    except Exception as exc:
        log.warning(f"TAP parallel refresh failed (ignored): {type(exc).__name__}: {exc}")
        return {}


def _normalize_parallel_country_results(
    countries: list[str],
    raw_results: list[Any],
) -> list[tuple[str, Any | None, float, BaseException | None]]:
    country_results = []
    for i, res in enumerate(raw_results):
        if isinstance(res, BaseException):
            country = countries[i]
            log.error(f"  [gather] {country.upper()} failed: {type(res).__name__}: {res}")
            country_results.append((country, None, 0.0, res))
        else:
            country_results.append(res)
    return country_results


def _report_parallel_country_results(country_results: list[tuple[str, Any | None, float, BaseException | None]]) -> list[tuple[str, BaseException]]:
    failures: list[tuple[str, BaseException]] = []

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

    return failures


def _handle_parallel_country_failures(failures: list[tuple[str, BaseException]], countries: list[str]) -> None:
    if not failures:
        return

    failed_countries = ", ".join(country.upper() for country, _ in failures)
    log.error(f"Parallel country run failed: {failed_countries}")
    try:
        from shared.notifications import Notifier

        notifier = Notifier.from_env()
        if notifier.has_channels:
            notifier.send_error(
                f"Parallel country run failed ({failed_countries}): {failures[0][1]}",
                error=failures[0][1],
                source="GetDayTrends",
            )
    except Exception as e:
        log.warning(f"Failed to send error notification: {e}")

    if len(failures) == len(countries):
        raise RuntimeError(f"All parallel country runs failed: {failed_countries}") from failures[0][1]


def _send_parallel_success_heartbeat(successful_countries: list[str], total_countries: int) -> None:
    try:
        if successful_countries:
            from shared.notifications import Notifier

            notifier = Notifier.from_env()
            if notifier.has_channels:
                notifier.send_heartbeat(
                    "GetDayTrends",
                    status="alive",
                    details=f"Parallel result: {', '.join(successful_countries)} / total: {total_countries}",
                )
    except Exception as e:
        log.warning(f"Failed to send heartbeat notification: {e}")


async def _run_parallel_country(
    config: AppConfig,
    semaphore: asyncio.Semaphore,
    country: str,
) -> tuple[str, Any | None, float, BaseException | None]:
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


def _parallel_country_limit(config: AppConfig, country_count: int) -> int:
    return min(config.country_parallel_limit, country_count)


def _print_parallel_run_header(config: AppConfig, countries: list[str], parallel_limit: int) -> None:
    print(f"\n  Parallel countries: {', '.join(country.upper() for country in countries)}")
    print(f"  Concurrency limit: {parallel_limit}")

    if config.smart_schedule and not config.one_shot:
        print(f"  Smart reschedule stays on base interval ({config.schedule_minutes} min) in parallel mode.")


async def _run_countries_parallel_job(config: AppConfig) -> list:
    countries = _normalize_countries(config.countries)
    if not countries:
        return []

    parallel_limit = _parallel_country_limit(config, len(countries))
    _print_parallel_run_header(config, countries, parallel_limit)
    semaphore = asyncio.Semaphore(parallel_limit)

    # B-004 fix: use return_exceptions=True so one failure does not stop all countries.
    # _run_parallel_country isolates exceptions per country.
    # If BaseException surfaces, keep collecting results for remaining jobs.
    raw_results = await asyncio.gather(
        *[_run_parallel_country(config, semaphore, country) for country in countries],
        return_exceptions=True,
    )
    # Gather returns entries for failed tasks, process them by index.
    country_results = _normalize_parallel_country_results(countries, raw_results)

    failures = _report_parallel_country_results(country_results)
    _handle_parallel_country_failures(failures, countries)

    successful_countries = [country for country, _, _, error in country_results if error is None]
    _send_parallel_success_heartbeat(successful_countries, len(countries))

    await _refresh_tap_products_after_parallel_runs(config, successful_countries)

    return [result for _, result, _, error in country_results if error is None]


#  Entry Point
# --------------------------------------------------


def main():
    # Skip lockfile for non-pipeline probes.
    _pre_args = sys.argv[1:]
    _skip_lock = any(a in _pre_args for a in ("--version", "--stats", "--serve", "--doctor", "--health-check"))
    if not _skip_lock and not _acquire_lock():
        sys.exit(1)

    try:
        _main_body()
    except Exception as exc:
        try:
            from shared.notifications import Notifier

            _notifier = Notifier.from_env()
            if _notifier.has_channels:
                _notifier.send_error(
                    f"GetDayTrends main loop stopped (main): {exc}", error=exc, source="GetDayTrends"
                )
        except Exception:
            pass
        raise
    finally:
        if not _skip_lock:
            _release_lock()


def _sleep_with_interrupt(sleep_seconds: float):
    for _ in range(int(sleep_seconds)):
        if _SHUTDOWN_FLAG.is_set():
            break
        time.sleep(1)


def _get_night_sleep_seconds() -> float:
    now = datetime.now()
    if 2 <= now.hour < 7:
        wake_at = now.replace(hour=7, minute=0, second=0, microsecond=0)
        return max(0.0, (wake_at - now).total_seconds())
    return 0.0


def _apply_cli_overrides(config: AppConfig, args: argparse.Namespace) -> None:
    if args.country:
        config.country = args.country.strip().lower()
        config.countries = [config.country]

    if args.countries:
        parsed_countries = [country.strip().lower() for country in args.countries.split(",") if country.strip()]
        if parsed_countries:
            config.countries = parsed_countries
            config.country = parsed_countries[0]

    if args.limit is not None:
        config.limit = args.limit

    if args.one_shot:
        config.one_shot = True

    if args.dry_run:
        config.dry_run = True

    if args.verbose:
        config.verbose = True

    if args.no_alerts:
        config.no_alerts = True

    if args.schedule_min is not None:
        config.schedule_minutes = args.schedule_min


async def _initialize_app(config: AppConfig) -> None:
    conn = await get_connection(
        config.db_path,
        database_url=config.database_url,
        allow_sqlite_fallback=config.dry_run or config.allow_sqlite_fallback,
    )
    await init_db(conn)
    await maybe_cleanup(conn, days=config.data_retention_days)
    await maybe_send_weekly_cost_report(conn, config)
    await conn.close()


def _serve_dashboard() -> None:
    try:
        import uvicorn

        try:
            from .dashboard import app as dashboard_app
        except ImportError:
            from dashboard import app as dashboard_app

        print("\n  Dashboard running: http://localhost:8080\n")
        uvicorn.run(dashboard_app, host="0.0.0.0", port=8080)
    except ImportError as e:
        print(f"\n  Dashboard startup failed: {e}")
        print("  Install dependency: pip install uvicorn\n")


def _run_doctor_probe_mode(args: argparse.Namespace, config: AppConfig) -> None:
    if args.doctor or args.health_check:
        status = _run_doctor_check(config, require_live_db=args.require_live_db)
        raise SystemExit(status)


def _run_stats_probe_mode(args: argparse.Namespace, config: AppConfig) -> bool:
    if not args.stats:
        return False
    run_async(print_stats(config))
    return True


def _initialize_app_and_maybe_serve(args: argparse.Namespace, config: AppConfig) -> bool:
    run_async(_initialize_app(config))
    if not args.serve:
        return False
    _serve_dashboard()
    return True


def _validate_runtime_config(config: AppConfig) -> bool:
    if config.dry_run:
        from shared.llm.config import load_keys

        keys = load_keys()
        if not any(keys.values()):
            print("\n  Validation failed:\n    LLM API key is required in dry-run mode.\n  Check .env file.\n")
            return False
        return True

    errors = config.validate()
    if errors:
        print("\n  Validation failed:")
        for error_message in errors:
            print(f"    {error_message}")
        print("\n  Fix .env values and retry.\n")
        return False
    return True


def _select_runtime_countries(config: AppConfig) -> None:
    config.countries = _normalize_countries(config.countries or [config.country])
    config.country = config.countries[0]


def _send_country_success_heartbeat(country_config: AppConfig, result: Any) -> None:
    from shared.notifications import Notifier

    notifier = Notifier.from_env()
    if notifier.has_channels and result:
        notifier.send_heartbeat(
            "GetDayTrends",
            status="alive",
            details=f"Country {country_config.country} completed ({result.trends_collected} collected)",
        )


def _send_country_error_notification(country_config: AppConfig, pipe_err: Exception) -> None:
    from shared.notifications import Notifier

    notifier = Notifier.from_env()
    if notifier.has_channels:
        notifier.send_error(
            f"Pipeline failed ({country_config.country}): {pipe_err}",
            error=pipe_err,
            source="GetDayTrends",
        )


def _run_single_configured_country(config: AppConfig, country: str, *, schedule_callback: Any) -> None:
    country_config = config.for_country(country) if country != config.country else config
    if len(config.countries) > 1:
        print(f"\n  Running country: {country.upper()}")

    try:
        result = run_pipeline(country_config, schedule_callback=schedule_callback)
        _send_country_success_heartbeat(country_config, result)
    except Exception as pipe_err:
        _send_country_error_notification(country_config, pipe_err)
        raise


def _run_configured_countries(config: AppConfig, *, schedule_callback: Any) -> None:
    try:
        if len(config.countries) > 1 and config.enable_parallel_countries:
            run_async(_run_countries_parallel_job(config))
        else:
            for country in config.countries:
                _run_single_configured_country(config, country, schedule_callback=schedule_callback)
    except Exception as run_err:
        log.exception(f"Pipeline execution failed: {run_err}")
        if config.one_shot:
            raise


def _run_initial_country_batch(config: AppConfig) -> Any:
    def _run_all_countries():
        _run_configured_countries(config, schedule_callback=_run_all_countries)

    _run_all_countries()
    return _run_all_countries


async def _cleanup_runtime_pools() -> None:
    await close_pg_pool()


def _run_scheduler_loop(config: AppConfig, run_all_countries: Any) -> None:
    schedule.every(config.schedule_minutes).minutes.do(run_all_countries)
    print(f"\n  Scheduler started. Interval: {config.schedule_minutes} minutes.")
    if config.night_mode:
        print("  Night mode enabled: sleep 02:00~07:00")
    print("  Ctrl+C to stop.\n")

    try:
        while not _SHUTDOWN_FLAG.is_set():
            if config.night_mode:
                sleep_seconds = _get_night_sleep_seconds()
                if sleep_seconds > 0:
                    log.info(f"Night mode sleep until 07:00 in {sleep_seconds / 60:.0f} minutes.")
                    print(f"  Night mode sleep active. Wake at 07:00 (about {sleep_seconds / 60:.0f} minutes).")
                    _sleep_with_interrupt(sleep_seconds)
                    continue

            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        _SHUTDOWN_FLAG.set()
    finally:
        try:
            run_async(_cleanup_runtime_pools())
        except Exception as exc:
            log.warning(f"Failed to close PostgreSQL pool cleanly: {exc}")
        print("\n\n  Scheduler stopped. Goodbye.")


def _main_body():
    args = parse_args()

    # Load configuration first, then apply CLI overrides.
    config = AppConfig.from_env()

    _apply_cli_overrides(config, args)

    setup_logging(config.verbose)
    print_banner()

    _run_doctor_probe_mode(args, config)

    # Register SIGTERM / SIGINT handlers.
    _install_signal_handlers()

    # --stats uses its own lightweight DB probe and should not fail
    # during startup-time PostgreSQL initialization when the DB endpoint
    # is unavailable. Keep the main init path for scheduled/production runs.
    if _run_stats_probe_mode(args, config):
        return

    if _initialize_app_and_maybe_serve(args, config):
        return

    # Validation path for dry-run and persistent storage modes.
    if not _validate_runtime_config(config):
        return

    _select_runtime_countries(config)

    print_config_summary(config)

    run_all_countries = _run_initial_country_batch(config)

    # one-shot exits right after first run.
    if config.one_shot:
        print("\n(one-shot mode: finished)")
        return

    _run_scheduler_loop(config, run_all_countries)
if __name__ == "__main__":
    main()
