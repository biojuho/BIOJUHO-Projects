"""Tests for publisher-original community listing parsers."""

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from direct_community_sources import (  # noqa: E402
    DIRECT_COMMUNITY_SOURCES,
    parse_82cook_free,
    parse_bobaedream_accident,
    parse_bobaedream_best,
    parse_bobaedream_dica,
    parse_bobaedream_freeb,
    parse_bobaedream_national,
    parse_bobaedream_strange,
    parse_clien_board,
    parse_direct_community_source,
    parse_dogdrip_latest,
    parse_ppomppu_free,
    parse_ppomppu_hot,
    parse_ruliweb_best,
    parse_theqoo_hot,
    parse_todayhumor_best,
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
            "attachment_kind": "unknown",
            "video_url": "",
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
            "community_source": "bobae",
            "community_label": "보배드림 베스트",
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
            "attachment_kind": "unknown",
            "video_url": "",
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
    # 키는 IssueLink 슬러그와 같아야 한다. 다르면 같은 글이 화면에 두 번 오르고,
    # "IssueLink 선행 감지" 표시가 거짓이 되며, 부당한 가산점이 붙는다.
    assert "bobae" in keys
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
    assert item["community_source"] == "ppomppu_freeboard"
    assert item["community_label"] == "뽐뿌 자유"
    assert item["source_url"] == "https://www.ppomppu.co.kr/zboard/view.php?id=freeboard&page=1&no=10069771"
    assert item["published_label"] == "09:05"
    assert item["age_minutes"] == 5
    assert item["votes"] == 3
    assert item["views"] == 213


def test_parse_ppomppu_hot_reads_board_date_cells_and_comment_span():
    # hot.php는 baseList-views 대신 board_date 세 칸(시각·추천-비추·조회)을 쓴다.
    html = """
    <table>
      <tr class="baseList" data-bbs_id="freeboard" data-bbs_no="10069788">
        <td class="baseList-space baseList-numb"><a href="/zboard/zboard.php?id=freeboard">자유게시판</a></td>
        <td class="baseList-space title">
          <a class="baseList-title" href="/zboard/zboard.php?id=freeboard&amp;no=10069788">
            이해찬대표 회고록 속 김민석
          </a>
          <span class="list_comment2">12</span>
        </td>
        <td class="baseList-space board_date">09:05:01</td>
        <td class="baseList-space board_date">17 - 0</td>
        <td class="baseList-space board_date">1609</td>
      </tr>
    </table>
    """

    items = parse_ppomppu_hot(html, now=NOW)
    assert len(items) == 1
    item = items[0]
    assert item["id"] == "10069788"
    assert item["community_source"] == "ppomppu"
    assert item["category"] == "자유게시판"
    assert item["published_label"] == "09:05"
    assert item["votes"] == 17
    assert item["views"] == 1609
    assert item["comments"] == 12


def test_parse_bobaedream_free_boards_share_table_structure_with_distinct_keys():
    # freeb/national/strange는 best와 같은 테이블이지만 code= 값만 다르다.
    freeb_html = """
    <table><tr>
      <td class="pl14">
        <a class="bsubject" href="/view?code=freeb&amp;No=3424935" title="짜장면 먹고 울어서 감사하고 싶은 글">
          짜장면 먹고 울어서 감사하고 싶은 글
        </a>
        <span class="Comment">(<strong class="totreply">218</strong>)</span>
      </td>
      <td class="date">09:03</td>
      <td class="recomm">2460</td>
      <td class="count">82310</td>
    </tr></table>
    """
    national_html = """
    <table><tr>
      <td class="pl14">
        <a class="bsubject" href="/view?code=national&amp;No=2412171">신차인증))드디어 신차 인증 합니다</a>
        <span class="Comment">(<strong class="totreply">175</strong>)</span>
      </td>
      <td class="date">08/01</td>
      <td class="recomm">640</td>
      <td class="count">43628</td>
    </tr></table>
    """
    strange_html = """
    <table><tr>
      <td class="pl14">
        <a class="bsubject" href="/view?code=strange&amp;No=6966536">울산 골때리게 됐네요</a>
        <span class="Comment">(<strong class="totreply">66</strong>)</span>
      </td>
      <td class="date">09:05</td>
      <td class="recomm">638</td>
      <td class="count">35068</td>
    </tr></table>
    """

    freeb = parse_bobaedream_freeb(freeb_html, now=NOW)[0]
    assert freeb["community_source"] == "bobae_freeb"
    assert freeb["id"] == "3424935"
    assert freeb["comments"] == 218
    assert freeb["views"] == 82_310
    assert freeb["age_minutes"] == 7

    national = parse_bobaedream_national(national_html, now=NOW)[0]
    assert national["community_source"] == "bobae_national"
    # 08/01 00:00 KST 기준. NOW=08/06 09:10 KST → 5일 9시간 10분 = 7750분.
    assert national["published_label"] == "08/01"
    assert national["age_minutes"] == 7750

    strange = parse_bobaedream_strange(strange_html, now=NOW)[0]
    assert strange["community_source"] == "bobae_strange"
    assert strange["id"] == "6966536"
    assert strange["age_minutes"] == 5

    # 다른 게시판 코드를 넘기면 0건 — 소스 키 분리가 깨지지 않게.
    assert parse_bobaedream_freeb(national_html, now=NOW) == []
    assert parse_bobaedream_best(freeb_html, now=NOW) == []


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
    keys = {s["key"] for s in DIRECT_COMMUNITY_SOURCES}
    assert keys >= {
        "dogdrip",
        "theqoo",
        "ruliweb",
        "bobae",
        "bobae_freeb",
        "bobae_national",
        "bobae_strange",
        "bobae_accident",
        "bobae_dica",
        "clien_park",
        "ppomppu",
        "ppomppu_freeboard",
        "todayhumor",
    }
    # 82cook은 직접 수집에서 제외(IP 차단). IssueLink 경유만 유지.
    assert "82cook" not in keys
    for source in DIRECT_COMMUNITY_SOURCES:
        assert parse_direct_community_source(source["key"], "<html></html>") == []
    # 파서 자체는 재개용으로 남겨 둔다.
    assert parse_direct_community_source("82cook", "<html></html>") == []


# --- 첨부 형태. 목록에 있는 표식만 읽고, 없으면 unknown. text 로 추정하지 않는다. ---

_LEGACY_ITEM_KEYS = {
    "id",
    "title",
    "category",
    "community_source",
    "community_label",
    "source_url",
    "link_kind",
    "published_label",
    "age_minutes",
    "views",
    "votes",
    "comments",
    "source_position",
    "signal_source",
}


def test_attachment_fields_are_pure_additions_on_existing_fixtures():
    html = """
    <ul><li class="ed webzine">
      <h5 class="title"><a class="ed title-link" data-document-srl="717603215"
        href="/dogdrip/717603215?page=1">지금 빠르게 퍼지는 목격담</a>
        <span class="ed text-primary text-xxsmall">12</span></h5>
      <div class="list-meta"><span><span class="text-primary">34</span></span>
        <span class="text-muted">7 분 전</span></div>
    </li></ul>
    """
    item = parse_dogdrip_latest(html, now=NOW)[0]
    assert set(item) - _LEGACY_ITEM_KEYS == {"attachment_kind", "video_url"}
    assert item["id"] == "717603215"
    assert item["title"] == "지금 빠르게 퍼지는 목격담"
    assert item["source_url"] == "https://www.dogdrip.net/dogdrip/717603215?page=1"
    assert item["views"] == 0
    assert item["votes"] == 34
    assert item["comments"] == 12


def test_dogdrip_play_circle_is_video_and_thumbnail_is_image():
    html = """
    <ul>
      <li class="ed webzine">
        <div class="icon-container">
          <img class="ed webzine-thumbnail" src="/files/thumbnails/1/100x100.crop.jpg"/>
          <i class="overlay-icon fas fa-play-circle"></i>
        </div>
        <a class="ed title-link" data-document-srl="1" href="/dogdrip/1">길거리 싸움</a>
      </li>
      <li class="ed webzine">
        <div class="icon-container">
          <img class="ed webzine-thumbnail" src="/files/thumbnails/2/100x100.crop.jpg"/>
        </div>
        <a class="ed title-link" data-document-srl="2" href="/dogdrip/2">보물상자.jpg</a>
      </li>
      <li class="ed webzine">
        <a class="ed title-link" data-document-srl="3" href="/dogdrip/3">표식 없는 글</a>
      </li>
    </ul>
    """
    items = parse_dogdrip_latest(html, now=NOW)
    assert [item["id"] for item in items] == ["1", "2", "3"]
    assert items[0]["attachment_kind"] == "video"
    assert items[0]["video_url"] == ""
    assert items[1]["attachment_kind"] == "image"
    assert items[2]["attachment_kind"] == "unknown"


def test_theqoo_images_and_youtube_icons_and_absence_is_unknown():
    html = """
    <table>
      <tr>
        <td class="title"><a href="/hot/11">영수증.twt</a><i class="fas fa-images"></i></td>
      </tr>
      <tr>
        <td class="title"><a href="/hot/22">유튜브 퍼온 글</a><i class="fab fa-youtube"></i></td>
      </tr>
      <tr>
        <td class="title"><a href="/hot/33">아이콘 없는 뉴스</a></td>
      </tr>
    </table>
    """
    items = parse_theqoo_hot(html, now=NOW)
    assert [item["attachment_kind"] for item in items] == ["image", "video", "unknown"]
    assert items[1]["video_url"] == ""


def test_ruliweb_title_suffix_is_the_only_listing_marker():
    html = """
    <table>
      <tr class="table_body">
        <td class="subject"><a class="subject_link" href="/best/board/300143/read/1">
          <strong class="text_over">장면.jpg</strong></a></td>
      </tr>
      <tr class="table_body">
        <td class="subject"><a class="subject_link" href="/best/board/300143/read/2">
          <strong class="text_over">살아남는 영상</strong></a></td>
      </tr>
    </table>
    """
    items = parse_ruliweb_best(html, now=NOW)
    assert items[0]["attachment_kind"] == "image"
    # 제목에 '영상' 글자가 있어도 목록 표식이 아니면 unknown. 추정 금지.
    assert items[1]["attachment_kind"] == "unknown"


def test_bobaedream_attach_icon_src_distinguishes_image_video_unknown():
    html = """
    <table>
      <tr>
        <td class="pl14">
          <a class="bsubject" href="/view?code=best&amp;No=1">사진글</a>
          <img alt="첨부파일" class="jpg" src="//image.bobaedream.co.kr/newimg/jpg.gif"/>
        </td>
      </tr>
      <tr>
        <td class="pl14">
          <a class="bsubject" href="/view?code=best&amp;No=2">영상글</a>
          <img alt="첨부파일" class="jpg" src="//image.bobaedream.co.kr/newimg/vod.gif"/>
        </td>
      </tr>
      <tr>
        <td class="pl14">
          <a class="bsubject" href="/view?code=best&amp;No=3">사이트도 모름</a>
          <img alt="첨부파일" class="jpg" src="//image.bobaedream.co.kr/newimg/unknown.gif"/>
        </td>
      </tr>
      <tr>
        <td class="pl14">
          <a class="bsubject" href="/view?code=best&amp;No=4">아이콘 없음</a>
        </td>
      </tr>
    </table>
    """
    items = parse_bobaedream_best(html, now=NOW)
    assert [item["id"] for item in items] == ["1", "2", "3", "4"]
    assert [item["attachment_kind"] for item in items] == ["image", "video", "unknown", "unknown"]
    assert items[1]["source_url"].endswith("No=2")
    assert items[1]["video_url"] == ""


def test_ppomppu_freeboard_reads_image_and_video_labels_not_mobile():
    html = """
    <table>
      <tr class="baseList">
        <td><img class="baseList-img" src="/images/icon_04.png" alt="이미지"/>
          <a class="baseList-title" href="view.php?id=freeboard&amp;no=1"><span>사진</span></a></td>
      </tr>
      <tr class="baseList">
        <td><img class="baseList-img" src="/images/icon_03.png" alt="동영상"/>
          <a class="baseList-title" href="view.php?id=freeboard&amp;no=2"><span>영상</span></a></td>
      </tr>
      <tr class="baseList">
        <td><img class="baseList-img" src="/images/icon_02.png" title="모바일"/>
          <a class="baseList-title" href="view.php?id=freeboard&amp;no=3"><span>모바일만</span></a></td>
      </tr>
    </table>
    """
    items = parse_ppomppu_free(html, now=NOW)
    assert [item["attachment_kind"] for item in items] == ["image", "video", "unknown"]


def test_ppomppu_hot_real_thumb_is_image_noimage_is_unknown():
    html = """
    <table>
      <tr class="baseList">
        <td><a class="baseList-title" href="/zboard/zboard.php?id=freeboard&amp;no=1">썸네일 있는 글</a>
          <img src="//img.ppomppu.co.kr/zboard/data/_thumb/freeboard/3/small_1.jpg"/></td>
        <td class="board_date">09:05:01</td>
      </tr>
      <tr class="baseList">
        <td><a class="baseList-title" href="/zboard/zboard.php?id=freeboard&amp;no=2">빈 썸네일</a>
          <img src="//static.ppomppu.co.kr/www/img/noimage/noimage_60x50.jpg"/></td>
        <td class="board_date">09:05:01</td>
      </tr>
    </table>
    """
    items = parse_ppomppu_hot(html, now=NOW)
    assert items[0]["attachment_kind"] == "image"
    assert items[1]["attachment_kind"] == "unknown"


def test_todayhumor_photo_icon_is_image_and_missing_icon_is_unknown():
    html = """
    <table>
      <tr class="view">
        <td class="subject"><a href="/board/view.php?table=bestofbest&amp;no=1">사진글</a>
          <img src="//www.todayhumor.co.kr/board/images/list_icon_photo.gif"/></td>
      </tr>
      <tr class="view">
        <td class="subject"><a href="/board/view.php?table=bestofbest&amp;no=2">아이콘 없음</a></td>
      </tr>
    </table>
    """
    items = parse_todayhumor_best(html, now=NOW)
    assert items[0]["attachment_kind"] == "image"
    assert items[1]["attachment_kind"] == "unknown"


def test_82cook_photolink_is_not_an_attachment_marker():
    # photolink 는 글 번호 칸의 클래스일 뿐 사진 표식이 아니다.
    html = """
    <table>
      <tr>
        <td class="numbers"><a class="photolink" href="read.php?bn=15&amp;num=1">1834406</a></td>
        <td class="title"><a href="read.php?bn=15&amp;num=1">장원영은 외모로는 깔 수가 없는 단계네요</a></td>
        <td class="regdate numbers" title="2026-08-06 09:03:20"> 09:03:20</td>
        <td class="numbers">42</td>
      </tr>
    </table>
    """
    item = parse_82cook_free(html, now=NOW)[0]
    assert item["attachment_kind"] == "unknown"


def test_title_video_suffix_is_video_even_without_site_icon():
    html = """
    <table><tr class="table_body">
      <td class="subject"><a class="subject_link" href="/best/board/300143/read/9">
        <strong class="text_over">현장.mp4</strong></a></td>
    </tr></table>
    """
    item = parse_ruliweb_best(html, now=NOW)[0]
    assert item["attachment_kind"] == "video"
    assert item["video_url"] == ""
    assert item["source_url"].endswith("/read/9")


def test_absence_of_marker_is_unknown_not_text():
    # 표식이 없다고 text 로 채우면 오늘 반복해 잡은 '모르는 것을 아는 것으로 적기'다.
    html = """
    <table><tr>
      <td class="pl14"><a class="bsubject" href="/view?code=best&amp;No=88">의견글</a></td>
    </tr></table>
    """
    item = parse_bobaedream_best(html, now=NOW)[0]
    assert item["attachment_kind"] == "unknown"
    assert item["attachment_kind"] != "text"


# --- 2026-08-27 소스 확대(0098-C). 실측 목록 구조를 그대로 옮긴 fixture. ---
# accident·dica는 best/freeb와 같은 표를 쓰지만 링크가 rtn 파라미터를 물고 있고,
# 사고 게시판은 vod 아이콘(블랙박스 영상)이 목록의 절반 가까이 온다.

_ACCIDENT_HTML = """
<table><tr itemscope="" itemtype="http://schema.org/Article">
  <td class="c"></td>
  <td class="pl14">
    <a class="bsubject" href="/view?code=accident&amp;No=858985&amp;rtn=%2Fboard%2Fbulletin%2Flist.php%3Fcode%3Daccident" title="양산 이마트 무개념 모녀">양산 이마트 무개념 모녀</a>
    <a href="/view?code=accident&amp;No=858985&amp;cmt=1"><span class="Comment">(<strong class="totreply">78</strong>)</span></a>
    <img alt="첨부파일" class="jpg" src="//image.bobaedream.co.kr/newimg/vod.gif"/>
  </td>
  <td class="author02"><span class="author">글쓴이</span></td>
  <td class="date">08/05</td>
  <td class="recomm">808</td>
  <td class="count">53,586</td>
</tr></table>
"""

_DICA_HTML = """
<table>
  <tr>
    <td class="pl14">
      <a class="bsubject" href="/view?code=dica&amp;No=118421&amp;rtn=%2Fboard%2Fbulletin%2Flist.php%3Fcode%3Ddica" title="마린시티 지하에 방치된 라페라리 ㄷㄷ">마린시티 지하에 방치된 라페라리 ㄷㄷ</a>
      <img alt="첨부파일" class="jpg" src="//image.bobaedream.co.kr/newimg/jpg.gif"/>
    </td>
    <td class="date">08/04</td>
    <td class="recomm">44</td>
    <td class="count">8,126</td>
  </tr>
  <tr>
    <td class="pl14">
      <a class="bsubject" href="/view?code=dica&amp;No=118424">자전거부대는 진짜…. 에효….</a>
    </td>
    <td class="date">09:05</td>
    <td class="recomm">22</td>
    <td class="count">2,871</td>
  </tr>
</table>
"""


def test_parse_bobaedream_accident_reads_incident_board_full_fields():
    # NOW(UTC 00:10)는 KST 09:10. 08/05 00:00 KST → 1일 9시간 10분 = 1990분.
    assert parse_bobaedream_accident(_ACCIDENT_HTML, now=NOW) == [
        {
            "id": "858985",
            "title": "양산 이마트 무개념 모녀",
            "category": "보배드림 교통사고/블박",
            "community_source": "bobae_accident",
            "community_label": "보배드림 사고",
            "source_url": (
                "https://www.bobaedream.co.kr/view?code=accident&No=858985"
                "&rtn=%2Fboard%2Fbulletin%2Flist.php%3Fcode%3Daccident"
            ),
            "link_kind": "publisher_original",
            "published_label": "08/05",
            "age_minutes": 1990,
            "views": 53_586,
            "votes": 808,
            "comments": 78,
            "source_position": 0,
            "signal_source": "직접 목록",
            # 블랙박스 게시판답게 vod 아이콘이 영상으로 읽힌다.
            "attachment_kind": "video",
            "video_url": "",
        }
    ]


def test_parse_bobaedream_dica_reads_photo_board_and_keeps_keys_separate():
    dica = parse_bobaedream_dica(_DICA_HTML, now=NOW)
    assert [item["id"] for item in dica] == ["118421", "118424"]
    first, second = dica
    assert first["community_source"] == "bobae_dica"
    assert first["community_label"] == "보배드림 직찍"
    assert first["category"] == "보배드림 직찍/특종발견"
    assert first["attachment_kind"] == "image"
    # 08/04 00:00 KST → 2일 9시간 10분 = 3430분.
    assert first["age_minutes"] == 3430
    assert first["views"] == 8_126
    assert second["attachment_kind"] == "unknown"
    assert second["age_minutes"] == 5

    # 게시판 코드가 다르면 서로의 목록을 0건으로 내보낸다 — 소스 키 분리.
    assert parse_bobaedream_accident(_DICA_HTML, now=NOW) == []
    assert parse_bobaedream_dica(_ACCIDENT_HTML, now=NOW) == []


def test_parse_clien_board_reads_full_timestamp_and_compact_hits():
    # 2026-08-27 실측 구조: 공지(div.list_item.notice)·홍보 자리(#hongboInfoList)는
    # symph_row 가 아니라 선택자에서 빠지고, 시각 칸에 전체 타임스탬프가 숨어 있다.
    html = """
    <div class="list_board">
      <div class="list_item notice" data-board-sn="1">
        <div class="list_title"><a class="list_subject" href="/service/board/annonce/19238259">
          <span class="subject_fixed">[베타] 토픽 필터 기능을 추가합니다</span></a></div>
        <div class="list_time"><span class="time popover">07-30<span class="timestamp">2026-07-30 15:51:11</span></span></div>
      </div>
      <div class="list_item hongbo" id="hongboInfoList"></div>
      <div class="list_item symph_row" data-board-sn="19254103" data-comment-count="0">
        <div class="list_symph view_symph"><span>7</span></div>
        <div class="list_title"><a class="list_subject" href="/service/board/park/19254103?od=T31&amp;po=0">
          <span class="subject_fixed" title="이해식 의원은 정무감각이 없는걸까요?">이해식 의원은 정무감각이 없는걸까요?</span></a></div>
        <div class="list_hit"><span class="hit">31</span></div>
        <div class="list_time"><span class="time popover">05:02<span class="timestamp">2026-08-06 09:03:53</span></span></div>
      </div>
      <div class="list_item symph_row" data-board-sn="19254102" data-comment-count="12">
        <div class="list_symph view_symph"><span>146</span></div>
        <div class="list_title"><a class="list_subject" href="/service/board/park/19254102?od=T31&amp;po=0">
          <span class="subject_fixed" title="이재명 지지율 떨어지는 이유">이재명 지지율 떨어지는 이유</span></a></div>
        <div class="list_hit"><span class="hit">14.7 k</span></div>
        <div class="list_time"><span class="time popover">08-05<span class="timestamp">2026-08-05 23:00:00</span></span></div>
      </div>
      <div class="list_item symph_row" data-board-sn="19254090">
        <div class="list_symph view_symph"><span>3</span></div>
        <div class="list_title"><a class="list_subject" href="/service/board/park/19254090">
          <span class="subject_fixed">현장 직찍.jpg</span></a></div>
        <div class="list_hit"><span class="hit">258</span></div>
        <div class="list_time"><span class="time popover">07-30</span></div>
      </div>
    </div>
    """

    items = parse_clien_board(html, now=NOW)
    # 공지(data-board-sn=1)와 홍보 자리는 symph_row 가 아니므로 빠진다.
    assert [item["id"] for item in items] == ["19254103", "19254102", "19254090"]

    assert items[0] == {
        "id": "19254103",
        "title": "이해식 의원은 정무감각이 없는걸까요?",
        "category": "클리앙 모두의공원",
        "community_source": "clien_park",
        "community_label": "클리앙 모두의공원",
        "source_url": "https://www.clien.net/service/board/park/19254103?od=T31&po=0",
        "link_kind": "publisher_original",
        "published_label": "2026-08-06 09:03",
        "age_minutes": 7,
        "views": 31,
        "votes": 7,
        "comments": 0,
        "source_position": 0,
        "signal_source": "직접 목록",
        "attachment_kind": "unknown",
        "video_url": "",
    }

    # "14.7 k" 조밀 조회수와 전체 타임스탬프 계산, data-comment-count 댓글 수.
    assert items[1]["views"] == 14_700
    assert items[1]["comments"] == 12
    assert items[1]["votes"] == 146
    assert items[1]["published_label"] == "2026-08-05 23:00"
    assert items[1]["age_minutes"] == 610

    # 타임스탬프가 없으면 보이는 대시 월/일("07-30")로 그날 00:00 KST를 잡는다.
    assert items[2]["published_label"] == "07-30"
    assert items[2]["age_minutes"] == 10_630
    assert items[2]["comments"] == 0
    # 클리앙 목록엔 첨부 아이콘이 없다 — 제목 접미 표식만 영상/사진으로 읽는다.
    assert items[2]["attachment_kind"] == "image"
    assert items[0]["attachment_kind"] == "unknown"


def test_new_sources_roundtrip_through_the_parser_registry():
    # 등록 키로 실제 수집 경로(parse_direct_community_source)를 타고 파싱된다.
    assert parse_direct_community_source("bobae_accident", _ACCIDENT_HTML, now=NOW)[0]["id"] == "858985"
    assert parse_direct_community_source("bobae_dica", _DICA_HTML, now=NOW)[0]["id"] == "118421"
    clien_html = """
    <div class="list_item symph_row" data-board-sn="19254103" data-comment-count="0">
      <div class="list_title"><a class="list_subject" href="/service/board/park/19254103">
        <span class="subject_fixed">제목</span></a></div>
      <div class="list_time"><span class="time popover">05:02<span class="timestamp">2026-08-06 09:03:53</span></span></div>
    </div>
    """
    assert parse_direct_community_source("clien_park", clien_html, now=NOW)[0]["community_source"] == "clien_park"
