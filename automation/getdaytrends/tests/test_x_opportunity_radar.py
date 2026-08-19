"""Tests for the live X source opportunity radar."""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models import RawTrend, TrendSource  # noqa: E402
import x_opportunity_radar as radar_module  # noqa: E402
from x_opportunity_radar import (  # noqa: E402
    XOpportunityRadar,
    _breaking_lane_items,
    _coherent_news_items,
    _daum_trend_items,
    _materiality_assessment,
    _news_ranking_items,
    _reddit_items,
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
    # 0072 실측: 신규 진입은 "new" 문자열이고 0은 변동 없음이다(0068의 «0=신규» 정정).
    assert data["items"][1]["rank_status_display"] == "순위 변동 없음"
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


# --- 0072: summary 통과·status 실물 부호화·언어 검사·health 원천 판정 ---


def test_breaking_lane_items_pass_summary_through_without_title_copy():
    now = datetime(2026, 8, 17, 9, 0, tzinfo=UTC)
    raw_candidates = [
        {
            "id": "yna-1",
            "keyword": "호우주의보 발표",
            "source": "yonhap-rss",
            "source_url": "https://www.yna.co.kr/a/1",
            "summary": "(춘천=연합뉴스) 기상청은 호우주의보를 발효한다고 밝혔다.",
            "source_published_at": "2026-08-17T08:50:00+00:00",
        },
        {"id": "kma-1", "keyword": "태풍 특보", "source": "kma:typ", "summary": ""},
        {"id": "yna-2", "keyword": "에볼라 확산", "source": "yonhap-rss"},
    ]

    items = _breaking_lane_items(raw_candidates, now, limit=10)

    assert [item["summary"] for item in items] == [
        "(춘천=연합뉴스) 기상청은 호우주의보를 발효한다고 밝혔다.",
        "",
        "",
    ]
    # 요약이 없다고 제목을 복사해 만들지 않는다(생성 금지 규칙).
    assert all(item["summary"] != item["keyword"] for item in items)
    assert [item["id"] for item in items] == ["yna-1", "kma-1", "yna-2"]


def test_daum_trend_items_recognize_new_string_and_label_zero_as_no_change():
    now = datetime(2026, 8, 17, 9, 40, tzinfo=UTC)
    raw_items = [
        {"keyword": "삼성전자 실명제 전환", "rank": 6, "display_rank": 3, "status": "new", "url": ""},
        {"keyword": "마르코 배정남 난투극", "rank": 1, "display_rank": 1, "status": 0, "url": ""},
        {"keyword": "인니 강진", "rank": 18, "display_rank": 8, "status": "-7", "url": ""},
        {"keyword": "상태 없음", "rank": 20, "display_rank": 9},
    ]

    items = _daum_trend_items(raw_items, now)

    # "new"는 문자열 그대로 신규 진입으로 인식한다(기존 isinstance(int)는 드롭했다).
    assert [item["keyword"] for item in items] == [
        "삼성전자 실명제 전환",
        "마르코 배정남 난투극",
        "인니 강진",
    ]
    assert items[0]["rank_status"] == "new"
    assert items[0]["rank_status_display"] == "신규 진입"
    assert items[1]["rank_status"] == 0
    assert items[1]["rank_status_display"] == "순위 변동 없음"
    assert items[2]["rank_status"] == -7
    assert items[2]["rank_status_display"] == "7계단 하락"


def test_coherent_news_items_blocks_foreign_language_crosscheck_and_keeps_korean():
    french_items = [
        {"title": "Elle est présidente du conseil", "url": "https://fr.example/1", "source": "Le Paper"},
        {"title": "Elle a annoncé sa démission", "url": "https://fr.example/2", "source": "Le Paper"},
        {"title": "Pour elle, la réponse est claire", "url": "https://fr.example/3", "source": "Le Paper"},
    ]

    # 0071 반증 재현: 한국어 트렌드 «elle»가 프랑스어 대명사에 매칭되던 것을 차단.
    assert _coherent_news_items("elle", french_items) == []
    # discovered_via 우대 경로(트렌드 첨부 원문)도 언어 검사를 통과해야 한다.
    attached_french = [{"title": "Elle est là", "url": "https://fr.example/4", "source": "Le Paper"}]
    assert _coherent_news_items("elle", attached_french) == []

    # 정상 한국어 매칭은 살아 있다.
    korean_items = [
        {"title": "엘르(elle) 커버 모델 발탁", "url": "https://kr.example/1", "source": "테스트뉴스"},
        {"title": "elle 협업 컬렉션 공개", "url": "https://kr.example/2", "source": "테스트경제"},
    ]
    assert _coherent_news_items("elle", korean_items) == korean_items


def test_materiality_no_longer_verifies_korean_trend_on_foreign_articles():
    candidate = {
        "keyword": "elle",
        "google": RawTrend(name="elle", source=TrendSource.GOOGLE_TRENDS, volume_numeric=5_000),
        "x": None,
        "x_rank": None,
        "age_minutes": 30,
    }
    french_items = [
        {
            "title": f"Elle est {word} dans la région",
            "url": f"https://fr.example/{index}",
            "source": f"Le Paper {index}",
            "discovered_via": "bing",
        }
        for index, word in enumerate(["présente", "annoncée", "attendue"], start=1)
    ]

    _, _, materiality_pass, gate_reason = _materiality_assessment(candidate, [], french_items, [])

    assert materiality_pass is False
    assert gate_reason == "주제 일치 원문·Threads 교차 근거 부족"


def test_news_ranking_items_carry_source_published_context_instead_of_unknown():
    now = datetime(2026, 8, 17, 9, 40, tzinfo=UTC)
    raw_items = [
        {
            "title": "주차비 10분에 1만원…식당 사장님, 8만원 받아내",
            "url": "https://news.nate.com/view/1",
            "source": "네이트 뉴스 랭킹",
            "publisher": "테스트신문",
            "rank": 8,
            "source_published_at": "2026-08-17T00:00:00+09:00",
            "first_seen_at": "2026-08-17T09:00:00+00:00",
        },
        {
            "title": "공중부양까지…테슬라 로드스터, 이번엔 뜰까",
            "url": "https://news.zum.com/view/2",
            "source": "줌 뉴스",
            "publisher": "테스트일보",
            "rank": 1,
        },
    ]

    items = _news_ranking_items(raw_items, now)

    first, second = items
    assert first["source_published_at"] == "2026-08-16T15:00:00+00:00"
    assert first["age_basis"] == "source_published_at"
    assert first["age_minutes"] == 1120
    assert first["age_display"] == "1120분"
    assert second["source_published_at"] is None
    assert second["age_basis"] == "unknown"
    assert second["age_display"] == "미상"


def test_daum_trend_items_carry_first_seen_age_not_list_updated_at():
    """0077: updatedAt은 목록 갱신 시각이라 발표 시각으로 안 쓰고 관측 시각으로 싣는다."""
    now = datetime(2026, 8, 17, 10, 0, tzinfo=UTC)
    list_updated = "2026-08-17T18:59:59.801+09:00"
    raw_items = [
        {
            "keyword": "이동하 소진 결혼",
            "rank": 1,
            "display_rank": 1,
            "status": -1,
            "url": "",
            "updated_at": list_updated,
            # 수집기는 updatedAt을 source_published_at으로 복제해 실어 온다(0073).
            "source_published_at": list_updated,
            "first_seen_at": "2026-08-17T09:30:00+00:00",
            "is_new": False,
        },
        {
            "keyword": "윤가이 장기하 연애",
            "rank": 2,
            "display_rank": 2,
            "status": 0,
            "url": "",
            "updated_at": list_updated,
            "source_published_at": list_updated,
            "first_seen_at": "2026-08-17T09:45:00+00:00",
            "is_new": True,
        },
        # first_seen_at 없는 주입 fetcher 입력 — 모르면 unknown이지 현재 시각으로 메우지 않는다.
        {"keyword": "에스파 콘서트 굿즈", "rank": 9, "display_rank": 3, "status": 1, "url": ""},
    ]

    items = _daum_trend_items(raw_items, now)

    first, second, third = items
    # 발표 시각을 주장하지 않는다 — 목록 갱신 시각은 발표 시각이 아니다(0077 판단).
    assert first["source_published_at"] is None
    assert first["first_seen_at"] == "2026-08-17T09:30:00+00:00"
    assert first["age_basis"] == "first_seen_at"
    assert first["age_minutes"] == 30
    assert first["age_display"] == "30분"
    assert first["is_new"] is False
    assert second["is_new"] is True
    assert second["age_basis"] == "first_seen_at"
    assert second["age_minutes"] == 15
    assert third["age_basis"] == "unknown"
    assert third["age_minutes"] is None
    assert third["age_display"] == "미상"
    assert third["first_seen_at"] is None
    # 목록 갱신 시각은 표시용 메타데이터로 그대로 남는다.
    assert all(item["updated_at"] == list_updated for item in items[:2])


def test_news_ranking_items_carry_rank_change_signals_without_scores():
    """0077: 수집기의 is_new·rank_change·status를 사실 그대로 싣는다(점수 환산 금지)."""
    now = datetime(2026, 8, 17, 10, 0, tzinfo=UTC)
    raw_items = [
        {
            "title": "주차비 10분에 1만원…식당 사장님, 8만원 받아내",
            "url": "https://news.nate.com/view/1",
            "source": "네이트 뉴스 랭킹",
            "publisher": "테스트신문",
            "rank": 8,
            "is_new": False,
            "rank_change": 3,
            "status": "+3",
        },
        {
            "title": "공중부양까지…테슬라 로드스터, 이번엔 뜰까",
            "url": "https://news.zum.com/view/2",
            "source": "줌 뉴스",
            "publisher": "테스트일보",
            "rank": 1,
            "is_new": True,
            "rank_change": None,
            "status": "new",
        },
    ]

    items = _news_ranking_items(raw_items, now)

    first, second = items
    assert first["is_new"] is False
    assert first["rank_change"] == 3
    assert first["rank_status"] == "+3"
    assert second["is_new"] is True
    assert second["rank_change"] is None
    assert second["rank_status"] == "new"
    # 사실 신호일 뿐 점수로 환산하지 않는다(0053).
    assert "materiality_score" not in first
    assert "x_exposure_score" not in first
    assert "opportunity_score" not in first


@pytest.mark.asyncio
async def test_radar_x_fallback_marks_health_false_and_reports_error(monkeypatch, tmp_path):
    async def google_fetcher(session, country, limit):
        return []

    async def fallback_x_fetcher(session, country, limit, force_refresh=False):
        # 실물 _fallback_trends() 모양: 이름 5개·빈 링크·_is_fallback 표식.
        return [
            RawTrend(
                name=name,
                source=TrendSource.GETDAYTRENDS,
                extra={"_is_fallback": True, "fallback_reason": "http_status_error"},
            )
            for name in ("주말 계획", "점심 메뉴", "날씨", "커피", "퇴근")
        ]

    monkeypatch.setattr(radar_module, "_async_fetch_getdaytrends", fallback_x_fetcher)
    radar = XOpportunityRadar(
        google_fetcher,
        fallback_x_fetcher,
        news_fetcher=None,
        observation_path=tmp_path / "x-fallback-observations.json",
    )

    data = await radar.refresh(limit=10)

    assert data["source_health"]["public_x_trends"] is False
    assert any("fallback" in error for error in data["errors"])
    assert data["items"] == []


@pytest.mark.asyncio
async def test_radar_x_markerless_production_items_do_not_count_as_healthy(monkeypatch):
    async def google_fetcher(session, country, limit):
        return []

    async def drifted_x_fetcher(session, country, limit, force_refresh=False):
        # 이름이 바뀐 fallback이 이름 필터를 뚫어도 원천 표식이 없으면 실패로 판정.
        return [
            RawTrend(
                name="우산 권장",
                source=TrendSource.GETDAYTRENDS,
                link="https://getdaytrends.com/korea/trend/umbrella/",
            )
        ]

    monkeypatch.setattr(radar_module, "_async_fetch_getdaytrends", drifted_x_fetcher)
    radar = XOpportunityRadar(google_fetcher, drifted_x_fetcher, news_fetcher=None)

    data = await radar.refresh(limit=10)

    assert data["source_health"]["public_x_trends"] is False
    assert any("표식" in error for error in data["errors"])


@pytest.mark.asyncio
async def test_radar_x_health_stays_true_for_source_sample_marker():
    async def google_fetcher(session, country, limit):
        return []

    async def x_fetcher(session, country, limit):
        return [
            RawTrend(
                name="운명의 포켓몬",
                source=TrendSource.GETDAYTRENDS,
                link="https://getdaytrends.com/korea/trend/fate/",
                extra={"_getdaytrends_sample_id": "korea:1786959468.24"},
            )
        ]

    data = await XOpportunityRadar(google_fetcher, x_fetcher, news_fetcher=None).refresh(limit=10)

    assert data["source_health"]["public_x_trends"] is True
    assert not any("표식" in error or "fallback" in error for error in data["errors"])


# --- 0079: Reddit 핫 포스트 수집기 연결 및 첨부/시각/언어 규약 검증 ---


def test_reddit_items_carry_subreddit_time_attachment_and_language():
    """0079: Reddit 항목은 시각(created_utc)·첨부 형태(video/image/text)·언어를 실어 보내며 점수화하지 않는다."""
    now = datetime(2026, 8, 18, 10, 0, tzinfo=UTC)
    raw_items = [
        {
            "id": "abc123",
            "title": "Dramatic school CCTV footage shows heroic rescue",
            "url": "https://v.redd.it/abc12345/DASH_720.mp4",
            "permalink": "/r/PublicFreakout/comments/abc123/dramatic_school_cctv/",
            "subreddit": "PublicFreakout",
            "author": "redditor1",
            "votes": 15420,
            "comments": 890,
            "source_published_at": "2026-08-18T09:30:00+00:00",
            "attachment_kind": "video",
            "video_url": "https://v.redd.it/abc12345/DASH_720.mp4",
            "language": "en",
            "is_korean": False,
        },
        {
            "id": "def456",
            "title": "한국 길거리 음식 반응 모음",
            "url": "https://i.redd.it/def45678.jpg",
            "permalink": "/r/mildlyinteresting/comments/def456/korean_street_food/",
            "subreddit": "mildlyinteresting",
            "author": "redditor2",
            "votes": 3400,
            "comments": 210,
            "source_published_at": None,
            "first_seen_at": "2026-08-18T09:45:00+00:00",
            "attachment_kind": "image",
            "video_url": "",
            "language": "ko",
            "is_korean": True,
        },
    ]

    items = _reddit_items(raw_items, now)

    assert len(items) == 2
    first, second = items[0], items[1]

    # 첫째: 비디오 첨부, 영문, 발표시각 기준 age
    assert first["id"] == "abc123"
    assert first["keyword"] == "Dramatic school CCTV footage shows heroic rescue"
    assert first["lane"] == "Reddit 핫 포스트"
    assert first["qualification_mode"] == "reddit_hot_post"
    assert first["subreddit"] == "PublicFreakout"
    assert first["source"] == "Reddit (r/PublicFreakout)"
    assert first["publisher"] == "r/PublicFreakout"
    assert first["attachment_kind"] == "video"
    assert first["video_url"] == "https://v.redd.it/abc12345/DASH_720.mp4"
    assert first["language"] == "en"
    assert first["is_korean"] is False
    assert first["votes"] == 15420
    assert first["comments"] == 890
    assert first["age_basis"] == "source_published_at"
    assert first["age_minutes"] == 30
    assert first["age_display"] == "30분"
    assert "materiality_score" not in first
    assert "x_exposure_score" not in first
    assert "opportunity_score" not in first

    # 둘째: 이미지 첨부, 국문, first_seen_at 기준 age
    assert second["id"] == "def456"
    assert second["attachment_kind"] == "image"
    assert second["video_url"] == ""
    assert second["language"] == "ko"
    assert second["is_korean"] is True
    assert second["age_basis"] == "first_seen_at"
    assert second["age_minutes"] == 15
    assert second["age_display"] == "15분"


@pytest.mark.asyncio
async def test_radar_reddit_lane_integration_preserves_existing_lanes():
    """0079: Reddit lane을 병기해도 기존 lane(다음, 랭킹, legacy) 항목의 id와 건수는 전혀 변하지 않는다."""
    async def google_fetcher(session, country, limit):
        return [
            RawTrend(
                name="AI 신제품",
                source=TrendSource.GOOGLE_TRENDS,
                volume="50000+",
                volume_numeric=50_000,
                link="https://trends.google.com/ai",
                published_at=datetime.now(UTC) - timedelta(minutes=20),
                extra={
                    "news_headlines": ["AI 신제품 공개"],
                    "news_items": [
                        {"title": "AI 신제품 공개", "url": "https://news.example.com/ai", "source": "테스트뉴스"}
                    ],
                },
            )
        ]

    async def x_fetcher(session, country, limit):
        return []

    async def daum_fetcher(session, limit):
        return (
            "2026-08-18T10:00:00+09:00",
            [
                {
                    "keyword": "다음 실시간 1위",
                    "rank": 1,
                    "display_rank": 1,
                    "status": "new",
                    "url": "https://search.daum.net/1",
                    "source": "다음 실시간 트렌드",
                    "first_seen_at": "2026-08-18T00:50:00+00:00",
                }
            ],
        )

    async def ranking_fetcher(session, limit):
        return [
            {
                "title": "뉴스 랭킹 1위 기사",
                "url": "https://news.nate.com/rank/1",
                "source": "네이트 뉴스 랭킹",
                "publisher": "테스트일보",
                "rank": 1,
                "first_seen_at": "2026-08-18T00:40:00+00:00",
            }
        ]

    async def reddit_fetcher(session, limit):
        return [
            {
                "id": "reddit_viral_1",
                "title": "Shocking viral video from intersection",
                "url": "https://v.redd.it/sample.mp4",
                "permalink": "/r/videos/comments/sample/",
                "subreddit": "videos",
                "author": "video_poster",
                "votes": 8500,
                "comments": 420,
                "source_published_at": "2026-08-18T00:30:00+00:00",
                "attachment_kind": "video",
                "video_url": "https://v.redd.it/sample.mp4",
                "language": "en",
                "is_korean": False,
            }
        ]

    # 1. Reddit 없는 기준선 radar
    baseline_radar = XOpportunityRadar(
        google_fetcher=google_fetcher,
        x_fetcher=x_fetcher,
        news_fetcher=None,
        news_ranking_fetcher=ranking_fetcher,
        daum_realtime_fetcher=daum_fetcher,
    )
    baseline_data = await baseline_radar.refresh(limit=10)

    # 2. Reddit 포함 radar
    reddit_radar = XOpportunityRadar(
        google_fetcher=google_fetcher,
        x_fetcher=x_fetcher,
        news_fetcher=None,
        news_ranking_fetcher=ranking_fetcher,
        daum_realtime_fetcher=daum_fetcher,
        reddit_fetcher=reddit_fetcher,
    )
    reddit_data = await reddit_radar.refresh(limit=10)

    # 기존 lane 건수 및 id 대조 검증: 기존 항목들은 한 글자도 변하지 않음
    baseline_items = baseline_data["items"]
    reddit_items = reddit_data["items"]

    assert len(reddit_items) == len(baseline_items) + 1
    assert [item["id"] for item in reddit_items[:len(baseline_items)]] == [item["id"] for item in baseline_items]
    assert [item["keyword"] for item in reddit_items[:len(baseline_items)]] == [item["keyword"] for item in baseline_items]

    # Reddit 항목 검증
    last_item = reddit_items[-1]
    assert last_item["id"] == "reddit_viral_1"
    assert last_item["lane"] == "Reddit 핫 포스트"
    assert last_item["attachment_kind"] == "video"
    assert last_item["video_url"] == "https://v.redd.it/sample.mp4"
    assert last_item["language"] == "en"
    assert last_item["votes"] == 8500
    assert last_item["comments"] == 420

    # Snapshot 상태 검증
    assert reddit_data["reddit_count"] == 1
    assert reddit_data["reddit_raw_count"] == 1
    assert reddit_data["source_health"]["reddit"] is True
    assert baseline_data["source_health"].get("reddit", False) is False


@pytest.mark.asyncio
async def test_radar_reddit_403_lands_in_errors_and_health_false():
    from collectors.reddit import RedditFetchError

    async def empty_google(session, country, limit):
        return []

    async def empty_x(session, country, limit):
        return []

    async def reddit_403(session, limit):
        raise RedditFetchError(403, "https://www.reddit.com/r/popular/hot.json")

    radar = XOpportunityRadar(
        google_fetcher=empty_google,
        x_fetcher=empty_x,
        news_fetcher=None,
        reddit_fetcher=reddit_403,
    )
    data = await radar.refresh(limit=5)
    assert data["source_health"]["reddit"] is False
    assert data["reddit_count"] == 0
    assert any("403" in err for err in data.get("errors") or [])

