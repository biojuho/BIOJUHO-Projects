"""
getdaytrends Phase 3+ - Content Performance Tracker (Adaptive Feedback Loop)

X/Twitter 寃뚯떆 ?몄쐵??李몄뿬 吏??impressions, likes, retweets, replies, quotes)瑜?
?섏쭛?섍퀬, ?듦? ?좏삎蹂??깃낵瑜?吏묎퀎?섏뿬 理쒖쟻 ?듦? 媛以묒튂瑜??쇰뱶諛?
"""

import asyncio
import json
import re
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from loguru import logger as log

# -- models import --
from perf_models import (  # noqa: F401
    _ANGLE_ALIASES,
    _HOOK_ALIASES,
    _KICK_ALIASES,
    ANGLE_TYPES,
    HOOK_PATTERNS,
    KICK_PATTERNS,
    AngleStats,
    GoldenReference,
    PatternStats,
    TweetMetrics,
    normalize_angle,
    normalize_hook,
    normalize_kick,
)

# ?? X API v2 Constants ???????????????????????????????????

_X_API_BASE = "https://api.twitter.com/2"
_TWEET_FIELDS = "public_metrics"
# Rate limit: 300 requests / 15 min (App-level) for GET /2/tweets
_RATE_LIMIT_DELAY = 1.0  # seconds between batch items (conservative)
_BATCH_CHUNK_SIZE = 100  # X API max IDs per request


# ?? PerformanceTracker ???????????????????????????????????


class PerformanceTracker:
    """
    X/Twitter 寃뚯떆 ?몄쐵???깃낵 吏?쒕? ?섏쭛?섍퀬
    ?듦? ?좏삎蹂?媛以묒튂瑜??쇰뱶諛깊븯??Phase 3 紐⑤뱢.
    """

    def __init__(self, db_path: str = "data/getdaytrends.db", bearer_token: str = ""):
        self.db_path = db_path
        self.bearer_token = bearer_token
        self._initialized = False

    # ?? DB Setup ?????????????????????????????????????????

    def _get_conn(self) -> sqlite3.Connection:
        """?숆린 SQLite ?곌껐 (?깃낵 ?뚯씠釉??꾩슜)."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init_table(self) -> None:
        """tweet_performance + golden_references + trend_genealogy ?뚯씠釉??앹꽦 (硫깅벑)."""
        if self._initialized:
            return
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS tweet_performance (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    tweet_id     TEXT NOT NULL UNIQUE,
                    impressions  INTEGER DEFAULT 0,
                    likes        INTEGER DEFAULT 0,
                    retweets     INTEGER DEFAULT 0,
                    replies      INTEGER DEFAULT 0,
                    quotes       INTEGER DEFAULT 0,
                    engagement_rate REAL DEFAULT 0.0,
                    angle_type   TEXT DEFAULT '',
                    hook_pattern TEXT DEFAULT '',
                    kick_pattern TEXT DEFAULT '',
                    collection_tier TEXT DEFAULT '48h',
                    collected_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_tp_angle ON tweet_performance(angle_type);
                CREATE INDEX IF NOT EXISTS idx_tp_collected ON tweet_performance(collected_at);
                CREATE INDEX IF NOT EXISTS idx_tp_tweet_id ON tweet_performance(tweet_id);
                CREATE INDEX IF NOT EXISTS idx_tp_hook ON tweet_performance(hook_pattern);
                CREATE INDEX IF NOT EXISTS idx_tp_kick ON tweet_performance(kick_pattern);

                -- [E] Golden References: 怨좎꽦怨??몄쐵 踰ㅼ튂留덊겕
                CREATE TABLE IF NOT EXISTS golden_references (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    tweet_id        TEXT NOT NULL UNIQUE,
                    content         TEXT NOT NULL,
                    angle_type      TEXT DEFAULT '',
                    hook_pattern    TEXT DEFAULT '',
                    kick_pattern    TEXT DEFAULT '',
                    engagement_rate REAL DEFAULT 0.0,
                    impressions     INTEGER DEFAULT 0,
                    category        TEXT DEFAULT '',
                    saved_at        TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_gr_angle ON golden_references(angle_type);
                CREATE INDEX IF NOT EXISTS idx_gr_er ON golden_references(engagement_rate);

                -- [A] Trend Genealogy: ?몃젋??怨꾨낫 異붿쟻
                CREATE TABLE IF NOT EXISTS trend_genealogy (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword         TEXT NOT NULL,
                    parent_keyword  TEXT DEFAULT '',
                    predicted_children TEXT DEFAULT '[]',
                    genealogy_depth INTEGER DEFAULT 0,
                    first_seen_at   TEXT NOT NULL,
                    last_seen_at    TEXT NOT NULL,
                    total_appearances INTEGER DEFAULT 1,
                    peak_viral_score INTEGER DEFAULT 0,
                    UNIQUE(keyword, parent_keyword)
                );
                CREATE INDEX IF NOT EXISTS idx_tg_keyword ON trend_genealogy(keyword);
                CREATE INDEX IF NOT EXISTS idx_tg_parent ON trend_genealogy(parent_keyword);
                CREATE INDEX IF NOT EXISTS idx_tg_last_seen ON trend_genealogy(last_seen_at);
            """)
            try:
                conn.execute("SELECT x_tweet_id FROM tweets LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute("ALTER TABLE tweets ADD COLUMN x_tweet_id TEXT DEFAULT ''")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tweets_x_tweet_id ON tweets(x_tweet_id)")
            conn.commit()
            self._initialized = True
            log.debug("tweet_performance + golden_references + trend_genealogy ?뚯씠釉?珥덇린???꾨즺")
        finally:
            conn.close()

    # ?? X API v2 Metric Collection ???????????????????????

    async def collect_metrics(self, tweet_id: str) -> TweetMetrics | None:
        """?⑥씪 ?몄쐵??public_metrics瑜?X API v2?먯꽌 ?섏쭛.

        Returns:
            TweetMetrics or None if API call fails.
        """
        if not self.bearer_token:
            log.warning("bearer_token 誘몄꽕??- X API ?몄텧 遺덇?")
            return None

        url = f"{_X_API_BASE}/tweets/{tweet_id}"
        params = {"tweet.fields": _TWEET_FIELDS}
        headers = {"Authorization": f"Bearer {self.bearer_token}"}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json().get("data", {})
                metrics = data.get("public_metrics", {})

                tm = TweetMetrics(
                    tweet_id=tweet_id,
                    impressions=metrics.get("impression_count", 0),
                    likes=metrics.get("like_count", 0),
                    retweets=metrics.get("retweet_count", 0),
                    replies=metrics.get("reply_count", 0),
                    quotes=metrics.get("quote_count", 0),
                    collected_at=datetime.now(UTC),
                )
                tm.compute_engagement_rate()
                return tm

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                retry_after = int(e.response.headers.get("retry-after", "60"))
                log.warning(f"X API rate limit hit - retry after {retry_after}s")
            else:
                log.error(f"X API ?ㅻ쪟 [{e.response.status_code}]: tweet_id={tweet_id}")
            return None
        except Exception as e:
            log.error(f"X API ?붿껌 ?ㅽ뙣: tweet_id={tweet_id} - {type(e).__name__}: {e}")
            return None

    async def batch_collect(self, tweet_ids: list[str]) -> list[TweetMetrics]:
        """?щ윭 ?몄쐵??硫뷀듃由?쓣 諛곗튂 ?섏쭛 (rate limit 以??.

        X API v2 GET /2/tweets??理쒕? 100媛?ID瑜???踰덉뿉 議고쉶 媛??
        100媛??⑥쐞濡?泥?겕 遺꾪븷 ???쒖감 ?몄텧.
        """
        if not self.bearer_token:
            log.warning("bearer_token 誘몄꽕??- batch_collect ?ㅽ궢")
            return []

        if not tweet_ids:
            return []

        results: list[TweetMetrics] = []
        headers = {"Authorization": f"Bearer {self.bearer_token}"}

        for i in range(0, len(tweet_ids), _BATCH_CHUNK_SIZE):
            chunk = tweet_ids[i : i + _BATCH_CHUNK_SIZE]
            ids_param = ",".join(chunk)
            url = f"{_X_API_BASE}/tweets"
            params = {"ids": ids_param, "tweet.fields": _TWEET_FIELDS}

            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(url, params=params, headers=headers)

                    if resp.status_code == 429:
                        retry_after = int(resp.headers.get("retry-after", "60"))
                        log.warning(f"Rate limit - {retry_after}s, retrying batch request")
                        await asyncio.sleep(retry_after)
                        resp = await client.get(url, params=params, headers=headers)

                    resp.raise_for_status()
                    data_list = resp.json().get("data", [])

                    for data in data_list:
                        metrics = data.get("public_metrics", {})
                        tm = TweetMetrics(
                            tweet_id=data["id"],
                            impressions=metrics.get("impression_count", 0),
                            likes=metrics.get("like_count", 0),
                            retweets=metrics.get("retweet_count", 0),
                            replies=metrics.get("reply_count", 0),
                            quotes=metrics.get("quote_count", 0),
                            collected_at=datetime.now(UTC),
                        )
                        tm.compute_engagement_rate()
                        results.append(tm)

            except Exception as e:
                log.error(f"batch_collect 泥?겕 ?ㅽ뙣 (ids {i}~{i+len(chunk)}): {e}")

            # Rate limit spacing between chunks
            if i + _BATCH_CHUNK_SIZE < len(tweet_ids):
                await asyncio.sleep(_RATE_LIMIT_DELAY)

        log.info(f"batch_collect ?꾨즺: {len(results)}/{len(tweet_ids)} ?몄쐵 ?섏쭛")
        return results

    # ?? DB Persistence ???????????????????????????????????

    _UPSERT_SQL = """INSERT INTO tweet_performance
           (tweet_id, impressions, likes, retweets, replies, quotes,
            engagement_rate, angle_type, hook_pattern, kick_pattern,
            collection_tier, collected_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(tweet_id) DO UPDATE SET
               impressions=excluded.impressions,
               likes=excluded.likes,
               retweets=excluded.retweets,
               replies=excluded.replies,
               quotes=excluded.quotes,
               engagement_rate=excluded.engagement_rate,
               collection_tier=excluded.collection_tier,
               collected_at=excluded.collected_at"""

    @staticmethod
    def _metrics_to_tuple(m: TweetMetrics) -> tuple:
        return (
            m.tweet_id,
            m.impressions,
            m.likes,
            m.retweets,
            m.replies,
            m.quotes,
            m.engagement_rate,
            m.angle_type,
            m.hook_pattern,
            m.kick_pattern,
            m.collection_tier,
            (m.collected_at or datetime.now(UTC)).isoformat(),
        )

    @staticmethod
    def _total_engagements(m: TweetMetrics) -> int:
        return int(m.likes + m.retweets + m.replies + m.quotes)

    def _sync_tweet_summary(self, conn: sqlite3.Connection, metrics: TweetMetrics) -> None:
        engagements = self._total_engagements(metrics)
        cursor = conn.execute(
            """UPDATE tweets
               SET impressions = ?,
                   engagements = ?,
                   engagement_rate = ?
               WHERE x_tweet_id = ?""",
            (metrics.impressions, engagements, metrics.engagement_rate, metrics.tweet_id),
        )
        if cursor.rowcount:
            return

        if metrics.tweet_id.isdigit():
            conn.execute(
                """UPDATE tweets
                   SET impressions = ?,
                       engagements = ?,
                       engagement_rate = ?
                   WHERE id = ?""",
                (metrics.impressions, engagements, metrics.engagement_rate, int(metrics.tweet_id)),
            )

    def save_metrics(self, metrics: TweetMetrics) -> None:
        """?⑥씪 TweetMetrics瑜?tweet_performance ?뚯씠釉붿뿉 ???媛깆떊."""
        self.init_table()
        conn = self._get_conn()
        try:
            conn.execute(self._UPSERT_SQL, self._metrics_to_tuple(metrics))
            self._sync_tweet_summary(conn, metrics)
            conn.commit()
        finally:
            conn.close()

    def save_metrics_batch(self, metrics_list: list[TweetMetrics]) -> int:
        """?щ윭 TweetMetrics瑜??쇨큵 ??? ???嫄댁닔 諛섑솚."""
        if not metrics_list:
            return 0
        self.init_table()
        conn = self._get_conn()
        saved = 0
        try:
            for m in metrics_list:
                try:
                    conn.execute(self._UPSERT_SQL, self._metrics_to_tuple(m))
                    self._sync_tweet_summary(conn, m)
                    saved += 1
                except Exception as e:
                    log.debug(f"save_metrics_batch 媛쒕퀎 ?ㅽ뙣 (臾댁떆): {m.tweet_id} - {e}")
            conn.commit()
        finally:
            conn.close()
        return saved

    # ?? Angle Performance Analytics ??????????????????????

    def get_angle_performance(self, days: int = 30) -> dict[str, AngleStats]:
        """?듦? ?좏삎蹂??깃낵 吏묎퀎.

        Returns:
            {angle_type: AngleStats} - 理쒓렐 N?쇨컙 ?듦?蹂??됯퇏 ?꾪봽?덉뀡/李몄뿬??
        """
        self.init_table()
        conn = self._get_conn()
        try:
            cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
            rows = conn.execute(
                """SELECT angle_type,
                          COUNT(*) as cnt,
                          AVG(impressions) as avg_imp,
                          AVG(engagement_rate) as avg_er
                   FROM tweet_performance
                   WHERE collected_at >= ? AND angle_type != '' AND angle_type != 'unknown'
                   GROUP BY angle_type
                   ORDER BY avg_er DESC""",
                (cutoff,),
            ).fetchall()

            result: dict[str, AngleStats] = {}
            for row in rows:
                angle = row["angle_type"]
                result[angle] = AngleStats(
                    angle=angle,
                    total_tweets=row["cnt"],
                    avg_impressions=round(row["avg_imp"] or 0.0, 1),
                    avg_engagement_rate=round(row["avg_er"] or 0.0, 6),
                )

            # ?곗씠???녿뒗 ?듦???湲곕낯媛믪쑝濡??ы븿
            for a in ANGLE_TYPES:
                if a not in result:
                    result[a] = AngleStats(angle=a)

            return result
        finally:
            conn.close()

    def get_optimal_angle_weights(
        self,
        days: int = 30,
        min_samples: int = 5,
        _precomputed_stats: dict[str, AngleStats] | None = None,
    ) -> dict[str, float]:
        """?듦? ?좏삎蹂?理쒖쟻 媛以묒튂 怨꾩궛.

        engagement_rate 湲곕컲 ?뚰봽?몃㎘???좎궗 ?뺢퇋??
        min_samples 誘몃쭔???듦?? 湲곕낯 媛以묒튂(1/N) ?좎?.

        Returns:
            {angle_type: weight} - ?⑷퀎 1.0 (?뺣쪧 遺꾪룷).
        """
        stats = _precomputed_stats or self.get_angle_performance(days)
        n = len(ANGLE_TYPES)
        default_weight = 1.0 / n

        # 異⑸텇???섑뵆???덈뒗 ?듦?留?媛以묒튂 怨꾩궛 ???
        scored: dict[str, float] = {}
        unscorable: list[str] = []

        for angle in ANGLE_TYPES:
            s = stats.get(angle)
            if s and s.total_tweets >= min_samples:
                # engagement_rate瑜??먯닔濡??ъ슜 (0 ?댁긽 蹂댁옣)
                scored[angle] = max(s.avg_engagement_rate, 1e-8)
            else:
                unscorable.append(angle)

        if not scored:
            # ?곗씠??遺덉땐遺?- 洹좊벑 遺꾨같
            return {a: default_weight for a in ANGLE_TYPES}

        # ?먯닔 鍮꾨? 媛以묒튂 怨꾩궛
        total_score = sum(scored.values())
        # unscorable ?듦????좊떦??珥?鍮꾩쨷 (?먯깋 ?덉궛)
        explore_budget = len(unscorable) * default_weight
        exploit_budget = 1.0 - explore_budget

        weights: dict[str, float] = {}
        for angle in ANGLE_TYPES:
            if angle in scored:
                weights[angle] = round(exploit_budget * (scored[angle] / total_score), 4)
            else:
                weights[angle] = round(default_weight, 4)

        # ?뺢퇋??蹂댁젙 (遺?숈냼?섏젏 ?ㅼ감)
        total = sum(weights.values())
        if total > 0:
            weights = {k: round(v / total, 4) for k, v in weights.items()}

        # AngleStats??weight 諛섏쁺
        for angle, w in weights.items():
            if angle in stats:
                stats[angle].weight = w

        return weights

    # ?? Scheduler Integration ????????????????????????????

    async def run_collection_cycle(self, lookback_hours: int = 48) -> int:
        """?ㅼ?以꾨윭 ?몄텧?? 理쒓렐 寃뚯떆?섏뿀?쇰굹 ?깃낵 誘몄닔吏??몄쐵??李얠븘 硫뷀듃由??섏쭛.

        1. tweets ?뚯씠釉붿뿉??posted_at???덇퀬 tweet_performance???녿뒗 ?몄쐵 議고쉶
        2. X API濡?硫뷀듃由??섏쭛
        3. angle_type 留ㅽ븨 ?????

        Returns:
            ?섏쭛 ?꾨즺 嫄댁닔.
        """
        self.init_table()
        conn = self._get_conn()
        try:
            cutoff = (datetime.now() - timedelta(hours=lookback_hours)).isoformat()

            # posted_at???덇퀬 ?꾩쭅 ?섏쭛?섏? ?딆? ?몄쐵 議고쉶
            # tweets.content?먯꽌 tweet_id瑜?異붿텧?섎뒗 寃껋씠 ?꾨땲??
            # posted_at???ㅼ젙???몄쐵??DB id + tweet_type??媛?몄샂
            rows = conn.execute(
                """SELECT t.id, t.tweet_type, t.posted_at, t.x_tweet_id, t.content
                   FROM tweets t
                   WHERE t.posted_at IS NOT NULL
                     AND t.posted_at >= ?
                     AND (
                         (t.x_tweet_id IS NOT NULL AND t.x_tweet_id != '' AND t.x_tweet_id NOT IN (
                             SELECT tweet_id
                             FROM tweet_performance
                         ))
                         OR
                         ((t.x_tweet_id IS NULL OR t.x_tweet_id = '') AND t.id NOT IN (
                             SELECT CAST(tweet_id AS INTEGER)
                             FROM tweet_performance
                             WHERE tweet_id GLOB '[0-9]*'
                         ))
                     )
                   ORDER BY t.posted_at DESC
                   LIMIT 200""",
                (cutoff,),
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            log.debug("run_collection_cycle: 誘몄닔吏??몄쐵 ?놁쓬")
            return 0

        log.info(f"run_collection_cycle: {len(rows)}媛?誘몄닔吏??몄쐵 諛쒓껄")

        # posted_at ?꾨뱶??X tweet_id媛 ??λ릺???덈떎怨?媛?뺥븯?????
        # tweets ?뚯씠釉붿쓽 id瑜?tweet_id濡??ъ슜 (濡쒖뺄 DB 異붿쟻)
        # ?ㅼ젣 X tweet_id媛 蹂꾨룄 而щ읆???덈떎硫?洹?而щ읆???ъ슜?댁빞 ??
        # ?ш린?쒕뒗 DB id 湲곗??쇰줈 濡쒖뺄 ?깃낵 異붿쟻

        # X API瑜??듯븳 ?ㅼ젣 硫뷀듃由??섏쭛 ?쒕룄
        # posted_at ?꾨뱶 媛믪씠 ?ㅼ젣 X tweet_id瑜??ы븿?섎뒗 寃쎌슦瑜?泥섎━
        tweet_id_map: dict[str, dict] = {}  # x_tweet_id -> row info
        local_only: list[dict] = []

        for row in rows:
            row_dict = dict(row)
            x_tweet_id = (row_dict.get("x_tweet_id", "") or "").strip()
            posted_at = (row_dict.get("posted_at", "") or "").strip()
            if x_tweet_id and re.match(r"^\d{10,}$", x_tweet_id):
                x_id = x_tweet_id
                tweet_id_map[x_id] = row_dict
            elif posted_at and re.match(r"^\d{10,}$", posted_at):
                x_id = posted_at
                tweet_id_map[x_id] = row_dict
            else:
                local_only.append(row_dict)

        collected_count = 0

        # X API 諛곗튂 ?섏쭛
        all_metrics: list[TweetMetrics] = []
        if tweet_id_map and self.bearer_token:
            x_ids = list(tweet_id_map.keys())
            metrics_list = await self.batch_collect(x_ids)

            for m in metrics_list:
                row_info = tweet_id_map.get(m.tweet_id, {})
                m.angle_type = normalize_angle(row_info.get("tweet_type", ""))
                all_metrics.append(m)

        # 濡쒖뺄 ?몄쐵 (X API ?놁씠 DB 湲곕줉留?
        for row_dict in local_only:
            db_id = str(row_dict["id"])
            angle = normalize_angle(row_dict.get("tweet_type", ""))
            all_metrics.append(
                TweetMetrics(
                    tweet_id=db_id,
                    angle_type=angle,
                    collected_at=datetime.now(UTC),
                )
            )

        # ?쇨큵 ???(N+1 諛⑹?)
        collected_count = self.save_metrics_batch(all_metrics)

        log.info(
            f"run_collection_cycle ?꾨즺: {collected_count}嫄??섏쭛 "
            f"(X API: {len(tweet_id_map)}嫄? 濡쒖뺄: {len(local_only)}嫄?"
        )
        return collected_count

    # ?? [B] Hook/Kick Pattern Analytics ??????????????????

    def get_hook_performance(self, days: int = 30) -> dict[str, PatternStats]:
        """[B] ???⑦꽩蹂??깃낵 吏묎퀎."""
        self.init_table()
        conn = self._get_conn()
        try:
            cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
            rows = conn.execute(
                """SELECT hook_pattern,
                          COUNT(*) as cnt,
                          AVG(impressions) as avg_imp,
                          AVG(engagement_rate) as avg_er
                   FROM tweet_performance
                   WHERE collected_at >= ? AND hook_pattern != '' AND hook_pattern != 'unknown'
                   GROUP BY hook_pattern
                   ORDER BY avg_er DESC""",
                (cutoff,),
            ).fetchall()

            result: dict[str, PatternStats] = {}
            for row in rows:
                p = row["hook_pattern"]
                result[p] = PatternStats(
                    pattern=p,
                    pattern_type="hook",
                    total_tweets=row["cnt"],
                    avg_impressions=round(row["avg_imp"] or 0.0, 1),
                    avg_engagement_rate=round(row["avg_er"] or 0.0, 6),
                )
            for p in HOOK_PATTERNS:
                if p not in result:
                    result[p] = PatternStats(pattern=p, pattern_type="hook")
            return result
        finally:
            conn.close()

    def get_kick_performance(self, days: int = 30) -> dict[str, PatternStats]:
        """[B] ???⑦꽩蹂??깃낵 吏묎퀎."""
        self.init_table()
        conn = self._get_conn()
        try:
            cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
            rows = conn.execute(
                """SELECT kick_pattern,
                          COUNT(*) as cnt,
                          AVG(impressions) as avg_imp,
                          AVG(engagement_rate) as avg_er
                   FROM tweet_performance
                   WHERE collected_at >= ? AND kick_pattern != '' AND kick_pattern != 'unknown'
                   GROUP BY kick_pattern
                   ORDER BY avg_er DESC""",
                (cutoff,),
            ).fetchall()

            result: dict[str, PatternStats] = {}
            for row in rows:
                p = row["kick_pattern"]
                result[p] = PatternStats(
                    pattern=p,
                    pattern_type="kick",
                    total_tweets=row["cnt"],
                    avg_impressions=round(row["avg_imp"] or 0.0, 1),
                    avg_engagement_rate=round(row["avg_er"] or 0.0, 6),
                )
            for p in KICK_PATTERNS:
                if p not in result:
                    result[p] = PatternStats(pattern=p, pattern_type="kick")
            return result
        finally:
            conn.close()

    def get_optimal_pattern_weights(
        self,
        days: int = 30,
        min_samples: int = 3,
    ) -> dict[str, dict[str, float]]:
        """[B] ?????⑦꽩蹂?理쒖쟻 媛以묒튂 怨꾩궛 ???앹꽦 ?꾨＼?꾪듃??二쇱엯."""
        hook_stats = self.get_hook_performance(days)
        kick_stats = self.get_kick_performance(days)

        def _compute_weights(stats: dict[str, PatternStats], all_patterns: list[str]) -> dict[str, float]:
            n = len(all_patterns)
            default_w = 1.0 / n
            scored = {}
            for p in all_patterns:
                s = stats.get(p)
                if s and s.total_tweets >= min_samples:
                    scored[p] = max(s.avg_engagement_rate, 1e-8)
            if not scored:
                return {p: round(default_w, 4) for p in all_patterns}
            total = sum(scored.values())
            unscorable_count = n - len(scored)
            explore = unscorable_count * default_w
            exploit = 1.0 - explore
            weights = {}
            for p in all_patterns:
                if p in scored:
                    weights[p] = round(exploit * (scored[p] / total), 4)
                else:
                    weights[p] = round(default_w, 4)
            w_total = sum(weights.values())
            if w_total > 0:
                weights = {k: round(v / w_total, 4) for k, v in weights.items()}
            return weights

        return {
            "hook_weights": _compute_weights(hook_stats, HOOK_PATTERNS),
            "kick_weights": _compute_weights(kick_stats, KICK_PATTERNS),
        }

    # ?? [E] Golden Reference Management ????????????????

    def save_golden_reference(self, ref: GoldenReference) -> None:
        """[E] 怨⑤뱺 ?덊띁?곗뒪 ??? 理쒕? 20媛??좎? (??? ER ?먮룞 援먯껜)."""
        self.init_table()
        conn = self._get_conn()
        try:
            # ?꾩옱 媛쒖닔 ?뺤씤
            count = conn.execute("SELECT COUNT(*) FROM golden_references").fetchone()[0]
            if count >= 20:
                # 媛????? engagement_rate ?쒓굅
                conn.execute(
                    """DELETE FROM golden_references WHERE id = (
                        SELECT id FROM golden_references ORDER BY engagement_rate ASC LIMIT 1
                    )"""
                )
            conn.execute(
                """INSERT INTO golden_references
                   (tweet_id, content, angle_type, hook_pattern, kick_pattern,
                    engagement_rate, impressions, category, saved_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(tweet_id) DO UPDATE SET
                       engagement_rate=excluded.engagement_rate,
                       impressions=excluded.impressions,
                       saved_at=excluded.saved_at""",
                (
                    ref.tweet_id,
                    ref.content,
                    ref.angle_type,
                    ref.hook_pattern,
                    ref.kick_pattern,
                    ref.engagement_rate,
                    ref.impressions,
                    ref.category,
                    (ref.saved_at or datetime.now(UTC)).isoformat(),
                ),
            )
            conn.commit()
            log.debug(f"怨⑤뱺 ?덊띁?곗뒪 ??? tweet_id={ref.tweet_id}, ER={ref.engagement_rate}")
        finally:
            conn.close()

    def get_golden_references(self, limit: int = 5, category: str = "") -> list[GoldenReference]:
        """[E] ?곸쐞 怨⑤뱺 ?덊띁?곗뒪 議고쉶 (QA 踰ㅼ튂留덊겕??."""
        self.init_table()
        conn = self._get_conn()
        try:
            if category:
                rows = conn.execute(
                    """SELECT * FROM golden_references
                       WHERE category = ?
                       ORDER BY engagement_rate DESC LIMIT ?""",
                    (category, limit),
                ).fetchall()
                if not rows:
                    rows = conn.execute(
                        "SELECT * FROM golden_references ORDER BY engagement_rate DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM golden_references ORDER BY engagement_rate DESC LIMIT ?",
                    (limit,),
                ).fetchall()

            return [
                GoldenReference(
                    tweet_id=r["tweet_id"],
                    content=r["content"],
                    angle_type=r["angle_type"],
                    hook_pattern=r["hook_pattern"],
                    kick_pattern=r["kick_pattern"],
                    engagement_rate=r["engagement_rate"],
                    impressions=r["impressions"],
                    category=r.get("category", ""),
                )
                for r in rows
            ]
        finally:
            conn.close()

    def auto_update_golden_references(self, days: int = 7, top_n: int = 10) -> int:
        """[E] 理쒓렐 N?쇨컙 ?곸쐞 ?몄쐵???먮룞?쇰줈 怨⑤뱺 ?덊띁?곗뒪???깅줉.
        tweets ?뚯씠釉붿뿉??content瑜?議곗씤?섏뿬 媛?몄샂.
        Returns: ?덈줈 ?깅줉??嫄댁닔.
        """
        self.init_table()
        conn = self._get_conn()
        saved = 0
        try:
            cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
            rows = conn.execute(
                """SELECT tp.tweet_id, tp.angle_type, tp.hook_pattern, tp.kick_pattern,
                          tp.engagement_rate, tp.impressions,
                          t.content, t.tweet_type
                   FROM tweet_performance tp
                   LEFT JOIN tweets t ON CAST(tp.tweet_id AS TEXT) = CAST(t.id AS TEXT)
                   WHERE tp.collected_at >= ?
                     AND tp.impressions > 0
                     AND tp.engagement_rate > 0
                   ORDER BY tp.engagement_rate DESC
                   LIMIT ?""",
                (cutoff, top_n),
            ).fetchall()

            for r in rows:
                content = r["content"] if r["content"] else ""
                if not content:
                    continue
                ref = GoldenReference(
                    tweet_id=r["tweet_id"],
                    content=content,
                    angle_type=r["angle_type"] or "",
                    hook_pattern=r["hook_pattern"] or "",
                    kick_pattern=r["kick_pattern"] or "",
                    engagement_rate=r["engagement_rate"],
                    impressions=r["impressions"],
                    saved_at=datetime.now(UTC),
                )
                self.save_golden_reference(ref)
                saved += 1

            log.info(f"Golden references auto-updated: {saved}/{len(rows)}")
        finally:
            conn.close()
        return saved

    # ?? [D] Real-time Signal (3-Tier Collection) ???????

    async def collect_early_signal(self, tweet_ids: list[str], tier: str = "1h") -> list[TweetMetrics]:
        """[D] 珥덇린 ?쒓렇???섏쭛 (諛쒗뻾 1?쒓컙 ??. ?믪? 珥덇린 ER ???꾩냽 肄섑뀗痢??몃━嫄?"""
        metrics = await self.batch_collect(tweet_ids)
        for m in metrics:
            m.collection_tier = tier
        if metrics:
            self.save_metrics_batch(metrics)
        return metrics

    def get_early_signal_analysis(self, hours: int = 2) -> dict:
        """[D] 理쒓렐 N?쒓컙 ???섏쭛??珥덇린 ?쒓렇??遺꾩꽍.
        Returns: {boost_candidates: [...], suppress_candidates: [...], avg_metrics: {...}}
        """
        self.init_table()
        conn = self._get_conn()
        try:
            cutoff = (datetime.now(UTC) - timedelta(hours=hours)).isoformat()
            rows = conn.execute(
                """SELECT tweet_id, impressions, engagement_rate, angle_type
                   FROM tweet_performance
                   WHERE collection_tier = '1h' AND collected_at >= ?
                   ORDER BY engagement_rate DESC""",
                (cutoff,),
            ).fetchall()

            if not rows:
                return {"boost_candidates": [], "suppress_candidates": [], "avg_metrics": {}}

            avg_er = sum(r["engagement_rate"] for r in rows) / len(rows)
            avg_imp = sum(r["impressions"] for r in rows) / len(rows)

            boost = [dict(r) for r in rows if r["engagement_rate"] >= avg_er * 2.0]
            suppress = [dict(r) for r in rows if r["engagement_rate"] <= avg_er * 0.3]

            return {
                "boost_candidates": boost,
                "suppress_candidates": suppress,
                "avg_metrics": {
                    "avg_engagement_rate": round(avg_er, 6),
                    "avg_impressions": round(avg_imp, 1),
                    "total_collected": len(rows),
                },
            }
        finally:
            conn.close()

    async def run_tiered_collection(self, lookback_hours: int = 48) -> dict:
        """[D] 3?④퀎 ?섏쭛 ?ㅼ??ㅽ듃?덉씠??
        - 1h tier: 諛쒗뻾 ??45遺?90遺????몄쐵
        - 6h tier: 諛쒗뻾 ??5~7?쒓컙 ???몄쐵
        - 48h tier: 諛쒗뻾 ??24~72?쒓컙 ???몄쐵
        Returns: {tier_1h: N, tier_6h: N, tier_48h: N}
        """
        self.init_table()
        conn = self._get_conn()
        result = {"tier_1h": 0, "tier_6h": 0, "tier_48h": 0}

        try:
            now = datetime.now()
            # 1h tier: 45遺?90遺???諛쒗뻾
            t1h_start = (now - timedelta(minutes=90)).isoformat()
            t1h_end = (now - timedelta(minutes=45)).isoformat()
            # 6h tier: 5~7?쒓컙 ??諛쒗뻾
            t6h_start = (now - timedelta(hours=7)).isoformat()
            t6h_end = (now - timedelta(hours=5)).isoformat()
            # 48h tier: 24~72?쒓컙 ??諛쒗뻾 (湲곗〈 濡쒖쭅)
            t48h_start = (now - timedelta(hours=72)).isoformat()
            t48h_end = (now - timedelta(hours=24)).isoformat()

            for tier, start, end in [
                ("1h", t1h_start, t1h_end),
                ("6h", t6h_start, t6h_end),
                ("48h", t48h_start, t48h_end),
            ]:
                rows = conn.execute(
                    """SELECT t.id, t.tweet_type, t.posted_at, t.x_tweet_id
                       FROM tweets t
                       WHERE t.posted_at IS NOT NULL
                         AND t.posted_at >= ? AND t.posted_at <= ?
                         AND (
                             (t.x_tweet_id IS NOT NULL AND t.x_tweet_id != '' AND t.x_tweet_id NOT IN (
                                 SELECT tweet_id
                                 FROM tweet_performance
                                 WHERE collection_tier = ?
                             ))
                             OR
                             ((t.x_tweet_id IS NULL OR t.x_tweet_id = '') AND t.id NOT IN (
                                 SELECT CAST(tweet_id AS INTEGER)
                                 FROM tweet_performance
                                 WHERE collection_tier = ? AND tweet_id GLOB '[0-9]*'
                             ))
                         )
                       LIMIT 100""",
                    (start, end, tier, tier),
                ).fetchall()

                if not rows:
                    continue

                tweet_ids = []
                id_map: dict[str, dict] = {}
                for r in rows:
                    x_tweet_id = (r["x_tweet_id"] or "").strip()
                    posted_at = (r["posted_at"] or "").strip()
                    if x_tweet_id and re.match(r"^\d{10,}$", x_tweet_id):
                        x_id = x_tweet_id
                        tweet_ids.append(x_id)
                        id_map[x_id] = dict(r)
                    elif posted_at and re.match(r"^\d{10,}$", posted_at):
                        x_id = posted_at
                        tweet_ids.append(x_id)
                        id_map[x_id] = dict(r)

                if tweet_ids and self.bearer_token:
                    metrics = await self.batch_collect(tweet_ids)
                    for m in metrics:
                        m.collection_tier = tier
                        row_info = id_map.get(m.tweet_id, {})
                        m.angle_type = normalize_angle(row_info.get("tweet_type", ""))
                    count = self.save_metrics_batch(metrics)
                    result[f"tier_{tier}"] = count

            log.info(f"3?④퀎 ?섏쭛 ?꾨즺: 1h={result['tier_1h']}, 6h={result['tier_6h']}, 48h={result['tier_48h']}")
        finally:
            conn.close()

        return result

    # ?? [A] Trend Genealogy ????????????????????????????

    def save_trend_genealogy(
        self,
        keyword: str,
        parent_keyword: str = "",
        predicted_children: list[str] | None = None,
        viral_score: int = 0,
    ) -> None:
        """[A] ?몃젋??怨꾨낫 ???媛깆떊."""
        self.init_table()
        conn = self._get_conn()
        now = datetime.now(UTC).isoformat()
        children_json = json.dumps(predicted_children or [], ensure_ascii=False)
        try:
            existing = conn.execute(
                "SELECT id, total_appearances, peak_viral_score FROM trend_genealogy WHERE keyword = ? AND parent_keyword = ?",
                (keyword, parent_keyword),
            ).fetchone()
            if existing:
                new_count = existing["total_appearances"] + 1
                new_peak = max(existing["peak_viral_score"], viral_score)
                conn.execute(
                    """UPDATE trend_genealogy
                       SET last_seen_at = ?, total_appearances = ?,
                           peak_viral_score = ?, predicted_children = ?
                       WHERE id = ?""",
                    (now, new_count, new_peak, children_json, existing["id"]),
                )
            else:
                depth = 0
                if parent_keyword:
                    parent = conn.execute(
                        "SELECT genealogy_depth FROM trend_genealogy WHERE keyword = ? LIMIT 1",
                        (parent_keyword,),
                    ).fetchone()
                    depth = (parent["genealogy_depth"] + 1) if parent else 1
                conn.execute(
                    """INSERT INTO trend_genealogy
                       (keyword, parent_keyword, predicted_children, genealogy_depth,
                        first_seen_at, last_seen_at, peak_viral_score)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (keyword, parent_keyword, children_json, depth, now, now, viral_score),
                )
            conn.commit()
        finally:
            conn.close()

    def get_trend_history(self, keyword: str, hours: int = 72) -> list[dict]:
        """[A] 理쒓렐 N?쒓컙 ?대궡 ?몃젋???덉뒪?좊━ (怨꾨낫 ?곌껐??."""
        self.init_table()
        conn = self._get_conn()
        try:
            cutoff = (datetime.now(UTC) - timedelta(hours=hours)).isoformat()
            rows = conn.execute(
                """SELECT keyword, parent_keyword, predicted_children,
                          genealogy_depth, total_appearances, peak_viral_score,
                          first_seen_at, last_seen_at
                   FROM trend_genealogy
                   WHERE last_seen_at >= ?
                   ORDER BY last_seen_at DESC""",
                (cutoff,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_predicted_children(self, keyword: str) -> list[str]:
        """[A] ?뱀젙 ?몃젋?쒖쓽 ?덉륫???뚯깮 ?몃젋??紐⑸줉."""
        self.init_table()
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT predicted_children FROM trend_genealogy WHERE keyword = ? ORDER BY last_seen_at DESC LIMIT 1",
                (keyword,),
            ).fetchone()
            if row and row["predicted_children"]:
                return json.loads(row["predicted_children"])
            return []
        finally:
            conn.close()

    # ?? Utility ??????????????????????????????????????????

    def get_summary(self, days: int = 30) -> dict:
        """??쒕낫??濡쒓퉭???깃낵 ?붿빟 (?????⑦꽩 ?ы븿)."""
        stats = self.get_angle_performance(days)
        weights = self.get_optimal_angle_weights(days, _precomputed_stats=stats)
        pattern_weights = self.get_optimal_pattern_weights(days)

        self.init_table()
        conn = self._get_conn()
        try:
            cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
            row = conn.execute(
                """SELECT COUNT(*) as total,
                          AVG(engagement_rate) as avg_er,
                          AVG(impressions) as avg_imp,
                          MAX(engagement_rate) as max_er
                   FROM tweet_performance
                   WHERE collected_at >= ?""",
                (cutoff,),
            ).fetchone()
            overview = dict(row) if row else {}
        finally:
            conn.close()

        return {
            "period_days": days,
            "total_tracked": overview.get("total", 0) or 0,
            "avg_engagement_rate": round(overview.get("avg_er", 0.0) or 0.0, 6),
            "avg_impressions": round(overview.get("avg_imp", 0.0) or 0.0, 1),
            "max_engagement_rate": round(overview.get("max_er", 0.0) or 0.0, 6),
            "angle_stats": {
                k: {
                    "total_tweets": v.total_tweets,
                    "avg_impressions": v.avg_impressions,
                    "avg_engagement_rate": v.avg_engagement_rate,
                    "weight": weights.get(k, 0.2),
                }
                for k, v in stats.items()
            },
            "optimal_weights": weights,
            "pattern_weights": pattern_weights,
        }
