"""Tests for DailyNews enhancements: dedup, credibility, critique, agents."""

import sys
from pathlib import Path

import pytest

# Ensure scripts/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


# ---- Deduplicator Tests ----


class TestNewsDeduplicator:
    def _make(self, threshold=0.85):
        from deduplicator import NewsDeduplicator
        return NewsDeduplicator(threshold=threshold)

    def test_identical_titles(self):
        dedup = self._make()
        assert dedup.compute_similarity("OpenAI launches GPT-5", "OpenAI launches GPT-5") == 1.0

    def test_similar_titles(self):
        dedup = self._make()
        sim = dedup.compute_similarity(
            "OpenAI가 GPT-5를 출시하다",
            "OpenAI, GPT-5 공식 출시",
        )
        assert sim > 0.6

    def test_different_titles(self):
        dedup = self._make()
        sim = dedup.compute_similarity(
            "애플, 새 아이폰 공개",
            "한은, 기준금리 동결 결정",
        )
        assert sim < 0.5

    def test_empty_titles(self):
        dedup = self._make()
        assert dedup.compute_similarity("", "test") == 0.0
        assert dedup.compute_similarity("", "") == 0.0

    def test_find_duplicates_basic(self):
        from deduplicator import ArticleItem, NewsDeduplicator
        dedup = NewsDeduplicator(threshold=0.8)

        articles = [
            ArticleItem(title="OpenAI launches GPT-5", link="a", source="TechCrunch", description="big news about GPT"),
            ArticleItem(title="OpenAI launches GPT-5 model", link="b", source="Wired", description=""),
            ArticleItem(title="한은 기준금리 동결", link="c", source="연합뉴스"),
        ]
        groups = dedup.find_duplicates(articles)
        assert len(groups) == 2  # GPT-5 group + 한은 group

    def test_find_duplicates_empty(self):
        dedup = self._make()
        assert dedup.find_duplicates([]) == []

    def test_canonical_selection(self):
        from deduplicator import ArticleItem, NewsDeduplicator
        dedup = NewsDeduplicator(threshold=0.7)

        articles = [
            ArticleItem(title="GPT-5 launched by OpenAI", link="a", description="short"),
            ArticleItem(title="GPT-5 launched by OpenAI today", link="b", description="longer description with more details about the launch"),
        ]
        groups = dedup.find_duplicates(articles)
        assert len(groups) == 1
        # Should select the one with more content
        assert groups[0].canonical.link == "b"

    def test_deduplicate_dicts(self):
        dedup = self._make(threshold=0.8)
        articles = [
            {"title": "AI 혁명이 시작됐다", "link": "a", "source": "A"},
            {"title": "AI 혁명이 시작됐다", "link": "b", "source": "B"},
            {"title": "한국 경제 전망", "link": "c", "source": "C"},
        ]
        result = dedup.deduplicate(articles)
        assert len(result) == 2
        assert result[0]["source_count"] == 2


# ---- Credibility Tests ----


class TestCredibilityScorer:
    def _make(self):
        from credibility import CredibilityScorer
        return CredibilityScorer()

    def test_extract_domain(self):
        scorer = self._make()
        assert scorer.extract_domain("https://www.reuters.com/article/123") == "reuters.com"
        assert scorer.extract_domain("https://techcrunch.com/post/abc") == "techcrunch.com"
        assert scorer.extract_domain("") == ""

    def test_tier1_source(self):
        scorer = self._make()
        tier, score = scorer.get_source_tier("reuters.com")
        assert tier == "tier1"
        assert score == 9.0

    def test_tier2_source(self):
        scorer = self._make()
        tier, score = scorer.get_source_tier("theverge.com")
        assert tier == "tier2"
        assert score == 7.0

    def test_tier3_source(self):
        scorer = self._make()
        tier, score = scorer.get_source_tier("unknownblog.xyz")
        assert tier == "tier3"
        assert score == 5.0

    def test_clickbait_detection(self):
        scorer = self._make()
        signals = scorer.detect_clickbait("충격!! 알고 보니 대박이었다")
        assert len(signals) >= 2

    def test_clean_title(self):
        scorer = self._make()
        signals = scorer.detect_clickbait("한국은행, 기준금리 3.5%로 동결 결정")
        assert len(signals) == 0

    def test_score_high_credibility(self):
        scorer = self._make()
        result = scorer.score_article(
            title="한국은행, 기준금리 동결 결정",
            source_url="https://www.reuters.com/article/123",
        )
        assert result.score >= 8.0
        assert result.tier == "tier1"
        assert result.is_clickbait is False

    def test_score_low_credibility(self):
        scorer = self._make()
        result = scorer.score_article(
            title="충격!! 당신이 몰랐던 5가지 사실!!!",
            source_url="https://unknownblog.xyz/post",
        )
        assert result.score < 5.0
        assert result.is_clickbait is True

    def test_filter_articles(self):
        scorer = self._make()
        articles = [
            {"title": "정상적인 뉴스", "link": "https://reuters.com/a"},
            {"title": "충격!! 경악!! 대박!!", "link": "https://spam.com/b"},
        ]
        filtered = scorer.filter_articles(articles, min_score=5.0)
        assert len(filtered) == 1
        assert filtered[0]["credibility_tier"] == "tier1"

    def test_korean_tier1(self):
        scorer = self._make()
        tier, _ = scorer.get_source_tier("yonhapnews.co.kr")
        assert tier == "tier1"


# ---- Briefing Critique Tests ----


class TestBriefingCritiqueResult:
    def test_from_dict_passing(self):
        from briefing_critique import BriefingCritiqueResult

        data = {
            "scores": {"accuracy": 8, "balance": 7, "readability": 9},
            "average": 8.0,
            "strengths": ["Clear"],
            "weaknesses": [],
            "suggestions": [],
        }
        result = BriefingCritiqueResult.from_dict(data, threshold=7.0)
        assert result.passed is True
        assert result.average == 8.0

    def test_from_dict_failing(self):
        from briefing_critique import BriefingCritiqueResult

        data = {
            "scores": {"accuracy": 5, "balance": 4, "readability": 6},
        }
        result = BriefingCritiqueResult.from_dict(data, threshold=7.0)
        assert result.passed is False
        assert result.average == 5.0

    def test_empty_scores(self):
        from briefing_critique import BriefingCritiqueResult

        result = BriefingCritiqueResult.from_dict({})
        assert result.average == 0.0
        assert result.passed is False


class TestBriefingCritiqueLoopResult:
    def test_basic(self):
        from briefing_critique import BriefingCritiqueLoopResult

        result = BriefingCritiqueLoopResult(
            final_briefing="Test briefing",
            revisions=1,
            passed=True,
        )
        assert result.final_briefing == "Test briefing"


# ---- News Agents Tests ----


class TestNewsAgent:
    def test_tech_matches(self):
        from news_agents import NewsAgent

        agent = NewsAgent("tech")
        assert agent.matches("OpenAI GPT-5 출시") is True
        assert agent.matches("한은 금리 결정") is False

    def test_finance_matches(self):
        from news_agents import NewsAgent

        agent = NewsAgent("finance")
        assert agent.matches("코스피 3000 돌파, 시장 환호") is True
        assert agent.matches("새 AI 칩 개발") is False

    def test_science_matches(self):
        from news_agents import NewsAgent

        agent = NewsAgent("science")
        assert agent.matches("Nature 논문: 유전자 편집 연구 결과") is True
        assert agent.matches("삼성 신제품 출시") is False


class TestAgentOrchestrator:
    def test_classify_articles(self):
        from news_agents import AgentOrchestrator

        orch = AgentOrchestrator()
        articles = [
            {"title": "OpenAI GPT-5 출시", "description": "AI 모델"},
            {"title": "코스피 3000 돌파", "description": "시장 뉴스"},
            {"title": "Nature 연구 논문 발표", "description": "유전자"},
            {"title": "새 카페 오픈", "description": "맛집"},
        ]
        classified = orch.classify_articles(articles)
        assert len(classified["tech"]) == 1
        assert len(classified["finance"]) == 1
        assert len(classified["science"]) == 1
        assert len(classified["general"]) == 1

    def test_classify_empty(self):
        from news_agents import AgentOrchestrator

        orch = AgentOrchestrator()
        classified = orch.classify_articles([])
        assert all(len(v) == 0 for v in classified.values())


class TestCredibilityResult:
    def test_labels(self):
        from credibility import CredibilityResult

        assert CredibilityResult(score=9.0).label == "high"
        assert CredibilityResult(score=6.0).label == "medium"
        assert CredibilityResult(score=3.0).label == "low"


class TestArticleItem:
    def test_info_density(self):
        from deduplicator import ArticleItem

        a = ArticleItem(title="short", description="desc")
        b = ArticleItem(title="much longer title here", description="much longer description")
        assert b.info_density > a.info_density
