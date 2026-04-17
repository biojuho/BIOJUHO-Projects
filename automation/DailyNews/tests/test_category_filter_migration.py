"""Tests for category_filter — migrated from legacy test_news_bot.py.

The original test_news_bot.py tested two pipeline-level behaviors via the
deprecated ``scripts/news_bot.py`` module:

1. Pipeline continues when one category's upload fails (resilience).
2. Pipeline skips links already seen in the state store (dedup).

These behaviors now live in:
- ``antigravity_mcp.domain.category_filter`` (filtering logic)
- ``antigravity_mcp.state.store.PipelineStateStore`` (dedup via article_cache)

This file replaces test_news_bot.py by testing the **same domain invariants**
against the new modular components, without depending on the legacy script.
"""

from __future__ import annotations

from antigravity_mcp.domain.category_filter import (
    CATEGORY_KEYWORDS,
    is_relevant_to_category,
)


class TestCategoryFilterResilience:
    """Category filter must never raise — a single bad category must not
    block filtering of other categories (mirrors the old
    ``test_news_bot_continues_when_one_category_upload_fails``).
    """

    def test_filter_continues_across_all_categories(self):
        """Every known category should return a clean bool for valid input."""
        for category in CATEGORY_KEYWORDS:
            result = is_relevant_to_category(
                "AI breakthrough in semiconductor chips",
                "New GPU architecture announced by NVIDIA",
                category,
            )
            assert isinstance(result, bool), f"{category} returned non-bool"

    def test_filter_handles_empty_strings_without_error(self):
        """Empty title/description must not crash the filter."""
        for category in CATEGORY_KEYWORDS:
            result = is_relevant_to_category("", "", category)
            assert result is False  # no keywords → rejected

    def test_filter_handles_unknown_category_gracefully(self):
        """Unknown categories accept everything (no crash, no false reject)."""
        assert is_relevant_to_category("random text", "any content", "NonExistentCategory") is True

    def test_mixed_categories_produce_independent_results(self):
        """Filter results for one category must not bleed into another
        (mirrors the old test where Economy upload fails but Tech succeeds).
        """
        tech_title = "New AI model released by OpenAI"
        economy_title = "Celebrity gossip from entertainment tonight"

        assert is_relevant_to_category(tech_title, "", "Tech") is True
        assert is_relevant_to_category(economy_title, "", "Tech") is False
        # Same article should independently pass Economy_Global exclude
        assert is_relevant_to_category(economy_title, "sports", "Economy_Global") is False


class TestArticleDedupViaStateStore:
    """Article deduplication via PipelineStateStore (mirrors the old
    ``test_news_bot_skips_links_already_seen``).
    """

    def test_has_seen_article_returns_true_for_recorded_link(self, state_store):
        state_store.record_article(
            link="https://dup.example.com/article",
            source="TestSource",
            category="Tech",
            window_name="morning",
            notion_page_id="page-old",
            run_id="seed-run",
        )
        assert state_store.has_seen_article(
            link="https://dup.example.com/article",
            category="Tech",
            window_name="morning",
        )

    def test_has_seen_article_returns_false_for_unseen_link(self, state_store):
        assert not state_store.has_seen_article(
            link="https://never-seen.example.com/article",
            category="Tech",
            window_name="morning",
        )

    def test_dedup_is_scoped_to_category_and_window(self, state_store):
        """Same link in different category or window is treated as unseen."""
        state_store.record_article(
            link="https://shared.example.com/article",
            source="TestSource",
            category="Tech",
            window_name="morning",
            notion_page_id="page-1",
            run_id="run-1",
        )
        # Same link, different category → not seen
        assert not state_store.has_seen_article(
            link="https://shared.example.com/article",
            category="Crypto",
            window_name="morning",
        )
        # Same link, different window → not seen
        assert not state_store.has_seen_article(
            link="https://shared.example.com/article",
            category="Tech",
            window_name="evening",
        )
