from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


class FakeLLMClient:
    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def acreate(self, **kwargs):
        self.calls.append(kwargs)
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return SimpleNamespace(text=response)


class TestDigestAdapter:
    def test_robust_json_parse_handles_fences_and_invalid_input(self):
        from antigravity_mcp.integrations.digest_adapter import _robust_json_parse

        assert _robust_json_parse('```json\n{"summary":"A","key_themes":"B","outlook":"C",}\n```') == {
            "summary": "A",
            "key_themes": "B",
            "outlook": "C",
        }
        assert _robust_json_parse("not json at all") is None

    @pytest.mark.asyncio
    async def test_digest_adapter_enqueue_generate_and_rollup(self, monkeypatch):
        from antigravity_mcp.integrations import digest_adapter as module

        client = FakeLLMClient(
            '```json\n{"summary":"Combined","key_themes":"AI, Markets","outlook":"Watch rates",}\n```',
            "# Digest Master\n\nBig picture",
        )
        store = MagicMock()
        store.get_next_serial_number.return_value = "0007"

        monkeypatch.setattr(module, "_get_llm_client", lambda: client)
        monkeypatch.setattr(module, "TaskTier", SimpleNamespace(HEAVY="heavy"))

        adapter = module.DigestAdapter(state_store=store)
        adapter.enqueue("report-1")
        result = await adapter.generate_digest(
            [
                {
                    "report_id": "report-1",
                    "category": "Tech",
                    "summary_lines": ["Line 1", "Line 2"],
                    "insights": [{"text": "Insight 1"}],
                }
            ]
        )
        master = await adapter.generate_digest_master([{"serial_number": "0007", "summary_text": "Combined"}])

        assert result["summary"] == "Combined"
        assert result["key_themes"] == "AI, Markets"
        assert master.startswith("# Digest Master")
        store.enqueue_for_digest.assert_called_once_with("report-1")
        store.save_digest.assert_called_once()
        saved_digest = store.save_digest.call_args.args[0]
        assert saved_digest.digest_id == "digest-0007"
        assert saved_digest.report_ids == ["report-1"]

    @pytest.mark.asyncio
    async def test_digest_adapter_falls_back_on_missing_data_and_errors(self, monkeypatch):
        from antigravity_mcp.integrations import digest_adapter as module

        monkeypatch.setattr(module, "_get_llm_client", lambda: FakeLLMClient(RuntimeError("boom")))
        monkeypatch.setattr(module, "TaskTier", SimpleNamespace(HEAVY="heavy"))

        adapter = module.DigestAdapter()

        assert await adapter.generate_digest([]) == {"summary": "", "key_themes": "", "outlook": ""}
        assert await adapter.generate_digest([{"category": "Tech"}]) == {"summary": "", "key_themes": "", "outlook": ""}
        assert await adapter.generate_digest_master([]) == ""


class TestReasoningAdapter:
    def test_reasoning_helpers_parse_and_load_prompts(self, monkeypatch, tmp_path: Path):
        from antigravity_mcp.integrations import reasoning_adapter as module
        from antigravity_mcp import config

        assert module._robust_json_parse('```json\n[{"fact_text":"A"}]\n```') == [{"fact_text": "A"}]
        assert module._robust_json_parse('noise {"a": 1}\n{"b": 2}') == [{"a": 1}, {"b": 2}]

        prompt_file = tmp_path / "reasoning_prompts.json"
        prompt_file.write_text('{"step1_extract_facts":{"system":"Use this"}}', encoding="utf-8")
        monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)

        prompts = module._load_prompts()
        assert prompts["step1_extract_facts"]["system"] == "Use this"

    @pytest.mark.asyncio
    async def test_reasoning_adapter_runs_full_pipeline_and_persists_results(self, monkeypatch):
        from antigravity_mcp.integrations import reasoning_adapter as module

        client = FakeLLMClient(
            '[{"fact_text":"Revenue rose 20%","why_question":"Why does it matter?"}]',
            '[{"hypothesis":"AI demand is lifting margins","based_on":["F-1"],"pattern":"AI capex upcycle"}]',
            '[{"hypothesis":"AI demand is lifting margins","status":"survived","counter":"None strong","new_pattern":"AI capex upcycle"}]',
        )
        store = MagicMock()
        store.get_active_patterns.return_value = [{"pattern_id": "p-1", "pattern_text": "Prior pattern"}]

        monkeypatch.setattr(module, "_get_llm_client", lambda: client)
        monkeypatch.setattr(module, "TaskTier", SimpleNamespace(HEAVY="heavy"))
        monkeypatch.setattr(module, "_load_prompts", lambda: {})

        adapter = module.ReasoningAdapter(state_store=store)
        result = await adapter.run_full_reasoning(
            report_id="report-1",
            category="Tech",
            content_text="Revenue rose 20% because AI demand improved server sales.",
            source_title="Example",
        )

        assert len(result["facts"]) == 1
        assert len(result["hypotheses"]) == 1
        assert result["survived_count"] == 1
        assert result["new_patterns"] == ["AI capex upcycle"]
        store.save_fact_fragments.assert_called_once()
        store.save_hypotheses.assert_called_once()
        store.upsert_pattern.assert_called_once()

    @pytest.mark.asyncio
    async def test_reasoning_adapter_returns_empty_when_unavailable_or_step_fails(self, monkeypatch):
        from antigravity_mcp.integrations import reasoning_adapter as module

        monkeypatch.setattr(module, "_get_llm_client", lambda: FakeLLMClient(RuntimeError("boom")))
        monkeypatch.setattr(module, "TaskTier", SimpleNamespace(HEAVY="heavy"))
        monkeypatch.setattr(module, "_load_prompts", lambda: {})

        adapter = module.ReasoningAdapter()
        failed = await adapter.run_full_reasoning("report-1", "Tech", "body")
        adapter._client = None
        unavailable = await adapter.run_full_reasoning("report-2", "Tech", "body")

        assert failed["facts"] == []
        assert unavailable["survived_count"] == 0


class TestSentimentAndProofreaderAdapters:
    @pytest.mark.asyncio
    async def test_sentiment_adapter_handles_success_and_fallbacks(self, monkeypatch):
        from antigravity_mcp.integrations import sentiment_adapter as module

        success_client = FakeLLMClient('```json\n[{"sentiment":"positive","topics":["AI"]}]\n```')
        monkeypatch.setattr(module, "_get_llm_client", lambda: success_client)
        monkeypatch.setattr(module, "TaskTier", SimpleNamespace(LIGHTWEIGHT="light"))
        monkeypatch.setattr(module, "LLMPolicy", lambda **kwargs: kwargs)

        adapter = module.SentimentAdapter()
        success = await adapter.analyze(["AI demand is strong"])

        assert success[0].to_dict() == {"sentiment": "POSITIVE", "topics": ["AI"]}
        assert success_client.calls[0]["policy"]["task_kind"] == "classification"

        fallback_client = FakeLLMClient(RuntimeError("failed"))
        monkeypatch.setattr(module, "_get_llm_client", lambda: fallback_client)
        fallback_adapter = module.SentimentAdapter()

        assert (await fallback_adapter.analyze(["text"]))[0].sentiment == "NEUTRAL"
        assert await fallback_adapter.analyze([]) == []

    @pytest.mark.asyncio
    async def test_proofreader_adapter_handles_success_and_fallbacks(self, monkeypatch):
        from antigravity_mcp.integrations import proofreader_adapter as module

        success_client = FakeLLMClient("교정된 문장입니다.")
        monkeypatch.setattr(module, "_get_llm_client", lambda: success_client)
        monkeypatch.setattr(module, "TaskTier", SimpleNamespace(LIGHTWEIGHT="light"))
        monkeypatch.setattr(module, "LLMPolicy", lambda **kwargs: kwargs)

        adapter = module.ProofreaderAdapter()
        corrected = await adapter.proofread("이 문장은 조금 어색한 표현을 포함하고 있습니다.")
        assert corrected == "교정된 문장입니다."
        assert success_client.calls[0]["policy"]["output_language"] == "ko"

        blank_client = FakeLLMClient("", RuntimeError("failed"))
        monkeypatch.setattr(module, "_get_llm_client", lambda: blank_client)
        fallback_adapter = module.ProofreaderAdapter()
        original = "이 문장은 충분히 길어서 교정 로직을 통과합니다."

        assert await fallback_adapter.proofread("짧다") == "짧다"
        assert await fallback_adapter.proofread(original) == original
        assert await fallback_adapter.proofread(original) == original
