"""Tests for the direct-community early viral collector."""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fast_viral_collector as fast_module  # noqa: E402
import dashboard_routes_fast_viral as fast_routes  # noqa: E402
from fast_viral_collector import (  # noqa: E402
    FastViralCollector,
    _annotate_community_clusters,
    _apply_og_second_pass,
    _collapse_community_clusters,
    _community_titles_match,
    _community_x_exposure_assessment,
    _cooling_signal,
    _direct_max_age_minutes,
    _direct_signal_score,
    _is_brand_safe_title,
    _is_recent_issuelink_item,
    _issuelink_age_minutes,
    _looks_blocked,
    _og_context_gate,
    _parse_count,
    _select_diverse_community_items,
    _select_unique_community_items,
    _unique_community_cluster_count,
    _velocity_score,
    aggregator_quota,
    parse_fmkorea_latest,
    parse_issuelink_community_items,
    parse_issuelink_fmkorea_ids,
    parse_issuelink_fmkorea_items,
    passes_spread_gate,
)
from og_enrich import OgEnrichmentReport, OgRequestEvent  # noqa: E402
from source_backoff import SourceBackoff  # noqa: E402


def test_parse_fmkorea_latest_preserves_direct_metrics_and_url():
    html = """
    <table class="bd_lst"><tbody>
      <tr class="notice"><td>공지</td></tr>
      <tr>
        <td class="cate">유머</td>
        <td class="title"><a href="/123456789">지금 빠르게 퍼지는 새 소식</a><a class="replyNum">3</a></td>
        <td class="author">작성자</td><td class="time">12:00</td>
        <td class="m_no">1,250</td><td class="m_no m_no_voted">7</td>
      </tr>
    </tbody></table>
    """
    now = datetime(2026, 8, 5, 3, 5, tzinfo=UTC)

    items = parse_fmkorea_latest(html, now=now)

    assert items == [
        {
            "id": "123456789",
            "title": "지금 빠르게 퍼지는 새 소식",
            "category": "유머",
            "source_url": "https://www.fmkorea.com/123456789",
            "published_label": "12:00",
            "age_minutes": 5,
            "views": 1250,
            "votes": 7,
            "comments": 3,
        }
    ]


def test_parse_issuelink_ids_and_brand_safety_gate():
    html = """
    <a href="https://www.issuelink.co.kr/community/go/fmkorea/123456789">이미 노출된 글</a>
    <a href="https://www.issuelink.co.kr/community/go/theqoo/999">다른 출처</a>
    """

    assert parse_issuelink_fmkorea_ids(html) == {"123456789"}
    assert _is_brand_safe_title("태풍 발생 위치와 현재 상황") is True
    assert _is_brand_safe_title("ㅇㅎ) 후방 사진") is False


def test_parse_issuelink_items_provides_direct_fmkorea_fallback():
    html = """
    <table><tr><td>
      <a href="https://www.issuelink.co.kr/community/go/fmkorea/123456789">
        지금 여러 곳에서 퍼지는 새 소식 <small>[12]</small>
      </a>
      <div class="second_date"><span>펨코</span><span>(2 시간, 7 분전)</span></div>
    </td></tr></table>
    <a href="https://www.issuelink.co.kr/community/go/fmkorea/123456789">중복</a>
    """

    assert parse_issuelink_fmkorea_items(html) == [
        {
            "id": "123456789",
            "title": "지금 여러 곳에서 퍼지는 새 소식",
            "category": "IssueLink 백업",
            "source_url": "https://www.fmkorea.com/123456789",
            "published_label": "(2 시간, 7 분전)",
            "age_minutes": 127,
            "views": 0,
            "votes": 0,
            "comments": 12,
        }
    ]


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("방금 전", 0),
        ("(32 분전)", 32),
        ("(2 시간전)", 120),
        ("(2 시간, 56 분전)", 176),
        ("(1 일, 2 시간, 3 분전)", 1563),
        ("날짜 미확인", None),
    ],
)
def test_issuelink_relative_age_parser(label, expected):
    assert _issuelink_age_minutes(label) == expected


def test_issuelink_age_gate_keeps_180_minutes_and_rejects_older_or_unknown():
    assert _is_recent_issuelink_item({"age_minutes": 179}) is True
    assert _is_recent_issuelink_item({"age_minutes": 180}) is True
    assert _is_recent_issuelink_item({"age_minutes": 181}) is False
    assert _is_recent_issuelink_item({"age_minutes": None}) is False


def test_velocity_score_rewards_fresh_pre_aggregator_growth():
    score, rate = _velocity_score(
        age_minutes=4,
        views=800,
        comments=5,
        votes=2,
        delta_views_per_minute=120,
        before_issuelink=True,
    )

    assert score >= 70
    assert rate == 200
    assert _parse_count("1.2만") == 12_000


def test_direct_age_window_defaults_to_120_minutes_but_keeps_env_override(monkeypatch):
    monkeypatch.delenv("GETDAYTRENDS_DIRECT_MAX_AGE_MINUTES", raising=False)
    assert _direct_max_age_minutes() == 120

    monkeypatch.setenv("GETDAYTRENDS_DIRECT_MAX_AGE_MINUTES", "360")
    assert _direct_max_age_minutes() == 360


def test_cooling_signal_observes_four_required_series_shapes():
    start = datetime(2026, 8, 10, 0, 0, tzinfo=UTC)

    def points(values, *, field="comments"):
        return [
            {"observed_at": (start + timedelta(minutes=index * 10)).isoformat(), field: value}
            for index, value in enumerate(values)
        ]

    growing = _cooling_signal(
        points([1, 2, 3], field="mentions"),
        now=start + timedelta(minutes=20),
        current_views=100,
        current_comments=0,
    )
    stalled = _cooling_signal(
        points([1, 4, 4, 4]),
        now=start + timedelta(minutes=30),
        current_views=100,
        current_comments=4,
    )
    sparse = _cooling_signal(
        points([1, 2]),
        now=start + timedelta(minutes=10),
        current_views=100,
        current_comments=2,
    )
    no_metrics = _cooling_signal(
        points([0, 0, 0]),
        now=start + timedelta(minutes=20),
        current_views=0,
        current_comments=0,
    )

    assert growing == {"cooling": False, "last_growth_minutes": 0}
    assert stalled == {"cooling": True, "last_growth_minutes": 20}
    assert sparse == {"cooling": None, "last_growth_minutes": None}
    assert no_metrics == {"cooling": None, "last_growth_minutes": None}


@pytest.mark.asyncio
async def test_og_second_pass_only_reads_weak_final_candidates_and_never_stores_text():
    weak_url = "https://www.dogdrip.net/dogdrip/123"
    strong_url = "https://www.dogdrip.net/dogdrip/456"
    items = [
        {
            "title": "결혼식에서 있었던 이야기",
            "source_url": weak_url,
            "link_kind": "publisher_original",
            "community_source": "dogdrip",
        },
        {
            "title": "팀장이 회식비를 떠넘김",
            "source_url": strong_url,
            "link_kind": "publisher_original",
            "community_source": "dogdrip",
        },
    ]

    async def fake_fetcher(urls, **kwargs):
        assert list(urls) == [weak_url]
        return OgEnrichmentReport(
            descriptions={weak_url: "남편이 축의금을 몰래 가로채고 거짓말했다"},
            events=[OgRequestEvent(host="www.dogdrip.net", status=200, outcome="enriched")],
        )

    summary = await _apply_og_second_pass(
        items,
        source_backoff=SourceBackoff(),
        fetcher=fake_fetcher,
        checked_at=datetime(2026, 8, 31, 3, 31, 23, tzinfo=UTC),
    )

    assert items[0]["kernel_screen"]["axis"] == "live_wrong"
    assert items[1]["kernel_screen"]["axis"] == "live_wrong"
    assert items[0]["original_context_verified"] is True
    assert items[0]["context_basis"] == "og_substantive"
    assert items[0]["context_checked_at"] == "2026-08-31T03:31:23+00:00"
    assert items[1]["original_context_verified"] is False
    assert items[1]["context_basis"] == "og_not_requested"
    assert "context_checked_at" not in items[1]
    assert all("description" not in key for item in items for key in item)
    assert all("summary" not in item and "context" not in item for item in items)
    assert summary["requested_count"] == 1
    assert summary["enriched_count"] == 1
    assert summary["context_gate"] == {
        "min_chars": 20,
        "candidate_count": 1,
        "evaluated_count": 1,
        "passed_count": 1,
        "pass_ratio": 1.0,
        "rejection_counts": {},
    }
    assert "축의금" not in repr(summary)


@pytest.mark.asyncio
async def test_og_second_pass_fails_closed_when_original_context_was_not_read():
    url = "https://www.dogdrip.net/dogdrip/789"
    items = [
        {
            "title": "결혼식에서 있었던 이야기",
            "source_url": url,
            "link_kind": "publisher_original",
            "community_source": "dogdrip",
            # A stale/injected value must not survive a failed verification.
            "original_context_verified": True,
            "context_basis": "untrusted",
            "context_checked_at": "2026-01-01T00:00:00+00:00",
        }
    ]

    async def fake_fetcher(urls, **kwargs):
        assert list(urls) == [url]
        return OgEnrichmentReport(
            events=[OgRequestEvent(host="www.dogdrip.net", status=200, outcome="missing_og")]
        )

    await _apply_og_second_pass(
        items,
        source_backoff=SourceBackoff(),
        fetcher=fake_fetcher,
        checked_at=datetime(2026, 8, 31, 3, 31, 23, tzinfo=UTC),
    )

    assert items[0]["original_context_verified"] is False
    assert items[0]["context_basis"] == "og_missing"
    assert "context_checked_at" not in items[0]
    assert "summary" not in items[0]
    assert "context" not in items[0]


def test_og_context_gate_rejects_boilerplate_echo_and_short_but_keeps_real_context():
    cases = [
        (
            "결혼식에서 있었던 이야기",
            "이 콘텐츠는 저작권법의 보호를 받으며 무단전재 및 재배포 금지입니다. 콘텐츠 제공 안내",
            (False, "og_boilerplate"),
        ),
        (
            "일본인 여친과 동거하며 겪은 실제 생활비와 문화 차이 후기",
            "일본인 여친과 동거하며 겪은 실제 생활비와 문화 차이 후기",
            (False, "og_echoes_title"),
        ),
        (
            "결혼식에서 있었던 이야기",
            "남편의 일",
            (False, "og_too_short"),
        ),
        (
            "결혼식에서 있었던 이야기",
            "남편이 가족 몰래 축의금을 가로채고 뒤늦게 거짓말한 실제 사연",
            (True, "og_substantive"),
        ),
    ]

    for title, description, expected in cases:
        accepted, basis, measured_chars = _og_context_gate(title, description)
        assert (accepted, basis) == expected
        assert measured_chars == len(description)


@pytest.mark.asyncio
async def test_og_second_pass_records_all_gate_reasons_and_does_not_use_rejected_text(
    monkeypatch, tmp_path
):
    urls = {
        "missing": "https://www.dogdrip.net/dogdrip/missing",
        "boilerplate": "https://www.dogdrip.net/dogdrip/boilerplate",
        "echo": "https://www.dogdrip.net/dogdrip/echo",
        "short": "https://www.dogdrip.net/dogdrip/short",
        "substantive": "https://www.dogdrip.net/dogdrip/substantive",
    }
    items = [
        {
            "title": "결혼식에서 있었던 이야기",
            "source_url": urls["missing"],
            "link_kind": "publisher_original",
            "community_source": "dogdrip",
        },
        {
            "title": "결혼식에서 있었던 이야기",
            "source_url": urls["boilerplate"],
            "link_kind": "publisher_original",
            "community_source": "dogdrip",
        },
        {
            "title": "일본인 여친과 동거하며 겪은 실제 생활비와 문화 차이 후기",
            "source_url": urls["echo"],
            "link_kind": "publisher_original",
            "community_source": "dogdrip",
        },
        {
            "title": "결혼식에서 있었던 이야기",
            "source_url": urls["short"],
            "link_kind": "publisher_original",
            "community_source": "dogdrip",
        },
        {
            "title": "결혼식에서 있었던 이야기",
            "source_url": urls["substantive"],
            "link_kind": "publisher_original",
            "community_source": "dogdrip",
        },
    ]

    async def fake_fetcher(requested_urls, **kwargs):
        assert list(requested_urls) == list(urls.values())
        return OgEnrichmentReport(
            descriptions={
                urls["boilerplate"]: "이 콘텐츠는 저작권법의 보호를 받으며 무단전재 및 재배포 금지입니다. 콘텐츠 제공 안내",
                urls["echo"]: "일본인 여친과 동거하며 겪은 실제 생활비와 문화 차이 후기",
                urls["short"]: "남편의 일",
                urls["substantive"]: "남편이 가족 몰래 축의금을 가로채고 뒤늦게 거짓말한 실제 사연",
            },
            events=[OgRequestEvent(host="www.dogdrip.net", status=200, outcome="enriched")],
        )

    summary = await _apply_og_second_pass(
        items,
        source_backoff=SourceBackoff(),
        fetcher=fake_fetcher,
        checked_at=datetime(2026, 8, 31, 3, 31, 23, tzinfo=UTC),
    )

    assert [item["context_basis"] for item in items] == [
        "og_missing",
        "og_boilerplate",
        "og_echoes_title",
        "og_too_short",
        "og_substantive",
    ]
    assert [item["original_context_verified"] for item in items] == [False, False, False, False, True]
    assert items[4]["context_checked_at"] == "2026-08-31T03:31:23+00:00"
    assert all("summary" not in item and "description" not in item for item in items)
    assert summary["context_gate"] == {
        "min_chars": 20,
        "candidate_count": 5,
        "evaluated_count": 4,
        "passed_count": 1,
        "pass_ratio": 1 / 4,
        "rejection_counts": {
            "og_missing": 1,
            "og_boilerplate": 1,
            "og_echoes_title": 1,
            "og_too_short": 1,
        },
    }
    await _assert_refresh_resorts_after_og_second_pass(monkeypatch, tmp_path)


async def _assert_refresh_resorts_after_og_second_pass(monkeypatch, tmp_path):
    direct_items = [
        {
            "id": "high",
            "title": "새벽 하늘의 이상한 빛 기록",
            "category": "유머",
            "source_url": "https://www.fmkorea.com/high",
            "published_label": "",
            "age_minutes": 10,
            "views": 100_000,
            "votes": 500,
            "comments": 500,
        },
        {
            "id": "weak",
            "title": "주방 타일의 낯선 얼룩 관찰",
            "category": "유머",
            "source_url": "https://www.fmkorea.com/weak",
            "published_label": "",
            "age_minutes": 10,
            "views": 2_000,
            "votes": 20,
            "comments": 20,
        },
    ]

    class FakeResponse:
        status_code = 200
        text = "<html></html>"

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, **kwargs):
            return FakeResponse()

    async def fake_og(items, **kwargs):
        next(item for item in items if item["id"] == "weak")["kernel_screen"] = {
            "person": True,
            "axis": "live_wrong",
        }
        return {}

    monkeypatch.setattr(fast_module, "DIRECT_COMMUNITY_SOURCES", ())
    monkeypatch.setattr(fast_module.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(fast_module, "parse_fmkorea_latest", lambda html, now: [dict(x) for x in direct_items])
    monkeypatch.setattr(fast_module, "parse_issuelink_fmkorea_ids", lambda html: set())
    monkeypatch.setattr(fast_module, "parse_issuelink_community_items", lambda html: [])
    monkeypatch.setattr(fast_module, "_apply_og_second_pass", fake_og)

    snapshot = await FastViralCollector(tmp_path / "og-resort.json").refresh(limit=5)

    assert len(snapshot["items"]) == 2
    assert [item["id"] for item in snapshot["items"]] == ["weak", "high"]


def test_fast_viral_topic_api_preserves_only_non_body_context_provenance(tmp_path):
    collector = FastViralCollector(tmp_path / "fast_viral_snapshot.json")
    collector._snapshot = {
        "available": True,
        "items": [
            {
                "id": "verified-1",
                "title": "남편이 결혼식에서 한 행동",
                "source_url": "https://www.dogdrip.net/123",
                "signal_source": "직접 목록",
                "original_context_verified": True,
                "context_basis": "og_substantive",
                "context_checked_at": "2026-08-31T03:31:23+00:00",
            }
        ],
        "refreshed_at": "2026-08-31T03:31:23+00:00",
    }
    fast_routes.init_fast_viral_router(collector)

    payload = fast_routes.get_fast_viral()
    item = payload["items"][0]

    assert item["original_context_verified"] is True
    assert item["context_basis"] == "og_substantive"
    assert item["context_checked_at"] == "2026-08-31T03:31:23+00:00"
    assert "summary" not in item
    assert "context" not in item


def test_direct_signal_score_supports_sources_without_view_counts():
    score, rate = _direct_signal_score(
        age_minutes=7,
        views=0,
        comments=12,
        votes=34,
        delta_views_per_minute=0,
        before_issuelink=True,
    )

    assert score >= 45
    assert rate is None


def test_parse_issuelink_expands_multiple_community_sources_and_diversifies():
    html = """
    <a href="https://www.issuelink.co.kr/community/go/fmkorea/100">FM 글 하나 <small>[20]</small></a>
    <a href="https://www.issuelink.co.kr/community/go/fmkorea/101">FM 글 둘 <small>[15]</small></a>
    <a href="https://www.issuelink.co.kr/community/go/clien/200">클리앙 글 <small>[3]</small></a>
    <a href="https://www.issuelink.co.kr/community/go/theqoo/300">더쿠 글 <small>[5]</small></a>
    """

    items = parse_issuelink_community_items(html)
    selected = _select_diverse_community_items(items, 3)

    assert {item["community_source"] for item in selected} == {"fmkorea", "clien", "theqoo"}
    assert [item["comments"] for item in selected] == [20, 5, 3]
    assert next(item for item in items if item["community_source"] == "fmkorea")["source_url"] == (
        "https://www.fmkorea.com/100"
    )
    assert next(item for item in items if item["community_source"] == "clien")["link_kind"] == "redirect_pending"


def test_community_exposure_score_rewards_observed_cross_community_spread():
    items = [
        {
            "id": "1",
            "title": "스타벅스 신제품 오늘 전국 매장 공개",
            "community_source": "fmkorea",
            "comments": 20,
        },
        {
            "id": "2",
            "title": "스타벅스 신제품 전국 매장 오늘 공개",
            "community_source": "theqoo",
            "comments": 10,
        },
        {
            "id": "3",
            "title": "도심 정전 복구 현황",
            "community_source": "clien",
            "comments": 20,
        },
    ]

    _annotate_community_clusters(items)
    cross_score, cross_breakdown, cross_reasons, cross_confidence, _ = _community_x_exposure_assessment(items[0])
    single_score, single_breakdown, _, single_confidence, _ = _community_x_exposure_assessment(items[2])

    assert items[0]["cross_community_source_count"] == 2
    assert items[2]["cross_community_source_count"] == 1
    assert cross_score > single_score
    assert cross_breakdown["cross_community"] == 13
    assert single_breakdown["cross_community"] == 0
    assert "커뮤니티 2곳 교차" in cross_reasons
    assert cross_confidence == "medium"
    assert single_confidence == "low"
    assert items[0]["community_cluster_key"] == items[1]["community_cluster_key"]


def test_community_titles_match_after_korean_particle_normalization():
    assert _community_titles_match(
        "편의점 알바가 진상 손님한테 한 말",
        "편의점 알바 진상 손님 응대 레전드",
    )


def test_community_titles_do_not_overmatch_on_two_generic_subjects():
    assert not _community_titles_match(
        "편의점 알바가 신제품 음료 공개",
        "편의점 알바 진상 손님 응대 레전드",
    )


def test_community_titles_match_colloquial_relationship_and_shock_variants():
    items = [
        {
            "id": "1",
            "title": "여자친구 본가 갔다가 충격받은 의사.jpg",
            "community_source": "ppomppu",
        },
        {
            "id": "2",
            "title": "여친 본가 갔다가 충격 먹은 의사",
            "community_source": "bobae",
        },
    ]

    _annotate_community_clusters(items)

    assert items[0]["community_cluster_key"] == items[1]["community_cluster_key"]
    assert items[0]["cross_community_source_count"] == 2
    assert items[0]["cross_community_labels"] == ["보배드림 베스트", "뽐뿌 HOT"]


def test_colloquial_normalization_does_not_merge_different_visits_to_the_same_home():
    assert not _community_titles_match(
        "여자친구 본가에서 처음 먹은 저녁 메뉴",
        "여친 본가 갔다가 충격 먹은 의사",
    )


def test_cluster_collapse_keeps_one_representative_and_all_spread_evidence():
    items = [
        {
            "title": "일본 음식을 한입 먹고 버린 한국인.jpg",
            "community_source": "humoruniv",
            "community_cluster_key": "same-event",
            "cross_community_sources": ["humoruniv", "inven"],
            "community_mentions": 2,
            "x_exposure_score": 90,
            "kernel_screen": {"axis": "dead_flat"},
        },
        {
            "title": "일본 음식을 한입 먹고 버린 한국인",
            "community_source": "inven",
            "community_cluster_key": "same-event",
            "cross_community_sources": ["humoruniv", "inven"],
            "community_mentions": 2,
            "x_exposure_score": 40,
            "kernel_screen": {"person": True, "axis": "live_wrong"},
        },
    ]

    collapsed = _collapse_community_clusters(items)

    assert len(collapsed) == 1
    assert collapsed[0]["community_source"] == "inven"
    assert collapsed[0]["cross_community_source_count"] == 2
    assert collapsed[0]["cross_community_sources"] == ["humoruniv", "inven"]
    assert collapsed[0]["cross_community_labels"] == ["웃긴대학", "인벤"]
    assert collapsed[0]["community_mentions"] == 2


def test_reannotation_preserves_collapsed_cross_community_evidence():
    items = [
        {
            "title": "일본 음식을 한입 먹고 버린 한국인.jpg",
            "community_source": "humoruniv",
            "community_cluster_key": "a22c433b2ec6899b",
            "cross_community_sources": ["humoruniv", "inven"],
            "community_mentions": 2,
        }
    ]

    _annotate_community_clusters(items)

    assert items[0]["community_cluster_key"] == "a22c433b2ec6899b"
    assert items[0]["cross_community_source_count"] == 2
    assert items[0]["cross_community_sources"] == ["humoruniv", "inven"]
    assert items[0]["cross_community_labels"] == ["웃긴대학", "인벤"]
    assert items[0]["community_mentions"] == 2


def test_diverse_selection_spends_one_seat_per_cluster_and_fills_the_saved_seat():
    items = [
        {
            "title": "같은 사건 A",
            "community_source": "humoruniv",
            "community_cluster_key": "same-event",
            "x_exposure_score": 90,
            "comments": 10,
            "source_position": 0,
        },
        {
            "title": "같은 사건 B",
            "community_source": "inven",
            "community_cluster_key": "same-event",
            "x_exposure_score": 80,
            "comments": 9,
            "source_position": 1,
        },
        {
            "title": "다른 소재 하나",
            "community_source": "ppomppu",
            "community_cluster_key": "other-one",
            "x_exposure_score": 70,
            "comments": 8,
            "source_position": 2,
        },
        {
            "title": "다른 소재 둘",
            "community_source": "bobae",
            "community_cluster_key": "other-two",
            "x_exposure_score": 60,
            "comments": 7,
            "source_position": 3,
        },
    ]

    selected = _select_diverse_community_items(items, 3)

    assert len(selected) == 3
    assert _unique_community_cluster_count(selected) == 3
    assert sum(item["community_cluster_key"] == "same-event" for item in selected) == 1


def test_final_selection_keeps_unique_clusters_and_the_issuelink_lane():
    items = [
        {
            "title": "직접 중복",
            "community_source": "inven",
            "community_cluster_key": "same-event",
            "signal_source": "직접 목록",
            "x_exposure_score": 90,
        },
        {
            "title": "IssueLink 중복",
            "community_source": "humoruniv",
            "community_cluster_key": "same-event",
            "signal_source": "IssueLink",
            "x_exposure_score": 80,
        },
        {
            "title": "직접 고유 1",
            "community_source": "bobae",
            "community_cluster_key": "direct-one",
            "signal_source": "직접 목록",
            "x_exposure_score": 70,
        },
        {
            "title": "직접 고유 2",
            "community_source": "ppomppu",
            "community_cluster_key": "direct-two",
            "signal_source": "직접 목록",
            "x_exposure_score": 60,
        },
        {
            "title": "IssueLink 고유",
            "community_source": "theqoo",
            "community_cluster_key": "issue-one",
            "signal_source": "IssueLink",
            "x_exposure_score": 50,
        },
    ]

    selected = _select_unique_community_items(items, 3)

    assert len(selected) == 3
    assert _unique_community_cluster_count(selected) == 3
    assert any(item["signal_source"] == "IssueLink" for item in selected)


def test_final_selection_drops_global_posts_and_keeps_domestic_twelve():
    items = []
    for lane, count in (
        ("직접 목록", 6),
        ("글로벌 공개 커뮤니티", 6),
        ("IssueLink", 6),
    ):
        for index in range(count):
            items.append(
                {
                    "title": f"{lane} 소재 {index}",
                    "community_source": f"{lane}-{index}",
                    "community_cluster_key": f"{lane}-{index}",
                    "signal_source": lane,
                    "x_exposure_score": 90 - index,
                }
            )

    selected = _select_unique_community_items(items, 12)

    assert len(selected) == 12
    assert _unique_community_cluster_count(selected) == 12
    assert sum(item["signal_source"] == "글로벌 공개 커뮤니티" for item in selected) == 0
    assert sum(item["signal_source"] == "직접 목록" for item in selected) == 6
    assert sum(item["signal_source"] == "IssueLink" for item in selected) == 6


def test_community_cluster_key_is_independent_of_member_order():
    first = [
        {"id": "1", "title": "편의점 알바가 진상 손님한테 한 말", "community_source": "fmkorea"},
        {"id": "2", "title": "편의점 알바 진상 손님 응대 레전드", "community_source": "theqoo"},
    ]
    reversed_members = [dict(item) for item in reversed(first)]

    _annotate_community_clusters(first)
    _annotate_community_clusters(reversed_members)

    assert first[0]["community_cluster_key"] == first[1]["community_cluster_key"]
    assert {item["community_cluster_key"] for item in first} == {
        item["community_cluster_key"] for item in reversed_members
    }


def test_community_annotation_preserves_kernel_and_exposure_evidence():
    kernel_screen = {"axis": "live_wrong", "signals": ["가해 역할 + 행위"]}
    exposure_reasons = ["분당 조회 12.0", "IssueLink 선행 감지"]
    items = [
        {
            "id": "1",
            "title": "편의점 알바가 진상 손님한테 한 말",
            "community_source": "fmkorea",
            "kernel_screen": kernel_screen,
            "exposure_reasons": exposure_reasons,
        },
        {
            "id": "2",
            "title": "편의점 알바 진상 손님 응대 레전드",
            "community_source": "theqoo",
        },
    ]

    _annotate_community_clusters(items)

    assert items[0]["kernel_screen"] == kernel_screen
    assert items[0]["exposure_reasons"] == exposure_reasons
    assert items[0]["cross_community_source_count"] == 2


def test_community_exposure_score_rewards_measured_spread_growth():
    item = {
        "title": "스타벅스 신제품 오늘 전국 매장 공개",
        "comments": 20,
        "cross_community_source_count": 2,
    }
    base_score, _, _, _, _ = _community_x_exposure_assessment(item)
    growth_score, breakdown, reasons, confidence, coverage = _community_x_exposure_assessment(
        item,
        {
            "previous_observed_at": "2026-08-05T23:58:00+00:00",
            "new_sources": 1,
            "new_mentions": 2,
            "comment_growth": 30,
        },
    )

    assert growth_score > base_score
    assert breakdown["observed_growth"] > 0
    assert any("새 출처 +1" in reason for reason in reasons)
    assert confidence == "high"
    assert coverage == 1.0


class _FakeResponse:
    """차단 판별용 최소 응답 스텁."""

    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


def test_looks_blocked_detects_refusal_status_codes():
    # 사이트가 자동 접근을 거부한 것이지 우리가 잘못 파싱한 게 아니다.
    for status in (401, 403, 429, 430, 451):
        assert _looks_blocked(_FakeResponse(status_code=status)) is True


def test_looks_blocked_detects_interstitial_bodies_returned_with_200():
    # 일부 사이트는 200으로 안내 페이지를 돌려준다.
    assert _looks_blocked(_FakeResponse(text="<title>에펨코리아 보안 시스템</title>")) is True
    assert _looks_blocked(_FakeResponse(text="<title>Just a moment...</title>")) is True


def test_looks_blocked_passes_normal_listing_pages():
    assert _looks_blocked(_FakeResponse(text="<html><li class='li'>목록</li></html>")) is False


def test_looks_blocked_survives_unreadable_body():
    class Broken:
        status_code = 200

        @property
        def text(self):
            raise UnicodeDecodeError("utf-8", b"", 0, 1, "broken")

    assert _looks_blocked(Broken()) is False


def test_diverse_selection_spreads_across_communities_instead_of_one_board():
    """애그리게이터에 준 자리가 한 커뮤니티로 쏠리면 확대한 의미가 없다."""
    items = [
        {"community_source": "fmkorea", "title": f"fm{i}", "x_exposure_score": 90 - i, "comments": 0, "source_position": i}
        for i in range(6)
    ] + [
        {"community_source": "ppomppu", "title": "뽐뿌글", "x_exposure_score": 40, "comments": 0, "source_position": 6},
        {"community_source": "inven", "title": "인벤글", "x_exposure_score": 30, "comments": 0, "source_position": 7},
        {"community_source": "clien", "title": "클리앙글", "x_exposure_score": 20, "comments": 0, "source_position": 8},
    ]

    picked = _select_diverse_community_items(items, 4)

    # 점수만 보면 FMKorea가 네 자리를 다 가져간다. 커뮤니티가 갈려야 한다.
    assert len({item["community_source"] for item in picked}) == 4
    assert picked[0]["community_source"] == "fmkorea"


def test_diverse_selection_does_not_leave_seats_empty_with_one_source():
    """커뮤니티가 하나뿐이면 그 커뮤니티로 자리를 채운다 — 다양성 때문에 화면을 비우지 않는다."""
    items = [
        {"community_source": "fmkorea", "title": f"fm{i}", "x_exposure_score": 90 - i, "comments": 0, "source_position": i}
        for i in range(3)
    ]

    picked = _select_diverse_community_items(items, 3)

    assert [item["title"] for item in picked] == ["fm0", "fm1", "fm2"]


class TestAggregatorQuota:
    """화면에서 애그리게이터에 내어 주는 자리 수.

    올리면 커뮤니티 종류가 늘고, 내리면 조회·추천 지표가 있는 직접 항목이 늘어난다.
    """

    def test_default_share_is_half_the_page(self, monkeypatch):
        monkeypatch.delenv("GETDAYTRENDS_AGGREGATOR_SHARE", raising=False)
        assert aggregator_quota(12, any_direct_ok=True) == 6

    def test_direct_outage_hands_the_whole_page_over(self, monkeypatch):
        monkeypatch.delenv("GETDAYTRENDS_AGGREGATOR_SHARE", raising=False)
        assert aggregator_quota(12, any_direct_ok=False) == 12

    def test_share_is_configurable(self, monkeypatch):
        monkeypatch.setenv("GETDAYTRENDS_AGGREGATOR_SHARE", "0.75")
        assert aggregator_quota(12, any_direct_ok=True) == 9
        monkeypatch.setenv("GETDAYTRENDS_AGGREGATOR_SHARE", "0.25")
        assert aggregator_quota(12, any_direct_ok=True) == 3

    def test_direct_items_always_keep_at_least_one_seat(self, monkeypatch):
        # 1.0을 넣어도 직접 목록이 통째로 사라지지는 않는다.
        monkeypatch.setenv("GETDAYTRENDS_AGGREGATOR_SHARE", "1.0")
        assert aggregator_quota(12, any_direct_ok=True) == 11

    def test_aggregator_always_keeps_at_least_one_seat(self, monkeypatch):
        # 0을 넣어도 애그리게이터가 통째로 사라지지는 않는다 — 그러면 확대한 의미가 없다.
        monkeypatch.setenv("GETDAYTRENDS_AGGREGATOR_SHARE", "0")
        assert aggregator_quota(12, any_direct_ok=True) == 1

    def test_garbage_value_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("GETDAYTRENDS_AGGREGATOR_SHARE", "절반")
        assert aggregator_quota(12, any_direct_ok=True) == 6

    def test_empty_page_asks_for_nothing(self, monkeypatch):
        monkeypatch.delenv("GETDAYTRENDS_AGGREGATOR_SHARE", raising=False)
        assert aggregator_quota(0, any_direct_ok=True) == 0


class TestBrandSafety:
    """2026-08-06 직접 소스를 넷으로 늘리자 성인성·화장실 유머가 화면에 올라왔다."""

    def test_blocks_explicit_titles(self):
        assert _is_brand_safe_title("첫경험인 남친에게 69자세 시킨 여친") is False
        assert _is_brand_safe_title("노브라로 출근한 썰 푼다") is False

    def test_blocks_toilet_humor_by_context(self):
        assert _is_brand_safe_title("밤송이로 똥을 닦았지요 성님") is False
        assert _is_brand_safe_title("전립선염 치료 받고 수치스러웠다는 사람") is False
        assert _is_brand_safe_title("엘리베이터에서 방귀 뀌고 도망감") is False

    def test_keeps_ordinary_titles_that_merely_share_a_syllable(self):
        # 단어 하나로 자르면 멀쩡한 글이 사라진다.
        assert _is_brand_safe_title("똥손인데 요리 도전해봤다") is True
        assert _is_brand_safe_title("똥차 팔고 새 차 뽑은 후기") is True
        assert _is_brand_safe_title("첫 경험담 아니고 첫 출근 이야기입니다") is True

    def test_still_rejects_too_short_titles(self):
        assert _is_brand_safe_title("ㅋㅋㅋ") is False


@pytest.mark.asyncio
async def test_collector_shadow_records_direct_and_issuelink_without_product_or_request_changes(
    monkeypatch, tmp_path
):
    direct_items = [
        {
            "id": "101",
            "title": "회사에서 신제품을 공개한 뒤 생긴 일",
            "category": "유머",
            "source_url": "https://www.fmkorea.com/101",
            "published_label": "",
            "age_minutes": 10,
            "views": 10_000,
            "votes": 100,
            "comments": 50,
        },
        {
            "id": "102",
            "title": "국회 새 법안 처리 논의",
            "category": "시사",
            "source_url": "https://www.fmkorea.com/102",
            "published_label": "",
            "age_minutes": 10,
            "views": 10_000,
            "votes": 100,
            "comments": 50,
        },
    ]
    issue_items = [
        {
            "id": "201",
            "title": "편의점 신제품을 먹고 놀란 손님 이야기",
            "category": "IssueLink 집계 확인",
            "community_source": "clien",
            "community_label": "클리앙",
            "source_url": "https://www.issuelink.co.kr/community/go/clien/201",
            "aggregator_url": "https://www.issuelink.co.kr/community/go/clien/201",
            "link_kind": "redirect_pending",
            "published_label": "(10 분전)",
            "age_minutes": 10,
            "views": 0,
            "votes": 0,
            "comments": 20,
            "source_position": 0,
        },
        {
            "id": "202",
            "title": "시의회 예산안 표결",
            "category": "IssueLink 집계 확인",
            "community_source": "inven",
            "community_label": "인벤",
            "source_url": "https://www.issuelink.co.kr/community/go/inven/202",
            "aggregator_url": "https://www.issuelink.co.kr/community/go/inven/202",
            "link_kind": "redirect_pending",
            "published_label": "(10 분전)",
            "age_minutes": 10,
            "views": 0,
            "votes": 0,
            "comments": 20,
            "source_position": 1,
        },
        {
            "id": "203",
            "title": "(민형배) 모두의 성장, 전남광주 반도체로 열겠습니다!",
            "category": "IssueLink 집계 확인",
            "community_source": "ruliweb",
            "community_label": "루리웹",
            "source_url": "https://www.issuelink.co.kr/community/go/ruliweb/203",
            "aggregator_url": "https://www.issuelink.co.kr/community/go/ruliweb/203",
            "link_kind": "redirect_pending",
            "published_label": "(10 분전)",
            "age_minutes": 10,
            "views": 0,
            "votes": 0,
            "comments": 20,
            "source_position": 2,
        },
        {
            "id": "204",
            "title": "오늘 하닉매도하면 수익 7억 찍을듯",
            "category": "IssueLink 집계 확인",
            "community_source": "fmkorea",
            "community_label": "FMKorea",
            "source_url": "https://www.issuelink.co.kr/community/go/fmkorea/204",
            "aggregator_url": "https://www.issuelink.co.kr/community/go/fmkorea/204",
            "link_kind": "redirect_pending",
            "published_label": "(10 분전)",
            "age_minutes": 10,
            "views": 0,
            "votes": 0,
            "comments": 20,
            "source_position": 3,
        },
    ]

    class FakeResponse:
        status_code = 200
        text = "<html></html>"

        def raise_for_status(self):
            return None

    request_calls = 0

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, **kwargs):
            nonlocal request_calls
            request_calls += 1
            return FakeResponse()

    async def no_resolve(session, items):
        return 0

    async def no_og(items, **kwargs):
        return {}

    monkeypatch.setattr(fast_module, "DIRECT_COMMUNITY_SOURCES", ())
    monkeypatch.setattr(fast_module.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(fast_module, "parse_fmkorea_latest", lambda html, now: [dict(x) for x in direct_items])
    monkeypatch.setattr(fast_module, "parse_issuelink_fmkorea_ids", lambda html: {"999"})
    monkeypatch.setattr(fast_module, "parse_issuelink_community_items", lambda html: [dict(x) for x in issue_items])
    monkeypatch.setattr(fast_module, "_resolve_community_origins", no_resolve)
    monkeypatch.setattr(fast_module, "_apply_og_second_pass", no_og)

    class RecordingStore:
        def __init__(self):
            self.rows = []

        def record(self, **candidate):
            self.rows.append(candidate)
            return True

    class ExplodingStore:
        def record(self, **candidate):
            raise RuntimeError("forced shadow failure")

    def projection(data):
        return {
            "items": [(item["id"], item["title"], item["signal_source"]) for item in data["items"]],
            "excluded_topic_counts": data["excluded_topic_counts"],
            "qualified_count": data["qualified_count"],
            "source_health": data["source_health"],
        }

    baseline = await FastViralCollector(tmp_path / "baseline.json").refresh(limit=5)
    baseline_calls = request_calls
    request_calls = 0
    store = RecordingStore()
    measured = await FastViralCollector(
        tmp_path / "measured.json", filter_shadow_store=store
    ).refresh(limit=5)
    measured_calls = request_calls
    request_calls = 0
    failed = await FastViralCollector(
        tmp_path / "failed.json", filter_shadow_store=ExplodingStore()
    ).refresh(limit=5)

    assert projection(measured) == projection(baseline)
    assert projection(failed) == projection(baseline)
    # 국내 전용 계약: 기본 FMKorea·IssueLink 2회만 호출한다.
    # shadow store 유무나 실패가 네트워크 수를 바꾸지 않는 것이 이 검사의 계약이다.
    assert baseline_calls == measured_calls == request_calls == 2
    assert baseline["excluded_topic_counts"] == {
        "정치 제외": 3,
        "증시·실적 제외": 1,
    }
    assert {(row["source"], row["filter_verdict"]) for row in store.rows} == {
        ("fast-viral:direct", "allow"),
        ("fast-viral:direct", "block"),
        ("fast-viral:issuelink", "allow"),
        ("fast-viral:issuelink", "block"),
    }


@pytest.mark.asyncio
async def test_collector_does_not_call_or_surface_foreign_community_sources(
    monkeypatch, tmp_path
):
    class FakeResponse:
        status_code = 200
        text = "<html></html>"

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, **kwargs):
            return FakeResponse()

    foreign_called = False

    async def federated(session, *, now):
        nonlocal foreign_called
        foreign_called = True
        del session, now
        return {
            "items": [
                {
                    "id": "at://did:plc:test/app.bsky.feed.post/1",
                    "title": "Unexpected public rescue caught on camera",
                    "category": "Bluesky 트렌드 · rescue",
                    "community_source": "bluesky_trending",
                    "community_label": "Bluesky 트렌드 피드",
                    "source_url": "https://bsky.app/profile/example.test/post/1",
                    "link_kind": "publisher_original",
                    "published_label": "2026-08-27T00:00:00Z",
                    "age_minutes": 10,
                    "views": 0,
                    "votes": 200,
                    "comments": 20,
                    "source_position": 0,
                    "signal_source": "글로벌 공개 커뮤니티",
                    "attachment_kind": "video",
                    "video_url": "",
                    "dedupe_key": "at://did:plc:test/app.bsky.feed.post/1",
                    "reposts": 200,
                    "likes": 400,
                    "quotes": 5,
                    "language": "en",
                    "region": None,
                    "sensitive": None,
                    "political": None,
                    "spoiler_text": "",
                    "media_kinds": ["app.bsky.embed.video#view"],
                }
            ],
            "source_health": {
                "mastodon_trends": True,
                "bluesky_trending": True,
                "lemmy_hot": True,
            },
            "errors": [],
        }

    async def no_og(items, **kwargs):
        return {}

    monkeypatch.setattr(fast_module, "DIRECT_COMMUNITY_SOURCES", ())
    monkeypatch.setattr(fast_module.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(fast_module, "collect_federated_community_sources", federated, raising=False)
    monkeypatch.setattr(fast_module, "parse_fmkorea_latest", lambda html, now: [])
    monkeypatch.setattr(fast_module, "parse_issuelink_fmkorea_ids", lambda html: set())
    monkeypatch.setattr(fast_module, "parse_issuelink_community_items", lambda html: [])
    monkeypatch.setattr(fast_module, "_apply_og_second_pass", no_og)

    snapshot = await FastViralCollector(tmp_path / "federated.json").refresh(limit=5)

    assert foreign_called is False
    assert snapshot["available"] is False
    assert snapshot["poll_interval_seconds"] == 300
    assert snapshot["collection_scope"] == "domestic_direct_only"
    assert snapshot["foreign_sources_enabled"] is False
    assert snapshot["total_federated_posts"] == 0
    assert snapshot["federated_source_count"] == 0
    assert snapshot["federated_source_total"] == 0
    assert snapshot["federated_displayed_count"] == 0
    assert snapshot["items"] == []
    assert not any(key.endswith("_public") for key in snapshot["source_health"])


def test_snapshot_boundary_filters_injected_foreign_items_and_health(tmp_path):
    collector = FastViralCollector(tmp_path / "domestic-boundary.json")
    collector._snapshot = {
        "items": [
            {"id": "kr", "signal_source": "직접 목록"},
            {"id": "foreign", "signal_source": "글로벌 공개 커뮤니티"},
        ],
        "source_health": {"dogdrip_direct": True, "mastodon_trends_public": True},
    }

    snapshot = collector.snapshot()

    assert [item["id"] for item in snapshot["items"]] == ["kr"]
    assert snapshot["foreign_filtered_count"] == 1
    assert snapshot["source_health"] == {"dogdrip_direct": True}
    assert snapshot["collection_scope"] == "domestic_direct_only"
    assert snapshot["foreign_sources_enabled"] is False


class TestSpreadGate:
    """확산 게이트가 커널 판정을 이기지 않는가.

    2026-08-07 새벽 실측(수집 292건)에서 필터를 통과한 77건 중 사는 축은 6건뿐이었는데
    그 6건 중 3건이 확산 게이트에서 다시 떨어졌다. 아래 세 건은 그때 실제로 떨어진 값이다.
    """

    def test_live_axis_material_survives_without_spread(self):
        # 조회 318·댓글 4·추천 4로 34점. 통과선 35점과 1점 차로 떨어졌던 군 부대 절도 고발 건.
        item = {"views": 318, "comments": 4, "votes": 4}
        assert passes_spread_gate(item, score=34, live_axis=True) is True

    def test_live_axis_survives_when_the_source_hides_comments(self):
        # 뽐뿌 자유게시판은 댓글을 아예 주지 않는다. 조회 1,887이어도 engagement 배점 40점을
        # 구조적으로 못 받아 30점에 묶였다. 소스가 노출하는 지표가 판정을 이겨서는 안 된다.
        item = {"views": 1887, "comments": 0, "votes": 1}
        assert passes_spread_gate(item, score=30, live_axis=True) is True

    def test_dead_axis_still_needs_real_spread(self):
        # 면제는 사는 축에만 준다. 풀어 주면 죽는 축 64건이 그대로 화면을 채운다.
        item = {"views": 1887, "comments": 0, "votes": 1}
        assert passes_spread_gate(item, score=30, live_axis=False) is False
        assert passes_spread_gate(item, score=55, live_axis=False) is True

    def test_dead_axis_without_view_counts_uses_the_reaction_path(self):
        # 개드립처럼 조회를 주지 않는 소스는 댓글+추천으로 판단한다.
        item = {"views": 0, "comments": 13, "votes": 21}
        assert passes_spread_gate(item, score=45, live_axis=False) is True
        assert passes_spread_gate(item, score=44, live_axis=False) is False

    def test_dead_axis_rejects_a_high_score_with_no_traction_at_all(self):
        item = {"views": 0, "comments": 1, "votes": 1}
        assert passes_spread_gate(item, score=90, live_axis=False) is False
