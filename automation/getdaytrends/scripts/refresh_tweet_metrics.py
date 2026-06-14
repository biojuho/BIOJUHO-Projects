"""getdaytrends — measured-metrics refresh CLI.

Closes the measured-label gap that blocks the viral-scoring A/B harness.

Posted tweets already carry an ``x_tweet_id`` in the ``tweets`` table, but their
``impressions`` / ``engagements`` / ``engagement_rate`` columns stay ``0`` until
something pulls real performance back in. Without those measured outcomes the
A/B export (``scripts/export_ab_test_viral_scoring_dataset.py``) can only fall
back to weak recurrence-inferred labels, so scoring experiments cannot be
validated against what actually performed.

This script wires the two helpers that already exist but were never connected:

* ``x_client.get_tweet_metrics`` — pull likes/retweets/quotes/replies/views.
* ``db_layer.tweet_repository.sync_tweet_metrics`` — persist the measured row.

Modes
-----
``--from-x``
    For every posted tweet with an ``x_tweet_id`` (and, unless ``--all``,
    still-zero impressions) call the X metrics endpoint and store the result.

manual entry
    ``--tweet-id <row_id>`` or ``--x-tweet-id <id>`` together with
    ``--impressions`` / ``--engagements`` records a measured outcome for the
    manual-publishing workflow when the X metrics API is unavailable. This is
    the realistic path for this project, which publishes manually.

No schema change and no new dependency: the columns and helpers already exist.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MetricsFetcher = Callable[[str], Awaitable[dict[str, Any] | None]]


def engagement_from_x_metrics(metrics: dict[str, Any]) -> tuple[int, int, float]:
    """Map a raw X metrics dict to ``(impressions, engagements, engagement_rate)``.

    ``impressions`` tracks views (the reach denominator). ``engagements`` sums
    the interaction signals. ``engagement_rate`` is engagements / impressions,
    clamped to ``0.0`` when impressions are unknown so we never divide by zero.
    """
    impressions = int(metrics.get("views", 0) or 0)
    engagements = (
        int(metrics.get("likes", 0) or 0)
        + int(metrics.get("retweets", 0) or 0)
        + int(metrics.get("quotes", 0) or 0)
        + int(metrics.get("replies", 0) or 0)
    )
    rate = round(engagements / impressions, 6) if impressions > 0 else 0.0
    return impressions, engagements, rate


async def _select_posted_tweets(conn, *, only_missing: bool) -> list[dict[str, Any]]:
    """Return posted tweets that carry an ``x_tweet_id`` for metric refresh."""
    query = (
        "SELECT id, x_tweet_id, impressions, engagements "
        "FROM tweets "
        "WHERE x_tweet_id IS NOT NULL AND x_tweet_id != ''"
    )
    if only_missing:
        query += " AND (impressions IS NULL OR impressions = 0)"
    cursor = await conn.execute(query)
    rows = await cursor.fetchall()
    return [
        {
            "id": row[0],
            "x_tweet_id": row[1],
            "impressions": row[2],
            "engagements": row[3],
        }
        for row in rows
    ]


async def refresh_from_x(
    conn,
    *,
    fetcher: MetricsFetcher,
    only_missing: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Fetch live X metrics for posted tweets and persist them.

    ``fetcher`` is injected so tests can exercise the orchestration without a
    real X client. Returns a machine-readable summary.
    """
    from db_layer.tweet_repository import sync_tweet_metrics

    candidates = await _select_posted_tweets(conn, only_missing=only_missing)
    updated = 0
    skipped: list[str] = []
    details: list[dict[str, Any]] = []

    for row in candidates:
        x_id = row["x_tweet_id"]
        metrics = await fetcher(x_id)
        if not metrics:
            skipped.append(x_id)
            continue
        impressions, engagements, rate = engagement_from_x_metrics(metrics)
        detail = {
            "tweet_id": row["id"],
            "x_tweet_id": x_id,
            "impressions": impressions,
            "engagements": engagements,
            "engagement_rate": rate,
        }
        details.append(detail)
        if not dry_run:
            await sync_tweet_metrics(
                conn,
                tweet_row_id=row["id"],
                impressions=impressions,
                engagements=engagements,
                engagement_rate=rate,
            )
            updated += 1

    return {
        "mode": "from_x",
        "dry_run": dry_run,
        "candidates": len(candidates),
        "updated": updated,
        "skipped_no_metrics": skipped,
        "details": details,
    }


async def set_manual(
    conn,
    *,
    tweet_row_id: int | None = None,
    x_tweet_id: str = "",
    impressions: int,
    engagements: int,
    engagement_rate: float | None = None,
) -> dict[str, Any]:
    """Record a manually measured outcome for one posted tweet."""
    from db_layer.tweet_repository import sync_tweet_metrics

    if engagement_rate is None:
        engagement_rate = round(engagements / impressions, 6) if impressions > 0 else 0.0

    rows = await sync_tweet_metrics(
        conn,
        tweet_row_id=tweet_row_id,
        x_tweet_id=x_tweet_id,
        impressions=impressions,
        engagements=engagements,
        engagement_rate=engagement_rate,
    )
    return {
        "mode": "manual",
        "matched": rows,
        "tweet_id": tweet_row_id,
        "x_tweet_id": x_tweet_id,
        "impressions": impressions,
        "engagements": engagements,
        "engagement_rate": engagement_rate,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh measured X engagement metrics for posted getdaytrends tweets.",
    )
    parser.add_argument(
        "--db-path",
        default=str(PROJECT_ROOT / "data" / "getdaytrends.db"),
        help="Path to the GetDayTrends SQLite database.",
    )
    parser.add_argument(
        "--from-x",
        action="store_true",
        help="Pull metrics from the X API for posted tweets with an x_tweet_id.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="With --from-x, refresh every posted tweet, not only those with zero impressions.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="With --from-x, report what would change without writing.",
    )
    parser.add_argument("--tweet-id", type=int, default=None, help="Manual entry: tweets.id row id.")
    parser.add_argument("--x-tweet-id", default="", help="Manual entry: x_tweet_id to match.")
    parser.add_argument("--impressions", type=int, default=None, help="Manual entry: measured impressions.")
    parser.add_argument("--engagements", type=int, default=None, help="Manual entry: measured engagements.")
    return parser.parse_args(argv)


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    from db_layer.connection import get_connection

    conn = await get_connection(db_path=args.db_path)
    try:
        if args.from_x:
            from x_client import get_tweet_metrics

            return await refresh_from_x(
                conn,
                fetcher=get_tweet_metrics,
                only_missing=not args.all,
                dry_run=args.dry_run,
            )
        if args.impressions is not None and (args.tweet_id is not None or args.x_tweet_id):
            return await set_manual(
                conn,
                tweet_row_id=args.tweet_id,
                x_tweet_id=args.x_tweet_id,
                impressions=args.impressions,
                engagements=args.engagements or 0,
            )
        raise SystemExit(
            "Nothing to do: pass --from-x, or a manual entry "
            "(--tweet-id/--x-tweet-id with --impressions)."
        )
    finally:
        try:
            await conn.close()
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    summary = asyncio.run(_run(args))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
