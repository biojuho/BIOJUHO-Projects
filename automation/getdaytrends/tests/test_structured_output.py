"""Tests for structured_output.py."""

from types import SimpleNamespace

import pytest

import structured_output
from structured_output import (
    LongPostResponse,
    ScoringResponseItem,
    ThreadResponse,
    TweetGenerationResponse,
    TweetItem,
    _log_fallback,
    _instructor_create,
    reset_instructor_client,
)


class TestScoringResponseItem:
    def test_default_values(self):
        item = ScoringResponseItem(keyword="test")
        assert item.keyword == "test"
        assert item.publishable is True
        assert item.viral_potential == 0
        assert item.sentiment == "neutral"
        assert item.safety_flag is False

    def test_full_construction(self):
        item = ScoringResponseItem(
            keyword="semiconductor",
            publishable=True,
            viral_potential=85,
            top_insight="Strong growth",
            why_trending="Market share shift",
            peak_status="rising",
            relevance_score=8,
            suggested_angles=["reversal", "data", "empathy"],
            best_hook_starter="Revenue doubled in 3 years",
            category="economy",
            sentiment="neutral",
            trigger_event="earnings release",
            chain_reaction="community spread",
            why_now="quarterly report",
            key_positions=["bull", "bear"],
            joongyeon_kick=75,
        )
        assert item.viral_potential == 85
        assert item.category == "economy"
        assert len(item.suggested_angles) == 3

    def test_model_dump_compatibility(self):
        item = ScoringResponseItem(keyword="test", viral_potential=50)
        dumped = item.model_dump()
        assert dumped["keyword"] == "test"
        assert dumped["viral_potential"] == 50
        assert dumped["publishable"] is True


class TestTweetGenerationResponse:
    def test_empty(self):
        resp = TweetGenerationResponse()
        assert resp.topic == ""
        assert resp.tweets == []

    def test_with_tweets(self):
        resp = TweetGenerationResponse(
            topic="trend",
            tweets=[
                TweetItem(type="reversal", content="First tweet"),
                TweetItem(type="data", content="Second tweet"),
            ],
        )
        assert len(resp.tweets) == 2
        assert resp.tweets[0].content == "First tweet"

    def test_model_dump_for_generator(self):
        resp = TweetGenerationResponse(
            topic="test",
            tweets=[TweetItem(type="reversal", content="payload")],
        )
        dumped = resp.model_dump()
        assert dumped["tweets"][0]["content"] == "payload"
        assert dumped["tweets"][0]["type"] == "reversal"


class TestLongPostResponse:
    def test_with_seo(self):
        resp = LongPostResponse(
            topic="AI",
            content="long form",
            seo_keywords=["AI", "LLM"],
        )
        assert len(resp.seo_keywords) == 2


class TestThreadResponse:
    def test_thread_structure(self):
        resp = ThreadResponse(
            topic="trend",
            hook="What are we missing?",
            tweets=["One", "Two", "Three"],
        )
        assert len(resp.tweets) == 3
        assert resp.hook.endswith("?")


class TestResetClient:
    def test_reset_does_not_error(self):
        reset_instructor_client()


class TestInstructorCreate:
    @pytest.mark.asyncio
    async def test_handles_sync_create(self):
        def create(**kwargs):
            return {"ok": True, "kwargs": kwargs}

        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        result = await _instructor_create(client, model="test-model")

        assert result["ok"] is True
        assert result["kwargs"]["model"] == "test-model"

    @pytest.mark.asyncio
    async def test_handles_async_create(self):
        async def create(**kwargs):
            return {"ok": True, "kwargs": kwargs}

        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        result = await _instructor_create(client, model="async-model")

        assert result["ok"] is True
        assert result["kwargs"]["model"] == "async-model"


class TestFallbackLogging:
    def test_retry_errors_are_downgraded_to_debug(self, monkeypatch):
        events: list[tuple[str, str]] = []

        monkeypatch.setattr(structured_output.log, "debug", lambda msg: events.append(("debug", msg)))
        monkeypatch.setattr(structured_output.log, "warning", lambda msg: events.append(("warning", msg)))

        retry_error = type("InstructorRetryException", (Exception,), {})("retry")
        _log_fallback("List extract fallback", retry_error)

        assert events[0][0] == "debug"

    def test_missing_instructor_is_downgraded_to_debug(self, monkeypatch):
        events: list[tuple[str, str]] = []

        monkeypatch.setattr(structured_output.log, "debug", lambda msg: events.append(("debug", msg)))
        monkeypatch.setattr(structured_output.log, "warning", lambda msg: events.append(("warning", msg)))

        _log_fallback("List extract fallback", ModuleNotFoundError("No module named 'instructor'"))

        assert events[0][0] == "debug"

    def test_other_errors_remain_warnings(self, monkeypatch):
        events: list[tuple[str, str]] = []

        monkeypatch.setattr(structured_output.log, "debug", lambda msg: events.append(("debug", msg)))
        monkeypatch.setattr(structured_output.log, "warning", lambda msg: events.append(("warning", msg)))

        _log_fallback("List extract fallback", ModuleNotFoundError("jsonref"))

        assert events[0][0] == "warning"
