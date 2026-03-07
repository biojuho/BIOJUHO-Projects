from __future__ import annotations

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

    notion_tasks_database_id, tasks_db_source = _first_non_empty(
        "NOTION_TASKS_DATABASE_ID",
        "ANTIGRAVITY_TASKS_DB_ID",
        "ANTIGRAVITY_DB_ID",
        "NOTION_DATABASE_ID",
    )
    if tasks_db_source in {"ANTIGRAVITY_TASKS_DB_ID", "ANTIGRAVITY_DB_ID", "NOTION_DATABASE_ID"}:
        warnings.append(
            f"{tasks_db_source} is deprecated; use NOTION_TASKS_DATABASE_ID instead."
        )

    notion_tasks_data_source_id, tasks_ds_source = _first_non_empty(
        "NOTION_TASKS_DATA_SOURCE_ID",
    )
    if tasks_ds_source:
        warnings.append(
            f"{tasks_ds_source} configured as the source of truth for task queries."
        )

    notion_reports_database_id, reports_db_source = _first_non_empty(
        "NOTION_REPORTS_DATABASE_ID",
        "ANTIGRAVITY_NEWS_DB_ID",
    )
    if reports_db_source == "ANTIGRAVITY_NEWS_DB_ID":
        warnings.append(
            "ANTIGRAVITY_NEWS_DB_ID is deprecated; use NOTION_REPORTS_DATABASE_ID instead."
        )

    notion_reports_data_source_id, reports_ds_source = _first_non_empty(
        "NOTION_REPORTS_DATA_SOURCE_ID",
    )
    if reports_ds_source:
        warnings.append(
            f"{reports_ds_source} configured as the source of truth for report queries."
        )

    notion_dashboard_page_id, dashboard_source = _first_non_empty(
        "NOTION_DASHBOARD_PAGE_ID",
        "DASHBOARD_PAGE_ID",
    )
    if dashboard_source == "DASHBOARD_PAGE_ID":
        warnings.append("DASHBOARD_PAGE_ID is deprecated; use NOTION_DASHBOARD_PAGE_ID instead.")

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
