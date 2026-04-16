"""Tests for the extracted category-relevance filter."""

from __future__ import annotations

from antigravity_mcp.domain.category_filter import (
    CATEGORY_KEYWORDS,
    is_relevant_to_category,
)


class TestIsRelevantToCategory:
    """Verify keyword-based filtering for each category."""

    def test_tech_accepts_ai_article(self):
        assert is_relevant_to_category("AI breakthrough in 2026", "New AI model released", "Tech")

    def test_tech_rejects_recipe_article(self):
        assert not is_relevant_to_category("Best recipe for pasta", "A delicious cookbook entry", "Tech")

    def test_economy_kr_accepts_korean_economy(self):
        assert is_relevant_to_category("코스피 3000 돌파", "증시 상승세 지속", "Economy_KR")

    def test_economy_global_accepts_fed_article(self):
        assert is_relevant_to_category("Fed raises interest rate", "Treasury bonds surge", "Economy_Global")

    def test_economy_global_rejects_sports(self):
        assert not is_relevant_to_category("Celebrity gossip from entertainment tonight", "sports", "Economy_Global")

    def test_crypto_accepts_bitcoin(self):
        assert is_relevant_to_category("Bitcoin hits new ATH", "BTC surges past 100k", "Crypto")

    def test_global_affairs_accepts_diplomacy(self):
        assert is_relevant_to_category("UN summit on peace", "Diplomacy efforts continue", "Global_Affairs")

    def test_ai_deep_accepts_llm(self):
        assert is_relevant_to_category("New LLM benchmark results", "Claude outperforms GPT", "AI_Deep")

    def test_unknown_category_accepts_everything(self):
        assert is_relevant_to_category("Random article", "Random content", "UnknownCategory")

    def test_no_keyword_match_returns_false(self):
        assert not is_relevant_to_category(
            "Gardening tips for spring", "Plant flowers in your backyard", "Tech"
        )

    def test_all_categories_have_include_keywords(self):
        for category, (include, _exclude) in CATEGORY_KEYWORDS.items():
            assert len(include) > 0, f"{category} has no include keywords"
