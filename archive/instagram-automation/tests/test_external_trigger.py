"""Tests for P2: External Trigger API and n8n integration."""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _tmp_db():
    """Create a temp DB with posts table."""
    import sqlite3

    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            caption TEXT DEFAULT '',
            image_url TEXT DEFAULT '',
            status TEXT DEFAULT 'queued',
            post_type TEXT DEFAULT 'IMAGE',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    conn.commit()
    conn.close()
    return path


class TestTokenAuth:
    def test_verify_token_empty(self):
        from services.external_trigger import verify_token

        # No env token set
        assert verify_token("anything") is False

    def test_verify_token_match(self, monkeypatch):
        from services.external_trigger import EXTERNAL_API_TOKEN

        monkeypatch.setattr("services.external_trigger.EXTERNAL_API_TOKEN", "secret123")
        from services.external_trigger import verify_token

        assert verify_token("secret123") is True

    def test_verify_token_mismatch(self, monkeypatch):
        monkeypatch.setattr("services.external_trigger.EXTERNAL_API_TOKEN", "secret123")
        from services.external_trigger import verify_token

        assert verify_token("wrong") is False


class TestTriggerPostRequest:
    def test_basic(self):
        from services.external_trigger import TriggerPostRequest

        req = TriggerPostRequest(topic="AI 트렌드")
        assert req.topic == "AI 트렌드"
        assert req.source == "n8n"
        assert req.post_type == "IMAGE"

    def test_with_all_fields(self):
        from services.external_trigger import TriggerPostRequest

        req = TriggerPostRequest(
            topic="Test",
            caption="Custom caption",
            hashtags=["#ai", "#tech"],
            image_url="https://example.com/img.jpg",
            publish_now=True,
            source="webhook",
        )
        assert req.caption == "Custom caption"
        assert req.publish_now is True


class TestExternalTriggerHandler:
    def _make_handler(self):
        from services.ab_testing import ABTestEngine
        from services.content_calendar import ContentCalendar
        from services.external_trigger import ExternalTriggerHandler
        from services.hashtag_strategy import HashtagDB

        db_path = _tmp_db()
        calendar = ContentCalendar(db_path)
        hashtag_db = HashtagDB(db_path)
        hashtag_db.seed_defaults()
        ab_engine = ABTestEngine(db_path)

        # Mock database with enqueue_post
        mock_db = MagicMock()
        mock_db.enqueue_post = MagicMock(return_value=42)

        return ExternalTriggerHandler(calendar, hashtag_db, ab_engine, mock_db)

    def test_handle_post_trigger(self):
        from services.external_trigger import TriggerPostRequest

        handler = self._make_handler()
        req = TriggerPostRequest(topic="AI 혁명", source="test")
        result = handler.handle_post_trigger(req)
        assert result.success is True
        assert result.action == "post_enqueued"
        assert result.data["post_id"] == 42

    def test_handle_post_trigger_with_hashtags(self):
        from services.external_trigger import TriggerPostRequest

        handler = self._make_handler()
        req = TriggerPostRequest(
            topic="Test", hashtags=["#custom1", "#custom2"]
        )
        result = handler.handle_post_trigger(req)
        assert result.success is True

    def test_handle_trend_push(self):
        from services.external_trigger import TrendPushRequest

        handler = self._make_handler()
        req = TrendPushRequest(
            trends=[
                {"topic": "AI 트렌드", "score": 80},
                {"topic": "클라우드", "score": 70},
            ],
            source="getdaytrends",
        )
        result = handler.handle_trend_push(req)
        assert result.success is True
        assert result.action == "trends_injected"

    def test_handle_trend_push_empty(self):
        from services.external_trigger import TrendPushRequest

        handler = self._make_handler()
        req = TrendPushRequest(trends=[], source="test")
        result = handler.handle_trend_push(req)
        assert result.success is True
        assert result.data["injected"] == 0

    def test_get_status(self):
        handler = self._make_handler()
        status = handler.get_status()
        assert status["service"] == "instagram-automation"
        assert status["status"] == "operational"
        assert "calendar_stats" in status
        assert "hashtag_stats" in status

    def test_trigger_log(self):
        from services.external_trigger import TriggerPostRequest

        handler = self._make_handler()
        for i in range(3):
            req = TriggerPostRequest(topic=f"Topic {i}", source="test")
            handler.handle_post_trigger(req)
        assert len(handler._trigger_log) == 3


class TestExternalTriggerResult:
    def test_auto_timestamp(self):
        from services.external_trigger import ExternalTriggerResult

        result = ExternalTriggerResult(
            success=True, action="test", message="ok"
        )
        assert result.timestamp != ""

    def test_model_dump(self):
        from services.external_trigger import ExternalTriggerResult

        result = ExternalTriggerResult(
            success=True, action="test", message="ok", data={"key": "val"}
        )
        d = result.model_dump()
        assert d["success"] is True
        assert d["data"]["key"] == "val"


class TestN8nWorkflow:
    def test_workflow_json_valid(self):
        workflow_path = (
            Path(__file__).resolve().parents[1] / "n8n_workflows" / "getdaytrends_bridge.json"
        )
        assert workflow_path.exists()
        with open(workflow_path) as f:
            data = json.load(f)
        assert "nodes" in data
        assert "connections" in data
        assert len(data["nodes"]) >= 5

    def test_workflow_has_schedule_trigger(self):
        workflow_path = (
            Path(__file__).resolve().parents[1] / "n8n_workflows" / "getdaytrends_bridge.json"
        )
        with open(workflow_path) as f:
            data = json.load(f)
        node_types = [n["type"] for n in data["nodes"]]
        assert "n8n-nodes-base.scheduleTrigger" in node_types
