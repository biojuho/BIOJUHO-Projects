"""Tests for the live X source opportunity radar."""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models import RawTrend, TrendSource  # noqa: E402
from x_opportunity_radar import XOpportunityRadar, _x_exposure_assessment  # noqa: E402


@pytest.mark.asyncio
async def test_radar_returns_direct_originals_without_generated_copy():
    async def google_fetcher(session, country, limit):
        return [
            RawTrend(
                name="AI 신제품",
                source=TrendSource.GOOGLE_TRENDS,
                volume="50000+",
                volume_numeric=50_000,
                link="https://trends.google.com/trending/rss?geo=KR",
                published_at=datetime.now(UTC) - timedelta(minutes=20),
                extra={
                    "news_headlines": ["AI 신제품 오늘 공개", "업계 반응 확산"],
                    "news_items": [
                        {"title": "AI 신제품 오늘 공개", "url": "https://news.example.com/ai", "source": "테스트뉴스"},
                        {"title": "업계 반응 확산", "url": "https://press.example.com/ai", "source": "테스트경제"},
                    ],
                },
            )
        ]

    async def x_fetcher(session, country, limit):
        return [
            RawTrend(
                name="AI 신제품",
                source=TrendSource.GETDAYTRENDS,
                link="https://getdaytrends.com/korea/trend/ai-product/",
            )
        ]

    data = await XOpportunityRadar(google_fetcher, x_fetcher, news_fetcher=None).refresh(limit=10)

    assert data["available"] is True
    item = data["items"][0]
    assert item["lane"] == "동시 폭발"
    assert item["source_url"] == "https://news.example.com/ai"
    assert item["news_items"][0] == {
        "title": "AI 신제품 오늘 공개",
        "url": "https://news.example.com/ai",
        "source": "테스트뉴스",
    }
    assert item["x_search_url"].startswith("https://x.com/search?")
    assert 0 <= item["x_exposure_score"] <= 100
    assert item["exposure_breakdown"]["cross_platform"] == 7
    assert item["exposure_signals"][0] == "주제 일치 원문 2/2건"
    assert item["score_version"] == "x-exposure-v3"
    assert item["exposure_confidence"] == "high"
    assert item["age_minutes"] is not None
    assert item["age_basis"] == "source_published_at"
    assert item["source_published_at"] is not None
    assert item["first_seen_at"] is not None
    assert "focus_match" not in item["exposure_breakdown"]
    assert "suggested_hook" not in item
    assert "recommended_format" not in item


def test_x_exposure_score_uses_continuous_time_decay_and_public_x_rank():
    now = datetime(2026, 8, 6, 0, 0, tzinfo=UTC)
    news_items = [
        {"title": "도심 정전 발생", "url": "https://one.example/power", "source": "원뉴스"},
        {"title": "도심 정전 복구 중", "url": "https://two.example/power", "source": "두뉴스"},
    ]
    base = {
        "keyword": "도심 정전",
        "google": RawTrend(
            name="도심 정전",
            source=TrendSource.GOOGLE_TRENDS,
            volume_numeric=1_000,
            extra={"news_headlines": ["도심 정전 발생"]},
        ),
        "x": None,
        "x_rank": None,
        "age_minutes": 30,
    }

    fresh_score, fresh_breakdown, _, _, _ = _x_exposure_assessment(base, news_items, [], now)
    old_score, old_breakdown, _, _, _ = _x_exposure_assessment(
        {**base, "age_minutes": 360}, news_items, [], now
    )
    x_score, x_breakdown, _, _, _ = _x_exposure_assessment(
        {**base, "x": RawTrend(name="도심 정전", source=TrendSource.GETDAYTRENDS), "x_rank": 0},
        news_items,
        [],
        now,
    )

    assert fresh_score > old_score
    assert fresh_breakdown["recency"] > old_breakdown["recency"]
    assert x_score > fresh_score
    assert x_breakdown["x_momentum"] == 20


def test_x_exposure_score_marks_unknown_time_low_confidence_and_rewards_observed_growth():
    now = datetime(2026, 8, 6, 0, 0, tzinfo=UTC)
    candidate = {
        "keyword": "도심 정전",
        "google": None,
        "x": RawTrend(name="도심 정전", source=TrendSource.GETDAYTRENDS),
        "x_rank": 4,
        "age_minutes": None,
    }
    news_items = [
        {"title": "도심 정전 발생", "url": "https://one.example/power", "source": "원뉴스"},
        {"title": "도심 정전 복구 중", "url": "https://two.example/power", "source": "두뉴스"},
    ]

    base_score, base_breakdown, _, confidence, coverage = _x_exposure_assessment(
        candidate, news_items, [], now
    )
    growth_score, growth_breakdown, signals, _, _ = _x_exposure_assessment(
        candidate,
        news_items,
        [],
        now,
        {
            "previous_observed_at": "2026-08-05T23:58:00+00:00",
            "new_originals": 2,
            "new_sources": 1,
            "x_rank_change": 2,
        },
    )

    assert base_breakdown["recency"] == 0
    assert confidence == "low"
    assert coverage == 0.75
    assert growth_score > base_score
    assert growth_breakdown["observed_growth"] == 10
    assert any("새 원문 +2" in signal for signal in signals)


@pytest.mark.asyncio
async def test_radar_drops_scraper_fallback_topics():
    async def google_fetcher(session, country, limit):
        return []

    async def x_fetcher(session, country, limit):
        return [RawTrend(name="날씨", source=TrendSource.GETDAYTRENDS)]

    data = await XOpportunityRadar(google_fetcher, x_fetcher, news_fetcher=None).refresh(limit=10)

    assert data["available"] is False
    assert data["items"] == []
    assert data["source_health"]["public_x_trends"] is False


@pytest.mark.asyncio
async def test_radar_filters_ranked_x_noise_without_context_sources():
    async def google_fetcher(session, country, limit):
        return []

    async def x_fetcher(session, country, limit):
        return [
            RawTrend(
                name="드림주들 모브",
                source=TrendSource.GETDAYTRENDS,
                link="https://getdaytrends.com/korea/trend/noise/",
            )
        ]

    data = await XOpportunityRadar(google_fetcher, x_fetcher, news_fetcher=None).refresh(limit=10)

    assert data["items"] == []
    assert data["total_candidates"] == 1
    assert data["filtered_out_count"] == 1
    assert data["filter_summary"] == {"주제 일치 원문·Threads 교차 근거 부족": 1}


@pytest.mark.asyncio
async def test_radar_promotes_repeated_top_x_phrase_to_low_context_native_lane(tmp_path):
    async def google_fetcher(session, country, limit):
        return []

    async def x_fetcher(session, country, limit):
        return [
            RawTrend(
                name="드림주들 모브",
                source=TrendSource.GETDAYTRENDS,
                link="https://getdaytrends.com/korea/trend/native-phrase/",
            )
        ]

    radar = XOpportunityRadar(
        google_fetcher,
        x_fetcher,
        news_fetcher=None,
        observation_path=tmp_path / "x-observations.json",
    )
    first = await radar.refresh(limit=10)
    second = await radar.refresh(limit=10)

    assert first["items"] == []
    assert len(second["items"]) == 1
    item = second["items"][0]
    assert item["lane"] == "X 네이티브 급등"
    assert item["qualification_mode"] == "x_native_history"
    assert item["context_level"] == "low"
    assert item["exposure_confidence"] == "low"
    assert item["age_minutes"] is not None
    assert item["age_basis"] == "first_seen_at"
    assert item["first_seen_at"] is not None
    assert item["source_published_at"] is None
    assert item["news_items"] == []
    assert item["source_url"] == "https://getdaytrends.com/korea/trend/native-phrase/"
    assert second["x_native_count"] == 1
    assert "suggested_hook" not in item
    assert "recommended_format" not in item


@pytest.mark.asyncio
async def test_radar_cache_sample_neither_promotes_nor_hides_verified_native_phrase(tmp_path):
    async def google_fetcher(session, country, limit):
        return []

    sample_id = "korea:1"

    async def x_fetcher(session, country, limit):
        return [
            RawTrend(
                name="캐시 확인 문구",
                source=TrendSource.GETDAYTRENDS,
                link="https://getdaytrends.com/korea/trend/cache-phrase/",
                extra={"_getdaytrends_sample_id": sample_id},
            )
        ]

    radar = XOpportunityRadar(
        google_fetcher,
        x_fetcher,
        news_fetcher=None,
        observation_path=tmp_path / "x-cache-observations.json",
    )
    first = await radar.refresh(limit=10)
    repeated = await radar.refresh(limit=10)
    sample_id = "korea:2"
    fresh = await radar.refresh(limit=10)
    replay = await radar.refresh(limit=10)

    assert first["items"] == []
    assert repeated["items"] == []
    assert len(fresh["items"]) == 1
    assert fresh["items"][0]["observation_delta"]["sample_advanced"] is True
    assert len(replay["items"]) == 1
    assert replay["items"][0]["observation_delta"]["sample_advanced"] is False
    assert "반복 관측에 미포함" in replay["items"][0]["exposure_signals"][1]


@pytest.mark.asyncio
async def test_radar_filters_publisher_name_when_article_titles_do_not_match_topic():
    async def google_fetcher(session, country, limit):
        return [
            RawTrend(
                name="테스트뉴스",
                source=TrendSource.GOOGLE_TRENDS,
                volume="5000+",
                volume_numeric=5_000,
                link="https://trends.google.com/publisher",
                extra={
                    "news_headlines": ["도심 정전 발생", "신제품 공개 현장"],
                    "news_items": [
                        {"title": "도심 정전 발생", "url": "https://one.example/a", "source": "테스트뉴스"},
                        {"title": "신제품 공개 현장", "url": "https://two.example/b", "source": "다른뉴스"},
                    ],
                },
            )
        ]

    async def x_fetcher(session, country, limit):
        return []

    data = await XOpportunityRadar(google_fetcher, x_fetcher, news_fetcher=None).refresh(limit=10)

    assert data["items"] == []
    assert data["filter_summary"] == {"주제와 원문 제목 불일치": 1}


@pytest.mark.asyncio
async def test_radar_qualifies_x_topic_when_threads_has_multiple_recent_authors():
    async def google_fetcher(session, country, limit):
        return []

    async def x_fetcher(session, country, limit):
        return [
            RawTrend(
                name="새로운 공개 기술",
                source=TrendSource.GETDAYTRENDS,
                link="https://getdaytrends.com/korea/trend/open-tech/",
            )
        ]

    class FakeThreadsCollector:
        available = True

        async def search(self, session, keyword, *, limit):
            return [
                {
                    "permalink": f"https://www.threads.com/@author{index}/post/{index}",
                    "username": f"author{index}",
                    "text": f"{keyword} 실제 논의 {index}",
                    "timestamp": "2026-08-05T09:00:00+0000",
                }
                for index in range(3)
            ]

    radar = XOpportunityRadar(google_fetcher, x_fetcher, FakeThreadsCollector(), news_fetcher=None)
    data = await radar.refresh(limit=10)

    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["materiality_pass"] is True
    assert item["threads_author_count"] == 3
    assert len(item["threads_posts"]) == 3
    assert "Threads" in item["sources"]
    assert item["source_url"].startswith("https://www.threads.com/")


@pytest.mark.asyncio
async def test_radar_excludes_requested_topics_before_materiality():
    async def google_fetcher(session, country, limit):
        return [
            RawTrend(
                name="마요르카 대 PSG",
                source=TrendSource.GOOGLE_TRENDS,
                volume="50000+",
                volume_numeric=50_000,
                link="https://trends.google.com/sports",
                extra={"news_headlines": ["마요르카 PSG 경기 결과"], "news_items": []},
            ),
            RawTrend(
                name="테스트기업 2분기 실적 발표",
                source=TrendSource.GOOGLE_TRENDS,
                volume="20000+",
                volume_numeric=20_000,
                link="https://trends.google.com/earnings",
                extra={"news_headlines": ["영업이익 컨센서스 상회"], "news_items": []},
            ),
            RawTrend(
                name="서울 아파트 실거래가",
                source=TrendSource.GOOGLE_TRENDS,
                link="https://trends.google.com/real-estate",
                extra={"news_headlines": ["아파트 매매가 상승"], "news_items": []},
            ),
            RawTrend(
                name="국회 새 법안",
                source=TrendSource.GOOGLE_TRENDS,
                link="https://trends.google.com/politics",
                extra={"news_headlines": ["여야 법안 처리 논의"], "news_items": []},
            ),
        ]

    async def x_fetcher(session, country, limit):
        return []

    data = await XOpportunityRadar(google_fetcher, x_fetcher, news_fetcher=None).refresh(limit=10)

    assert data["items"] == []
    assert data["filter_summary"] == {
        "스포츠 제외": 1,
        "증시·실적 제외": 1,
        "부동산 제외": 1,
        "정치 제외": 1,
    }


@pytest.mark.asyncio
async def test_radar_shadow_records_both_verdicts_without_product_or_request_changes():
    calls = {"google": 0, "x": 0}

    async def google_fetcher(session, country, limit):
        calls["google"] += 1
        return [
            RawTrend(
                name="AI 신제품",
                source=TrendSource.GOOGLE_TRENDS,
                volume="50000+",
                volume_numeric=50_000,
                link="https://trends.google.com/ai",
                published_at=datetime.now(UTC) - timedelta(minutes=10),
                extra={
                    "news_headlines": ["AI 신제품 공개", "AI 신제품 업계 반응"],
                    "news_items": [
                        {"title": "AI 신제품 공개", "url": "https://one.example/ai", "source": "원뉴스"},
                        {"title": "AI 신제품 업계 반응", "url": "https://two.example/ai", "source": "두뉴스"},
                    ],
                },
            ),
            RawTrend(
                name="국회 새 법안",
                source=TrendSource.GOOGLE_TRENDS,
                link="https://trends.google.com/politics",
                extra={"news_headlines": ["여야 법안 처리 논의"], "news_items": []},
            ),
        ]

    async def x_fetcher(session, country, limit):
        calls["x"] += 1
        return []

    class RecordingStore:
        def __init__(self):
            self.rows = []

        def record(self, **candidate):
            self.rows.append(candidate)
            return True

    class ExplodingStore:
        def record(self, **candidate):
            raise RuntimeError("forced shadow failure")

    def product_projection(data):
        return {
            "items": [(item["id"], item["keyword"]) for item in data["items"]],
            "total_candidates": data["total_candidates"],
            "filtered_out_count": data["filtered_out_count"],
            "filter_summary": data["filter_summary"],
        }

    baseline = await XOpportunityRadar(google_fetcher, x_fetcher, news_fetcher=None).refresh(limit=10)
    baseline_calls = dict(calls)
    calls.update(google=0, x=0)
    store = RecordingStore()
    measured = await XOpportunityRadar(
        google_fetcher,
        x_fetcher,
        news_fetcher=None,
        filter_shadow_store=store,
    ).refresh(limit=10)
    measured_calls = dict(calls)
    calls.update(google=0, x=0)
    failed = await XOpportunityRadar(
        google_fetcher,
        x_fetcher,
        news_fetcher=None,
        filter_shadow_store=ExplodingStore(),
    ).refresh(limit=10)

    assert product_projection(measured) == product_projection(baseline)
    assert product_projection(failed) == product_projection(baseline)
    assert baseline_calls == measured_calls == calls == {"google": 1, "x": 1}
    assert {(row["title"], row["filter_verdict"]) for row in store.rows} == {
        ("AI 신제품", "allow"),
        ("국회 새 법안", "block"),
    }


@pytest.mark.asyncio
async def test_radar_expands_timestamped_originals_and_marks_earliest_observed():
    async def google_fetcher(session, country, limit):
        return [
            RawTrend(
                name="도심 정전",
                source=TrendSource.GOOGLE_TRENDS,
                volume="50000+",
                volume_numeric=50_000,
                link="https://trends.google.com/power",
                published_at=datetime.now(UTC) - timedelta(minutes=10),
                extra={
                    "news_headlines": ["도심 정전 발생"],
                    "news_items": [
                        {"title": "도심 정전 발생", "url": "https://one.example/power", "source": "원뉴스"}
                    ],
                },
            )
        ]

    async def x_fetcher(session, country, limit):
        return []

    async def news_fetcher(session, keyword, limit):
        return [
            {
                "title": "도심 정전 현장",
                "url": "https://two.example/power",
                "source": "두뉴스",
                "published_at": "2026-08-05T23:05:00+00:00",
                "discovered_via": "test",
            },
            {
                "title": "도심 정전 최초 확인",
                "url": "https://three.example/power",
                "source": "세뉴스",
                "published_at": "2026-08-05T22:55:00+00:00",
                "discovered_via": "test",
            },
        ]

    data = await XOpportunityRadar(
        google_fetcher,
        x_fetcher,
        news_fetcher=news_fetcher,
    ).refresh(limit=10)

    item = data["items"][0]
    assert len(item["news_items"]) == 3
    assert item["first_report"]["source"] == "세뉴스"
    assert item["first_report"]["first_report_scope"] == "수집 원문 중 최초"
    assert "urgency" not in item
