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
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dashboard_routes_x_radar as x_radar_routes  # noqa: E402
from breaking_news_observer import BreakingNewsObserver  # noqa: E402
from collectors.breaking_news import (  # noqa: E402
    KMA_OPERATIONS,
    AdapterResult,
    BreakingNewsItem,
    KmaWeatherAdapter,
    fetch_google_news_breaking,
    fetch_yonhap_breaking,
)
from dashboard_routes_x_radar import _with_explicit_age  # noqa: E402
from filter_eval.shadow_store import FilterShadowStore  # noqa: E402
from filter_eval.source_time_shadow import SOURCE_PUBLISHED_AT_COLUMN  # noqa: E402
from models import RawTrend, TrendSource  # noqa: E402
from x_opportunity_radar import XOpportunityRadar, _breaking_lane_items  # noqa: E402


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
                "description": '그는 &quot;속보&quot;라고 &apos;말했다&apos; &amp; &lt;b&gt;강조&lt;/b&gt;',
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
    assert result.results[0].summary == '그는 "속보"라고 \'말했다\' & 강조'
    assert result.results[1].summary == ""
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
async def test_rss_item_without_description_keeps_summary_empty_not_title():
    now = datetime(2026, 8, 16, tzinfo=UTC)
    payload = _rss(
        [
            {
                "title": "제목만 있는 기사",
                "link": "https://www.yna.co.kr/a/no-description",
                "pub_date": format_datetime(now - timedelta(minutes=10)),
            }
        ]
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await fetch_yonhap_breaking(client, observed_at=now)

    assert [item.title for item in result.results] == ["제목만 있는 기사"]
    assert result.results[0].summary == ""
    assert result.results[0].summary != result.results[0].title


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
async def test_kma_wthr_wrn_msg_body_becomes_summary_and_other_operations_stay_empty():
    observed_at = datetime(2026, 8, 16, 0, 0, tzinfo=UTC)

    def fake_request(url: str, timeout: float):
        operation = urllib.parse.urlparse(url).path.rsplit("/", 1)[-1]
        if operation == "getWthrWrnMsg":
            raw = [
                {
                    "tmFc": "202608160830",
                    "t6": "o 호우주의보 : 서울\r\no 강풍주의보 : 부산",
                    "t7": "(1) 호우 예비특보\r\no 08월 16일 밤 : 경기남부",
                    "other": "<유의 사항>\r\no 산사태에 유의",
                },
                {
                    "tmFc": "202608160845",
                    "t6": "",
                    "t7": "",
                    "other": "o 없음",
                },
            ]
        else:
            raw = [
                {
                    "tmFc": "202608160830",
                    "area": "서울",
                    "warnVar": "호우",
                }
            ]
        return {
            "response": {
                "header": {"resultCode": "00", "resultMsg": "NORMAL_SERVICE"},
                "body": {"items": {"item": raw}},
            }
        }

    result = await KmaWeatherAdapter(
        key_loader=lambda: "fake%2Bkey%3D",
        request_json=fake_request,
    ).collect(observed_at=observed_at)

    msg_items = [item for item in result.results if item.source == "kma:getWthrWrnMsg"]
    list_items = [item for item in result.results if item.source == "kma:getWthrWrnList"]
    assert len(msg_items) == 2
    assert msg_items[0].summary.startswith("o 호우주의보 : 서울 o 강풍주의보 : 부산 ·")
    assert "호우 예비특보" in msg_items[0].summary
    assert "산사태에 유의" in msg_items[0].summary
    assert msg_items[1].summary == ""
    assert msg_items[1].title == "[기상청 기상특보 통보문]"
    assert all(item.summary == "" for item in list_items)


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
async def test_observer_exposes_only_allowed_yonhap_and_kma_product_candidates():
    now = datetime(2026, 8, 16, tzinfo=UTC)
    published = now - timedelta(minutes=15)

    async def fake_google(client, keywords, *, observed_at):
        return AdapterResult(
            source="google-news-rss",
            available=True,
            results=(
                BreakingNewsItem(
                    source="google-news-rss",
                    candidate_id="google-control",
                    title="AI 신제품 공개",
                    extra_text="",
                    published_at=published,
                    source_url="https://news.google.com/control",
                ),
            ),
        )

    async def fake_yonhap(client, *, observed_at):
        return AdapterResult(
            source="yonhap-rss",
            available=True,
            results=(
                BreakingNewsItem(
                    source="yonhap-rss",
                    candidate_id="yonhap-allowed",
                    title="신기술 공개 속보",
                    extra_text="",
                    published_at=published,
                    source_url="https://www.yna.co.kr/view/allowed",
                    summary="(서울=연합뉴스) 테스트 요약 문장",
                ),
                BreakingNewsItem(
                    source="yonhap-rss",
                    candidate_id="yonhap-blocked",
                    title="국회 새 법안 논의",
                    extra_text="",
                    published_at=published,
                    source_url="https://www.yna.co.kr/view/blocked",
                ),
            ),
        )

    class FakeKma:
        async def collect(self, *, observed_at):
            return AdapterResult(
                source="kma-weather",
                available=True,
                results=(
                    BreakingNewsItem(
                        source="kma:getWthrWrnList",
                        candidate_id="kma-allowed",
                        title="[기상청 기상특보 목록] 서울 호우",
                        extra_text="operation=getWthrWrnList",
                        published_at=None,
                        summary="통보문 본문 예시",
                    ),
                ),
            )

    summary = await BreakingNewsObserver(
        None,
        google_fetcher=fake_google,
        yonhap_fetcher=fake_yonhap,
        kma_adapter=FakeKma(),
    ).observe(["AI"], observed_at=now)

    assert summary["verdicts"] == {"allow": 3, "block": 1}
    assert summary["product_candidate_count"] == 2
    assert summary["product_candidates"] == [
        {
            "id": "yonhap-allowed",
            "keyword": "신기술 공개 속보",
            "source": "yonhap-rss",
            "source_label": "연합뉴스",
            "source_url": "https://www.yna.co.kr/view/allowed",
            "summary": "(서울=연합뉴스) 테스트 요약 문장",
            "source_published_at": published.isoformat(),
        },
        {
            "id": "kma-allowed",
            "keyword": "[기상청 기상특보 목록] 서울 호우",
            "source": "kma:getWthrWrnList",
            "source_label": "기상청",
            "source_url": "",
            "summary": "통보문 본문 예시",
            "source_published_at": None,
        },
    ]
    assert all("detection_delay_minutes" not in item for item in summary["product_candidates"])


@pytest.mark.asyncio
async def test_radar_appends_unscored_breaking_lane_without_changing_legacy_ids():
    published = datetime.now(UTC) - timedelta(minutes=15)

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
                        {"title": "AI 신제품 반응", "url": "https://two.example/ai", "source": "두뉴스"},
                    ],
                },
            )
        ]

    async def x_fetcher(session, country, limit):
        return []

    class FakeObserver:
        async def observe(self, keywords, *, observed_at):
            return {
                "enabled": True,
                "available": True,
                "sources": {},
                "product_candidates": [
                    {
                        "id": "yonhap-live",
                        "keyword": "연합뉴스 직접 속보",
                        "source": "yonhap-rss",
                        "source_url": "https://www.yna.co.kr/view/live",
                        "source_published_at": published.isoformat(),
                    },
                    {
                        "id": "kma-unknown-time",
                        "keyword": "[기상청 현재 특보 현황] 서울",
                        "source": "kma:getPwnStatus",
                        "source_url": "",
                        "source_published_at": None,
                    },
                ],
            }

    baseline = await XOpportunityRadar(google_fetcher, x_fetcher, news_fetcher=None).refresh(limit=10)
    measured = await XOpportunityRadar(
        google_fetcher,
        x_fetcher,
        news_fetcher=None,
        breaking_news_observer=FakeObserver(),
    ).refresh(limit=10)

    baseline_ids = [item["id"] for item in baseline["items"]]
    legacy_ids = [item["id"] for item in measured["items"] if item["lane"] != "속보·공적발표"]
    assert legacy_ids == baseline_ids
    breaking_items = [item for item in measured["items"] if item["lane"] == "속보·공적발표"]
    assert [item["id"] for item in breaking_items] == ["yonhap-live", "kma-unknown-time"]
    assert measured["breaking_news_count"] == 2
    assert "product_candidates" not in measured["breaking_news_observation"]

    yonhap, kma = breaking_items
    assert yonhap["source_published_at"] == published.isoformat()
    assert 14.9 <= yonhap["detection_delay_minutes"] <= 15.1
    assert yonhap["age_basis"] == "source_published_at"
    assert yonhap["age_minutes"] == 15
    assert yonhap["source_url"] == "https://www.yna.co.kr/view/live"
    assert "x_exposure_score" not in yonhap
    assert "opportunity_score" not in yonhap
    assert kma["source_published_at"] is None
    assert kma["detection_delay_minutes"] is None
    assert kma["age_minutes"] is None
    assert kma["age_basis"] == "unknown"
    assert kma["age_display"] == "미상"


def test_route_marks_unknown_age_explicitly_without_mutating_snapshot():
    snapshot = {
        "items": [
            {"id": "known", "age_minutes": 12, "age_basis": "first_seen_at"},
            {"id": "unknown", "age_minutes": None},
        ]
    }

    response = _with_explicit_age(snapshot)

    assert response["items"][0]["age_display"] == "12분"
    assert response["items"][0]["age_basis"] == "first_seen_at"
    assert response["items"][1]["age_minutes"] is None
    assert response["items"][1]["age_basis"] == "unknown"
    assert response["items"][1]["age_display"] == "미상"
    assert "age_display" not in snapshot["items"][0]


def test_breaking_lane_limit_interleaves_sources_without_scoring():
    now = datetime(2026, 8, 16, tzinfo=UTC)
    raw = [
        {
            "id": f"yonhap-{index}",
            "keyword": f"연합뉴스 속보 {index}",
            "source": "yonhap-rss",
            "source_published_at": (now - timedelta(minutes=index + 1)).isoformat(),
        }
        for index in range(6)
    ]
    raw.append(
        {
            "id": "kma-0",
            "keyword": "기상청 특보",
            "source": "kma:getWthrWrnList",
            "source_published_at": (now - timedelta(minutes=3)).isoformat(),
        }
    )

    items = _breaking_lane_items(raw, now, limit=5)

    assert [item["id"] for item in items] == ["yonhap-0", "kma-0", "yonhap-1", "yonhap-2", "yonhap-3"]
    assert all("x_exposure_score" not in item and "opportunity_score" not in item for item in items)


def test_get_route_exposes_breaking_source_time_and_derived_delay(monkeypatch):
    class StubRadar:
        @staticmethod
        def snapshot():
            return {
                "items": [
                    {
                        "id": "breaking-route",
                        "keyword": "연합뉴스 직접 속보",
                        "lane": "속보·공적발표",
                        "age_minutes": 15,
                        "age_basis": "source_published_at",
                        "source_published_at": "2026-08-16T01:00:00+00:00",
                        "detection_delay_minutes": 15.0,
                    }
                ],
                "refreshed_at": "2026-08-16T01:15:00+00:00",
            }

    monkeypatch.setattr(x_radar_routes, "_radar", StubRadar())
    app = FastAPI()
    app.include_router(x_radar_routes.router)

    response = TestClient(app).get("/api/x-radar")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["lane"] == "속보·공적발표"
    assert item["source_published_at"] == "2026-08-16T01:00:00+00:00"
    assert item["detection_delay_minutes"] == 15.0
    assert item["age_basis"] == "source_published_at"
    assert item["age_display"] == "15분"


@pytest.mark.asyncio
async def test_radar_observer_without_product_candidates_only_exposes_source_health():
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
