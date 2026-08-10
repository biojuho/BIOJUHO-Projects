#!/usr/bin/env python3
"""Export a deterministic, verdict-stratified human-labeling TSV."""

from __future__ import annotations

import argparse
import csv
import hashlib
import sqlite3
import sys
from datetime import UTC, datetime, time, timedelta, timezone
from pathlib import Path

try:
    from .shadow_store import DEFAULT_DB_PATH
except ImportError:
    from shadow_store import DEFAULT_DB_PATH

KST = timezone(timedelta(hours=9))
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "shadow-eval-set.tsv"

COLUMNS = [
    "id",
    "source",
    "title",
    "extra_text",
    "filter_verdict",
    "filter_reason",
    "observed_at",
    "policy_fingerprint",
    "population_count",
    "sample_count",
    "sample_weight",
    "label",
    "labeled_by",
    "labeled_at",
]


def _kst_day(value: str, *, end: bool = False) -> datetime:
    day = datetime.strptime(value, "%Y-%m-%d").date()
    local = datetime.combine(day, time.min, tzinfo=KST)
    if end:
        local += timedelta(days=1)
    return local.astimezone(UTC)


def _load_rows(
    db_path: Path,
    *,
    from_day: str,
    to_day: str,
    policy_fingerprint: str | None = None,
) -> list[dict[str, str]]:
    start = _kst_day(from_day)
    end = _kst_day(to_day, end=True)
    query = """
        SELECT observed_at, source, candidate_id, title, extra_text,
               filter_verdict, filter_reason, policy_fingerprint
        FROM filter_candidates
        WHERE observed_at >= ? AND observed_at < ?
    """
    params: list[str] = [start.isoformat(), end.isoformat()]
    if policy_fingerprint:
        query += " AND policy_fingerprint = ?"
        params.append(policy_fingerprint)
    query += " ORDER BY observed_at, source, candidate_id"
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(query, params)]


def _stable_rank(row: dict[str, str], seed: str) -> str:
    identity = "\x1f".join(
        [seed, row["source"], row["candidate_id"], row["policy_fingerprint"]]
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def build_sample(
    rows: list[dict[str, str]],
    *,
    seed: str,
    per_verdict: int,
) -> list[dict[str, str]]:
    fingerprints = {row["policy_fingerprint"] for row in rows}
    if len(fingerprints) > 1:
        raise ValueError("여러 policy_fingerprint가 섞였다. --policy-fingerprint로 하나를 고른다.")

    selected: list[dict[str, str]] = []
    for verdict in ("allow", "block"):
        population = [row for row in rows if row["filter_verdict"] == verdict]
        population.sort(key=lambda row: _stable_rank(row, seed))
        sample = population[:per_verdict]
        sample_count = len(sample)
        weight = (len(population) / sample_count) if sample_count else 0.0
        for row in sample:
            selected.append(
                {
                    "id": row["candidate_id"],
                    "source": row["source"],
                    "title": row["title"],
                    "extra_text": row["extra_text"],
                    "filter_verdict": verdict,
                    "filter_reason": row["filter_reason"],
                    "observed_at": row["observed_at"],
                    "policy_fingerprint": row["policy_fingerprint"],
                    "population_count": str(len(population)),
                    "sample_count": str(sample_count),
                    "sample_weight": f"{weight:.12g}",
                    "label": "",
                    "labeled_by": "",
                    "labeled_at": "",
                }
            )
    return selected


def write_tsv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="정치 필터 shadow 평가 표본 생성기")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--from", dest="from_day", required=True, help="KST 시작일 YYYY-MM-DD")
    parser.add_argument("--to", dest="to_day", required=True, help="KST 종료일 YYYY-MM-DD, 포함")
    parser.add_argument("--seed", required=True)
    parser.add_argument("--per-verdict", type=int, required=True)
    parser.add_argument("--policy-fingerprint")
    args = parser.parse_args(argv)

    if args.per_verdict < 1:
        parser.error("--per-verdict는 1 이상이어야 한다")
    if not args.db.exists():
        print(f"shadow DB가 없습니다: {args.db}", file=sys.stderr)
        return 2

    rows = _load_rows(
        args.db,
        from_day=args.from_day,
        to_day=args.to_day,
        policy_fingerprint=args.policy_fingerprint,
    )
    try:
        sample = build_sample(rows, seed=args.seed, per_verdict=args.per_verdict)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    write_tsv(args.out, sample)
    print(f"후보 {len(rows)}건 → 표본 {len(sample)}건: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
