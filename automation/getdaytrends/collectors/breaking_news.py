"""L0/L1 breaking-news adapters used only for shadow observation.

The adapters return timestamped candidates and source-health metadata.  They do
not score, rank, publish, or mutate product snapshots.  RSS entries are filtered
item-by-item at 120 minutes; the unfiltered timestamp ages remain available for
the Google News/Yonhap comparison ledger.
"""

from __future__ import annotations

import asyncio
import getpass
import hashlib
import html
import json
import os
import re
import statistics
import subprocess
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

try:
    from .google_news import _parse_rss_date
except ImportError:
    from google_news import _parse_rss_date

GOOGLE_NEWS_SEARCH_BASE = "https://news.google.com/rss/search"
YONHAP_RSS_URL = "https://www.yna.co.kr/rss/news.xml"
KMA_BASE_URL = "https://apis.data.go.kr/1360000/WthrWrnInfoService"
KMA_API_KEY_ENV = "KMA_API_KEY"
KMA_KEYCHAIN_SERVICE = "kma-api"
KMA_OPERATIONS = (
    "getWthrWrnList",
    "getWthrWrnMsg",
    "getPwnCd",
    "getPwnStatus",
)
KMA_OPERATION_LABELS = {
    "getWthrWrnList": "기상특보 목록",
    "getWthrWrnMsg": "기상특보 통보문",
    "getPwnCd": "특보 코드",
    "getPwnStatus": "현재 특보 현황",
}

_USER_AGENT = "Mozilla/5.0 (compatible; GetDayTrendsBreakingObserver/1.0)"
_RSS_TIMEOUT = httpx.Timeout(10.0, connect=4.0)
_KMA_TIMEOUT_SECONDS = 10.0
_KST = timezone(timedelta(hours=9))
_MAX_AGE_MINUTES = 120.0
_MAX_FUTURE_SKEW_MINUTES = 10.0


@dataclass(frozen=True, slots=True)
class BreakingNewsItem:
    source: str
    candidate_id: str
    title: str
    extra_text: str
    published_at: datetime | None


@dataclass(frozen=True, slots=True)
class AdapterResult:
    source: str
    available: bool
    results: tuple[BreakingNewsItem, ...] = ()
    sample_ages_minutes: tuple[float, ...] = ()
    error: str = ""
    operation_status: tuple[tuple[str, bool], ...] = ()

    def metrics(self) -> dict[str, int | float | bool | str | None]:
        ages = self.sample_ages_minutes
        return {
            "available": self.available,
            "result_count": len(self.results),
            "sample_n": len(ages),
            "latest_minutes": round(min(ages), 1) if ages else None,
            "median_minutes": round(statistics.median(ages), 1) if ages else None,
            "within_120_count": sum(0 <= age <= _MAX_AGE_MINUTES for age in ages),
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class _ParsedRssItem:
    item: BreakingNewsItem
    age_minutes: float


def _one_line(value: object) -> str:
    return " ".join(str(value or "").split())


def _plain_text(value: object, *, limit: int = 600) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", html.unescape(str(value or "")))
    return _one_line(without_tags)[:limit]


def _normalized_datetime(value: datetime) -> datetime:
    timestamp = value if value.tzinfo else value.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)


def _age_minutes(published_at: datetime, observed_at: datetime) -> float | None:
    age = (_normalized_datetime(observed_at) - _normalized_datetime(published_at)).total_seconds() / 60
    if age < -_MAX_FUTURE_SKEW_MINUTES:
        return None
    return max(0.0, age)


def _candidate_id(source: str, identity: str) -> str:
    return hashlib.sha256(f"{source}|{identity}".encode()).hexdigest()[:24]


def _parse_rss_payload(
    payload: bytes,
    *,
    source: str,
    observed_at: datetime,
    context: str = "",
    max_items: int | None = None,
) -> list[_ParsedRssItem]:
    root = ET.fromstring(payload)
    elements = root.findall(".//item")
    if max_items is not None:
        elements = elements[:max_items]

    parsed: list[_ParsedRssItem] = []
    for element in elements:
        title = _one_line(element.findtext("title"))
        published = _parse_rss_date(element.findtext("pubDate"))
        if not title or published is None:
            continue
        published = _normalized_datetime(published)
        age = _age_minutes(published, observed_at)
        if age is None:
            continue
        link = _one_line(element.findtext("link"))
        publisher = _one_line(element.findtext("source"))
        description = _plain_text(element.findtext("description"), limit=400)
        extra_text = _one_line(" · ".join(value for value in (context, publisher, description) if value))[:600]
        identity = link or f"{title}|{published.isoformat()}"
        parsed.append(
            _ParsedRssItem(
                item=BreakingNewsItem(
                    source=source,
                    candidate_id=_candidate_id(source, identity),
                    title=title,
                    extra_text=extra_text,
                    published_at=published,
                ),
                age_minutes=age,
            )
        )
    return parsed


async def _get_rss(client: httpx.AsyncClient, url: str) -> bytes:
    response = await client.get(url, headers={"User-Agent": _USER_AGENT}, timeout=_RSS_TIMEOUT)
    response.raise_for_status()
    return bytes(response.content)


def _google_news_url(keyword: str, *, hl: str, gl: str, ceid: str) -> str:
    encoded = urllib.parse.quote(keyword)
    return f"{GOOGLE_NEWS_SEARCH_BASE}?q={encoded}&hl={hl}&gl={gl}&ceid={ceid}"


async def _fetch_google_keyword(
    client: httpx.AsyncClient,
    keyword: str,
    observed_at: datetime,
) -> tuple[bool, list[_ParsedRssItem]]:
    locales = (("ko", "KR", "KR:ko"), ("en-US", "US", "US:en"))
    responses = await asyncio.gather(
        *(_get_rss(client, _google_news_url(keyword, hl=hl, gl=gl, ceid=ceid)) for hl, gl, ceid in locales),
        return_exceptions=True,
    )
    available = False
    parsed: list[_ParsedRssItem] = []
    seen_titles: set[str] = set()
    for payload in responses:
        if isinstance(payload, BaseException):
            continue
        try:
            observations = _parse_rss_payload(
                payload,
                source="google-news-rss",
                observed_at=observed_at,
                context=f"검색어 {keyword}",
                max_items=5,
            )
        except ET.ParseError:
            continue
        available = True
        for observation in observations:
            title_key = observation.item.title.casefold()
            if title_key in seen_titles:
                continue
            seen_titles.add(title_key)
            parsed.append(observation)
    return available, parsed


async def fetch_google_news_breaking(
    client: httpx.AsyncClient,
    keywords: Iterable[str],
    *,
    observed_at: datetime | None = None,
    max_keywords: int = 8,
) -> AdapterResult:
    """Measure the existing Google News path and return only <=120m rows."""
    now = _normalized_datetime(observed_at or datetime.now(UTC))
    selected: list[str] = []
    seen_keywords: set[str] = set()
    for raw in keywords:
        keyword = _one_line(raw)
        key = keyword.casefold()
        if not keyword or key in seen_keywords:
            continue
        selected.append(keyword)
        seen_keywords.add(key)
        if len(selected) >= max(1, max_keywords):
            break
    if not selected:
        return AdapterResult(source="google-news-rss", available=False, error="no_keywords")

    batches = await asyncio.gather(
        *(_fetch_google_keyword(client, keyword, now) for keyword in selected),
        return_exceptions=True,
    )
    available = False
    sample_ages: list[float] = []
    fresh: dict[str, BreakingNewsItem] = {}
    for batch in batches:
        if isinstance(batch, BaseException):
            continue
        batch_available, observations = batch
        available = available or batch_available
        for observation in observations:
            sample_ages.append(observation.age_minutes)
            if observation.age_minutes <= _MAX_AGE_MINUTES:
                fresh.setdefault(observation.item.candidate_id, observation.item)
    return AdapterResult(
        source="google-news-rss",
        available=available,
        results=tuple(fresh.values()),
        sample_ages_minutes=tuple(sample_ages),
        error="" if available else "request_or_parse_failed",
    )


async def fetch_yonhap_breaking(
    client: httpx.AsyncClient,
    *,
    observed_at: datetime | None = None,
) -> AdapterResult:
    """Fetch Yonhap directly and filter every item by its own ``pubDate``."""
    now = _normalized_datetime(observed_at or datetime.now(UTC))
    try:
        payload = await _get_rss(client, YONHAP_RSS_URL)
        observations = _parse_rss_payload(
            payload,
            source="yonhap-rss",
            observed_at=now,
            context="연합뉴스 직접 RSS",
        )
    except (httpx.HTTPError, ET.ParseError):
        return AdapterResult(source="yonhap-rss", available=False, error="request_or_parse_failed")

    fresh = tuple(observation.item for observation in observations if observation.age_minutes <= _MAX_AGE_MINUTES)
    return AdapterResult(
        source="yonhap-rss",
        available=True,
        results=fresh,
        sample_ages_minutes=tuple(observation.age_minutes for observation in observations),
    )


def load_kma_service_key() -> str:
    """Read an explicit environment override, otherwise the approved Keychain item."""
    environment_value = os.getenv(KMA_API_KEY_ENV, "").strip()
    if environment_value:
        return environment_value
    account = os.getenv("USER", "").strip() or getpass.getuser()
    try:
        result = subprocess.run(
            [
                "/usr/bin/security",
                "find-generic-password",
                "-s",
                KMA_KEYCHAIN_SERVICE,
                "-a",
                account,
                "-w",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _default_kma_request_json(url: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed HTTPS base
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def _parse_kma_datetime(value: object) -> datetime | None:
    raw = _one_line(value)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        parsed = None
    if parsed is not None:
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=_KST)
        return parsed.astimezone(UTC)

    digits = re.sub(r"\D", "", raw)
    formats = {14: "%Y%m%d%H%M%S", 12: "%Y%m%d%H%M", 10: "%Y%m%d%H", 8: "%Y%m%d"}
    date_format = formats.get(len(digits))
    if date_format is None:
        return None
    try:
        return datetime.strptime(digits, date_format).replace(tzinfo=_KST).astimezone(UTC)
    except ValueError:
        return None


def _kma_published_at(item: dict[str, Any]) -> datetime | None:
    priorities = (
        "tmFc",
        "tmEf",
        "startTime",
        "effectTime",
        "regTm",
        "regTime",
        "announceTime",
    )
    for key in priorities:
        if key in item:
            parsed = _parse_kma_datetime(item.get(key))
            if parsed is not None:
                return parsed
    for key, value in item.items():
        lowered = str(key).casefold()
        if "time" in lowered or lowered.startswith("tm"):
            parsed = _parse_kma_datetime(value)
            if parsed is not None:
                return parsed
    return None


def _kma_title(operation: str, item: dict[str, Any]) -> tuple[str, str]:
    label = KMA_OPERATION_LABELS[operation]
    title_fields = (
        "title",
        "t6",
        "area",
        "regName",
        "warnVar",
        "wrn",
        "lvl",
        "stress",
        "command",
        "cmd",
    )
    selected: list[str] = []
    for key in title_fields:
        value = item.get(key)
        if isinstance(value, (str, int, float)):
            normalized = _plain_text(value, limit=360)
            if normalized and normalized not in selected:
                selected.append(normalized)
        if len(selected) >= 4:
            break
    detail = " · ".join(selected)
    title = f"[기상청 {label}] {detail}" if detail else f"[기상청 {label}]"
    return title[:500], f"operation={operation}" + (f" · {detail}" if detail else "")


def _kma_response_items(payload: dict[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
    response = payload.get("response")
    if not isinstance(response, dict):
        return False, []
    header = response.get("header")
    if not isinstance(header, dict) or _one_line(header.get("resultCode")) not in {"0", "00"}:
        return False, []
    body = response.get("body")
    if not isinstance(body, dict):
        return True, []
    items_node = body.get("items")
    if not isinstance(items_node, dict):
        return True, []
    raw_items = items_node.get("item")
    if isinstance(raw_items, dict):
        return True, [raw_items]
    if isinstance(raw_items, list):
        return True, [item for item in raw_items if isinstance(item, dict)]
    return True, []


class KmaWeatherAdapter:
    """Fetch the four approved KMA warning operations without logging the key."""

    def __init__(
        self,
        *,
        key_loader: Callable[[], str] = load_kma_service_key,
        request_json: Callable[[str, float], dict[str, Any]] = _default_kma_request_json,
    ) -> None:
        self._key_loader = key_loader
        self._request_json = request_json

    @staticmethod
    def _build_url(operation: str, service_key: str, observed_at: datetime) -> str:
        local_date = _normalized_datetime(observed_at).astimezone(_KST).date()
        params = {
            "pageNo": 1,
            "numOfRows": 100,
            "dataType": "JSON",
            "stnId": 108,
            "fromTmFc": (local_date - timedelta(days=1)).strftime("%Y%m%d"),
            "toTmFc": local_date.strftime("%Y%m%d"),
        }
        # The approved key is already URL encoded.  Concatenate it verbatim and
        # encode only the non-secret parameters to avoid % -> %25 corruption.
        return f"{KMA_BASE_URL}/{operation}?serviceKey={service_key}&{urllib.parse.urlencode(params)}"

    async def _fetch_operation(
        self,
        operation: str,
        service_key: str,
        observed_at: datetime,
    ) -> tuple[str, bool, list[dict[str, Any]]]:
        url = self._build_url(operation, service_key, observed_at)
        try:
            payload = await asyncio.to_thread(self._request_json, url, _KMA_TIMEOUT_SECONDS)
        except Exception:
            return operation, False, []
        available, items = _kma_response_items(payload)
        return operation, available, items

    async def collect(self, *, observed_at: datetime | None = None) -> AdapterResult:
        now = _normalized_datetime(observed_at or datetime.now(UTC))
        try:
            service_key = self._key_loader().strip()
        except Exception:
            service_key = ""
        if not service_key:
            return AdapterResult(source="kma-weather", available=False, error="key_unavailable")

        operation_results = await asyncio.gather(
            *(self._fetch_operation(operation, service_key, now) for operation in KMA_OPERATIONS)
        )
        statuses: list[tuple[str, bool]] = []
        sample_ages: list[float] = []
        results: dict[str, BreakingNewsItem] = {}
        for operation, available, raw_items in operation_results:
            statuses.append((operation, available))
            if not available:
                continue
            for raw_item in raw_items:
                published_at = _kma_published_at(raw_item)
                if published_at is not None:
                    age = _age_minutes(published_at, now)
                    if age is None:
                        continue
                    sample_ages.append(age)
                    if age > _MAX_AGE_MINUTES:
                        continue
                title, extra_text = _kma_title(operation, raw_item)
                canonical = json.dumps(raw_item, ensure_ascii=False, sort_keys=True, default=str)
                source = f"kma:{operation}"
                candidate = BreakingNewsItem(
                    source=source,
                    candidate_id=_candidate_id(source, canonical),
                    title=title,
                    extra_text=extra_text[:600],
                    published_at=published_at,
                )
                results.setdefault(candidate.candidate_id, candidate)

        any_available = any(available for _, available in statuses)
        return AdapterResult(
            source="kma-weather",
            available=any_available,
            results=tuple(results.values()),
            sample_ages_minutes=tuple(sample_ages),
            error="" if any_available else "all_operations_failed",
            operation_status=tuple(statuses),
        )


__all__ = [
    "AdapterResult",
    "BreakingNewsItem",
    "GOOGLE_NEWS_SEARCH_BASE",
    "KMA_API_KEY_ENV",
    "KMA_BASE_URL",
    "KMA_OPERATIONS",
    "KmaWeatherAdapter",
    "YONHAP_RSS_URL",
    "fetch_google_news_breaking",
    "fetch_yonhap_breaking",
    "load_kma_service_key",
]
