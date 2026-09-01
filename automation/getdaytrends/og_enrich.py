"""Safely read publisher-provided ``og:description`` metadata.

Only a bounded ``<head>`` prefix is held in memory. Article bodies are neither
returned nor persisted. Network access is fail-closed to article URL shapes
whose robots policy was already reviewed for this project.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Awaitable, Callable, Iterable
from urllib.parse import parse_qs, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

from source_backoff import SourceBackoff


LOGGER = logging.getLogger(__name__)

MAX_OG_REQUESTS_PER_REFRESH = 8
MIN_DOMAIN_INTERVAL_SECONDS = 2.0
MAX_HEAD_BYTES = 256 * 1024
MAX_DESCRIPTION_CHARS = 2_000
_BLOCKED_STATUSES = {401, 403, 429, 430, 451}
_RULIWEB_BLOCKED_QUERY_KEYS = {"orderby", "range", "custom_list", "cate"}


@dataclass(frozen=True)
class OgRequestEvent:
    """One actual article request. No page text is retained here."""

    host: str
    status: int | None
    outcome: str


@dataclass
class OgEnrichmentReport:
    """Transient descriptions plus a safe-to-expose request audit."""

    descriptions: dict[str, str] = field(default_factory=dict)
    events: list[OgRequestEvent] = field(default_factory=list)
    skipped: Counter[str] = field(default_factory=Counter)

    def public_summary(self) -> dict[str, object]:
        """Return counts and host/status outcomes, never description text."""
        return {
            "requested_count": len(self.events),
            "request_budget": MAX_OG_REQUESTS_PER_REFRESH,
            "enriched_count": len(self.descriptions),
            "skipped": dict(self.skipped),
            "requests": [
                {"host": event.host, "status": event.status, "outcome": event.outcome}
                for event in self.events
            ],
        }


def extract_og_description(head_html: str | bytes) -> str | None:
    """Extract only ``og:description`` from a ``<head>`` document fragment."""
    if not head_html:
        return None
    soup = BeautifulSoup(head_html, "html.parser")
    if soup.head is None:
        return None
    for meta in soup.head.find_all("meta"):
        property_name = str(meta.get("property") or "").strip().casefold()
        if property_name != "og:description":
            continue
        value = " ".join(str(meta.get("content") or "").split())
        return value[:MAX_DESCRIPTION_CHARS] or None
    return None


def og_url_policy(url: str) -> tuple[bool, str]:
    """Fail closed to robots-reviewed publisher article URL shapes.

    The project reviewed these publishers' robots policies on 2026-08-06.
    Restricting each host to its known article route prevents an IssueLink
    redirect from turning this enrichment step into a general-purpose fetcher.
    Sources known to publish no usable OG description are skipped before a
    request, as are publishers whose automated access is blocked.
    """
    parsed = urlparse(str(url or ""))
    if parsed.scheme != "https" or not parsed.hostname:
        return False, "invalid_or_non_https"

    host = parsed.hostname.casefold().rstrip(".")
    bare_host = host[4:] if host.startswith("www.") else host
    path = parsed.path or "/"
    query = parse_qs(parsed.query, keep_blank_values=True)

    if bare_host in {"theqoo.net", "todayhumor.co.kr"}:
        return False, "known_empty_og"
    if bare_host in {
        "fmkorea.com",
        "clien.net",
        "mlbpark.donga.com",
        "pann.nate.com",
        "instiz.net",
    }:
        return False, "robots_or_access_blocked"

    if bare_host == "dogdrip.net":
        segments = [part for part in path.split("/") if part]
        allowed = bool(segments and segments[-1].isdigit())
    elif host == "bbs.ruliweb.com":
        query_keys = {key.casefold() for key in query}
        allowed = "/read/" in path and not (_RULIWEB_BLOCKED_QUERY_KEYS & query_keys)
    elif bare_host == "bobaedream.co.kr":
        allowed = path == "/view" and any(key.casefold() == "no" for key in query)
    elif bare_host == "82cook.com":
        allowed = path == "/entiz/read.php" and "num" in {key.casefold() for key in query}
    elif bare_host == "ppomppu.co.kr":
        allowed = path in {"/zboard/view.php", "/zboard/zboard.php"} and "no" in {
            key.casefold() for key in query
        }
    elif bare_host == "etoland.co.kr":
        # robots.txt: User-agent:* Allow:/, Disallow:/private/ (2026-08-06 재확인).
        # IssueLink가 해석한 게시물 원문 경로만 좁게 허용한다.
        allowed = path.startswith("/b/") and "/view/" in path and not path.startswith("/private/")
    else:
        return False, "unreviewed_host"
    return (True, "allowed_article") if allowed else (False, "unreviewed_path")


def canonical_og_url(url: str) -> str:
    """Use known canonical article URLs without following a network redirect."""
    parsed = urlparse(str(url or ""))
    host = str(parsed.hostname or "").casefold()
    bare_host = host[4:] if host.startswith("www.") else host
    segments = [part for part in parsed.path.split("/") if part]
    if bare_host == "dogdrip.net" and len(segments) == 2 and segments[0] == "dogdrip":
        if segments[1].isdigit():
            return urlunparse(parsed._replace(path=f"/{segments[1]}", query="", fragment=""))
    if bare_host == "etoland.co.kr" and host.startswith("www."):
        return urlunparse(parsed._replace(netloc="etoland.co.kr", fragment=""))
    return str(url)


async def _read_head(response: httpx.Response) -> bytes:
    """Read at most a bounded prefix and stop immediately after ``</head>``."""
    buffer = bytearray()
    chunks = response.aiter_bytes()
    try:
        async for chunk in chunks:
            remaining = MAX_HEAD_BYTES - len(buffer)
            if remaining <= 0:
                break
            buffer.extend(chunk[:remaining])
            lowered = bytes(buffer).lower()
            start = lowered.find(b"</head")
            if start >= 0:
                close = lowered.find(b">", start)
                if close >= 0:
                    del buffer[close + 1 :]
                    break
    finally:
        await chunks.aclose()
    return bytes(buffer)


async def fetch_og_descriptions(
    urls: Iterable[str],
    *,
    source_keys: dict[str, str] | None = None,
    source_backoff: SourceBackoff | None = None,
    client: httpx.AsyncClient | None = None,
    max_requests: int = MAX_OG_REQUESTS_PER_REFRESH,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    now: Callable[[], datetime] | None = None,
) -> OgEnrichmentReport:
    """Fetch OG metadata within the hard request and per-domain budgets.

    Requests are sequential. Different domains need no artificial wait, while
    repeat requests to one domain are separated by at least two seconds. No
    retry or redirect following is performed.
    """
    report = OgEnrichmentReport()
    backoff = source_backoff or SourceBackoff()
    clock = now or (lambda: datetime.now(UTC))
    keys = source_keys or {}
    budget = min(MAX_OG_REQUESTS_PER_REFRESH, max(0, int(max_requests)))
    last_request_at: dict[str, float] = {}
    seen: set[str] = set()
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            follow_redirects=False,
            headers={
                "User-Agent": "GetDayTrends-OGPreview/1.0 (robots-respecting metadata reader)",
                "Accept": "text/html,application/xhtml+xml",
            },
        )

    try:
        for raw_url in urls:
            url = str(raw_url or "").strip()
            if not url or url in seen:
                report.skipped["duplicate_or_empty"] += 1
                continue
            seen.add(url)

            allowed, reason = og_url_policy(url)
            if not allowed:
                report.skipped[reason] += 1
                continue
            if len(report.events) >= budget:
                report.skipped["request_budget"] += 1
                continue

            request_url = canonical_og_url(url)
            request_allowed, request_reason = og_url_policy(request_url)
            if not request_allowed:
                report.skipped[request_reason] += 1
                continue
            host = str(urlparse(request_url).hostname or "").casefold()
            source_key = str(keys.get(url) or host)
            og_backoff_key = f"og:{source_key}"
            current = clock()
            if backoff.should_skip(source_key, current) or backoff.should_skip(
                og_backoff_key, current
            ):
                report.skipped["source_backoff"] += 1
                continue

            previous = last_request_at.get(host)
            if previous is not None:
                wait_seconds = MIN_DOMAIN_INTERVAL_SECONDS - (monotonic() - previous)
                if wait_seconds > 0:
                    await sleep(wait_seconds)
            last_request_at[host] = monotonic()

            status: int | None = None
            outcome = "request_error"
            try:
                async with client.stream(
                    "GET", request_url, timeout=httpx.Timeout(10.0, connect=4.0)
                ) as response:
                    status = response.status_code
                    if status in _BLOCKED_STATUSES:
                        outcome = "blocked"
                        backoff.record_failure(og_backoff_key, clock())
                    elif 300 <= status < 400:
                        outcome = "redirect_not_followed"
                        backoff.record_failure(og_backoff_key, clock())
                    elif status >= 400:
                        outcome = "http_error"
                        backoff.record_failure(og_backoff_key, clock())
                    else:
                        content_type = response.headers.get("content-type", "").casefold()
                        if content_type and "html" not in content_type:
                            outcome = "non_html"
                        else:
                            description = extract_og_description(await _read_head(response))
                            if description:
                                report.descriptions[url] = description
                                outcome = "enriched"
                            else:
                                outcome = "missing_og"
                        backoff.record_success(og_backoff_key)
            except httpx.HTTPError:
                backoff.record_failure(og_backoff_key, clock())

            event = OgRequestEvent(host=host, status=status, outcome=outcome)
            report.events.append(event)
            LOGGER.info(
                "og_enrich_request request=%d/%d host=%s status=%s outcome=%s",
                len(report.events),
                MAX_OG_REQUESTS_PER_REFRESH,
                host,
                status if status is not None else "transport_error",
                outcome,
            )
    finally:
        if owns_client:
            await client.aclose()

    return report
