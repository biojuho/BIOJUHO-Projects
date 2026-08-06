"""Tests for publisher-original community listing parsers."""

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from direct_community_sources import (  # noqa: E402
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
