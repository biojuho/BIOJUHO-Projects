"""Tests for the direct-community early viral collector."""

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fast_viral_collector import (  # noqa: E402
    _annotate_community_clusters,
    _looks_blocked,
    _community_x_exposure_assessment,
    _direct_signal_score,
    _is_brand_safe_title,
    _parse_count,
    _select_diverse_community_items,
    _velocity_score,
    parse_fmkorea_latest,
    parse_issuelink_community_items,
    parse_issuelink_fmkorea_ids,
    parse_issuelink_fmkorea_items,
)


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
