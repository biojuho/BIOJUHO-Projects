"""OG metadata enrichment safety and request-budget contracts."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from og_enrich import (  # noqa: E402
    MAX_OG_REQUESTS_PER_REFRESH,
    MIN_DOMAIN_INTERVAL_SECONDS,
    canonical_og_url,
    extract_og_description,
    fetch_og_descriptions,
    og_url_policy,
)
from source_backoff import SourceBackoff  # noqa: E402


def _og_page(value: str = "남편이 축의금을 몰래 가로챈 사연") -> str:
    return (
        "<html><head><title>제목</title>"
        f'<meta property="og:description" content="{value}">'
        "</head><body>저장하거나 출력하면 안 되는 본문 전체</body></html>"
    )


def test_extracts_only_og_description_from_head():
    html = (
        '<html><head><meta name="description" content="일반 설명">'
        '<meta property="OG:DESCRIPTION" content="  공유용   요약  "></head>'
        '<body><meta property="og:description" content="본문 속 가짜 태그"></body></html>'
    )

    assert extract_og_description(html) == "공유용 요약"
    assert extract_og_description("<body><meta property='og:description' content='본문'></body>") is None


def test_robots_reviewed_routes_are_allowlisted_and_unknowns_fail_closed():
    assert og_url_policy("https://www.dogdrip.net/dogdrip/123")[0] is True
    assert og_url_policy("https://bbs.ruliweb.com/community/board/300/read/456")[0] is True
    assert og_url_policy("https://bbs.ruliweb.com/community/board/300/read/456?orderby=readcount")[0] is False
    assert og_url_policy("https://www.fmkorea.com/123")[0] is False
    assert og_url_policy("https://www.ppomppu.co.kr/zboard/zboard.php?id=freeboard&no=1")[0] is True
    assert og_url_policy("https://www.etoland.co.kr/b/etohumor07/view/story-123")[0] is True
    assert og_url_policy("https://www.etoland.co.kr/private/story-123")[0] is False
    assert og_url_policy("https://unknown.example/post/1") == (False, "unreviewed_host")


def test_dogdrip_listing_url_is_canonicalized_without_following_a_redirect():
    assert canonical_og_url(
        "https://www.dogdrip.net/dogdrip/123?page=1&sort_index=popular"
    ) == "https://www.dogdrip.net/123"
    assert canonical_og_url(
        "https://www.etoland.co.kr/b/etohumor07/view/story-123"
    ) == "https://etoland.co.kr/b/etohumor07/view/story-123"


@pytest.mark.asyncio
async def test_hard_caps_requests_at_eight_and_spaces_one_domain_by_two_seconds():
    urls = [f"https://www.dogdrip.net/dogdrip/{number}" for number in range(9)]
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(200, headers={"content-type": "text/html"}, text=_og_page())

    fake_time = [0.0]
    waits: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        waits.append(seconds)
        fake_time[0] += seconds

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        report = await fetch_og_descriptions(
            urls,
            client=client,
            sleep=fake_sleep,
            monotonic=lambda: fake_time[0],
        )

    assert len(requested) == MAX_OG_REQUESTS_PER_REFRESH
    assert report.public_summary()["requested_count"] == MAX_OG_REQUESTS_PER_REFRESH
    assert report.skipped["request_budget"] == 1
    assert waits == [MIN_DOMAIN_INTERVAL_SECONDS] * (MAX_OG_REQUESTS_PER_REFRESH - 1)


@pytest.mark.asyncio
async def test_blocked_response_is_not_retried_and_enters_source_backoff():
    urls = [
        "https://www.bobaedream.co.kr/view?code=best&No=1",
        "https://www.bobaedream.co.kr/view?code=best&No=2",
    ]
    requested = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requested
        requested += 1
        return httpx.Response(403, text="blocked")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        report = await fetch_og_descriptions(
            urls,
            source_keys={url: "bobae" for url in urls},
            source_backoff=SourceBackoff(),
            client=client,
        )

    assert requested == 1
    assert report.events[0].outcome == "blocked"
    assert report.skipped["source_backoff"] == 1


@pytest.mark.asyncio
async def test_blocked_robots_and_known_empty_sources_make_no_request():
    requested = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requested
        requested += 1
        return httpx.Response(200, text=_og_page())

    urls = [
        "https://www.fmkorea.com/123",
        "https://www.clien.net/service/board/park/456",
        "https://theqoo.net/hot/789",
        "https://unknown.example/post/1",
    ]
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        report = await fetch_og_descriptions(urls, client=client)

    assert requested == 0
    assert report.events == []
    assert report.skipped["robots_or_access_blocked"] == 2
    assert report.skipped["known_empty_og"] == 1
    assert report.skipped["unreviewed_host"] == 1


@pytest.mark.asyncio
async def test_public_audit_never_contains_description_or_body_text():
    url = "https://www.ppomppu.co.kr/zboard/view.php?id=freeboard&no=1"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html"}, text=_og_page())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        report = await fetch_og_descriptions([url], client=client)

    assert report.descriptions[url] == "남편이 축의금을 몰래 가로챈 사연"
    audit_text = repr(report.public_summary())
    assert "축의금" not in audit_text
    assert "본문 전체" not in audit_text
