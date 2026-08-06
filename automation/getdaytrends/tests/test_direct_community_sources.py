"""Tests for publisher-original community listing parsers."""

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from direct_community_sources import (  # noqa: E402
    DIRECT_COMMUNITY_SOURCES,
    parse_bobaedream_best,
    parse_direct_community_source,
    parse_dogdrip_latest,
    parse_ruliweb_best,
    parse_theqoo_hot,
)


NOW = datetime(2026, 8, 6, 0, 10, tzinfo=UTC)


def test_parse_dogdrip_latest_keeps_original_url_and_observed_metrics():
    html = """
    <ul><li class="ed webzine">
      <h5 class="title"><a class="ed title-link" data-document-srl="717603215"
        href="/dogdrip/717603215?page=1">지금 빠르게 퍼지는 목격담</a>
        <span class="ed text-primary text-xxsmall">12</span></h5>
      <div class="list-meta"><span><span class="text-primary">34</span></span>
        <span class="text-muted">7 분 전</span></div>
    </li></ul>
    """

    assert parse_dogdrip_latest(html, now=NOW) == [
        {
            "id": "717603215",
            "title": "지금 빠르게 퍼지는 목격담",
            "category": "개드립",
            "community_source": "dogdrip",
            "community_label": "개드립",
            "source_url": "https://www.dogdrip.net/dogdrip/717603215?page=1",
            "link_kind": "publisher_original",
            "published_label": "7 분 전",
            "age_minutes": 7,
            "views": 0,
            "votes": 34,
            "comments": 12,
            "source_position": 0,
            "signal_source": "직접 목록",
        }
    ]


def test_parse_theqoo_hot_reads_time_views_and_comments():
    html = """
    <table><tr>
      <td class="cate"><span>기사/뉴스</span></td>
      <td class="title"><a href="/hot/4304265213">배우 공동 모델 오늘 공개</a>
        <a class="replyNum" href="#comments">338</a></td>
      <td class="time">09:02</td><td class="m_no">26,506</td>
    </tr></table>
    """

    item = parse_theqoo_hot(html, now=NOW)[0]
    assert item["source_url"] == "https://theqoo.net/hot/4304265213"
    assert item["category"] == "기사/뉴스"
    assert item["age_minutes"] == 8
    assert item["views"] == 26_506
    assert item["comments"] == 338


def test_parse_ruliweb_best_reads_original_metrics_without_rank_text():
    html = """
    <table><tr class="table_body">
      <td class="id">76218717</td><td class="subject">
        <a class="subject_link" href="/best/board/300143/read/76218717?m=humor">
          <span>1</span><strong class="text_over">새로 발견된 기묘한 장면</strong>
          <span class="num_reply">(69)</span>
        </a></td>
      <td class="recomd">46</td><td class="hit">15,563</td><td class="time">08:59</td>
    </tr></table>
    """

    item = parse_ruliweb_best(html, now=NOW)[0]
    assert item["title"] == "새로 발견된 기묘한 장면"
    assert item["source_url"] == "https://bbs.ruliweb.com/best/board/300143/read/76218717?m=humor"
    assert item["age_minutes"] == 11
    assert item["views"] == 15_563
    assert item["votes"] == 46
    assert item["comments"] == 69


def test_parse_bobaedream_best_reads_full_category_and_metrics():
    html = """
    <table><tr itemscope="" itemtype="http://schema.org/Article">
      <td class="category" title="신유머/이슈/움짤"><a href="/list.php?code=strange">신유머/이..</a></td>
      <td class="pl14">
        <a class="bsubject" href="/view?code=best&amp;No=1018692&amp;vdate=" title="지금 퍼지는 목격담">지금 퍼지는 목격담</a>
        <a href="/view?code=best&amp;No=1018692&amp;vdate=&amp;cmt=1"><span class="Comment">(<strong class="totreply">13</strong>)</span></a>
      </td>
      <td class="author02"><span class="author">글쓴이</span></td>
      <td class="date">09:03</td>
      <td class="recomm">60</td>
      <td class="count">4,889</td>
    </tr></table>
    """

    assert parse_bobaedream_best(html, now=NOW) == [
        {
            "id": "1018692",
            "title": "지금 퍼지는 목격담",
            # 목록 글자는 "신유머/이.."로 잘려 나오므로 title 속성의 전체 이름을 쓴다.
            "category": "신유머/이슈/움짤",
            "community_source": "bobaedream",
            "community_label": "보배드림",
            "source_url": "https://www.bobaedream.co.kr/view?code=best&No=1018692&vdate=",
            "link_kind": "publisher_original",
            # 목록 시각은 KST다. NOW(UTC 00:10)는 KST 09:10이므로 09:03은 7분 전이다.
            "published_label": "09:03",
            "age_minutes": 7,
            "views": 4_889,
            "votes": 60,
            "comments": 13,
            "source_position": 0,
            "signal_source": "직접 목록",
        }
    ]


def test_parse_bobaedream_best_skips_duplicates_and_non_best_links():
    html = """
    <table>
      <tr><td class="pl14"><a class="bsubject" href="/view?code=freeb&amp;No=999">베스트 아닌 글</a></td></tr>
      <tr><td class="pl14"><a class="bsubject" href="/view?code=best&amp;No=555">첫 등장</a></td><td class="date">23:50</td></tr>
      <tr><td class="pl14"><a class="bsubject" href="/view?code=best&amp;No=555&amp;cmt=1">같은 글 다른 링크</a></td></tr>
      <tr><td class="pl14"><a class="bsubject" href="/view?code=best&amp;No=556"></a></td></tr>
    </table>
    """

    items = parse_bobaedream_best(html, now=NOW)

    # 베스트가 아닌 글, 같은 글의 댓글 링크, 제목이 빈 행은 모두 빠진다.
    assert [item["id"] for item in items] == ["555"]
    # 23:50은 KST 09:10 기준으로 미래이므로 전날 23:50으로 읽는다 — 9시간 20분 전.
    assert items[0]["age_minutes"] == 560


def test_parse_bobaedream_best_falls_back_when_category_title_missing():
    html = """
    <table><tr>
      <td class="category"><a href="/list.php?code=strange">자유게시판</a></td>
      <td class="pl14"><a class="bsubject" href="/view?code=best&amp;No=777">제목</a></td>
    </tr></table>
    """

    assert parse_bobaedream_best(html, now=NOW)[0]["category"] == "자유게시판"


def test_bobaedream_is_registered_as_a_direct_source():
    keys = {source["key"] for source in DIRECT_COMMUNITY_SOURCES}
    assert "bobaedream" in keys
    # 등록만 하고 파서를 빠뜨리면 수집이 조용히 0건이 된다.
    for source in DIRECT_COMMUNITY_SOURCES:
        assert parse_direct_community_source(source["key"], "<html></html>") == []
