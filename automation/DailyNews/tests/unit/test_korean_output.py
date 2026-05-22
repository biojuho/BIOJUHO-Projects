"""Regression tests: every reader-facing path must produce Korean output.

Guards against the regression where the v2 / v2-multi deep-dive prompts
omitted an explicit Korean-language directive, causing the evening
newsletter to render its analytic sections in English.
"""

from __future__ import annotations

import pytest
from antigravity_mcp.domain.models import ContentItem, ContentReport
from antigravity_mcp.integrations import llm_prompts as lp
from antigravity_mcp.integrations.llm_prompts import build_report_prompt, category_label

_KOREAN_MARKER = "natural, fluent Korean"


def _items() -> list[ContentItem]:
    return [
        ContentItem(
            source_name="Source",
            category="AI_Deep",
            title="Some headline",
            link="https://example.com/a",
            summary="A short article summary.",
        ),
        ContentItem(
            source_name="Source",
            category="AI_Deep",
            title="Another headline",
            link="https://example.com/b",
            summary="Another short article summary.",
        ),
    ]


@pytest.mark.parametrize("prompt_version", ["v2", "v2-deep", "v2-multi"])
def test_v2_prompts_enforce_korean_output(monkeypatch, prompt_version: str) -> None:
    """v2-family deep-dive prompts must explicitly require Korean body text.

    Patches the module-level prompt-version globals directly so ``monkeypatch``
    restores them on teardown — avoids the import-time env recompute that an
    ``importlib.reload`` would otherwise leak into sibling tests.
    """
    monkeypatch.setattr(lp, "_PROMPT_VERSION_RAW", prompt_version)
    monkeypatch.setattr(lp, "PROMPT_VERSION", prompt_version)

    _, system_prompt, _ = lp.build_report_prompt(
        category="AI_Deep",
        items=_items(),
        window_name="evening",
    )
    assert _KOREAN_MARKER in system_prompt, f"{prompt_version} prompt missing Korean directive"
    # English section anchors must survive for the response parser.
    assert "Signal" in system_prompt
    assert "Draft Post" in system_prompt


def test_v1_brief_prompt_still_enforces_korean() -> None:
    """The morning v1-brief prompt keeps its Korean directive."""
    _, system_prompt, _ = build_report_prompt(
        category="Tech",
        items=_items(),
        window_name="morning",
        detail_level="minimal",
    )
    assert "Write the actual output in Korean" in system_prompt
    # The Brief opener must use the Korean category label, not the raw key.
    assert "오늘의 핫 이슈: 테크" in system_prompt


def test_category_label_maps_known_keys() -> None:
    assert category_label("Tech") == "테크"
    assert category_label("AI_Deep") == "AI 심층"
    assert category_label("Economy_KR") == "한국 경제"
    assert category_label("Economy_Global") == "글로벌 경제"
    assert category_label("Crypto") == "크립토"
    assert category_label("Global_Affairs") == "국제 정세"


def test_category_label_humanizes_unknown_keys() -> None:
    """Unknown keys never leak a raw snake_case token to readers."""
    assert category_label("Some_New_Category") == "Some New Category"
    assert category_label("") == "뉴스"


def test_content_report_exposes_korean_category_label() -> None:
    report = ContentReport(
        report_id="r1",
        category="Economy_KR",
        window_name="evening",
        window_start="",
        window_end="",
    )
    assert report.category_label == "한국 경제"
    # The stored key is unchanged — only the display label is localized.
    assert report.category == "Economy_KR"
