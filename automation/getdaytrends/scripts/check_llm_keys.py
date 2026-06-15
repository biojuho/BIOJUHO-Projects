"""getdaytrends — live LLM key/tier preflight check.

`--doctor` validates that LLM *modules* import, but not that the configured API
*keys* actually work. A leaked/revoked/quota-exhausted key (e.g. a Google key
Google flags as leaked → 403) stays invisible until a MEDIUM/HEAVY-tier call
fails at runtime, silently degrading generation. This probe sends a 1-token
request per task tier and reports the status, so the operator catches dead keys
before launch.

Run: python scripts/check_llm_keys.py   (spends a few cents)
Exit code is non-zero if any tier fails, for CI/launch gating.
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


def _classify(error: Exception) -> str:
    """Map a probe error to a short operator-facing status."""
    msg = str(error).lower()
    if "leaked" in msg:
        return "key_leaked"
    if "403" in msg or "permission denied" in msg or "unauthorized" in msg or "401" in msg:
        return "auth_failed"
    if "invalid api key" in msg or "invalid_api_key" in msg or "authentication" in msg:
        return "auth_failed"
    if "quota" in msg or "insufficient_quota" in msg or "429" in msg:
        return "quota_exhausted"
    if "not found" in msg and "model" in msg:
        return "model_not_found"
    if "timeout" in msg or "timed out" in msg:
        return "timeout"
    return "error"


async def _probe_tier(client: Any, tier: Any) -> dict[str, Any]:
    try:
        # max_tokens must be a few tokens: with 1, some providers (Anthropic)
        # return an empty body (stop_reason=max_tokens) and look falsely dead.
        resp = await client.acreate(
            tier=tier,
            max_tokens=5,
            system="Reply with the word: ok",
            messages=[{"role": "user", "content": "ping"}],
        )
        ok = bool((resp.text or "").strip())
        return {"tier": tier.name, "status": "ok" if ok else "empty_response", "ok": ok}
    except Exception as exc:  # noqa: BLE001 - operator probe: report every failure mode
        return {"tier": tier.name, "status": _classify(exc), "ok": False, "detail": str(exc)[:140]}


async def _run() -> dict[str, Any]:
    from shared.llm import TaskTier, get_client

    client = get_client()
    results = [await _probe_tier(client, tier) for tier in TaskTier]
    failed = [r for r in results if not r["ok"]]
    return {
        "status": "pass" if not failed else "fail",
        "tiers": results,
        "failed_tiers": [r["tier"] for r in failed],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe each LLM task tier and report key/tier health.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON only.")
    args = parser.parse_args(argv)

    summary = asyncio.run(_run())
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"LLM key preflight: {summary['status']}")
        for tier in summary["tiers"]:
            mark = "OK " if tier["ok"] else "XX "
            line = f"  [{mark}] {tier['tier']}: {tier['status']}"
            if tier.get("detail") and not tier["ok"]:
                line += f"  ({tier['detail']})"
            print(line)
        if summary["failed_tiers"]:
            print(f"  -> rotate/fix keys for: {', '.join(summary['failed_tiers'])}")
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
