from __future__ import annotations

import sqlite3
import sys
from types import ModuleType, SimpleNamespace

import pytest

from shared.content import (
    check_banned_patterns,
    format_llm_cost_summary,
    parse_json_array,
    parse_json_response,
    trim_content,
)
from shared.content.prompts import build_context_injection, build_json_output_instruction, get_tone_description
from shared.telemetry import cost_tracker, sentry_integration
from shared.test_utils.fixtures import SystemFixtureFactory, make_mock_llm_client, make_sample_articles


def test_content_helpers_parse_trim_and_format():
    assert parse_json_response('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_response("[1]") is None
    assert parse_json_response("bad") is None
    assert parse_json_array("[1, 2]") == [1, 2]
    assert parse_json_array("{}") is None
    assert trim_content("abcdef", max_length=5, suffix="..") == "abc.."
    assert format_llm_cost_summary(0.123456, 3).startswith("$0.1235")
    assert check_banned_patterns("clean") == []


def test_content_prompt_helpers():
    instruction = build_json_output_instruction('{"ok": true}')
    context = build_context_injection(news="News", twitter="Tweet", reddit="Reddit")

    assert '{"ok": true}' in instruction
    assert "[X/Twitter" in context
    assert get_tone_description("professional") != "professional"
    assert get_tone_description("custom") == "custom"
    assert build_context_injection(news="없음", twitter="없음", reddit="없음") == ""


def test_shared_test_fixture_factory(monkeypatch, tmp_path):
    env = SystemFixtureFactory.construct_isolated_workspace(monkeypatch, tmp_path)
    module = SimpleNamespace(DATA_DIR=None, LOG_DIR=None, PIPELINE_STATE_DB=None, SCHEDULER_LOG_PATH=None)
    patched = SystemFixtureFactory.patch_runtime_paths(monkeypatch, module, tmp_path)
    client = make_mock_llm_client("ok")
    articles = make_sample_articles(2, category="Science")

    assert env["data_dir"].exists()
    assert patched["log_dir"].exists()
    assert module.PIPELINE_STATE_DB.name == "pipeline_state.db"
    assert client.create().text == "ok"
    assert len(articles) == 2


def test_cost_tracker_summary_and_error_paths(tmp_path, monkeypatch):
    db = tmp_path / "costs.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE llm_calls (project TEXT, cost_usd REAL, timestamp TEXT)")
    conn.execute("INSERT INTO llm_calls VALUES ('demo', 0.25, datetime('now'))")
    conn.execute("INSERT INTO llm_calls VALUES ('', 0.75, datetime('now'))")
    conn.commit()
    conn.close()

    summary = cost_tracker.get_daily_cost_summary(db, days=-1)
    assert summary["total_calls"] == 2
    assert summary["projects"]["demo"]["cost_usd"] == 0.25
    assert cost_tracker.get_daily_cost_summary(tmp_path / "missing.db")["total_calls"] == 0

    monkeypatch.setattr(cost_tracker.inspect, "stack", lambda: [SimpleNamespace(filename=str(cost_tracker.WORKSPACE / "automation" / "x" / "job.py"))])
    assert cost_tracker.detect_project_context() == "automation"


def test_sentry_integration_noop_and_fake_sdk(monkeypatch):
    monkeypatch.setattr(sentry_integration, "_initialized", False)
    assert sentry_integration.init_sentry(dsn="") is False
    assert sentry_integration.capture_exception(RuntimeError("x")) is None
    sentry_integration.add_breadcrumb("x")

    events: list[tuple[str, object]] = []

    class Scope:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def set_tag(self, key, value):
            events.append(("tag", (key, value)))

        def set_extra(self, key, value):
            events.append(("extra", (key, value)))

    fake = ModuleType("sentry_sdk")
    fake.init = lambda **kwargs: events.append(("init", kwargs))
    fake.set_tag = lambda key, value: events.append(("set_tag", (key, value)))
    fake.push_scope = lambda: Scope()
    fake.capture_exception = lambda error: "event-exc"
    fake.capture_message = lambda message, level="info": f"event-{level}"
    fake.add_breadcrumb = lambda **kwargs: events.append(("breadcrumb", kwargs))
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake)
    monkeypatch.setattr(sentry_integration, "_initialized", False)

    assert sentry_integration.init_sentry(dsn="dsn", project="demo") is True
    assert sentry_integration.capture_exception(ValueError("bad"), project="demo") == "event-exc"
    assert sentry_integration.capture_message("msg", level="warning", extra={"x": 1}) == "event-warning"
    sentry_integration.add_breadcrumb("step")
    sentry_integration.sentry_cost_warning(9, 10)
    sentry_integration.send_quality_alert("trend", 40)
    with pytest.raises(RuntimeError):
        with sentry_integration.pipeline_span("stage", project="demo"):
            raise RuntimeError("boom")
    with sentry_integration.pipeline_span("ok", project="demo"):
        pass
    assert events
