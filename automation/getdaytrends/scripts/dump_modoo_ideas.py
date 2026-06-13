"""Standalone runner: dump modoo.or.kr 도전 아이디어 to disk.

Bypasses the main `collect_trends` pipeline (where modoo signals get crowded out
by the primary getdaytrends source) and writes a raw dump suited for daily
Korean startup-trend mining.

Usage:
    python scripts/dump_modoo_ideas.py --pages 5
    python scripts/dump_modoo_ideas.py --pages 10 --out-dir ./var/modoo

Outputs (date-stamped, KST):
    <out-dir>/modoo-ideas-YYYY-MM-DD.json    # full RawTrend dump
    <out-dir>/modoo-ideas-YYYY-MM-DD.md      # categorized markdown summary
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
GDT_DIR = SCRIPT_DIR.parent
if str(GDT_DIR) not in sys.path:
    sys.path.insert(0, str(GDT_DIR))

from collectors.modoo import fetch_modoo_ideas  # noqa: E402
from models import RawTrend  # noqa: E402

KST = timezone(timedelta(hours=9))


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return parsed


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pages", type=_positive_int, default=5, help="modoo list pages to fetch (each = 12 ideas)")
    parser.add_argument("--timeout-ms", type=int, default=60_000, help="per-page Playwright nav timeout")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=GDT_DIR.parent.parent / "var" / "modoo",
        help="output directory (default: <workspace>/var/modoo)",
    )
    return parser.parse_args(argv)


def _to_jsonable(trend: RawTrend) -> dict:
    return {
        "name": trend.name,
        "category": trend.extra.get("category", ""),
        "time": trend.extra.get("time", ""),
        "page": trend.extra.get("page", 0),
        "volume_numeric": trend.volume_numeric,
        "fetched_at": trend.fetched_at.isoformat(),
    }


def _to_markdown(trends: list[RawTrend], stamp: str) -> str:
    by_cat: dict[str, list[RawTrend]] = defaultdict(list)
    for t in trends:
        by_cat[t.extra.get("category", "기타")].append(t)

    lines = [
        f"# 모두의 창업 도전 아이디어 — {stamp}",
        "",
        f"- 수집 시각(KST): {datetime.now(KST):%Y-%m-%d %H:%M}",
        f"- 총 아이디어: **{len(trends)}건** (중복 제거 후)",
        f"- 카테고리: {', '.join(f'{c} {len(v)}건' for c, v in sorted(by_cat.items(), key=lambda x: -len(x[1])))}",
        "",
    ]
    for cat, items in sorted(by_cat.items(), key=lambda x: -len(x[1])):
        lines.append(f"## {cat} ({len(items)}건)")
        lines.append("")
        for t in items:
            time_str = t.extra.get("time", "")
            time_suffix = f" — {time_str}" if time_str else ""
            lines.append(f"- {t.name}{time_suffix}")
        lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    trends = fetch_modoo_ideas(pages=args.pages, timeout_ms=args.timeout_ms)
    if not trends:
        print("[dump_modoo_ideas] collected 0 ideas — Node/Playwright unavailable or fetch failed", file=sys.stderr)
        return 1

    stamp = datetime.now(KST).strftime("%Y-%m-%d")
    json_path = args.out_dir / f"modoo-ideas-{stamp}.json"
    md_path = args.out_dir / f"modoo-ideas-{stamp}.md"

    payload = {
        "fetched_at_kst": datetime.now(KST).isoformat(),
        "pages_requested": args.pages,
        "count": len(trends),
        "ideas": [_to_jsonable(t) for t in trends],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_to_markdown(trends, stamp), encoding="utf-8")

    print(f"[dump_modoo_ideas] {len(trends)} ideas → {json_path}", file=sys.stderr)
    print(f"[dump_modoo_ideas] markdown summary → {md_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
