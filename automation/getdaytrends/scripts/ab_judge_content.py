"""getdaytrends — LLM-judge pairwise content A/B.

The deterministic content_qa scorer is a proxy: it measures hooks/format/fact
rules but cannot judge *insight depth* — whether a tweet says something sharp
and non-obvious. Three prompt hypotheses (tone, hook, endings) all tied/lost
under that proxy. This harness uses an LLM judge instead: it generates the
current prompt (A) vs a candidate (B) for the same trends and asks the model to
pick the better set, with A/B position randomized per trend to cancel order
bias. B is adopted only on a clear majority.

Candidate B adds an insight-density directive — the dimension the rule scorer
can't see but a judge can.

Run: python scripts/ab_judge_content.py --live --limit 4
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.ab_test_content_variants import _load_recent_trends

CANDIDATE_ENHANCEMENT = (
    "\n[인사이트 밀도 — 각 트윗은 남들이 놓친 '하나의 날카로운 관점'에 집중]\n"
    "표면적 사실 나열 금지. '왜 이게 진짜 중요한가'를 한 줄로 꿰뚫어라.\n"
    "구체적 디테일 1개로 그 관점을 뒷받침하라."
)

_JUDGE_SYSTEM = (
    "너는 한국어 X(트위터) 콘텐츠 편집장이다. 같은 주제로 작성된 트윗 묶음 둘(A/B)을 비교해, "
    "참여(답글·리트윗)와 인사이트 깊이 측면에서 더 나은 쪽을 고른다. "
    "표면적 요약보다 날카로운 관점·구체성을 높게 평가한다. "
    "반드시 'A' 또는 'B' 한 글자만 출력한다."
)


def _tweets_text(batch: Any) -> str:
    from content_qa import _content_group_map

    if batch is None:
        return ""
    tweets = _content_group_map(batch).get("tweets", [])
    return "\n".join(f"- {t.content}" for t in tweets if getattr(t, "content", ""))


async def _judge(client: Any, keyword: str, text_a: str, text_b: str) -> str:
    from shared.llm import TaskTier

    user = (
        f"주제: {keyword}\n\n[묶음 A]\n{text_a}\n\n[묶음 B]\n{text_b}\n\n"
        "어느 묶음이 더 나은가? 'A' 또는 'B'만."
    )
    try:
        resp = await client.acreate(
            tier=TaskTier.LIGHTWEIGHT,
            max_tokens=4,
            system=_JUDGE_SYSTEM,
            messages=[{"role": "user", "content": user}],
        )
    except Exception:
        return "?"  # judge unavailable → counted as a tie, never crashes the run
    verdict = (resp.text or "").strip().upper()
    return "A" if verdict.startswith("A") else "B" if verdict.startswith("B") else "?"


async def _run_live(limit: int, db_path: str) -> dict[str, Any]:
    import generator
    from config import AppConfig
    from generator import generate_tweets_async

    from shared.llm import get_client

    config = AppConfig.from_env()
    client = get_client()
    trends = _load_recent_trends(db_path, limit)
    if not trends:
        raise SystemExit(f"No trends found in {db_path}; run the pipeline first.")

    async def gen_a(trend: Any) -> Any:
        return await generate_tweets_async(trend, config, client)

    async def gen_b(trend: Any) -> Any:
        original = generator._system_tweets
        generator._system_tweets = lambda tone: original(tone) + CANDIDATE_ENHANCEMENT
        try:
            return await generate_tweets_async(trend, config, client)
        finally:
            generator._system_tweets = original

    a_wins = b_wins = ties = compared = 0
    # Deterministic A/B-position assignment per index (no Math.random in this env):
    # even index -> A shown first; odd -> B shown first. Verdict is mapped back.
    for idx, trend in enumerate(trends):
        batch_a = await gen_a(trend)
        batch_b = await gen_b(trend)
        text_a, text_b = _tweets_text(batch_a), _tweets_text(batch_b)
        if not text_a or not text_b:
            continue
        compared += 1
        a_first = idx % 2 == 0
        first, second = (text_a, text_b) if a_first else (text_b, text_a)
        verdict = await _judge(client, getattr(trend, "keyword", ""), first, second)
        if verdict == "?":
            ties += 1
            continue
        # map shown-position verdict back to A/B
        winner_is_a = (verdict == "A") == a_first
        if winner_is_a:
            a_wins += 1
        else:
            b_wins += 1

    decision = "adopt_B" if b_wins > a_wins and b_wins - a_wins >= 2 and compared >= 4 else "keep_A"
    return {
        "compared": compared,
        "a_wins": a_wins,
        "b_wins": b_wins,
        "ties": ties,
        "decision": decision,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LLM-judge pairwise content A/B (insight-density candidate).")
    parser.add_argument("--live", action="store_true", help="Generate + judge with the real LLM (spends budget).")
    parser.add_argument("--limit", type=int, default=4, help="Recent trends to test (default 4).")
    parser.add_argument("--db-path", default=str(PROJECT_ROOT / "data" / "getdaytrends.db"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if not args.live:
        print(json.dumps({"status": "dry", "message": "Re-run with --live to spend budget."}, ensure_ascii=False))
        return 0
    summary = asyncio.run(_run_live(args.limit, args.db_path))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
