"""news_scraper.py 테스트 — Scrapling 뉴스 수집 모듈."""

import pytest

from news_scraper import (
    SCRAPLING_AVAILABLE,
    enrich_news_context,
    fetch_news_enhanced,
)


class TestFetchNewsEnhanced:
    """뉴스 수집 테스트."""

    def test_returns_list(self):
        # Scrapling 미설치 시 빈 리스트, 설치 시 결과 리스트
        result = fetch_news_enhanced("테스트 키워드", max_results=3)
        assert isinstance(result, list)

    def test_max_results_limit(self):
        result = fetch_news_enhanced("테스트", max_results=2)
        assert len(result) <= 2

    @pytest.mark.skipif(not SCRAPLING_AVAILABLE, reason="Scrapling 미설치")
    def test_article_structure(self):
        """Scrapling 설치 시 기사 구조 검증."""
        result = fetch_news_enhanced("삼성전자", max_results=2)
        for article in result:
            assert "title" in article
            assert "source" in article
            assert "url" in article
            assert "snippet" in article


class TestEnrichNewsContext:
    """뉴스 컨텍스트 보강 테스트."""

    def test_sufficient_context_not_enriched(self):
        # 기존 인사이트가 5건 이상이면 보강하지 않음
        existing = "a | b | c | d | e"
        result = enrich_news_context("테스트", existing)
        assert result == existing

    def test_empty_context_enriched(self):
        result = enrich_news_context("테스트", "")
        assert isinstance(result, str)

    def test_partial_context_enriched(self):
        existing = "기존 뉴스 1 | 기존 뉴스 2"
        result = enrich_news_context("테스트", existing)
        assert isinstance(result, str)
        # 원본이 포함되어 있어야 함
        assert "기존 뉴스 1" in result
