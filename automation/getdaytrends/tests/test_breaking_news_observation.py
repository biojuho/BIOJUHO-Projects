"""Tests for additive L0/L1 shadow observation."""

from __future__ import annotations

import sqlite3
import sys
import urllib.parse
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from breaking_news_observer import BreakingNewsObserver  # noqa: E402
from collectors.breaking_news import (  # noqa: E402
    KMA_OPERATIONS,
    AdapterResult,
    BreakingNewsItem,
    KmaWeatherAdapter,
    fetch_google_news_breaking,
    fetch_yonhap_breaking,
)
from filter_eval.shadow_store import FilterShadowStore  # noqa: E402
from filter_eval.source_time_shadow import SOURCE_PUBLISHED_AT_COLUMN  # noqa: E402
from models import RawTrend, TrendSource  # noqa: E402
from x_opportunity_radar import XOpportunityRadar  # noqa: E402


def _rss(items: list[dict[str, str]]) -> bytes:
    rendered = []
    for item in items:
        pub_date = f"<pubDate>{item['pub_date']}</pubDate>" if item.get("pub_date") else ""
        rendered.append(
            "<item>"
            f"<title>{item['title']}</title>"
            f"<link>{item['link']}</link>"
            f"<source>{item.get('source', '')}</source>"
            f"<description>{item.get('description', '')}</description>"
            f"{pub_date}"
            "</item>"
        )
    return ("<rss><channel>" + "".join(rendered) + "</channel></rss>").encode()


def test_radar_enables_breaking_observer_only_on_the_production_fetch_path(tmp_path):
    store = FilterShadowStore(tmp_path / "shadow.sqlite3", policy_fingerprint_value="policy-a")
    production = XOpportunityRadar(filter_shadow_store=store)

    async def custom_fetcher(session, country, limit):
        return []

    custom = XOpportunityRadar(custom_fetcher, custom_fetcher, filter_shadow_store=store)

    assert isinstance(production.breaking_news_observer, BreakingNewsObserver)
    assert custom.breaking_news_observer is None


@pytest.mark.asyncio
async def test_yonhap_filters_each_pubdate_at_120_minutes():
    now = datetime(2026, 8, 16, tzinfo=UTC)
    payload = _rss(
        [
            {
                "title": "30분 기사",
                "link": "https://www.yna.co.kr/a/30",
                "pub_date": format_datetime(now - timedelta(minutes=30)),
            },
            {
                "title": "120분 경계 기사",
                "link": "https://www.yna.co.kr/a/120",
                "pub_date": format_datetime(now - timedelta(minutes=120)),
            },
            {
                "title": "121분 기사",
                "link": "https://www.yna.co.kr/a/121",
                "pub_date": format_datetime(now - timedelta(minutes=121)),
            },
            {"title": "시각 미확인", "link": "https://www.yna.co.kr/a/unknown"},
        ]
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await fetch_yonhap_breaking(client, observed_at=now)

    assert result.available is True
    assert [item.title for item in result.results] == ["30분 기사", "120분 경계 기사"]
    assert result.metrics() == {
        "available": True,
        "result_count": 2,
        "sample_n": 3,
        "latest_minutes": 30.0,
        "median_minutes": 120.0,
        "within_120_count": 2,
        "error": "",
    }


@pytest.mark.asyncio
async def test_google_news_control_keeps_exact_search_path_and_deduplicates_locales():
    now = datetime(2026, 8, 16, tzinfo=UTC)
    requested: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.params["hl"] == "ko":
            payload = _rss(
                [
                    {
                        "title": "공통 최신",
                        "link": "https://news.google.com/a/common",
                        "pub_date": format_datetime(now - timedelta(minutes=20)),
                    },
                    {
                        "title": "오래된 대조군",
                        "link": "https://news.google.com/a/old",
                        "pub_date": format_datetime(now - timedelta(minutes=300)),
                    },
                ]
            )
        else:
            payload = _rss(
                [
                    {
                        "title": "공통 최신",
                        "link": "https://news.google.com/a/common-en",
                        "pub_date": format_datetime(now - timedelta(minutes=20)),
                    },
                    {
                        "title": "영문권 최신",
                        "link": "https://news.google.com/a/en",
                        "pub_date": format_datetime(now - timedelta(minutes=40)),
                    },
                ]
            )
        return httpx.Response(200, content=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await fetch_google_news_breaking(client, ["도심 정전"], observed_at=now)

    assert len(requested) == 2
    assert all(url.startswith("https://news.google.com/rss/search?") for url in requested)
    assert {item.title for item in result.results} == {"공통 최신", "영문권 최신"}
    assert result.sample_ages_minutes == (20.0, 300.0, 40.0)


@pytest.mark.asyncio
async def test_kma_without_key_is_quietly_unavailable_and_does_not_request():
    def forbidden_request(url: str, timeout: float):
        raise AssertionError("request must not run without a key")

    result = await KmaWeatherAdapter(
        key_loader=lambda: "",
        request_json=forbidden_request,
    ).collect(observed_at=datetime(2026, 8, 16, tzinfo=UTC))

    assert result.available is False
    assert result.results == ()
    assert result.error == "key_unavailable"


@pytest.mark.asyncio
async def test_kma_calls_exact_four_operations_without_reencoding_key():
    observed_at = datetime(2026, 8, 16, 0, 0, tzinfo=UTC)
    urls: list[str] = []

    def fake_request(url: str, timeout: float):
        urls.append(url)
        operation = urllib.parse.urlparse(url).path.rsplit("/", 1)[-1]
        return {
            "response": {
                "header": {"resultCode": "00", "resultMsg": "NORMAL_SERVICE"},
                "body": {
                    "items": {
                        "item": [
                            {
                                "tmFc": "202608160830",
                                "area": "서울",
                                "warnVar": "호우",
                                "operationMarker": operation,
                            }
                        ]
                    }
                },
            }
        }

    result = await KmaWeatherAdapter(
        key_loader=lambda: "fake%2Bkey%3D",
        request_json=fake_request,
    ).collect(observed_at=observed_at)

    assert result.available is True
    assert len(urls) == len(KMA_OPERATIONS) == 4
    assert {urllib.parse.urlparse(url).path.rsplit("/", 1)[-1] for url in urls} == set(KMA_OPERATIONS)
    assert all("serviceKey=fake%2Bkey%3D&" in url for url in urls)
    assert all("%252B" not in url and "%253D" not in url for url in urls)
    assert all("fromTmFc=20260815" in url and "toTmFc=20260816" in url for url in urls)
    assert len(result.results) == 4
    assert result.sample_ages_minutes == (30.0, 30.0, 30.0, 30.0)
    assert dict(result.operation_status) == {operation: True for operation in KMA_OPERATIONS}


@pytest.mark.asyncio
async def test_observer_adds_source_time_only_to_new_rows_and_preserves_old_sample(tmp_path):
    now = datetime(2026, 8, 16, tzinfo=UTC)
    db_path = tmp_path / "shadow.sqlite3"
    store = FilterShadowStore(db_path, policy_fingerprint_value="policy-a")
    assert store.record(
        source="x-radar",
        candidate_id="old-1",
        title="기존 후보",
        filter_verdict="allow",
        observed_at=now - timedelta(days=1),
    )
    with sqlite3.connect(db_path) as conn:
        before_count = conn.execute("SELECT COUNT(*) FROM filter_candidates").fetchone()[0]
        before_sample = conn.execute(
            "SELECT observed_at, source, candidate_id, title, extra_text, "
            "filter_verdict, filter_reason, policy_fingerprint "
            "FROM filter_candidates WHERE candidate_id = 'old-1'"
        ).fetchone()

    published = now - timedelta(minutes=15)

    async def fake_google(client, keywords, *, observed_at):
        return AdapterResult(
            source="google-news-rss",
            available=True,
            results=(
                BreakingNewsItem(
                    source="google-news-rss",
                    candidate_id="google-1",
                    title="AI 신제품 공개",
                    extra_text="검색어 AI",
                    published_at=published,
                ),
            ),
            sample_ages_minutes=(15.0,),
        )

    async def fake_yonhap(client, *, observed_at):
        return AdapterResult(
            source="yonhap-rss",
            available=True,
            results=(
                BreakingNewsItem(
                    source="yonhap-rss",
                    candidate_id="yonhap-1",
                    title="국회 새 법안 논의",
                    extra_text="",
                    published_at=None,
                ),
            ),
        )

    class MissingKma:
        async def collect(self, *, observed_at):
            return AdapterResult(source="kma-weather", available=False, error="key_unavailable")

    summary = await BreakingNewsObserver(
        store,
        google_fetcher=fake_google,
        yonhap_fetcher=fake_yonhap,
        kma_adapter=MissingKma(),
    ).observe(["AI"], observed_at=now)

    with sqlite3.connect(db_path) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(filter_candidates)")]
        after_count = conn.execute("SELECT COUNT(*) FROM filter_candidates").fetchone()[0]
        after_sample = conn.execute(
            "SELECT observed_at, source, candidate_id, title, extra_text, "
            "filter_verdict, filter_reason, policy_fingerprint "
            "FROM filter_candidates WHERE candidate_id = 'old-1'"
        ).fetchone()
        source_times = dict(
            conn.execute(
                "SELECT candidate_id, source_published_at FROM filter_candidates ORDER BY candidate_id"
            ).fetchall()
        )

    assert SOURCE_PUBLISHED_AT_COLUMN in columns
    assert before_count == 1
    assert after_count == 3
    assert after_sample == before_sample
    assert source_times == {
        "google-1": published.isoformat(),
        "old-1": "",
        "yonhap-1": "",
    }
    assert summary["recorded_count"] == 2
    assert summary["verdicts"] == {"allow": 1, "block": 1}
    assert "median_minutes" not in summary["sources"]["kma-weather"]


@pytest.mark.asyncio
async def test_radar_observer_is_shadow_only_and_exposes_source_health():
    async def google_fetcher(session, country, limit):
        return [
            RawTrend(
                name="AI 신제품",
                source=TrendSource.GOOGLE_TRENDS,
                volume_numeric=10_000,
                published_at=datetime.now(UTC) - timedelta(minutes=10),
                extra={
                    "news_headlines": ["AI 신제품 공개"],
                    "news_items": [
                        {"title": "AI 신제품 공개", "url": "https://one.example/ai", "source": "원뉴스"},
                        {
                            "title": "AI 신제품 업계 반응",
                            "url": "https://two.example/ai",
                            "source": "두뉴스",
                        },
                    ],
                },
            )
        ]

    async def x_fetcher(session, country, limit):
        return []

    class FakeObserver:
        def __init__(self):
            self.keywords = []

        async def observe(self, keywords, *, observed_at):
            self.keywords = list(keywords)
            return {
                "enabled": True,
                "available": True,
                "detected_count": 7,
                "recorded_count": 5,
                "sources": {
                    "google-news-rss": {"available": True},
                    "yonhap-rss": {"available": True},
                    "kma-weather": {"available": False},
                },
            }

    observer = FakeObserver()
    data = await XOpportunityRadar(
        google_fetcher,
        x_fetcher,
        news_fetcher=None,
        breaking_news_observer=observer,
    ).refresh(limit=10)

    assert observer.keywords == ["AI 신제품"]
    assert len(data["items"]) == 1
    assert data["items"][0]["keyword"] == "AI 신제품"
    assert data["breaking_news_observation"]["detected_count"] == 7
    assert data["source_health"]["google_news_rss"] is True
    assert data["source_health"]["yonhap_rss"] is True
    assert data["source_health"]["kma_weather"] is False
    assert "breaking_news" not in data["items"][0]
