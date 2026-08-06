"""Tests for publisher-original community listing parsers."""

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from direct_community_sources import (  # noqa: E402
    DIRECT_COMMUNITY_SOURCES,
    parse_82cook_free,
    parse_ppomppu_free,
    parse_todayhumor_best,
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


def test_parse_82cook_reads_full_timestamp_from_the_title_attribute():
    # 목록 텍스트는 "18:42:20"뿐이고 전체 시각은 title 속성에 있다.
    html = """
    <table>
      <tr class="noticeList"><td class="title"><a href="read.php?bn=15&amp;num=1">공지</a></td></tr>
      <tr>
        <td class="numbers"><a class="photolink" href="read.php?bn=15&amp;num=4224140">1831734</a></td>
        <td class="title"><a href="read.php?bn=15&amp;num=4224140">맛 없는 복숭아 고기에 넣어도 돼요?</a> <em>7</em></td>
        <td class="regdate numbers" title="2026-08-06 09:03:20"> 09:03:20</td>
        <td class="numbers">74</td>
      </tr>
    </table>
    """

    items = parse_82cook_free(html, now=NOW)

    # 공지 행은 빠진다.
    assert [item["id"] for item in items] == ["4224140"]
    item = items[0]
    assert item["title"] == "맛 없는 복숭아 고기에 넣어도 돼요?"
    assert item["community_label"] == "82cook"
    assert item["source_url"] == "https://www.82cook.com/entiz/read.php?bn=15&num=4224140"
    assert item["published_label"] == "09:03"
    assert item["age_minutes"] == 7
    assert item["views"] == 74
    assert item["comments"] == 7


def test_parse_ppomppu_skips_notices_and_reads_metrics():
    html = """
    <table>
      <tr class="baseNotice"><td><a class="baseList-title" href="view.php?id=regulation&amp;no=6">규칙</a></td></tr>
      <tr class="baseList">
        <td class="baseList-space baseList-numb">10069771</td>
        <td class="baseList-space"><a class="baseList-title" href="view.php?id=freeboard&amp;page=1&amp;no=10069771"><span>요코하마 경기 보러왔네요</span></a></td>
        <td class="baseList-space">글쓴이</td>
        <td class="baseList-space">09:05:50</td>
        <td class="baseList-space baseList-rec">3</td>
        <td class="baseList-space baseList-views">213</td>
      </tr>
    </table>
    """

    items = parse_ppomppu_free(html, now=NOW)

    assert [item["id"] for item in items] == ["10069771"]
    item = items[0]
    assert item["title"] == "요코하마 경기 보러왔네요"
    assert item["source_url"] == "https://www.ppomppu.co.kr/zboard/view.php?id=freeboard&page=1&no=10069771"
    assert item["published_label"] == "09:05"
    assert item["age_minutes"] == 5
    assert item["votes"] == 3
    assert item["views"] == 213


def test_parse_todayhumor_reads_comment_count_outside_the_title_link():
    # 댓글 수가 제목 링크 밖 span에 있어서 처음에는 0으로 읽혔다.
    html = """
    <table>
      <tr class="view">
        <td class="no"><a href="/board/view.php?table=bestofbest&amp;no=483548">483548</a></td>
        <td class="subject"><a href="/board/view.php?table=bestofbest&amp;no=483548">올리브영에서 아내 기다리는 남편</a><span class="list_memo_count_span"> [9]</span></td>
        <td class="date">26/08/06 09:04</td>
        <td class="hits">4,842</td>
        <td class="oknok">80</td>
      </tr>
    </table>
    """

    items = parse_todayhumor_best(html, now=NOW)
    item = items[0]

    assert item["title"] == "올리브영에서 아내 기다리는 남편"
    assert item["comments"] == 9
    assert item["views"] == 4_842
    assert item["votes"] == 80
    assert item["age_minutes"] == 6


def test_all_registered_sources_have_a_parser():
    # 등록만 하고 파서를 빠뜨리면 그 소스는 조용히 0건이 된다.
    assert {s["key"] for s in DIRECT_COMMUNITY_SOURCES} >= {
        "dogdrip", "theqoo", "ruliweb", "bobaedream", "cook82", "ppomppu", "todayhumor",
    }
    for source in DIRECT_COMMUNITY_SOURCES:
        assert parse_direct_community_source(source["key"], "<html></html>") == []
