"""getdaytrends — content variant A/B harness (tone experiment).

The generator already ships ``generate_ab_variant_async`` (variant B: a blunt,
argumentative tone) but **nothing ever called it** — the variant-B tone was
dormant infrastructure with no way to tell whether it beats the default tone
(variant A). This harness wires both up:

1. generate variant A (``generate_for_trend_async``) and variant B
   (``generate_ab_variant_async``) for the same trends;
2. score each batch's shortform tweets with the deterministic, rule-based
   content_qa auditor (``_audit_content_group`` — **no extra LLM cost**);
3. report per-trend winners and an aggregate adopt/keep decision.

Cost model: only generation spends LLM budget. The comparison and decision
logic is pure and unit-tested offline with injected generators (zero spend).
Live generation runs only under ``--live`` (this spends API budget).

Decision rule: adopt variant B only if its mean deterministic score beats
variant A and it does not introduce more QA failures than A.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# (trend) -> TweetBatch | None
VariantGenerator = Callable[[Any], Awaitable[Any]]


def score_tweet_batch(batch: Any, trend: Any, config: Any) -> dict[str, Any]:
    """Score a batch's shortform tweets with the deterministic content_qa auditor."""
    from content_qa import _audit_content_group, _content_group_map

    if batch is None:
        return {"total": 0, "failed": True, "n": 0, "worst": "", "generated": False}
    tweets = _content_group_map(batch).get("tweets", [])
    if not tweets:
        return {"total": 0, "failed": True, "n": 0, "worst": "", "generated": False}
    res = _audit_content_group("tweets", tweets, trend, config)
    return {
        "total": int(res.get("total", 0)),
        "failed": bool(res.get("failed", False)),
        "n": len(tweets),
        "worst": str(res.get("worst", "")),
        "generated": True,
    }


def decide_winner(score_a: dict[str, Any], score_b: dict[str, Any]) -> str:
    """Per-trend winner. B wins only if it scored higher without adding a failure."""
    if not score_b.get("generated"):
        return "A" if score_a.get("generated") else "none"
    if not score_a.get("generated"):
        return "B"
    b_no_worse_failure = score_b["failed"] is False or score_a["failed"] is True
    if score_b["total"] > score_a["total"] and b_no_worse_failure:
        return "B"
    return "A"


async def compare_trend_variants(
    trend: Any,
    config: Any,
    gen_a: VariantGenerator,
    gen_b: VariantGenerator,
) -> dict[str, Any]:
    """Generate both variants for one trend and score them."""
    batch_a = await gen_a(trend)
    batch_b = await gen_b(trend)
    score_a = score_tweet_batch(batch_a, trend, config)
    score_b = score_tweet_batch(batch_b, trend, config)
    return {
        "keyword": getattr(trend, "keyword", ""),
        "score_a": score_a,
        "score_b": score_b,
        "winner": decide_winner(score_a, score_b),
        "delta": score_b["total"] - score_a["total"],
    }


async def run_ab(
    trends: list[Any],
    config: Any,
    gen_a: VariantGenerator,
    gen_b: VariantGenerator,
) -> dict[str, Any]:
    """Run the A/B comparison across trends and aggregate the decision."""
    results = [await compare_trend_variants(t, config, gen_a, gen_b) for t in trends]
    scored = [r for r in results if r["score_a"]["generated"] and r["score_b"]["generated"]]
    avg_a = round(sum(r["score_a"]["total"] for r in scored) / len(scored), 2) if scored else 0.0
    avg_b = round(sum(r["score_b"]["total"] for r in scored) / len(scored), 2) if scored else 0.0
    a_fail = sum(1 for r in scored if r["score_a"]["failed"])
    b_fail = sum(1 for r in scored if r["score_b"]["failed"])
    adopt_b = bool(scored) and avg_b > avg_a and b_fail <= a_fail
    return {
        "trends": len(results),
        "compared": len(scored),
        "a_wins": sum(1 for r in results if r["winner"] == "A"),
        "b_wins": sum(1 for r in results if r["winner"] == "B"),
        "avg_a": avg_a,
        "avg_b": avg_b,
        "a_failures": a_fail,
        "b_failures": b_fail,
        "decision": "adopt_B" if adopt_b else "keep_A",
        "results": results,
    }


def _row_to_scored_trend(row: sqlite3.Row) -> Any:
    """Reconstruct a minimal ScoredTrend from a trends-table row for generation."""
    from models import MultiSourceContext, ScoredTrend

    def _loads(value: Any) -> list:
        try:
            parsed = json.loads(value) if value else []
            return parsed if isinstance(parsed, list) else []
        except (TypeError, ValueError):
            return []

    data = dict(row)
    context = MultiSourceContext(
        twitter_insight=str(data.get("twitter_context") or ""),
        reddit_insight=str(data.get("reddit_context") or ""),
        news_insight=str(data.get("news_context") or ""),
    )
    return ScoredTrend(
        keyword=str(data.get("keyword") or ""),
        rank=int(data.get("rank") or 1),
        viral_potential=int(data.get("viral_potential") or 0),
        trend_acceleration=str(data.get("trend_acceleration") or "+0%"),
        top_insight=str(data.get("top_insight") or ""),
        suggested_angles=[str(a) for a in _loads(data.get("suggested_angles"))],
        best_hook_starter=str(data.get("best_hook_starter") or ""),
        category=str(data.get("category") or ""),
        sentiment=str(data.get("sentiment") or "neutral"),
        context=context,
    )


def _load_recent_trends(db_path: str, limit: int) -> list[Any]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM trends WHERE keyword IS NOT NULL AND keyword != '' "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_scored_trend(row) for row in rows]


async def _run_live(limit: int, db_path: str) -> dict[str, Any]:
    from config import AppConfig
    from generator import generate_ab_variant_async, generate_tweets_async

    from shared.llm import get_client

    config = AppConfig.from_env()
    client = get_client()
    trends = _load_recent_trends(db_path, limit)
    if not trends:
        raise SystemExit(f"No trends found in {db_path}; run the pipeline first.")

    # Variant A = default-tone shortform tweets, symmetric with variant B
    # (generate_ab_variant_async). Using the tweet-only generator keeps the
    # comparison apples-to-apples and avoids the slow/broken heavy-tier blog path.
    async def gen_a(trend: Any) -> Any:
        return await generate_tweets_async(trend, config, client)

    async def gen_b(trend: Any) -> Any:
        return await generate_ab_variant_async(trend, config, client)

    return await run_ab(trends, config, gen_a, gen_b)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="A/B test content tone variants (A=default, B=blunt) and score them.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Generate with the real LLM client (SPENDS API BUDGET). Without it the harness only self-checks.",
    )
    parser.add_argument("--limit", type=int, default=3, help="How many recent trends to test (default 3).")
    parser.add_argument(
        "--db-path",
        default=str(PROJECT_ROOT / "data" / "getdaytrends.db"),
        help="SQLite DB to pull recent trends from.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if not args.live:
        print(
            json.dumps(
                {
                    "status": "dry",
                    "message": (
                        "Comparison/scoring logic is import-OK. Re-run with --live to spend "
                        "LLM budget on real generation across --limit trends."
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    summary = asyncio.run(_run_live(args.limit, args.db_path))
    summary.pop("results", None)  # keep stdout compact; per-trend detail is large
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
