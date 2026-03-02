from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = PROJECT_ROOT / "logs"
OUTPUT_DIR = PROJECT_ROOT / "output"
CONFIG_DIR = PROJECT_ROOT / "config"
ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(ENV_PATH)

for directory in (DATA_DIR, LOG_DIR, OUTPUT_DIR, CONFIG_DIR):
    directory.mkdir(parents=True, exist_ok=True)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


NOTION_API_KEY = os.getenv("NOTION_API_KEY", "").strip()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
GOOGLE_API_KEY = (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()

ANTIGRAVITY_TASKS_DB_ID = (
    os.getenv("ANTIGRAVITY_TASKS_DB_ID")
    or os.getenv("ANTIGRAVITY_DB_ID")
    or "bb5cf3c8-d2bb-4b8b-a866-ba9ea86f16b7"
).strip()
ANTIGRAVITY_NEWS_DB_ID = (
    os.getenv("ANTIGRAVITY_NEWS_DB_ID")
    or "9a372e84-8883-421f-8725-d90a494aca5a"
).strip()
DASHBOARD_PAGE_ID = os.getenv("DASHBOARD_PAGE_ID", "").strip()

PIPELINE_HTTP_TIMEOUT_SEC = _env_int("PIPELINE_HTTP_TIMEOUT_SEC", 15)
PIPELINE_MAX_RETRIES = _env_int("PIPELINE_MAX_RETRIES", 3)
PIPELINE_MAX_CONCURRENCY = _env_int("PIPELINE_MAX_CONCURRENCY", 3)
PIPELINE_LOCK_TIMEOUT_SEC = _env_int("PIPELINE_LOCK_TIMEOUT_SEC", 7200)
PIPELINE_LOG_LEVEL = os.getenv("PIPELINE_LOG_LEVEL", "INFO").strip().upper()
AUTO_PUSH_ENABLED = _env_bool("AUTO_PUSH_ENABLED", False)
DEFAULT_RESEARCH_TOPIC = os.getenv("DEFAULT_RESEARCH_TOPIC", "Agentic AI Trends").strip()

# Canva Connect API
CANVA_CLIENT_ID = os.getenv("CANVA_CLIENT_ID", "").strip()
CANVA_CLIENT_SECRET = os.getenv("CANVA_CLIENT_SECRET", "").strip()
CANVA_REFRESH_TOKEN = os.getenv("CANVA_REFRESH_TOKEN", "").strip()
CANVA_REDIRECT_URI = os.getenv("CANVA_REDIRECT_URI", "http://127.0.0.1:8080/oauth/callback").strip()
CANVA_ENABLED = _env_bool("CANVA_ENABLED", bool(CANVA_CLIENT_ID and CANVA_CLIENT_SECRET))

# Agent Skill Integration (X Radar + Opinion Generator -> X post drafts)
SKILL_INTEGRATION_ENABLED = _env_bool("SKILL_INTEGRATION_ENABLED", False)

PIPELINE_STATE_DB = DATA_DIR / "pipeline_state.db"
SCHEDULER_LOG_PATH = LOG_DIR / "scheduler.log"
NEWS_SOURCES_FILE = CONFIG_DIR / "news_sources.json"
DASHBOARD_CONFIG_FILE = CONFIG_DIR / "dashboard_config.json"
