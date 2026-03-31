from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from antigravity_mcp.config import get_settings

_SETTINGS = get_settings()

DATA_DIR = _SETTINGS.data_dir
LOG_DIR = _SETTINGS.log_dir
OUTPUT_DIR = _SETTINGS.output_dir
CONFIG_DIR = _SETTINGS.config_dir
ENV_PATH = _SETTINGS.env_path

NOTION_API_KEY = _SETTINGS.notion_api_key
NOTION_API_VERSION = _SETTINGS.notion_api_version
NOTION_TASKS_DATABASE_ID = _SETTINGS.notion_tasks_database_id
NOTION_REPORTS_DATABASE_ID = _SETTINGS.notion_reports_database_id
NOTION_DASHBOARD_PAGE_ID = _SETTINGS.notion_dashboard_page_id

GOOGLE_API_KEY = _SETTINGS.google_api_key
ANTHROPIC_API_KEY = _SETTINGS.anthropic_api_key
OPENAI_API_KEY = _SETTINGS.openai_api_key

PIPELINE_HTTP_TIMEOUT_SEC = _SETTINGS.pipeline_http_timeout_sec
PIPELINE_MAX_RETRIES = _SETTINGS.pipeline_max_retries
PIPELINE_MAX_CONCURRENCY = _SETTINGS.pipeline_max_concurrency
PIPELINE_LOCK_TIMEOUT_SEC = _SETTINGS.pipeline_lock_timeout_sec
PIPELINE_LOG_LEVEL = _SETTINGS.pipeline_log_level
AUTO_PUSH_ENABLED = _SETTINGS.auto_push_enabled
DEFAULT_RESEARCH_TOPIC = "Agentic AI Trends"

CANVA_CLIENT_ID = ""
CANVA_CLIENT_SECRET = ""
CANVA_REFRESH_TOKEN = ""
CANVA_REDIRECT_URI = ""
CANVA_ENABLED = False

SKILL_INTEGRATION_ENABLED = False

PIPELINE_STATE_DB = _SETTINGS.pipeline_state_db
SCHEDULER_LOG_PATH = LOG_DIR / "scheduler.log"
NEWS_SOURCES_FILE = _SETTINGS.news_sources_file
DASHBOARD_CONFIG_FILE = CONFIG_DIR / "dashboard_config.json"
