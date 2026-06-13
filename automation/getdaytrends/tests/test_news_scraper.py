"""news_scraper.py 테스트 — Scrapling 뉴스 수집 모듈."""

import pytest
from news_scraper import (
    SCRAPLING_AVAILABLE,
    _parse_daum_news_page,
    _parse_naver_news_page,
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

    def test_parse_naver_news_page_extracts_article_fields(self):
        class _Element:
            def __init__(self, text="", href=""):
                self.text = text
                self.attrib = {"href": href} if href else {}

        class _Item:
            def __init__(self, selectors):
                self.selectors = selectors

            def css_first(self, selector):
                return self.selectors.get(selector)

        class _Page:
            def css(self, selector):
                if selector != ".news_area":
                    return []
                return [
                    _Item(
                        {
                            ".news_tit": _Element(" Headline ", "https://news.example/a"),
                            ".info.press": _Element(" Press "),
                            ".news_dsc": _Element(" Summary " * 40),
                        }
                    ),
                    _Item({}),
                ]

        result = _parse_naver_news_page(_Page(), max_results=5)

        assert result == [
            {
                "title": "Headline",
                "source": "Press",
                "url": "https://news.example/a",
                "snippet": (" Summary " * 40).strip()[:200],
            }
        ]

    def test_parse_daum_news_page_extracts_article_fields(self):
        class _Element:
            def __init__(self, text="", href=""):
                self.text = text
                self.attrib = {"href": href} if href else {}

        class _Item:
            def __init__(self, selectors):
                self.selectors = selectors

            def css_first(self, selector):
                return self.selectors.get(selector)

        class _Page:
            def css(self, selector):
                if selector != ".c-list-basic > li":
                    return []
                return [
                    _Item(
                        {
                            "a.tit_main": _Element(" Daum headline ", "https://news.example/d"),
                            ".info_cp": _Element(" DaumPress "),
                            ".desc": _Element(" Daum summary " * 30),
                        }
                    ),
                    _Item({}),
                ]

        result = _parse_daum_news_page(_Page(), max_results=5)

        assert result == [
            {
                "title": "Daum headline",
                "source": "DaumPress",
                "url": "https://news.example/d",
                "snippet": (" Daum summary " * 30).strip()[:200],
            }
        ]


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
