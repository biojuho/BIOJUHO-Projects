"""Multi-source trend signal collectors for Real-Time Signal Arbitrage.

Collects trending signals from multiple sources:
  - Google Trends RSS (free, no auth)
  - Reddit Rising JSON (unauthenticated HTTP feed)
  - GetDayTrends DB (cross-project SQLite bridge)

Each collector implements the SignalSource protocol and returns
normalised TrendSignal objects for downstream cross-source scoring.

Required env vars (optional — graceful fallback when missing):
  GDT_DB_PATH   — Path to GetDayTrends SQLite database
"""

from __future__ import annotations

import logging
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, runtime_checkable

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain Models
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class TrendSignal:
    """A single trending signal detected from any source."""

    keyword: str
    score: float  # 0.0~1.0 normalised relevance
    source: str  # "google_trends" | "reddit" | "x_trending" | "getdaytrends"
    velocity: float = 0.0  # rate of score change (higher = faster rise)
    category_hint: str = ""  # auto-classification hint
    first_seen_at: str = ""
    raw_data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.first_seen_at:
            self.first_seen_at = datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class SignalSource(Protocol):
    """Interface for all signal collectors."""

    @property
    def source_name(self) -> str: ...

    async def fetch_trending(self, *, limit: int = 20) -> list[TrendSignal]: ...


# ---------------------------------------------------------------------------
# Google Trends Collector
# ---------------------------------------------------------------------------

_GOOGLE_TRENDS_RSS_KR = "https://trends.google.co.kr/trending/rss?geo=KR"
_GOOGLE_TRENDS_RSS_US = "https://trends.google.com/trending/rss?geo=US"


class GoogleTrendsCollector:
    """Fetches trending topics from Google Trends RSS feed.

    This is a free, unauthenticated endpoint that returns the top 20
    trending searches in a country. Items include approximate traffic
    volumes when available.
    """

    def __init__(
        self,
        *,
        country: str = "KR",
        timeout: int = 15,
    ) -> None:
        self._country = country.upper()
        self._timeout = timeout
        self._url = _GOOGLE_TRENDS_RSS_KR if self._country == "KR" else _GOOGLE_TRENDS_RSS_US

    @property
    def source_name(self) -> str:
        return "google_trends"

    async def fetch_trending(self, *, limit: int = 20) -> list[TrendSignal]:
        """Fetch and parse Google Trends RSS into TrendSignals."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
                resp = await client.get(self._url)
                resp.raise_for_status()
            return self._parse_rss(resp.text, limit=limit)
        except Exception as exc:
            logger.warning("Google Trends fetch failed: %s", exc)
            return []

    def _parse_rss(self, xml_text: str, *, limit: int = 20) -> list[TrendSignal]:
        """Parse Google Trends RSS XML into TrendSignal list."""
        signals: list[TrendSignal] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.warning("Google Trends XML parse error: %s", exc)
            return []

        # Google Trends RSS uses <item> elements in <channel>
        ns = {"ht": "https://trends.google.co.kr/trending/rss"}
        items = root.findall(".//item")

        for rank, item in enumerate(items[:limit], start=1):
            title_el = item.find("title")
            keyword = title_el.text.strip() if title_el is not None and title_el.text else ""
            if not keyword:
                continue

            # Parse traffic volume (e.g. "100,000+" or "10K+")
            traffic_el = item.find("ht:approx_traffic", ns)
            if traffic_el is None:
                # Try without namespace
                traffic_el = item.find("{https://trends.google.co.kr/trending/rss}approx_traffic")

            volume = 0
            volume_raw = ""
            if traffic_el is not None and traffic_el.text:
                volume_raw = traffic_el.text.strip()
                volume = self._parse_volume(volume_raw)

            # Normalise score: rank 1 -> 1.0, rank 20 -> 0.05
            score = max(0.05, 1.0 - (rank - 1) * 0.05)

            # Boost by volume
            if volume > 500_000:
                score = min(1.0, score * 1.3)
            elif volume > 100_000:
                score = min(1.0, score * 1.1)

            pub_date_el = item.find("pubDate")
            first_seen = ""
            if pub_date_el is not None and pub_date_el.text:
                first_seen = pub_date_el.text.strip()

            signals.append(
                TrendSignal(
                    keyword=keyword,
                    score=round(score, 3),
                    source="google_trends",
                    velocity=round(score * 0.8, 3),  # heuristic — higher rank → higher velocity
                    category_hint=self._guess_category(keyword),
                    first_seen_at=first_seen or datetime.now(UTC).isoformat(),
                    raw_data={
                        "rank": rank,
                        "volume_raw": volume_raw,
                        "volume_numeric": volume,
                        "country": self._country,
                    },
                )
            )
        return signals

    @staticmethod
    def _parse_volume(raw: str) -> int:
        """Parse '100,000+' or '10K+' into integer."""
        cleaned = raw.replace(",", "").replace("+", "").strip()
        if not cleaned:
            return 0
        multiplier = 1
        if cleaned.upper().endswith("K"):
            multiplier = 1_000
            cleaned = cleaned[:-1]
        elif cleaned.upper().endswith("M"):
            multiplier = 1_000_000
            cleaned = cleaned[:-1]
        try:
            return int(float(cleaned) * multiplier)
        except (ValueError, OverflowError):
            return 0

    @staticmethod
    def _guess_category(keyword: str) -> str:
        """Simple keyword-based category heuristic."""
        kw_lower = keyword.lower()
        economy_hints = {"주가", "환율", "금리", "코스피", "코스닥", "증시", "경제", "부동산", "stock", "market", "fed"}
        tech_hints = {"ai", "반도체", "삼성", "apple", "google", "meta", "nvidia", "openai", "chatgpt", "chip"}
        crypto_hints = {"비트코인", "이더리움", "코인", "bitcoin", "ethereum", "crypto", "nft", "web3"}
        for hint in economy_hints:
            if hint in kw_lower:
                return "Economy_KR"
        for hint in tech_hints:
            if hint in kw_lower:
                return "Tech"
        for hint in crypto_hints:
            if hint in kw_lower:
                return "Crypto"
        return ""


# ---------------------------------------------------------------------------
# GetDayTrends DB Connector
# ---------------------------------------------------------------------------

_DEFAULT_GDT_DB = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", "..", "GetDayTrends", "data", "getdaytrends.db",
)


class GetDayTrendsConnector:
    """Reads recent trending data from GetDayTrends' SQLite database.

    This is a **read-only** cross-project bridge — it opens the DB in
    WAL mode with a busy timeout so it never blocks ongoing writes.
    """

    def __init__(self, *, db_path: str = "") -> None:
        self._db_path = db_path or os.getenv("GDT_DB_PATH", "")
        if not self._db_path:
            resolved = os.path.normpath(_DEFAULT_GDT_DB)
            if os.path.exists(resolved):
                self._db_path = resolved

    @property
    def source_name(self) -> str:
        return "getdaytrends"

    @property
    def is_available(self) -> bool:
        return bool(self._db_path and os.path.exists(self._db_path))

    async def fetch_trending(self, *, limit: int = 20) -> list[TrendSignal]:
        """Read the most recent scored trends from GetDayTrends DB."""
        if not self.is_available:
            logger.debug("GetDayTrends DB not available at %s", self._db_path)
            return []

        try:
            import aiosqlite
        except ImportError:
            logger.warning("aiosqlite not installed — cannot read GetDayTrends DB")
            return []

        signals: list[TrendSignal] = []
        try:
            async with aiosqlite.connect(self._db_path) as conn:
                conn.row_factory = aiosqlite.Row
                await conn.execute("PRAGMA journal_mode=WAL")
                await conn.execute("PRAGMA busy_timeout=3000")

                # Get trends from last 6 hours, ordered by viral_potential desc
                cutoff = (datetime.now(UTC) - timedelta(hours=6)).isoformat()
                cursor = await conn.execute(
                    """
                    SELECT keyword, viral_potential, cross_source_confidence,
                           scored_at, sentiment, volume_numeric, trend_acceleration,
                           rank
                    FROM trends
                    WHERE scored_at >= ?
                    ORDER BY viral_potential DESC
                    LIMIT ?
                    """,
                    (cutoff, limit),
                )
                rows = await cursor.fetchall()

                for row in rows:
                    viral = row["viral_potential"] or 0
                    confidence = row["cross_source_confidence"] or 0

                    # Normalise: viral_potential is 0-100 in GDT → 0.0~1.0
                    score = min(1.0, viral / 100.0)
                    # Boost by cross-source confidence
                    if confidence >= 3:
                        score = min(1.0, score * 1.3)
                    elif confidence >= 2:
                        score = min(1.0, score * 1.15)

                    # Parse acceleration for velocity
                    accel_str = row["trend_acceleration"] or "+0%"
                    velocity = self._parse_acceleration(accel_str)

                    signals.append(
                        TrendSignal(
                            keyword=row["keyword"],
                            score=round(score, 3),
                            source="getdaytrends",
                            velocity=round(velocity, 3),
                            category_hint="",  # GDT doesn't categorise
                            first_seen_at=row["scored_at"] or "",
                            raw_data={
                                "viral_potential": viral,
                                "cross_source_confidence": confidence,
                                "sentiment": row["sentiment"] or "neutral",
                                "volume_numeric": row["volume_numeric"] or 0,
                                "trend_acceleration": accel_str,
                                "rank": row["rank"] or 0,
                            },
                        )
                    )
        except Exception as exc:
            logger.warning("GetDayTrends DB read failed: %s", exc)

        return signals

    @staticmethod
    def _parse_acceleration(accel: str) -> float:
        """Parse '+150%' into 1.5 velocity score."""
        match = re.search(r"([+-]?\d+)", accel)
        if not match:
            return 0.0
        pct = int(match.group(1))
        # Normalise: +100% → 0.5, +500% → 1.0
        return min(1.0, max(0.0, abs(pct) / 500.0))


# ---------------------------------------------------------------------------
# Reddit Rising Collector
# ---------------------------------------------------------------------------


class RedditRisingCollector:
    """Fetches trending topics from Reddit's rising feeds.

    Queries unauthenticated JSON feeds like /r/popular/rising.json.
    Respects a basic User-Agent to avoid immediate 429 blocks.
    """

    def __init__(self, *, subreddits: list[str] | None = None, timeout: int = 15) -> None:
        self._subreddits = subreddits or ["popular", "worldnews"]
        self._timeout = timeout

    @property
    def source_name(self) -> str:
        return "reddit"

    async def fetch_trending(self, *, limit: int = 20) -> list[TrendSignal]:
        """Fetch and parse Reddit JSON into TrendSignals."""
        import asyncio

        async def _fetch_sub(sub: str) -> list[TrendSignal]:
            url = f"https://www.reddit.com/r/{sub}/rising.json?limit={limit}"
            headers = {"User-Agent": "DailyNewsBot/1.0 (by /u/bioju)"}
            try:
                async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
                    resp = await client.get(url, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    return self._parse_reddit_json(sub, data, limit=limit)
            except Exception as exc:
                logger.warning("Reddit fetch failed for r/%s: %s", sub, exc)
                return []

        results = await asyncio.gather(*[_fetch_sub(sub) for sub in self._subreddits])
        signals: list[TrendSignal] = []
        for batch in results:
            signals.extend(batch)

        # Deduplicate across subreddits if the same keyword appears, keeping highest score
        merged: dict[str, TrendSignal] = {}
        for s in signals:
            key = s.keyword.lower()
            if key not in merged or s.score > merged[key].score:
                merged[key] = s

        # Return top N by score across all fetched subreddits
        sorted_signals = sorted(merged.values(), key=lambda x: x.score, reverse=True)
        return sorted_signals[:limit]

    def _parse_reddit_json(self, subreddit: str, data: dict[str, Any], *, limit: int = 20) -> list[TrendSignal]:
        signals: list[TrendSignal] = []
        try:
            children = data.get("data", {}).get("children", [])
        except AttributeError:
            return []

        for rank, child in enumerate(children[:limit], start=1):
            post = child.get("data", {})
            title = post.get("title", "").strip()
            if not title:
                continue

            # In Reddit, the 'keyword' could just be the title or the first prominent N-gram.
            # To keep things simple and comparable, we use the title itself, but cap at ~10 words.
            words = title.split()
            keyword = " ".join(words[:15])

            upvotes = post.get("ups", 0)
            upvote_ratio = post.get("upvote_ratio", 0.0)
            num_comments = post.get("num_comments", 0)

            # Normalise score based on rank (1st = 1.0, 20th = 0.05)
            base_score = max(0.05, 1.0 - (rank - 1) * 0.05)

            # Boost score based on engagement metrics relative to rising limits
            if upvotes > 1000:
                base_score = min(1.0, base_score * 1.3)
            elif upvotes > 500:
                base_score = min(1.0, base_score * 1.1)

            if upvote_ratio > 0.95:
                base_score = min(1.0, base_score * 1.1)

            # Velocity roughly inferred from upvote ratios and total comments early in cycle
            velocity = min(1.0, (upvotes / 1000.0) + (num_comments / 500.0))

            category_hint = "WorldNews" if subreddit == "worldnews" else ""

            signals.append(
                TrendSignal(
                    keyword=keyword,
                    score=round(base_score, 3),
                    source="reddit",
                    velocity=round(velocity, 3),
                    category_hint=category_hint,
                    first_seen_at=datetime.now(UTC).isoformat(),
                    raw_data={
                        "subreddit": subreddit,
                        "upvotes": upvotes,
                        "upvote_ratio": upvote_ratio,
                        "comments": num_comments,
                        "url": post.get("url", ""),
                        "permalink": post.get("permalink", ""),
                        "rank": rank,
                    },
                )
            )
        return signals


# ---------------------------------------------------------------------------
# Aggregate Collector
# ---------------------------------------------------------------------------


class MultiSourceCollector:
    """Aggregates signals from all configured sources (parallel fetch)."""

    def __init__(
        self,
        *,
        sources: list[SignalSource] | None = None,
        country: str = "KR",
    ) -> None:
        if sources is not None:
            self._sources = sources
        else:
            self._sources: list[SignalSource] = [
                GoogleTrendsCollector(country=country),
                RedditRisingCollector(),
            ]
            gdt = GetDayTrendsConnector()
            if gdt.is_available:
                self._sources.append(gdt)

    @property
    def source_names(self) -> list[str]:
        return [s.source_name for s in self._sources]

    async def collect_all(self, *, limit_per_source: int = 20) -> list[TrendSignal]:
        """Fetch from all sources in parallel, return merged signal list."""
        import asyncio

        async def _safe_fetch(source: SignalSource) -> list[TrendSignal]:
            try:
                return await source.fetch_trending(limit=limit_per_source)
            except Exception as exc:
                logger.warning("Source %s failed: %s", source.source_name, exc)
                return []

        results = await asyncio.gather(*[_safe_fetch(s) for s in self._sources])
        all_signals: list[TrendSignal] = []
        for batch in results:
            all_signals.extend(batch)

        logger.info(
            "MultiSourceCollector: %d signals from %d sources (%s)",
            len(all_signals),
            len(self._sources),
            ", ".join(self.source_names),
        )
        return all_signals
