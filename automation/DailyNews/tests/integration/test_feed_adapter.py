"""Integration tests for FeedAdapter — uses respx to mock httpx at transport level."""

from __future__ import annotations

import httpx
import pytest
import respx
from antigravity_mcp.integrations.feed_adapter import FeedAdapter

# Minimal valid RSS 2.0 feed
_RSS_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>https://example.com</link>
    <description>Test</description>
    <item>
      <title>Article One</title>
      <link>https://example.com/article-1</link>
      <description>Summary of article one.</description>
      <pubDate>Mon, 04 Mar 2026 06:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Article Two</title>
      <link>https://example.com/article-2</link>
      <description>Summary of article two.</description>
      <pubDate>Mon, 04 Mar 2026 07:30:00 +0000</pubDate>
    </item>
  </channel>
</rss>"""

_FEED_URL = "https://example.com/feed.rss"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_entries_returns_parsed_entries():
    respx.get(_FEED_URL).mock(return_value=httpx.Response(200, text=_RSS_SAMPLE))
    adapter = FeedAdapter()
    entries = await adapter.fetch_entries(_FEED_URL)
    assert len(entries) == 2
    assert entries[0].title == "Article One"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_entries_304_returns_empty():
    respx.get(_FEED_URL).mock(return_value=httpx.Response(304, text=""))
    adapter = FeedAdapter()
    entries = await adapter.fetch_entries(_FEED_URL)
    assert entries == []


@pytest.mark.asyncio
@respx.mock
async def test_fetch_entries_retries_on_network_error():
    """Should retry on transient errors and succeed on the second attempt."""
    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise httpx.NetworkError("connection reset")
        return httpx.Response(200, text=_RSS_SAMPLE)

    respx.get(_FEED_URL).mock(side_effect=side_effect)
    adapter = FeedAdapter()
    entries = await adapter.fetch_entries(_FEED_URL)
    assert len(entries) == 2
    assert call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_fetch_entries_retries_on_retryable_http_status():
    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            return httpx.Response(503, text="service unavailable", request=request)
        return httpx.Response(200, text=_RSS_SAMPLE, request=request)

    respx.get(_FEED_URL).mock(side_effect=side_effect)
    adapter = FeedAdapter()
    entries = await adapter.fetch_entries(_FEED_URL)

    assert len(entries) == 2
    assert call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_fetch_entries_raises_after_max_retries():
    """Should raise after exhausting all retries."""
    respx.get(_FEED_URL).mock(side_effect=httpx.NetworkError("persistent failure"))
    adapter = FeedAdapter()
    with pytest.raises(httpx.NetworkError):
        await adapter.fetch_entries(_FEED_URL)


@pytest.mark.asyncio
@respx.mock
async def test_fetch_entries_sends_etag_header(tmp_path):
    from antigravity_mcp.state.store import PipelineStateStore

    store = PipelineStateStore(path=tmp_path / "state.db")
    store.put_feed_etag(_FEED_URL, etag='"abc123"', last_modified=None)

    received_headers: dict[str, str] = {}

    def capture(request):
        received_headers.update(dict(request.headers))
        return httpx.Response(304, text="")

    respx.get(_FEED_URL).mock(side_effect=capture)
    adapter = FeedAdapter(state_store=store)
    await adapter.fetch_entries(_FEED_URL)
    assert received_headers.get("if-none-match") == '"abc123"'
