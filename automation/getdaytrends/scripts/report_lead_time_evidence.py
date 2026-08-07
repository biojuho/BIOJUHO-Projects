#!/usr/bin/env python3
"""Re-runnable lead-time evidence report (read-only over observation store).

Definition:
  lead_minutes = aggregator_first_seen_at − direct_first_seen_at
  positive → we saw the post on a direct community listing before IssueLink
  negative → IssueLink/aggregator had it first (we were late)

Does not write to the observation JSON. Pass the path to viral_lead_times.json.

Example:
  python scripts/report_lead_time_evidence.py data/viral_lead_times.json
  python scripts/report_lead_time_evidence.py /path/to/viral_lead_times.json --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lead_time_tracker import load_lead_time_store, summarize_lead_time_store  # noqa: E402


def _print_human(summary: dict) -> None:
    signed = summary["signed_lead"]
    span = summary["time_span_utc"]
    print("LEAD TIME EVIDENCE (read-only)")
    print("definition:", summary["definition"])
    print("store_updated_at:", summary.get("store_updated_at"))
    print("time_span_utc:", span.get("start"), "->", span.get("end"))
    print("records:", summary["record_count"])
    print(
        "paired (both timestamps):",
        summary["paired_count"],
        f"({summary['pair_rate_pct']}% of records)",
    )
    print("status_counts:", summary["status_counts"])
    print("evidence_grade:", summary["evidence_grade"])
    if summary["paired_count"] < 10:
        print(
            "NOTE: paired sample < 10 — treat as a directional signal only; "
            "do not promote to a conclusion."
        )
    print("--- signed lead (both timestamps only) ---")
    print("n:", signed["n"])
    print("median_minutes (all signed):", signed["median_minutes"])
    print("mean_minutes (all signed):", signed["mean_minutes"])
    print(
        "positive:",
        signed["positive_count"],
        f"({signed['positive_share_pct']}%)",
        "median:",
        signed["positive_median_minutes"],
    )
    print(
        "negative (late):",
        signed["negative_count"],
        f"({signed['negative_share_pct']}%)",
        "median:",
        signed["negative_median_minutes"],
    )
    print(
        "zero (same poll):",
        signed["zero_count"],
        f"({signed['zero_share_pct']}%)",
    )
    print("buckets_minutes:", signed["buckets"])
    print("--- by source (paired only) ---")
    for row in summary["by_source"]:
        print(
            f"{row['community_source']}: n={row['paired_count']} "
            f"med={row['median_lead_minutes']} "
            f"pos%={row['positive_share_pct']} neg%={row['negative_share_pct']} "
            f"zero%={row['zero_share_pct']}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "store",
        type=Path,
        help="Path to viral_lead_times.json (read-only)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable summary JSON",
    )
    args = parser.parse_args(argv)
    store_path = args.store.expanduser().resolve()
    if not store_path.is_file():
        print(f"error: store not found: {store_path}", file=sys.stderr)
        return 2
    # Read only — never open for write.
    payload = load_lead_time_store(store_path)
    summary = summarize_lead_time_store(payload)
    summary["store_path"] = str(store_path)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        _print_human(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
