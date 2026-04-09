from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from antigravity_mcp.domain.models import ChannelDraft, GeneratedPayload
from antigravity_mcp.evals.frozen_eval import load_frozen_eval_cases, run_frozen_eval
from antigravity_mcp.integrations.llm_prompts import resolve_prompt_mode


@pytest.fixture
def frozen_eval_dataset(tmp_path: Path) -> Path:
    dataset_path = tmp_path / "frozen_eval.json"
    dataset_path.write_text(
        json.dumps(
            {
                "version": "test-v1",
                "description": "Unit test frozen eval dataset",
                "cases": [
                    {
                        "case_id": "tech_manual_duo",
                        "category": "Tech",
                        "window_name": "manual",
                        "window_start": "2026-03-15T00:00:00+00:00",
                        "window_end": "2026-03-15T06:00:00+00:00",
                        "expected_generation_mode": "v1-brief",
                        "items": [
                            {
                                "source_name": "Reuters",
                                "title": "AI infra pricing shifts",
                                "link": "https://example.com/tech-1",
                                "summary": "Cloud vendors are revising AI infra pricing.",
                            },
                            {
                                "source_name": "The Information",
                                "title": "GPU reservation contracts expand",
                                "link": "https://example.com/tech-2",
                                "summary": "Enterprise buyers are locking longer reservation windows.",
                            },
                        ],
                    },
                    {
                        "case_id": "crypto_evening_trio",
                        "category": "Crypto",
                        "window_name": "evening",
                        "window_start": "2026-03-16T07:00:00+00:00",
                        "window_end": "2026-03-16T18:00:00+00:00",
                        "expected_generation_mode": "v1-brief",
                        "items": [
                            {
                                "source_name": "CoinDesk",
                                "title": "Crypto market structure changes",
                                "link": "https://example.com/crypto-1",
                                "summary": "Institutional desks are favoring basis trades.",
                            },
                            {
                                "source_name": "The Block",
                                "title": "Stablecoin settlement rails expand",
                                "link": "https://example.com/crypto-2",
                                "summary": "Asian exchanges are competing on settlement speed.",
                            },
                            {
                                "source_name": "Bloomberg",
                                "title": "Exchange liquidity fragments across venues",
                                "link": "https://example.com/crypto-3",
                                "summary": "Liquidity is becoming more fragmented across regional venues.",
                            },
                        ],
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return dataset_path


class _FakeLLM:
    async def build_report_payload(self, *, category, items, window_name, **kwargs):
        mode = resolve_prompt_mode(window_name, len(items))
        if category == "Crypto":
            return (
                GeneratedPayload(
                    summary_lines=["Fallback crypto summary"],
                    insights=["Fallback crypto insight"],
                    channel_drafts=[
                        ChannelDraft(
                            channel="x",
                            status="draft",
                            content="Fallback crypto draft",
                            source="fallback",
                            is_fallback=True,
                        )
                    ],
                    generation_mode=mode,
                    parse_meta={
                        "used_fallback": True,
                        "format": "fallback",
                        "missing_sections": ["draft"],
                        "sections_found": {"signal": 1},
                    },
                    quality_state="fallback",
                ),
                ["parse_fallback:Crypto:evening"],
            )
        return (
            GeneratedPayload(
                summary_lines=["Dominant signal [A1]"],
                insights=[
                    "Pattern ties pricing pressure to reservations [Inference:A1+A2]",
                    "Action within 48 hours for infra buyers [A2]",
                ],
                channel_drafts=[
                    ChannelDraft(
                        channel="x",
                        status="draft",
                        content="Builder-focused draft",
                        source="llm",
                        is_fallback=False,
                    )
                ],
                generation_mode=mode,
                parse_meta={
                    "used_fallback": False,
                    "format": "v2",
                    "missing_sections": [],
                    "sections_found": {"signal": 1, "pattern": 1, "action": 1},
                    "evidence": {
                        "line_count": 3,
                        "tagged_line_count": 3,
                        "missing_line_count": 0,
                        "article_ref_count": 2,
                        "article_refs": ["[A1]", "[A2]"],
                        "inference_count": 1,
                        "background_line_count": 0,
                    },
                },
                quality_state="ok",
            ),
            [],
        )


def test_load_frozen_eval_cases_parses_dataset(frozen_eval_dataset: Path):
    metadata, cases = load_frozen_eval_cases(frozen_eval_dataset)

    assert metadata["version"] == "test-v1"
    assert len(cases) == 2
    assert cases[0].case_id == "tech_manual_duo"
    assert cases[1].expected_generation_mode == "v1-brief"


@pytest.mark.asyncio
async def test_run_frozen_eval_writes_outputs_and_summarizes_metrics(
    frozen_eval_dataset: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import antigravity_mcp.integrations.fact_check_adapter as fact_check_module

    class FakeFactCheckAdapter:
        @staticmethod
        def is_available() -> bool:
            return True

        async def check_report(self, summary_lines, insights, drafts_text, source_articles):
            if "Fallback" in drafts_text:
                return {"passed": False, "issues": ["Fallback quality issue"], "fact_check_score": 0.2}
            return {"passed": True, "issues": [], "fact_check_score": 0.8}

    monkeypatch.setattr(fact_check_module, "FactCheckAdapter", FakeFactCheckAdapter)

    output_path = tmp_path / "frozen_eval_result.json"
    state_db_path = tmp_path / "frozen_eval_state.db"
    result = await run_frozen_eval(
        dataset_path=frozen_eval_dataset,
        output_path=output_path,
        state_db_path=state_db_path,
        llm_adapter=_FakeLLM(),
        pipeline_overrides={"embedding_adapter": SimpleNamespace(is_available=False)},
    )

    assert output_path.exists()
    assert output_path.with_suffix(".md").exists()
    assert result["summary"]["case_count"] == 2
    assert result["summary"]["report_count"] == 2
    assert result["summary"]["fallback_rate"] == 0.5
    assert result["summary"]["x_fallback_rate"] == 0.5
    assert result["summary"]["prompt_mode_match_rate"] == 1.0
    assert result["summary"]["evidence_coverage_ratio"] == 1.0
    assert result["summary"]["direct_article_ref_rate"] == 1.0
    assert any("fell back" in warning for warning in result["warnings"])

    markdown = output_path.with_suffix(".md").read_text(encoding="utf-8")
    assert "# Frozen Eval Report" in markdown
    assert "`tech_manual_duo`" in markdown
    assert "`crypto_evening_trio`" in markdown


@pytest.mark.asyncio
async def test_ops_run_frozen_eval_tool_wraps_result_as_partial(monkeypatch: pytest.MonkeyPatch):
    from antigravity_mcp.tooling.ops_tools import ops_run_frozen_eval_tool

    async def fake_run_frozen_eval(**kwargs):
        return {
            "run_id": "frozen_eval-20260329T000000Z",
            "output_path": "D:/tmp/result.json",
            "markdown_path": "D:/tmp/result.md",
            "warnings": ["1 case(s) fell back to deterministic generation."],
            "summary": {"case_count": 1},
            "cases": [],
        }

    monkeypatch.setattr("antigravity_mcp.tooling.ops_tools.run_frozen_eval", fake_run_frozen_eval)

    result = await ops_run_frozen_eval_tool()

    assert result["status"] == "partial"
    assert result["meta"]["run_id"] == "frozen_eval-20260329T000000Z"
    assert result["meta"]["warnings"] == ["1 case(s) fell back to deterministic generation."]
