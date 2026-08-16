"""Tests for the live X source opportunity radar."""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models import RawTrend, TrendSource  # noqa: E402
from x_opportunity_radar import (  # noqa: E402
    XOpportunityRadar,
    _spam_trend_reason,
    _x_exposure_assessment,
)


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
    old_score, old_breakdown, _, _, _ = _x_exposure_assessment({**base, "age_minutes": 360}, news_items, [], now)
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

    base_score, base_breakdown, _, confidence, coverage = _x_exposure_assessment(candidate, news_items, [], now)
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
async def test_radar_demotes_repeated_contextless_x_phrase_to_observed_only(tmp_path):
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
    assert second["items"] == []
    assert second["x_native_count"] == 0
    assert second["observed_only_count"] == 1
    observed = second["observed_only_items"][0]
    assert observed["keyword"] == "드림주들 모브"
    assert observed["context_level"] == "low"
    assert observed["news_headlines"] == []
    assert observed["first_report"] is None
    assert observed["x_rank"] == 0
    assert observed["spam_likely_reason"] is None
    assert observed["trend_url"] == "https://getdaytrends.com/korea/trend/native-phrase/"


@pytest.mark.asyncio
async def test_radar_cache_sample_replay_demotes_contextless_phrase_to_observed_only(tmp_path):
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
    assert fresh["items"] == []
    assert fresh["observed_only_count"] == 1
    assert fresh["observed_only_items"][0]["keyword"] == "캐시 확인 문구"
    assert replay["items"] == []
    assert replay["observed_only_count"] == 1
    assert replay["observed_only_items"][0]["keyword"] == "캐시 확인 문구"


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
                    "news_items": [{"title": "도심 정전 발생", "url": "https://one.example/power", "source": "원뉴스"}],
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


def test_spam_trend_reason_matches_measured_samples_and_spares_non_spam():
    flagged = [
        "빠른이동 연락",
        "라인 qq750",
        "전국 출장 만남 진행중",
        "무직자대출 진행",
        "후불 유심",
    ]
    for keyword in flagged:
        assert _spam_trend_reason(keyword), f"스팸으로 판정돼야 함: {keyword!r}"
    spared = [
        "군인 가능",
        "오하욘사",
        "테슬라 로드스터",
        "대출 금리",
        "온라인 게임",
        "카톡 대화",
        "라인프렌즈",
    ]
    for keyword in spared:
        assert _spam_trend_reason(keyword) is None, f"오탐이면 안 됨: {keyword!r}"


@pytest.mark.asyncio
async def test_radar_news_ranking_items_keep_rank_order_and_carry_title_link_source():
    async def google_fetcher(session, country, limit):
        return []

    async def x_fetcher(session, country, limit):
        return []

    async def ranking_fetcher(session, limit):
        return [
            {
                "title": "주차비 10분에 1만원…식당 사장님, 8만원 받아내",
                "url": "https://news.example.com/parking",
                "source": "네이트 뉴스 랭킹",
                "publisher": "테스트신문",
                "rank": 8,
            },
            {
                "title": "공중부양까지…테슬라 로드스터, 이번엔 뜰까",
                "url": "https://news.example.com/roadster",
                "source": "줌 뉴스",
                "publisher": "테스트일보",
                "rank": 1,
            },
        ]

    data = await XOpportunityRadar(
        google_fetcher,
        x_fetcher,
        news_fetcher=None,
        news_ranking_fetcher=ranking_fetcher,
    ).refresh(limit=10)

    assert data["news_ranking_count"] == 2
    items = data["items"]
    assert [item["keyword"] for item in items] == [
        "주차비 10분에 1만원…식당 사장님, 8만원 받아내",
        "공중부양까지…테슬라 로드스터, 이번엔 뜰까",
    ]
    first = items[0]
    assert first["lane"] == "뉴스 랭킹"
    assert first["qualification_mode"] == "news_ranking"
    assert first["source"] == "네이트 뉴스 랭킹"
    assert first["publisher"] == "테스트신문"
    assert first["rank"] == 8
    assert first["source_url"] == "https://news.example.com/parking"
    assert first["news_headlines"] == ["주차비 10분에 1만원…식당 사장님, 8만원 받아내"]
    assert first["news_items"] == [
        {
            "title": "주차비 10분에 1만원…식당 사장님, 8만원 받아내",
            "url": "https://news.example.com/parking",
            "source": "테스트신문",
        }
    ]
    assert first["x_signal_keywords"] == []
    assert "materiality_score" not in first
    assert "opportunity_score" not in first
    assert "x_exposure_score" not in first


@pytest.mark.asyncio
async def test_radar_daum_trend_items_lead_and_carry_rank_status_without_scores():
    async def google_fetcher(session, country, limit):
        return []

    async def x_fetcher(session, country, limit):
        return []

    async def daum_fetcher(session, limit):
        return (
            "2026-08-16T17:30:01.801+09:00",
            [
                {
                    "keyword": "이동하 소진 결혼",
                    "rank": 2,
                    "display_rank": 1,
                    "status": -1,
                    "url": "https://search.daum.net/search?q=%EC%9D%B4%EB%8F%99%ED%95%98",
                    "source": "다음 실시간 트렌드",
                    "updated_at": "2026-08-16T17:30:01.801+09:00",
                },
                {
                    "keyword": "윤가이 장기하 연애",
                    "rank": 6,
                    "display_rank": 2,
                    "status": 0,
                    "url": "https://search.daum.net/search?q=%EA%B9%80%ED%83%9C%ED%98%B8",
                    "source": "다음 실시간 트렌드",
                    "updated_at": "2026-08-16T17:30:01.801+09:00",
                },
                {
                    "keyword": "김태호 개헌 논의",
                    "rank": 9,
                    "display_rank": 3,
                    "status": 1,
                    "url": "https://search.daum.net/search?q=%EA%B9%80%ED%83%9C%ED%98%B8",
                    "source": "다음 실시간 트렌드",
                    "updated_at": "2026-08-16T17:30:01.801+09:00",
                },
            ],
        )

    data = await XOpportunityRadar(
        google_fetcher,
        x_fetcher,
        news_fetcher=None,
        daum_realtime_fetcher=daum_fetcher,
    ).refresh(limit=10)

    assert data["daum_trend_count"] == 2
    assert data["daum_raw_count"] == 3
    assert data["daum_trend_filter_summary"] == {"정치 제외": 1}
    assert data["daum_updated_at"] == "2026-08-16T17:30:01.801+09:00"
    assert data["items"][0]["keyword"] == "이동하 소진 결혼"
    assert data["items"][0]["lane"] == "다음 실시간 트렌드"
    assert data["items"][0]["qualification_mode"] == "daum_realtime_trend"
    assert data["items"][0]["context_level"] == "source_direct"
    assert data["items"][0]["rank"] == 1
    assert data["items"][0]["rank_status"] == -1
    assert data["items"][0]["rank_status_display"] == "1계단 하락"
    assert data["items"][1]["keyword"] == "윤가이 장기하 연애"
    assert data["items"][1]["rank_status"] == 0
    assert data["items"][1]["rank_status_display"] == "신규 진입"
    assert "materiality_score" not in data["items"][0]
    assert "x_exposure_score" not in data["items"][0]


@pytest.mark.asyncio
async def test_radar_attaches_matching_x_word_and_demotes_unmatched():
    async def google_fetcher(session, country, limit):
        return []

    async def x_fetcher(session, country, limit):
        return [
            RawTrend(
                name="테슬라 로드스터",
                source=TrendSource.GETDAYTRENDS,
                link="https://getdaytrends.com/korea/trend/roadster/",
            ),
            RawTrend(
                name="군인 가능",
                source=TrendSource.GETDAYTRENDS,
                link="https://getdaytrends.com/korea/trend/soldier/",
            ),
        ]

    async def ranking_fetcher(session, limit):
        return [
            {
                "title": "공중부양까지…테슬라 로드스터, 이번엔 뜰까",
                "url": "https://news.example.com/roadster",
                "source": "줌 뉴스",
                "publisher": "테스트일보",
                "rank": 1,
            }
        ]

    radar = XOpportunityRadar(
        google_fetcher,
        x_fetcher,
        news_fetcher=None,
        news_ranking_fetcher=ranking_fetcher,
        observation_path=None,
    )
    first = await radar.refresh(limit=10)
    second = await radar.refresh(limit=10)

    assert [item["keyword"] for item in second["items"]] == ["공중부양까지…테슬라 로드스터, 이번엔 뜰까"]
    item = second["items"][0]
    assert item["x_signal_keywords"] == [{"keyword": "테슬라 로드스터", "x_rank": 0}]
    assert "공개 X 트렌드" in item["sources"]
    assert any("X에서도 뜨고 있음" in reason for reason in item["reasons"])
    assert item["x_search_url"].startswith("https://x.com/search?q=")
    observed = second["observed_only_items"]
    assert [entry["keyword"] for entry in observed] == ["군인 가능"]
    assert observed[0]["x_rank"] == 1
    assert observed[0]["spam_likely_reason"] is None
    assert [item["keyword"] for item in first["items"]] == ["공중부양까지…테슬라 로드스터, 이번엔 뜰까"]
    assert second["filtered_out_count"] == 1
    assert second["filter_summary"] == {"맥락 없음 관측만 강등": 1}


@pytest.mark.asyncio
async def test_radar_spam_x_words_never_become_candidates_and_are_flagged_only():
    async def google_fetcher(session, country, limit):
        return []

    async def x_fetcher(session, country, limit):
        return [
            RawTrend(
                name="라인 qq750",
                source=TrendSource.GETDAYTRENDS,
                link="https://getdaytrends.com/korea/trend/spam/",
            ),
            RawTrend(
                name="군인 가능",
                source=TrendSource.GETDAYTRENDS,
                link="https://getdaytrends.com/korea/trend/soldier/",
            ),
        ]

    radar = XOpportunityRadar(
        google_fetcher,
        x_fetcher,
        news_fetcher=None,
        observation_path=None,
    )
    first = await radar.refresh(limit=10)
    second = await radar.refresh(limit=10)

    assert first["items"] == []
    assert second["items"] == []
    assert second["spam_flagged_count"] == 1
    assert second["spam_flagged_items"] == [
        {"keyword": "라인 qq750", "x_rank": 0, "reason": second["spam_flagged_items"][0]["reason"]}
    ]
    assert second["spam_flagged_items"][0]["reason"].startswith("스팸·불법광고 패턴")
    observed = {entry["keyword"]: entry for entry in second["observed_only_items"]}
    assert set(observed) == {"라인 qq750", "군인 가능"}
    assert observed["라인 qq750"]["spam_likely_reason"].startswith("스팸·불법광고 패턴")
    assert observed["군인 가능"]["spam_likely_reason"] is None
