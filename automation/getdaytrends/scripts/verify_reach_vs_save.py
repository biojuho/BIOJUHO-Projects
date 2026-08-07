#!/usr/bin/env python3
"""Verify the claim: X reach and save move in opposite directions.

Read-only over docs/x-reach-vs-save-*.csv. Does not modify the CSV.

Claim under test (planner, 2026-08-07):
  posts that spread widely and posts that get bookmarked are different;
  save_rate (bookmarks/views) bottom tertile had median views 1.46M vs
  top tertile 120k on a 44-row scrape (not fully preserved).

This script only sees the surviving 20 rows. It also checks absolute
bookmarks, because save_rate has views in the denominator.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from statistics import mean, median
from typing import Any


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    def ranks(vals: list[float]) -> list[float]:
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        out = [0.0] * len(vals)
        i = 0
        while i < len(vals):
            j = i
            while j + 1 < len(vals) and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out

    if len(xs) != len(ys) or len(xs) < 2:
        return None
    rx, ry = ranks(xs), ranks(ys)
    mx, my = mean(rx), mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    denx = sum((a - mx) ** 2 for a in rx) ** 0.5
    deny = sum((b - my) ** 2 for b in ry) ** 0.5
    if denx == 0 or deny == 0:
        return None
    return num / (denx * deny)


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", newline="") as fh:
        for raw in csv.DictReader(fh):
            views = int(str(raw["views"]).replace(",", ""))
            bookmark = int(str(raw["bookmark"]).replace(",", ""))
            rows.append(
                {
                    "views": views,
                    "reply": int(str(raw["reply"]).replace(",", "")),
                    "rt": int(str(raw["rt"]).replace(",", "")),
                    "like": int(str(raw["like"]).replace(",", "")),
                    "bookmark": bookmark,
                    "media": raw.get("media") or "",
                    "is_quote": raw.get("is_quote") or "",
                    "caption_prefix": raw.get("caption_prefix") or "",
                    "save_rate": (bookmark / views) if views else None,
                }
            )
    return rows


def tertile_ends(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda r: r[key])
    n = len(ordered)
    k = n // 3
    low, high = ordered[:k], ordered[-k:]
    return {
        "n_each_end": k,
        "bottom": {
            "n": len(low),
            "views_median": median([r["views"] for r in low]),
            "bookmark_median": median([r["bookmark"] for r in low]),
            "save_rate_median_pct": 100 * median([r["save_rate"] for r in low]),
        },
        "top": {
            "n": len(high),
            "views_median": median([r["views"] for r in high]),
            "bookmark_median": median([r["bookmark"] for r in high]),
            "save_rate_median_pct": 100 * median([r["save_rate"] for r in high]),
        },
    }


def analyze(path: Path) -> dict[str, Any]:
    blob = path.read_bytes()
    rows = load_rows(path)
    views = [r["views"] for r in rows]
    rates = [float(r["save_rate"]) for r in rows]
    bookmarks = [r["bookmark"] for r in rows]
    by_views = sorted(rows, key=lambda r: -r["views"])
    return {
        "csv_path": str(path.resolve()),
        "sha256": hashlib.sha256(blob).hexdigest(),
        "n_rows": len(rows),
        "note_44_row_aggregate": (
            "Planner reported bottom/top save-rate tertile view medians "
            "1.46M / 120k on 44 rows; only 20 rows remain in the file "
            "(browser session lost 24). That 44-row table is not reproducible."
        ),
        "claimed_44": {
            "bottom_sr_tertile_views_median": 1_460_000,
            "top_sr_tertile_views_median": 120_000,
            "ratio": 12.0,
        },
        "observed_20_by_save_rate": tertile_ends(rows, "save_rate"),
        "observed_20_by_absolute_bookmark": tertile_ends(rows, "bookmark"),
        "spearman": {
            "views_vs_save_rate": _spearman(views, rates),
            "views_vs_bookmark_absolute": _spearman(views, bookmarks),
            "views_vs_like": _spearman(views, [r["like"] for r in rows]),
        },
        "top_views": [
            {
                "views": r["views"],
                "bookmark": r["bookmark"],
                "save_rate_pct": round(100 * float(r["save_rate"]), 4),
                "caption_prefix": r["caption_prefix"][:40],
            }
            for r in by_views[:3]
        ],
        "top_save_rate": [
            {
                "views": r["views"],
                "bookmark": r["bookmark"],
                "save_rate_pct": round(100 * float(r["save_rate"]), 4),
                "caption_prefix": r["caption_prefix"][:40],
            }
            for r in sorted(rows, key=lambda r: -float(r["save_rate"]))[:3]
        ],
        "confounders": {
            "elapsed_time": (
                "No posted_at column. Sample was said to mix 5h–3d age. "
                "Cannot control; kernel 0-1#2 applies. Uncontrollable here."
            ),
            "rate_definition": (
                "save_rate = bookmark/views; large views shrink the rate "
                "even when absolute bookmarks are high."
            ),
            "sample_bias": (
                "Creator inspiration feed for one account; includes mega "
                "fan/official posts (e.g. ROSÉ notice, celebrity quote)."
            ),
            "sample_size": "n=20 — directional signal only (kernel 0-1#3).",
        },
        "verdict": "판단 불가",
        "verdict_sentence": (
            "판단 불가 — 남은 20건에서 저장률↔노출의 역방향은 보이지만 "
            "북마크 절대수는 노출과 같이 커지고, 게시 경과시간을 통제할 수 없으며 "
            "주장의 44건 3분위(146만/12만)는 재현 불가라  substantive 반비례를 "
            "이 자료만으로 확정하거나 기각할 수 없다."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "csv_path",
        type=Path,
        nargs="?",
        default=Path(__file__).resolve().parents[3] / "docs" / "x-reach-vs-save-2026-08-07.csv",
        help="Path to reach-vs-save CSV (read-only)",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    path = args.csv_path.expanduser().resolve()
    if not path.is_file():
        print(f"error: csv not found: {path}", file=sys.stderr)
        return 2
    report = analyze(path)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print("REACH vs SAVE VERIFICATION (read-only)")
    print("csv:", report["csv_path"])
    print("sha256:", report["sha256"])
    print("n_rows:", report["n_rows"])
    print("NOTE:", report["note_44_row_aggregate"])
    sr = report["observed_20_by_save_rate"]
    print("--- by save_rate tertile ends (n//3 each) ---")
    print("bottom views_median:", sr["bottom"]["views_median"], "bm_median:", sr["bottom"]["bookmark_median"])
    print("top    views_median:", sr["top"]["views_median"], "bm_median:", sr["top"]["bookmark_median"])
    if sr["top"]["views_median"]:
        print(
            "views ratio bottom/top:",
            round(sr["bottom"]["views_median"] / sr["top"]["views_median"], 2),
        )
    print("claimed_44 ratio ~12; 20-row direction:", "same" if sr["bottom"]["views_median"] > sr["top"]["views_median"] else "different")
    ab = report["observed_20_by_absolute_bookmark"]
    print("--- by ABSOLUTE bookmark tertile ends ---")
    print("low-bm  views_median:", ab["bottom"]["views_median"])
    print("high-bm views_median:", ab["top"]["views_median"])
    print("spearman views vs save_rate:", report["spearman"]["views_vs_save_rate"])
    print("spearman views vs bookmark abs:", report["spearman"]["views_vs_bookmark_absolute"])
    print("VERDICT:", report["verdict"])
    print(report["verdict_sentence"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
