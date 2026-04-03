from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock


def _load_script_module():
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "publishing_workflow.py"
    spec = importlib.util.spec_from_file_location("getdaytrends_publishing_workflow", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _draft_page(*, status: str, draft_id: str = "draft-1", receipt_id: str = "", platform: str = "X") -> dict:
    return {
        "id": "page-1",
        "properties": {
            "Name": {"title": [{"text": {"content": "Draft Title"}}]},
            "Status": {"select": {"name": status}},
            "Draft ID": {"rich_text": [{"text": {"content": draft_id}}]},
            "Receipt ID": {"rich_text": [{"text": {"content": receipt_id}}]},
            "Platform": {"multi_select": [{"name": platform}]},
            "Published URL": {},
            "Published At": {},
        },
    }


def test_sync_approved_from_notion_records_review_decision(monkeypatch):
    module = _load_script_module()
    notion = MagicMock()
    notion.databases.query.return_value = {"results": [_draft_page(status="Approved")]}
    captured: list[dict] = []

    async def fake_sync_review_decision(draft_id, decision, reviewed_by, review_note, db_path, database_url):
        captured.append(
            {
                "draft_id": draft_id,
                "decision": decision,
                "reviewed_by": reviewed_by,
                "review_note": review_note,
                "db_path": db_path,
                "database_url": database_url,
            }
        )

    monkeypatch.setattr(module, "_get_notion_client", lambda: notion)
    monkeypatch.setattr(module, "_get_hub_db_id", lambda: "hub-db")
    monkeypatch.setattr(module, "_sync_review_decision", fake_sync_review_decision)

    module.sync_approved_from_notion("workflow.db", database_url="sqlite://")

    assert captured == [
        {
            "draft_id": "draft-1",
            "decision": "approved",
            "reviewed_by": "notion-manual",
            "review_note": "Draft Title",
            "db_path": "workflow.db",
            "database_url": "sqlite://",
        }
    ]


def test_mark_as_published_records_receipt_and_updates_notion(monkeypatch):
    module = _load_script_module()
    notion = MagicMock()
    notion.pages.retrieve.return_value = _draft_page(status="Approved")
    captured: list[dict] = []

    async def fake_record_publish_receipt_async(**kwargs):
        captured.append(kwargs)
        return "receipt-1"

    monkeypatch.setattr(module, "_get_notion_client", lambda: notion)
    monkeypatch.setattr(module, "_record_publish_receipt_async", fake_record_publish_receipt_async)

    module.mark_as_published("page-1", "https://x.com/i/status/1", "workflow.db", database_url="sqlite://")

    assert captured == [
        {
            "draft_id": "draft-1",
            "platform": "X",
            "published_url": "https://x.com/i/status/1",
            "db_path": "workflow.db",
            "database_url": "sqlite://",
        }
    ]
    notion.pages.update.assert_called_once()
    update_kwargs = notion.pages.update.call_args.kwargs
    assert update_kwargs["page_id"] == "page-1"
    assert update_kwargs["properties"]["Status"]["select"]["name"] == "Published"
    assert update_kwargs["properties"]["Receipt ID"]["rich_text"][0]["text"]["content"] == "receipt-1"


def test_record_feedback_requires_receipt_and_calls_async_writer(monkeypatch):
    module = _load_script_module()
    notion = MagicMock()
    notion.pages.retrieve.return_value = _draft_page(status="Published", receipt_id="receipt-1")
    captured: list[dict] = []

    async def fake_record_feedback_async(**kwargs):
        captured.append(kwargs)

    monkeypatch.setattr(module, "_get_notion_client", lambda: notion)
    monkeypatch.setattr(module, "_record_feedback_async", fake_record_feedback_async)

    module.record_feedback(
        "page-1",
        metric_window="48h",
        impressions=1000,
        engagements=120,
        clicks=33,
        collector_status="manual",
        strategy_notes="Lead with the sharper hook.",
        db_path="workflow.db",
        database_url="sqlite://",
    )

    assert captured == [
        {
            "draft_id": "draft-1",
            "receipt_id": "receipt-1",
            "metric_window": "48h",
            "impressions": 1000,
            "engagements": 120,
            "clicks": 33,
            "collector_status": "manual",
            "strategy_notes": "Lead with the sharper hook.",
            "db_path": "workflow.db",
            "database_url": "sqlite://",
        }
    ]
