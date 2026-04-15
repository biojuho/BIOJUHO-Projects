"""
getdaytrends v2.4 - Storage module facade.

Implementation modules:
    storage_notion.py
    storage_content_hub.py
    storage_gsheets.py
"""

import time
from typing import Any

try:
    from . import storage_content_hub as _storage_content_hub
    from . import storage_gsheets as _storage_gsheets
    from . import storage_notion as _storage_notion
except ImportError:
    import storage_content_hub as _storage_content_hub
    import storage_gsheets as _storage_gsheets
    import storage_notion as _storage_notion

APIResponseError = _storage_notion.APIResponseError
NOTION_AVAILABLE = _storage_notion.NOTION_AVAILABLE
NotionClient = _storage_notion.NotionClient
_bg_tasks = _storage_notion._bg_tasks
_build_legacy_notion_properties = _storage_notion._build_legacy_notion_properties
_build_notion_body = _storage_notion._build_notion_body
_is_notion_provider_error = _storage_notion._is_notion_provider_error
_notion_page_exists = _storage_notion._notion_page_exists
_persist_content_hub_link = _storage_notion._persist_content_hub_link

_content_hub_default_priority = _storage_content_hub._content_hub_default_priority
_content_hub_properties = _storage_content_hub._content_hub_properties
_content_hub_workflow_meta = _storage_content_hub._content_hub_workflow_meta
_get_hub_schema = _storage_content_hub._get_hub_schema
_query_content_hub_by_draft_id = _storage_content_hub._query_content_hub_by_draft_id
_rich_text_prop = _storage_content_hub._rich_text_prop

GSPREAD_AVAILABLE = _storage_gsheets.GSPREAD_AVAILABLE
GoogleAuthError = _storage_gsheets.GoogleAuthError
Credentials = _storage_gsheets.Credentials
_is_gspread_provider_error = _storage_gsheets._is_gspread_provider_error

_retry_notion_call_impl = _storage_notion._retry_notion_call
_save_to_notion_impl = _storage_notion.save_to_notion
_save_to_content_hub_impl = _storage_content_hub.save_to_content_hub
_save_to_google_sheets_impl = _storage_gsheets.save_to_google_sheets


def _sync_notion_exports() -> None:
    _storage_notion.APIResponseError = APIResponseError
    _storage_notion.NOTION_AVAILABLE = NOTION_AVAILABLE
    _storage_notion.NotionClient = NotionClient
    _storage_notion._build_notion_body = _build_notion_body
    _storage_notion._notion_page_exists = _notion_page_exists
    _storage_notion.time = time


def _sync_content_hub_exports() -> None:
    _storage_content_hub.NOTION_AVAILABLE = NOTION_AVAILABLE
    _storage_content_hub.NotionClient = NotionClient
    _storage_content_hub._retry_notion_call = _retry_notion_call
    _storage_content_hub._is_notion_provider_error = _is_notion_provider_error
    _storage_content_hub._persist_content_hub_link = _persist_content_hub_link


def _sync_gsheets_exports() -> None:
    _storage_gsheets.GSPREAD_AVAILABLE = GSPREAD_AVAILABLE
    _storage_gsheets.GoogleAuthError = GoogleAuthError
    _storage_gsheets.Credentials = Credentials


def _retry_notion_call(*args: Any, **kwargs: Any) -> Any:
    _sync_notion_exports()
    return _retry_notion_call_impl(*args, **kwargs)


def save_to_notion(*args: Any, **kwargs: Any) -> Any:
    _sync_notion_exports()
    _storage_notion._retry_notion_call = _retry_notion_call
    return _save_to_notion_impl(*args, **kwargs)


def save_to_content_hub(*args: Any, **kwargs: Any) -> Any:
    _sync_content_hub_exports()
    return _save_to_content_hub_impl(*args, **kwargs)


def save_to_google_sheets(*args: Any, **kwargs: Any) -> Any:
    _sync_gsheets_exports()
    return _save_to_google_sheets_impl(*args, **kwargs)
