"""Tests for the direct-community early viral collector."""

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fast_viral_collector import (  # noqa: E402
    _apply_og_second_pass,
    _annotate_community_clusters,
    _looks_blocked,
    aggregator_quota,
    _community_x_exposure_assessment,
    _direct_signal_score,
    _is_brand_safe_title,
    _parse_count,
    _select_diverse_community_items,
    _velocity_score,
    passes_spread_gate,
    parse_fmkorea_latest,
    parse_issuelink_community_items,
    parse_issuelink_fmkorea_ids,
    parse_issuelink_fmkorea_items,
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
    <a href="https://www.issuelink.co.kr/community/go/fmkorea/123456789">
      지금 여러 곳에서 퍼지는 새 소식 <small>[12]</small>
    </a>
    <a href="https://www.issuelink.co.kr/community/go/fmkorea/123456789">중복</a>
    """

    assert parse_issuelink_fmkorea_items(html) == [
        {
            "id": "123456789",
            "title": "지금 여러 곳에서 퍼지는 새 소식",
            "category": "IssueLink 백업",
            "source_url": "https://www.fmkorea.com/123456789",
            "published_label": "",
            "age_minutes": None,
            "views": 0,
            "votes": 0,
            "comments": 12,
        }
    ]


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
    )

    assert items[0]["kernel_screen"]["axis"] == "live_wrong"
    assert items[1]["kernel_screen"]["axis"] == "live_wrong"
    assert all("description" not in key for item in items for key in item)
    assert summary["requested_count"] == 1
    assert summary["enriched_count"] == 1
    assert "축의금" not in repr(summary)


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
