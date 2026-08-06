"""Tests for factual source expansion and topic exclusions."""

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from content_filters import excluded_topic_reason, topic_is_allowed  # noqa: E402
from news_origin_collector import parse_bing_news_rss  # noqa: E402


def test_topic_filter_excludes_requested_topics_without_broad_false_positive():
    assert excluded_topic_reason("마요르카 대 PSG") == "스포츠 제외"
    assert excluded_topic_reason("김하성 시즌 20호 홈런") == "스포츠 제외"
    assert excluded_topic_reason("김병지 600만원씩 받고 욕먹은 이유") == "스포츠 제외"
    assert excluded_topic_reason("inter miami vs san luis") == "스포츠 제외"
    assert excluded_topic_reason("이정후 5경기 연속 안타") == "스포츠 제외"
    assert excluded_topic_reason("쇼트트랙 임종언 도핑 징계 위기") == "스포츠 제외"
    assert excluded_topic_reason("롤) 어제 치열한 경기로 1위를 수성한 팀") == "스포츠 제외"
    assert excluded_topic_reason("코스피 장중 급락") == "증시·실적 제외"
    assert excluded_topic_reason("A사 2분기 영업이익 컨센서스 상회") == "증시·실적 제외"
    assert excluded_topic_reason("서울 아파트 실거래가 상승") == "부동산 제외"
    assert excluded_topic_reason("전세 끼고 산 집을 매도했다") == "부동산 제외"
    assert excluded_topic_reason("국회에서 새 법안 통과") == "정치 제외"
    assert excluded_topic_reason("대통령실 개각 검토") == "정치 제외"
    assert excluded_topic_reason("백악관 긴급 브리핑") == "정치 제외"
    assert excluded_topic_reason("트럼프 공화당 행사 참석") == "정치 제외"
    assert excluded_topic_reason("남성연대 신규 영상") == "정치 제외"
    assert excluded_topic_reason("추석 전 민생지원금 또 푼다") == "정치 제외"
    assert excluded_topic_reason("경기도 사실상 부도라네요") == "정치 제외"
    assert topic_is_allowed("제주가 폭염 경보를 발령했다") is True
    assert topic_is_allowed("도심 정전으로 지하철 운행 중단") is True


def test_bing_rss_parser_returns_only_direct_publisher_urls_with_timestamps():
    raw = """<?xml version="1.0" encoding="UTF-8"?>
    <rss xmlns:News="https://example.test/news"><channel>
      <item><title>도심 정전 발생</title>
        <link>http://www.bing.com/news/apiclick.aspx?url=https%3A%2F%2Fnews.example.com%2Fpower%3Fid%3D7</link>
        <pubDate>Wed, 05 Aug 2026 12:05:00 GMT</pubDate><News:Source>Example News</News:Source></item>
      <item><title>스포츠 홈런 소식</title>
        <link>http://www.bing.com/news/apiclick.aspx?url=https%3A%2F%2Fsports.example.com%2F1</link>
        <pubDate>Wed, 05 Aug 2026 12:06:00 GMT</pubDate><News:Source>Sports</News:Source></item>
      <item><title>MSN 재전송</title>
        <link>http://www.bing.com/news/apiclick.aspx?url=https%3A%2F%2Fwww.msn.com%2Farticle</link>
        <pubDate>Wed, 05 Aug 2026 12:07:00 GMT</pubDate><News:Source>Wire on MSN</News:Source></item>
    </channel></rss>""".encode()

    assert parse_bing_news_rss(raw, now=datetime(2026, 8, 5, 13, 0, tzinfo=UTC)) == [
        {
            "title": "도심 정전 발생",
            "url": "https://news.example.com/power?id=7",
            "source": "Example News",
            "published_at": "2026-08-05T12:05:00+00:00",
            "discovered_via": "Bing News RSS",
        }
    ]
