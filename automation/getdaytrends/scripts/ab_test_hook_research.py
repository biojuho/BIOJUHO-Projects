"""getdaytrends — research-informed hook A/B experiment.

External research on 2025-2026 viral short-form copy (HOOK → VALUE → CTA; the
curiosity / contrarian / question / problem-agitation hook families; first ~10
words decide the scroll-stop; specific beats generic) suggests the default tweet
prompt under-specifies the hook: it says only "첫 문장에 훅 필수" without naming a
technique.

This experiment A/B-tests that hypothesis cheaply and reproducibly:
variant A = the current production prompt, variant B = the same prompt plus a
research-backed hook block. Both are generated for the same trends and scored
with the deterministic content_qa auditor (no extra LLM cost beyond generation),
reusing the run_ab harness. If B wins under the strengthened adoption rule, the
hook block is worth folding into the production prompt.

Run: python scripts/ab_test_hook_research.py --live --limit 3
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

from scripts.ab_test_content_variants import _load_recent_trends, run_ab

# Named prompt-enhancement hypotheses, each appended to the production system
# prompt for the experimental variant. Add new candidates here to A/B them.
PROMPT_ENHANCEMENTS = {
    # Research-backed hook block, from 2025-26 viral short-form findings.
    "hook": (
        "\n[훅 강화 — 첫 문장 10단어 이내, 스크롤 정지가 목표]\n"
        "5개 트윗의 첫 문장은 아래 훅 유형을 서로 다르게 변형해 사용:\n"
        "- 호기심: 의외의 결과·수치를 미끼로 ('~했더니 ~됐다')\n"
        "- 논쟁: 통념을 뒤집는 단언 ('~는 이제 끝났다')\n"
        "- 질문: 독자의 지금 고민을 정확히 찌르는 질문\n"
        "- 문제제기: 독자의 불편을 콕 집기 ('~때문에 지친 사람?')\n"
        "일반론 금지 — 구체적 디테일이 공감을 만든다."
    ),
    # Targets the content_qa clipped-ending penalty (>2 sentences ending in 음/임).
    "endings": (
        "\n[종결 다양화 — 5개 트윗의 끝맺음을 서로 다르게]\n"
        "'~음/~임'으로 끝나는 트윗은 최대 2개. 나머지는 질문(?)·명령·인용·여운(…)·감탄 등으로 변형.\n"
        "같은 종결 어미를 반복하면 단조롭다."
    ),
}


async def _run_live(limit: int, db_path: str, variant: str) -> dict[str, Any]:
    enhancement = PROMPT_ENHANCEMENTS[variant]
    import generator
    from config import AppConfig
    from generator import generate_tweets_async

    from shared.llm import get_client

    config = AppConfig.from_env()
    client = get_client()
    trends = _load_recent_trends(db_path, limit)
    if not trends:
        raise SystemExit(f"No trends found in {db_path}; run the pipeline first.")

    async def gen_current(trend: Any) -> Any:
        return await generate_tweets_async(trend, config, client)

    async def gen_research(trend: Any) -> Any:
        # Patch the system prompt only for this variant's generation, then restore.
        original = generator._system_tweets
        generator._system_tweets = lambda tone: original(tone) + enhancement
        try:
            return await generate_tweets_async(trend, config, client)
        finally:
            generator._system_tweets = original

    # In this harness, "A" is the baseline (current prompt), "B" is the research variant.
    return await run_ab(trends, config, gen_current, gen_research)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A/B test a prompt-enhancement hypothesis against the baseline.")
    parser.add_argument("--live", action="store_true", help="Generate with the real LLM (spends budget).")
    parser.add_argument("--limit", type=int, default=3, help="Recent trends to test (default 3).")
    parser.add_argument(
        "--variant",
        choices=sorted(PROMPT_ENHANCEMENTS),
        default="hook",
        help="Which prompt-enhancement hypothesis to test against the baseline.",
    )
    parser.add_argument("--db-path", default=str(PROJECT_ROOT / "data" / "getdaytrends.db"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if not args.live:
        print(
            json.dumps(
                {"status": "dry", "variant": args.variant, "message": "Re-run with --live to spend budget."},
                ensure_ascii=False,
            )
        )
        return 0
    summary = asyncio.run(_run_live(args.limit, args.db_path, args.variant))
    summary["variant"] = args.variant
    summary.pop("results", None)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
