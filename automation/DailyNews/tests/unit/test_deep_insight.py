"""Tests for single-topic deep insight mode in brain_adapter."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


def _resp(thread_text: str, tagline: str = "t") -> SimpleNamespace:
    payload = {
        "tagline": tagline,
        "summary": [],
        "insights": [],
        "x_thread": [thread_text],
    }
    return SimpleNamespace(text=json.dumps(payload, ensure_ascii=False))


class TestDeepInsightModeFlag:
    def test_default_on(self, monkeypatch):
        monkeypatch.delenv("DAILYNEWS_DEEP_INSIGHT_MODE", raising=False)
        from antigravity_mcp.integrations.brain_adapter import _deep_insight_mode_enabled

        assert _deep_insight_mode_enabled() is True

    @pytest.mark.parametrize("value", ["0", "false", "False", "OFF", "no"])
    def test_opt_out(self, monkeypatch, value):
        monkeypatch.setenv("DAILYNEWS_DEEP_INSIGHT_MODE", value)
        from antigravity_mcp.integrations.brain_adapter import _deep_insight_mode_enabled

        assert _deep_insight_mode_enabled() is False

    @pytest.mark.parametrize("value", ["1", "true", "on", "yes", ""])
    def test_opt_in_variants(self, monkeypatch, value):
        monkeypatch.setenv("DAILYNEWS_DEEP_INSIGHT_MODE", value)
        from antigravity_mcp.integrations.brain_adapter import _deep_insight_mode_enabled

        assert _deep_insight_mode_enabled() is True


class TestValidateDeepInsight:
    def _well_formed(self) -> dict:
        body = (
            "## 🎯 Signal\n"
            "오늘 비트코인이 $69,355로 5.2% 하락했다 [A1].\n"
            "옵션 시장 변동성이 12.4bp 확대됐다 [A2].\n"
            "## 🔁 Pattern\n"
            "전년 대비 3개월 누적 -18% 추세 [Inference:A1+A2].\n"
            "## 🌊 Ripple\n"
            "국내 거래소 거래량 33% 감소가 다음 주 마진 콜을 압박한다 [A1].\n"
            "## ⚠️ Counterpoint\n"
            "그러나 ETF 순유입은 6일 연속 양전환 중이다 [Background].\n"
            "## ✅ Action\n"
            "이번 주 안에 레버리지 ≤2배로 축소하고, 이번 분기 안에 헤지 비율을 30%까지 늘릴 것 [Inference:A1+A2].\n"
        )
        return {
            "tagline": "겉은 잔잔, 속은 갈라지고 있다",
            "summary": ["Signal", "Pattern", "Ripple"],
            "insights": [],
            "x_thread": [body],
        }

    def test_well_formed_passes(self):
        from antigravity_mcp.integrations.brain_adapter import validate_deep_insight

        qc = validate_deep_insight(self._well_formed())
        assert qc["ok"] is True
        assert qc["warnings"] == []
        assert qc["metrics"]["evidence_tags"] >= 3
        assert qc["metrics"]["number_anchors"] >= 3
        assert qc["metrics"]["has_counterpoint"] is True
        assert qc["metrics"]["has_action_timeframe"] is True

    def test_missing_evidence_tags_warns(self):
        from antigravity_mcp.integrations.brain_adapter import validate_deep_insight

        thin = self._well_formed()
        thin["x_thread"] = ["비트코인이 5.2% 하락. 변동성이 12bp 확대. 그러나 ETF 유입 양전환. 이번 주 헤지."]
        qc = validate_deep_insight(thin)
        assert qc["ok"] is False
        assert any("evidence_tags" in w for w in qc["warnings"])

    def test_missing_counterpoint_warns(self):
        from antigravity_mcp.integrations.brain_adapter import validate_deep_insight

        no_counter = self._well_formed()
        no_counter["x_thread"] = [
            "## 🎯 Signal\n5.2% 하락 [A1].\n"
            "## 🔁 Pattern\n전년 대비 3개월 누적 -18% [A2].\n"
            "## 🌊 Ripple\n거래량 33% 감소 [A1].\n"
            "## ✅ Action\n이번 주 안에 레버리지 ≤2배로 축소 [Inference:A1+A2]."
        ]
        qc = validate_deep_insight(no_counter)
        assert qc["ok"] is False
        assert any("counterpoint" in w for w in qc["warnings"])

    def test_missing_action_timeframe_warns(self):
        from antigravity_mcp.integrations.brain_adapter import validate_deep_insight

        no_action = self._well_formed()
        no_action["x_thread"] = [
            "## 🎯 Signal\n5.2% 하락 [A1].\n"
            "## 🔁 Pattern\n전년 대비 -18% [A2].\n"
            "## 🌊 Ripple\n거래량 33% 감소 [A1].\n"
            "## ⚠️ Counterpoint\n그러나 ETF 유입은 양전환 [Background].\n"
            "## ✅ Action\n레버리지를 줄일 것 [Inference:A1+A2]."
        ]
        qc = validate_deep_insight(no_action)
        assert qc["ok"] is False
        assert any("action_timeframe" in w for w in qc["warnings"])

    def test_non_dict_input_safe(self):
        from antigravity_mcp.integrations.brain_adapter import validate_deep_insight

        qc = validate_deep_insight(None)
        assert qc["ok"] is False
        assert qc["warnings"]

    def test_x_thread_as_string_supported(self):
        from antigravity_mcp.integrations.brain_adapter import validate_deep_insight

        single_str = self._well_formed()
        single_str["x_thread"] = single_str["x_thread"][0]
        qc = validate_deep_insight(single_str)
        assert qc["ok"] is True


class TestAnalyzeNewsDeepMode:
    @pytest.mark.asyncio
    async def test_directives_injected_when_enabled(self, monkeypatch):
        monkeypatch.setenv("DAILYNEWS_DEEP_INSIGHT_MODE", "1")
        from antigravity_mcp.integrations.brain_adapter import BrainAdapter

        captured: dict = {}

        class FakeClient:
            async def acreate(self, *, tier, max_tokens, messages):
                captured["prompt"] = messages[0]["content"]
                captured["max_tokens"] = max_tokens
                return SimpleNamespace(
                    text='{"tagline":"t","summary":[],"insights":[],"x_thread":["body"]}'
                )

        adapter = BrainAdapter()
        adapter._client = FakeClient()
        monkeypatch.setattr(adapter, "select_top_articles", AsyncMock(return_value=[0]))

        await adapter.analyze_news("Tech", [{"title": "x", "description": "y"}], "today")

        assert "단일 주제 수렴 모드" in captured["prompt"]
        assert "🎯 Signal" in captured["prompt"]
        assert "Counterpoint" in captured["prompt"]
        assert captured["max_tokens"] == 4500

    @pytest.mark.asyncio
    async def test_directives_skipped_when_disabled(self, monkeypatch):
        monkeypatch.setenv("DAILYNEWS_DEEP_INSIGHT_MODE", "0")
        from antigravity_mcp.integrations.brain_adapter import BrainAdapter

        captured: dict = {}

        class FakeClient:
            async def acreate(self, *, tier, max_tokens, messages):
                captured["prompt"] = messages[0]["content"]
                captured["max_tokens"] = max_tokens
                return SimpleNamespace(
                    text='{"tagline":"t","summary":[],"insights":[],"x_thread":["body"]}'
                )

        adapter = BrainAdapter()
        adapter._client = FakeClient()
        monkeypatch.setattr(adapter, "select_top_articles", AsyncMock(return_value=[0]))

        await adapter.analyze_news("Tech", [{"title": "x", "description": "y"}], "today")

        assert "단일 주제 수렴 모드" not in captured["prompt"]
        assert captured["max_tokens"] == 3000

    @pytest.mark.asyncio
    async def test_result_schema_unchanged_with_qc_active(self, monkeypatch):
        """Ensure deep mode does not break the downstream normalize_analysis contract."""
        monkeypatch.setenv("DAILYNEWS_DEEP_INSIGHT_MODE", "1")
        from antigravity_mcp.integrations.brain_adapter import BrainAdapter

        class FakeClient:
            async def acreate(self, *, tier, max_tokens, messages):
                return SimpleNamespace(
                    text='{"tagline":"t","summary":["s1"],"insights":[],"x_thread":["body"]}'
                )

        adapter = BrainAdapter()
        adapter._client = FakeClient()
        monkeypatch.setattr(adapter, "select_top_articles", AsyncMock(return_value=[0]))

        result = await adapter.analyze_news("Tech", [{"title": "x", "description": "y"}], "today")

        assert result == {"tagline": "t", "summary": ["s1"], "insights": [], "x_thread": ["body"]}


class TestDeepInsightRetry:
    @pytest.mark.asyncio
    async def test_default_off_no_second_call(self, monkeypatch):
        monkeypatch.setenv("DAILYNEWS_DEEP_INSIGHT_MODE", "1")
        monkeypatch.delenv("DAILYNEWS_DEEP_INSIGHT_RETRY", raising=False)
        from antigravity_mcp.integrations.brain_adapter import BrainAdapter

        call_count = {"n": 0}

        class FakeClient:
            async def acreate(self, *, tier, max_tokens, messages):
                call_count["n"] += 1
                return SimpleNamespace(
                    text='{"tagline":"t","summary":[],"insights":[],"x_thread":["short body no tags"]}'
                )

        adapter = BrainAdapter()
        adapter._client = FakeClient()
        monkeypatch.setattr(adapter, "select_top_articles", AsyncMock(return_value=[0]))

        await adapter.analyze_news("Tech", [{"title": "x", "description": "y"}], "today")

        assert call_count["n"] == 1

    @pytest.mark.asyncio
    async def test_retry_replaces_when_qc_improves(self, monkeypatch):
        monkeypatch.setenv("DAILYNEWS_DEEP_INSIGHT_MODE", "1")
        monkeypatch.setenv("DAILYNEWS_DEEP_INSIGHT_RETRY", "1")
        from antigravity_mcp.integrations.brain_adapter import BrainAdapter

        bad_thread = "## 🎯 Signal\n오늘은 평범한 하루였다."
        good_thread = (
            "## 🎯 Signal\n비트코인 **5.2%** [A1].\n"
            "## 🔁 Pattern\n전년 대비 **-18%** [A2].\n"
            "## 🌊 Ripple\n거래량 **33%** 감소 [Inference:A1+A2].\n"
            "## ⚠️ Counterpoint\n그러나 ETF는 **6일** 연속 양전환 [Background].\n"
            "## ✅ Action\n이번 주 안에 레버리지 축소 [A1]."
        )
        responses = [_resp(bad_thread), _resp(good_thread)]

        class FakeClient:
            def __init__(self):
                self.calls = []

            async def acreate(self, *, tier, max_tokens, messages):
                self.calls.append(messages[0]["content"])
                return responses[len(self.calls) - 1]

        adapter = BrainAdapter()
        client = FakeClient()
        adapter._client = client
        monkeypatch.setattr(adapter, "select_top_articles", AsyncMock(return_value=[0]))

        result = await adapter.analyze_news("Tech", [{"title": "x", "description": "y"}], "today")

        assert len(client.calls) == 2
        assert "재시도" in client.calls[1]
        assert result is not None
        assert "Counterpoint" in result["x_thread"][0]

    @pytest.mark.asyncio
    async def test_retry_keeps_original_when_not_better(self, monkeypatch):
        monkeypatch.setenv("DAILYNEWS_DEEP_INSIGHT_MODE", "1")
        monkeypatch.setenv("DAILYNEWS_DEEP_INSIGHT_RETRY", "1")
        from antigravity_mcp.integrations.brain_adapter import BrainAdapter

        original_thread = "## 🎯 Signal\n수치 **1.2%** [A1].\n## 🔁 Pattern\n."
        worse_thread = "no structure at all"
        responses = [_resp(original_thread, tagline="orig"), _resp(worse_thread, tagline="worse")]

        class FakeClient:
            def __init__(self):
                self.idx = 0

            async def acreate(self, *, tier, max_tokens, messages):
                r = responses[self.idx]
                self.idx += 1
                return r

        adapter = BrainAdapter()
        adapter._client = FakeClient()
        monkeypatch.setattr(adapter, "select_top_articles", AsyncMock(return_value=[0]))

        result = await adapter.analyze_news("Tech", [{"title": "x", "description": "y"}], "today")

        assert result["tagline"] == "orig"

    def test_retry_flag_default_off(self, monkeypatch):
        monkeypatch.delenv("DAILYNEWS_DEEP_INSIGHT_RETRY", raising=False)
        from antigravity_mcp.integrations.brain_adapter import _deep_insight_retry_enabled

        assert _deep_insight_retry_enabled() is False

    @pytest.mark.parametrize("val", ["1", "true", "yes", "on"])
    def test_retry_flag_opt_in(self, monkeypatch, val):
        monkeypatch.setenv("DAILYNEWS_DEEP_INSIGHT_RETRY", val)
        from antigravity_mcp.integrations.brain_adapter import _deep_insight_retry_enabled

        assert _deep_insight_retry_enabled() is True
