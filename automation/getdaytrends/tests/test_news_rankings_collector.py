"""뉴스 랭킹(네이트·줌)·다음 실시간 트렌드 수집기 파서 테스트."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors.daum_realtime import _parse_daum_realtime_html  # noqa: E402
from collectors.news_rankings import (  # noqa: E402
    _decode_body,
    _dedupe_across_portals,
    _parse_nate_ranking_html,
    _parse_zum_news_html,
)

_NATE_HTML = """\
<html><body>
<div class="postRankSubjectList">
  <dl class="mduRank rank1"><dt><em>1</em></dt><dd><span class="noupdown">-<i>순위변동없음</i></span></dd></dl>
  <div class="mlt01">
    <a href="//news.nate.com/view/20260816n07086?mid=n1008" class="lt1">
      <h2 class="tit">김민희, 하루 만에 확 달라진 얼굴 &quot;화제&quot;</h2>
    </a><span class="medium">MK스포츠<em>2026-08-16</em></span>
  </div>
  <ul class="mduSubject">
    <li>
      <dl class="mduRank rank6"><dt><em>6</em></dt><dd><span class="up">상승</span></dd></dl>
      <a href="//news.nate.com/view/20260816n02007?mid=n1006"><h2>인천 아파트서 6살 아이 추락해 사망</h2></a>
      <span class="medium">연합뉴스</span>
    </li>
    <li>
      <dl class="mduRank rank7"><dt><em>7</em></dt><dd></dd></dl>
      <a href="//news.nate.com/view/20260816n01526"><h2>프라이팬에 9차례 난타…가해자 불구속</h2></a>
      <span class="medium">JTBC</span>
    </li>
  </ul>
</div>
<div class="sidebar">
  <a href="//news.nate.com/view/other1"><h2>다른 섹션 광고성 제목</h2></a>
</div>
</body></html>
"""

_ZUM_HTML = """\
<html><body>
<a class="item" data-recommender="" href="https://www.segye.com/newsView/1">
  <div class="thumb"><img src="x.jpg" alt=""></div>
  <h2 class="title" title="‘공중부양까지’…9년째 못 나온 ‘테슬라 로드스터’, 뜰까">‘공중부양까지’…9년째 못 나온 ‘테슬라 로드스터’, 뜰까</h2>
</a>
<!--<span class="logo"><img src="x.png" alt=""></span>-->
<span class="media">
  <a href="http://www.segye.com/"> </a>세계일보
</span>
<h2>정치</h2>
<a class="item" href="https://sports.example.com/a">
  <h2 class="title">日 골키퍼 스즈키, PSG 이적 무산</h2>
</a>
<span class="media">스포츠경향</span>
</body></html>
"""

_DAUM_HTML = """\
<html><body>
<script>
window.__x = {"slot":{"attributes":{"landingUrl":"https://search.daum.net/search?w=tot&DA=RT1&rtmaxcoll=AIO,NNS,DNS&q="},
"contents":{"data":{"updatedAt":"2026-08-16T17:30:01.801+09:00","keywords":[
{"keyword":"이동하 소진 결혼","rank":2,"displayRank":1,"status":"-1","tiara":{"layer2":"REALTIME_TREND_TOP"}},
{"keyword":"테슬라 \\"로드스터\\" 발표","rank":4,"displayRank":2,"status":"0","tiara":{}},
{"keyword":"윤가이 장기하 연애","rank":32,"displayRank":3,"status":"2","tiara":{}}
]}}};
</script>
</body></html>
"""


def test_nate_parser_extracts_rank_title_link_and_publisher():
    items = _parse_nate_ranking_html(_NATE_HTML, limit=10)
    assert [item["rank"] for item in items] == [1, 6, 7]
    assert items[0]["title"] == '김민희, 하루 만에 확 달라진 얼굴 "화제"'
    assert items[0]["url"].startswith("https://news.nate.com/view/20260816n07086")
    assert items[0]["publisher"] == "MK스포츠"
    assert items[0]["source"] == "네이트 뉴스 랭킹"
    assert items[1]["publisher"] == "연합뉴스"
    assert items[2]["publisher"] == "JTBC"


def test_nate_decode_falls_back_from_utf8_to_euc_kr():
    raw = _NATE_HTML.encode("euc-kr")
    assert _decode_body(raw) == _NATE_HTML


def test_zum_parser_extracts_title_link_and_publisher_ignoring_comments():
    items = _parse_zum_news_html(_ZUM_HTML, limit=10)
    assert len(items) == 2
    assert items[0]["title"] == "‘공중부양까지’…9년째 못 나온 ‘테슬라 로드스터’, 뜰까"
    assert items[0]["url"] == "https://www.segye.com/newsView/1"
    assert items[0]["publisher"] == "세계일보"
    assert items[0]["source"] == "줌 뉴스"
    assert items[1]["publisher"] == "스포츠경향"


def test_daum_parser_extracts_updated_at_keywords_status_and_landing_url():
    updated_at, items = _parse_daum_realtime_html(_DAUM_HTML, limit=10)
    assert updated_at == "2026-08-16T17:30:01.801+09:00"
    assert [item["keyword"] for item in items] == [
        "이동하 소진 결혼",
        '테슬라 "로드스터" 발표',
        "윤가이 장기하 연애",
    ]
    assert [item["status"] for item in items] == [-1, 0, 2]
    assert [item["display_rank"] for item in items] == [1, 2, 3]
    assert items[0]["url"].startswith("https://search.daum.net/search?w=tot&DA=RT1")
    assert "q=" in items[0]["url"]
    assert items[0]["source"] == "다음 실시간 트렌드"


def test_dedupe_across_portals_keeps_first_occurrence():
    items = _dedupe_across_portals(
        [
            {
                "title": "‘테슬라 로드스터’, 이번엔 뜰까",
                "url": "https://one.example/a",
                "source": "네이트 뉴스 랭킹",
                "rank": 3,
            },
            {
                "title": "테슬라 로드스터, 이번엔 뜰까",
                "url": "https://two.example/b",
                "source": "줌 뉴스",
                "rank": 1,
            },
            {
                "title": "다른 사건 제목",
                "url": "https://three.example/c",
                "source": "줌 뉴스",
                "rank": 2,
            },
        ]
    )
    assert [item["title"] for item in items] == [
        "‘테슬라 로드스터’, 이번엔 뜰까",
        "다른 사건 제목",
    ]


def test_async_news_rankings_keeps_both_portals_when_nate_fills_limit():
    """포털별 cap은 지키되, 네이트가 limit을 채워도 줌 결과를 자르지 않는다."""
    import asyncio

    import httpx

    nate_small = """
    <dl class="mduRank rank1"><dt><em>1</em></dt></dl>
    <a href="//news.nate.com/view/a1" class="lt1"><h2 class="tit">네이트 제목 1</h2></a>
    <dl class="mduRank rank2"><dt><em>2</em></dt></dl>
    <a href="//news.nate.com/view/a2" class="lt1"><h2 class="tit">네이트 제목 2</h2></a>
    <dl class="mduRank rank3"><dt><em>3</em></dt></dl>
    <a href="//news.nate.com/view/a3" class="lt1"><h2 class="tit">네이트 제목 3</h2></a>
    """
    zum_small = """
    <a class="item" href="https://zum.example.com/1">
      <h2 class="title">줌 제목 1</h2>
    </a><span class="media">줌매체</span>
    <a class="item" href="https://zum.example.com/2">
      <h2 class="title">줌 제목 2</h2>
    </a><span class="media">줌매체2</span>
    """

    from collectors.news_rankings import _async_fetch_news_rankings

    async def run():
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "news.nate.com":
                return httpx.Response(200, text=nate_small)
            return httpx.Response(200, text=zum_small)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as session:
            items = await _async_fetch_news_rankings(session, limit=2)
        return items

    items = asyncio.run(run())
    assert [item["title"] for item in items] == [
        "네이트 제목 1",
        "네이트 제목 2",
        "줌 제목 1",
        "줌 제목 2",
    ]


def test_nate_and_zum_timestamp_and_ranking_tracking():
    from collectors.news_rankings import _reset_ranking_history

    _reset_ranking_history()
    # 1회차 파싱
    items1 = _parse_nate_ranking_html(_NATE_HTML, limit=10, now_iso="2026-08-17T09:00:00+00:00")
    assert items1[0]["source_published_at"] == "2026-08-16T00:00:00+09:00"
    assert items1[0]["age_basis"] == "source_published_at"
    assert items1[0]["first_seen_at"] == "2026-08-17T09:00:00+00:00"
    assert items1[0]["is_new"] is True
    assert items1[0]["rank_change"] is None
    assert items1[0]["status"] == "new"

    # 2회차 파싱: 같은 URL이지만 순위가 6위 -> 2위로 상승
    nate_html_round2 = """\
    <html><body>
    <div class="postRankSubjectList">
      <dl class="mduRank rank2"><dt><em>2</em></dt></dl>
      <div class="mlt01">
        <a href="//news.nate.com/view/20260816n02007?mid=n1006" class="lt1">
          <h2 class="tit">인천 아파트서 6살 아이 추락해 사망</h2>
        </a><span class="medium">연합뉴스<em>2026-08-16</em></span>
      </div>
    </div>
    </body></html>
    """
    items2 = _parse_nate_ranking_html(nate_html_round2, limit=10, now_iso="2026-08-17T09:10:00+00:00")
    assert len(items2) == 1
    # 1회차에서 6위였던 기사가 2위로 상승 -> diff = 6 - 2 = +4
    assert items2[0]["is_new"] is False
    assert items2[0]["rank_change"] == 4
    assert items2[0]["status"] == "+4"
    assert items2[0]["first_seen_at"] == "2026-08-17T09:00:00+00:00"
    assert items2[0]["observed_at"] == "2026-08-17T09:10:00+00:00"


def test_zum_parser_extracts_published_at_from_url():
    from collectors.news_rankings import _reset_ranking_history

    _reset_ranking_history()
    zum_html = """\
    <a class="item" href="https://www.ytn.co.kr/_ln/0104_202608171048529458">
      <h2 class="title">트럼프 "한미 연합훈련 축소"</h2>
    </a><span class="media">YTN</span>
    """
    items = _parse_zum_news_html(zum_html, limit=10)
    assert len(items) == 1
    assert items[0]["source_published_at"] == "2026-08-17T10:48:52+09:00"
    assert items[0]["age_basis"] == "source_published_at"
    assert items[0]["is_new"] is True


def test_daum_parser_handles_new_status_and_timestamps():
    from collectors.daum_realtime import _reset_daum_history

    _reset_daum_history()
    daum_html_with_new = """\
    <html><body>
    <script>
    window.__x = {"slot":{"attributes":{"landingUrl":"https://search.daum.net/search?q="},
    "contents":{"data":{"updatedAt":"2026-08-17T18:29:15.478+09:00","keywords":[
    {"keyword":"삼성전자 실명제","rank":6,"displayRank":3,"status":"new"},
    {"keyword":"인니 강진","rank":10,"displayRank":4,"status":"-6"},
    {"keyword":"마르코 배정남","rank":1,"displayRank":1,"status":"0"}
    ]}}};
    </script>
    </body></html>
    """
    updated_at, items = _parse_daum_realtime_html(
        daum_html_with_new, limit=10, now_iso="2026-08-17T09:30:00+00:00"
    )
    assert updated_at == "2026-08-17T18:29:15.478+09:00"
    assert len(items) == 3
    # "new" status 항목이 누락 없이 파싱됨
    assert items[0]["keyword"] == "삼성전자 실명제"
    assert items[0]["status"] == "new"
    assert items[0]["raw_status"] == "new"
    assert items[0]["is_new"] is True
    assert items[0]["source_published_at"] == "2026-08-17T18:29:15.478+09:00"
    assert items[0]["first_seen_at"] == "2026-08-17T09:30:00+00:00"
    assert items[0]["age_basis"] == "source_published_at"

    # "-6" status 항목
    assert items[1]["keyword"] == "인니 강진"
    assert items[1]["status"] == -6
    assert items[1]["raw_status"] == "-6"

    # "0" status 항목
    assert items[2]["keyword"] == "마르코 배정남"
    assert items[2]["status"] == 0
    assert items[2]["raw_status"] == "0"


def test_sources_fallback_explicit_indicator_bidirectional():
    from collectors.sources import _fallback_trends
    from models import RawTrend, TrendSource

    # 1. Fallback인 경우 표식 부착 확인
    fallback_items = _fallback_trends(reason="simulated_failure")
    assert len(fallback_items) == 5
    for item in fallback_items:
        assert item.extra.get("is_fallback") is True
        assert item.extra.get("fallback_reason") == "simulated_failure"
        assert item.extra.get("_is_fallback") is True

    # 2. 정상 수집된 RawTrend인 경우 표식 없음 (양방향 검증)
    normal_item = RawTrend(
        name="정상 트렌드",
        source=TrendSource.GETDAYTRENDS,
        volume="10K",
    )
    assert normal_item.extra.get("is_fallback") is not True
    assert "fallback_reason" not in normal_item.extra
