from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    project_dir = script_dir.parent
    parser = argparse.ArgumentParser(description="Collect X performance metrics for posted GetDayTrends tweets.")
    parser.add_argument(
        "--db-path",
        default=str(project_dir / "data" / "getdaytrends.db"),
        help="Path to the GetDayTrends SQLite database.",
    )
    parser.add_argument(
        "--lookback-hours",
        type=int,
        default=72,
        help="Only inspect tweets posted within this lookback window.",
    )
    parser.add_argument(
        "--bearer-token",
        default=os.environ.get("TWITTER_BEARER_TOKEN", os.environ.get("X_BEARER_TOKEN", "")),
        help="X bearer token. Defaults to TWITTER_BEARER_TOKEN or X_BEARER_TOKEN.",
    )
    parser.add_argument(
        "--json-out",
        help="Optional JSON summary output path.",
    )
    return parser.parse_args()


async def run_collection(args: argparse.Namespace) -> dict:
    from performance_tracker import PerformanceTracker

    tracker = PerformanceTracker(db_path=args.db_path, bearer_token=args.bearer_token)
    collected = await tracker.run_collection_cycle(lookback_hours=args.lookback_hours)
    summary = tracker.get_summary(days=max(1, round(args.lookback_hours / 24)))
    return {
        "generated_at": datetime.now(UTC).astimezone().isoformat(),
        "db_path": str(Path(args.db_path).resolve()),
        "lookback_hours": args.lookback_hours,
        "collected_count": collected,
        "summary": summary,
    }


def write_json(path_str: str, payload: dict) -> Path:
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def main() -> int:
    args = parse_args()
    if not args.bearer_token:
        raise SystemExit("Missing bearer token. Set TWITTER_BEARER_TOKEN or pass --bearer-token.")

    payload = asyncio.run(run_collection(args))
    if args.json_out:
        output_path = write_json(args.json_out, payload)
        print(f"json_out: {output_path}")

    print(f"collected_count: {payload['collected_count']}")
    print(f"db_path: {payload['db_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
