from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = PROJECT_ROOT / "logs"
OUTPUT_DIR = PROJECT_ROOT / "output"
CONFIG_DIR = PROJECT_ROOT / "config"
DOCS_DIR = PROJECT_ROOT / "docs"
APPS_DIR = PROJECT_ROOT / "apps"
ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(ENV_PATH)

for directory in (DATA_DIR, LOG_DIR, OUTPUT_DIR, CONFIG_DIR, DOCS_DIR, APPS_DIR):
    directory.mkdir(parents=True, exist_ok=True)


def _first_non_empty(*names: str) -> tuple[str, str | None]:
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip(), name
    return "", None


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _load_dashboard_page_id_from_config() -> str:
    config_path = CONFIG_DIR / "dashboard_config.json"
    if not config_path.exists():
        return ""
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    page_id = str(data.get("dashboard_page_id", "")).strip()
    return page_id


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


@dataclass(frozen=True)
class AppSettings:
    project_root: Path
    src_root: Path
    data_dir: Path
    log_dir: Path
    output_dir: Path
    config_dir: Path
    docs_dir: Path
    env_path: Path
    notion_api_key: str
    notion_api_version: str
    notion_tasks_database_id: str
    notion_tasks_data_source_id: str
    notion_reports_database_id: str
    notion_reports_data_source_id: str
    notion_dashboard_page_id: str
    google_api_key: str
    anthropic_api_key: str
    openai_api_key: str
    canva_client_id: str
    canva_client_secret: str
    canva_refresh_token: str
    telegram_bot_token: str
    telegram_chat_id: str
    x_api_key: str
    x_api_secret: str
    x_access_token: str
    x_access_token_secret: str
    x_bearer_token: str
    supabase_database_url: str
    x_daily_post_limit: int
    pipeline_max_concurrency: int
    pipeline_http_timeout_sec: int
    pipeline_max_retries: int
    pipeline_lock_timeout_sec: int
    content_approval_mode: str
    pipeline_log_level: str
    auto_push_enabled: bool
    settings_warnings: tuple[str, ...]

    @property
    def pipeline_state_db(self) -> Path:
        return self.data_dir / "pipeline_state.db"

    @property
    def analytics_db(self) -> Path:
        return self.data_dir / "analytics.db"

    @property
    def news_sources_file(self) -> Path:
        return self.config_dir / "news_sources.json"

    @property
    def channels_file(self) -> Path:
        return self.config_dir / "channels.json"

    def validate(self) -> list[str]:
        """Validate configuration on startup. Returns list of critical issues."""
        issues: list[str] = []
        # At least one LLM key required
        if not any([self.google_api_key, self.anthropic_api_key, self.openai_api_key]):
            issues.append("No LLM API key configured (GOOGLE_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY).")
        # news_sources.json must exist
        if not self.news_sources_file.exists():
            issues.append(f"News sources config not found: {self.news_sources_file}")
        else:
            try:
                data = json.loads(self.news_sources_file.read_text(encoding="utf-8"))
                if not data:
                    issues.append("news_sources.json is empty.")
            except (json.JSONDecodeError, OSError) as exc:
                issues.append(f"news_sources.json is invalid: {exc}")
        # DB path writable
        try:
            self.pipeline_state_db.parent.mkdir(parents=True, exist_ok=True)
            test_file = self.pipeline_state_db.parent / ".write_test"
            test_file.write_text("ok")
            test_file.unlink()
        except OSError as exc:
            issues.append(f"Database path not writable: {exc}")
        # Pipeline config sanity
        if self.pipeline_max_concurrency < 1:
            issues.append("PIPELINE_MAX_CONCURRENCY must be >= 1.")
        if self.pipeline_http_timeout_sec < 1:
            issues.append("PIPELINE_HTTP_TIMEOUT_SEC must be >= 1.")
        return issues

    def public_summary(self) -> dict[str, str | int | bool | list[str]]:
        return {
            "notion_api_version": self.notion_api_version,
            "notion_tasks_database_id": self.notion_tasks_database_id,
            "notion_tasks_data_source_id": self.notion_tasks_data_source_id,
            "notion_reports_database_id": self.notion_reports_database_id,
            "notion_reports_data_source_id": self.notion_reports_data_source_id,
            "notion_dashboard_page_id": self.notion_dashboard_page_id,
            "notion_api_key": _mask_secret(self.notion_api_key),
            "google_api_key": _mask_secret(self.google_api_key),
            "anthropic_api_key": _mask_secret(self.anthropic_api_key),
            "openai_api_key": _mask_secret(self.openai_api_key),
            "canva_client_id": _mask_secret(self.canva_client_id),
            "telegram_bot_token": _mask_secret(self.telegram_bot_token),
            "x_api_key": _mask_secret(self.x_api_key),
            "x_access_token": _mask_secret(self.x_access_token),
            "supabase_database_url": _mask_secret(self.supabase_database_url),
            "x_daily_post_limit": self.x_daily_post_limit,
            "pipeline_max_concurrency": self.pipeline_max_concurrency,
            "pipeline_http_timeout_sec": self.pipeline_http_timeout_sec,
            "pipeline_max_retries": self.pipeline_max_retries,
            "content_approval_mode": self.content_approval_mode,
            "settings_warnings": list(self.settings_warnings),
        }


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    warnings: list[str] = []

    notion_tasks_database_id, _ = _first_non_empty(
        "NOTION_TASKS_DATABASE_ID",
    )
    _legacy_tasks_database_id, tasks_db_source = _first_non_empty(
        "ANTIGRAVITY_TASKS_DB_ID",
        "ANTIGRAVITY_DB_ID",
        "NOTION_DATABASE_ID",
    )
    if tasks_db_source:
        warnings.append(f"{tasks_db_source} is no longer read; set NOTION_TASKS_DATABASE_ID instead.")

    _legacy_tasks_data_source_id, tasks_ds_source = _first_non_empty(
        "NOTION_TASKS_DATA_SOURCE_ID",
    )
    notion_tasks_data_source_id = ""
    if tasks_ds_source:
        warnings.append(
            f"{tasks_ds_source} is no longer read; task queries require "
            "NOTION_TASKS_DATABASE_ID and /v1/databases/{id}/query."
        )

    notion_reports_database_id, _ = _first_non_empty(
        "NOTION_REPORTS_DATABASE_ID",
    )
    _legacy_reports_database_id, reports_db_source = _first_non_empty(
        "ANTIGRAVITY_NEWS_DB_ID",
    )
    if reports_db_source:
        warnings.append("ANTIGRAVITY_NEWS_DB_ID is no longer read; set NOTION_REPORTS_DATABASE_ID instead.")

    _legacy_reports_data_source_id, reports_ds_source = _first_non_empty(
        "NOTION_REPORTS_DATA_SOURCE_ID",
    )
    notion_reports_data_source_id = ""
    if reports_ds_source:
        warnings.append(
            f"{reports_ds_source} is no longer read; report queries require "
            "NOTION_REPORTS_DATABASE_ID and /v1/databases/{id}/query."
        )

    notion_dashboard_page_id, _ = _first_non_empty(
        "NOTION_DASHBOARD_PAGE_ID",
    )
    _legacy_dashboard_page_id, dashboard_source = _first_non_empty(
        "DASHBOARD_PAGE_ID",
    )
    if not notion_dashboard_page_id:
        notion_dashboard_page_id = _load_dashboard_page_id_from_config()
        if notion_dashboard_page_id:
            warnings.append(
                "NOTION_DASHBOARD_PAGE_ID loaded from config/dashboard_config.json fallback. "
                "Treat this as a local fallback, not a stable deployment contract."
            )
    if dashboard_source:
        warnings.append("DASHBOARD_PAGE_ID is no longer read; use NOTION_DASHBOARD_PAGE_ID instead.")

    notion_api_key, _ = _first_non_empty("NOTION_API_KEY")
    google_api_key, _ = _first_non_empty("GOOGLE_API_KEY", "GEMINI_API_KEY")
    anthropic_api_key, _ = _first_non_empty("ANTHROPIC_API_KEY")
    openai_api_key, _ = _first_non_empty("OPENAI_API_KEY")
    canva_client_id, _ = _first_non_empty("CANVA_CLIENT_ID")
    canva_client_secret, _ = _first_non_empty("CANVA_CLIENT_SECRET")
    canva_refresh_token, _ = _first_non_empty("CANVA_REFRESH_TOKEN")
    telegram_bot_token, _ = _first_non_empty("TELEGRAM_BOT_TOKEN")
    telegram_chat_id, _ = _first_non_empty("TELEGRAM_CHAT_ID")
    x_api_key, _ = _first_non_empty("X_API_KEY", "TWITTER_API_KEY")
    x_api_secret, _ = _first_non_empty("X_API_SECRET", "TWITTER_API_SECRET")
    x_access_token, _ = _first_non_empty("X_ACCESS_TOKEN", "TWITTER_ACCESS_TOKEN")
    x_access_token_secret, _ = _first_non_empty("X_ACCESS_TOKEN_SECRET", "TWITTER_ACCESS_TOKEN_SECRET")
    x_bearer_token, _ = _first_non_empty("X_BEARER_TOKEN", "TWITTER_BEARER_TOKEN")
    supabase_database_url, _ = _first_non_empty("SUPABASE_DATABASE_URL", "DATABASE_URL")

    return AppSettings(
        project_root=PROJECT_ROOT,
        src_root=SRC_ROOT,
        data_dir=DATA_DIR,
        log_dir=LOG_DIR,
        output_dir=OUTPUT_DIR,
        config_dir=CONFIG_DIR,
        docs_dir=DOCS_DIR,
        env_path=ENV_PATH,
        notion_api_key=notion_api_key,
        notion_api_version="2025-09-03",
        notion_tasks_database_id=notion_tasks_database_id,
        notion_tasks_data_source_id=notion_tasks_data_source_id,
        notion_reports_database_id=notion_reports_database_id,
        notion_reports_data_source_id=notion_reports_data_source_id,
        notion_dashboard_page_id=notion_dashboard_page_id,
        google_api_key=google_api_key,
        anthropic_api_key=anthropic_api_key,
        openai_api_key=openai_api_key,
        canva_client_id=canva_client_id,
        canva_client_secret=canva_client_secret,
        canva_refresh_token=canva_refresh_token,
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
        x_api_key=x_api_key,
        x_api_secret=x_api_secret,
        x_access_token=x_access_token,
        x_access_token_secret=x_access_token_secret,
        x_bearer_token=x_bearer_token,
        supabase_database_url=supabase_database_url,
        x_daily_post_limit=_env_int("X_DAILY_POST_LIMIT", 10),
        pipeline_max_concurrency=_env_int("PIPELINE_MAX_CONCURRENCY", 3),
        pipeline_http_timeout_sec=_env_int("PIPELINE_HTTP_TIMEOUT_SEC", 15),
        pipeline_max_retries=_env_int("PIPELINE_MAX_RETRIES", 3),
        pipeline_lock_timeout_sec=_env_int("PIPELINE_LOCK_TIMEOUT_SEC", 7200),
        content_approval_mode=os.getenv("CONTENT_APPROVAL_MODE", "manual").strip().lower() or "manual",
        pipeline_log_level=os.getenv("PIPELINE_LOG_LEVEL", "INFO").strip().upper() or "INFO",
        auto_push_enabled=_env_bool("AUTO_PUSH_ENABLED", False),
        settings_warnings=tuple(warnings),
    )


class _JsonlFormatter(logging.Formatter):
    """Structured JSON formatter that includes extra metric fields when present."""

    _RESERVED = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Auto-include trace_id from contextvars if active
        from antigravity_mcp.tracing import current_trace_id

        trace_id = current_trace_id()
        if trace_id:
            entry["trace_id"] = trace_id
        if record.exc_info and record.exc_info[1]:
            entry["exception"] = str(record.exc_info[1])
        # Include any extra fields passed via logger.info("...", extra={...})
        for key, value in record.__dict__.items():
            if key not in self._RESERVED and not key.startswith("_"):
                entry[key] = value
        return json.dumps(entry, ensure_ascii=False, default=str)


def emit_metric(
    event: str,
    *,
    logger_name: str = "antigravity_mcp.metrics",
    **kwargs: Any,
) -> None:
    """Emit a structured metric event to the JSONL log.

    Usage:
        emit_metric("llm_call", provider="gemini", latency_ms=340, tokens=150)
        emit_metric("pipeline_run", stage="collect", item_count=25, status="ok")
    """
    _logger = logging.getLogger(logger_name)
    _logger.info(event, extra={"metric_event": event, **kwargs})


def configure_logging(settings: AppSettings | None = None) -> None:
    """Configure structured JSON logging to logs/pipeline.jsonl."""
    settings = settings or get_settings()
    log_level = getattr(logging, settings.pipeline_log_level, logging.INFO)

    # Console handler
    logging.basicConfig(level=log_level, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    # JSON file handler
    jsonl_path = settings.log_dir / "pipeline.jsonl"
    try:
        from logging.handlers import RotatingFileHandler

        file_handler = RotatingFileHandler(
            jsonl_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(_JsonlFormatter())
        logging.getLogger().addHandler(file_handler)
    except OSError as exc:
        import sys

        print(f"WARNING: File logging unavailable ({jsonl_path}): {exc}", file=sys.stderr)
