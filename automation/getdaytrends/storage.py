"""
getdaytrends v2.4 - Storage Module (facade)
Notion + Google Sheets + Content Hub 저장.

Implementation modules:
    storage_notion.py        — Notion 레거시 저장 + 재시도 로직
    storage_content_hub.py   — Notion Content Hub V2.0 upsert
    storage_gsheets.py       — Google Sheets 동기화
"""

# ── Re-export all public APIs so existing callers don't break ──
from .storage_notion import (  # noqa: F401
    NOTION_AVAILABLE,
    _bg_tasks,
    _build_legacy_notion_properties,
    _is_notion_provider_error,
    _persist_content_hub_link,
    _retry_notion_call,
    save_to_notion,
)
from .storage_content_hub import (  # noqa: F401
    _content_hub_default_priority,
    _content_hub_properties,
    _content_hub_workflow_meta,
    _get_hub_schema,
    _query_content_hub_by_draft_id,
    _rich_text_prop,
    save_to_content_hub,
)
from .storage_gsheets import (  # noqa: F401
    GSPREAD_AVAILABLE,
    _is_gspread_provider_error,
    save_to_google_sheets,
)
