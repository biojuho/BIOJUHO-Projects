"""AgriGuard — SQLite vs PostgreSQL Performance Benchmark.

Usage:
    # SQLite only:
    python scripts/benchmark_postgres.py

    # Compare with PostgreSQL:
    DATABASE_URL=postgresql://user:pw@host/db python scripts/benchmark_postgres.py

    # Save results:
    python scripts/benchmark_postgres.py --markdown-out AgriGuard/BENCHMARK_RESULTS.md
"""

from __future__ import annotations

import argparse
import json
import os
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, text


QUERIES = [
    {
        "name": "COUNT all products",
        "sql": 'SELECT COUNT(*) FROM "products"',
        "category": "COUNT",
    },
    {
        "name": "SELECT products with index",
        "sql": "SELECT * FROM products WHERE name LIKE '%sensor%' LIMIT 50",
        "category": "SELECT+INDEX",
    },
    {
        "name": "JOIN products → tracking_events",
        "sql": """
            SELECT p.name, COUNT(t.id) AS event_count
            FROM products p
            LEFT JOIN tracking_events t ON t.product_id = p.id
            GROUP BY p.id, p.name
            ORDER BY event_count DESC
            LIMIT 20
        """,
        "category": "JOIN+GROUP",
    },
    {
        "name": "Recent tracking events",
        "sql": """
            SELECT t.*, p.name AS product_name
            FROM tracking_events t
            JOIN products p ON p.id = t.product_id
            ORDER BY t.timestamp DESC
            LIMIT 100
        """,
        "category": "JOIN+ORDER",
    },
    {
        "name": "User statistics",
        "sql": """
            SELECT role, COUNT(*) AS cnt
            FROM users
            GROUP BY role
            ORDER BY cnt DESC
        """,
        "category": "GROUP",
    },
]

WARMUP_ROUNDS = 2
BENCH_ROUNDS = 5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark AgriGuard SQLite vs PostgreSQL query performance.",
    )
    parser.add_argument(
        "--sqlite-db",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "agriguard.db",
        help="Path to the SQLite database file.",
    )
    parser.add_argument(
        "--pg-url",
        default=os.environ.get("DATABASE_URL", ""),
        help="PostgreSQL connection URL (default: $DATABASE_URL).",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=BENCH_ROUNDS,
        help=f"Number of measurement rounds (default: {BENCH_ROUNDS}).",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        help="Optional path to save results as JSON.",
    )
    parser.add_argument(
        "--markdown-out",
        type=Path,
        help="Optional path to save results as Markdown.",
    )
    return parser.parse_args()


@contextmanager
def timed():
    """Context manager yielding a callable that returns elapsed ms."""
    start = time.perf_counter()
    result = {"ms": 0.0}
    yield result
    result["ms"] = (time.perf_counter() - start) * 1000


def run_benchmark(engine, label: str, rounds: int) -> list[dict]:
    """Run all queries against an engine, return timing results."""
    results = []

    with engine.connect() as conn:
        for q in QUERIES:
            # Warmup
            for _ in range(WARMUP_ROUNDS):
                conn.execute(text(q["sql"])).fetchall()

            # Measure
            times_ms = []
            row_count = 0
            for _ in range(rounds):
                with timed() as t:
                    rows = conn.execute(text(q["sql"])).fetchall()
                    row_count = len(rows)
                times_ms.append(t["ms"])

            avg_ms = sum(times_ms) / len(times_ms)
            min_ms = min(times_ms)
            max_ms = max(times_ms)

            results.append({
                "query": q["name"],
                "category": q["category"],
                "engine": label,
                "avg_ms": round(avg_ms, 3),
                "min_ms": round(min_ms, 3),
                "max_ms": round(max_ms, 3),
                "rows": row_count,
                "rounds": rounds,
            })

            print(f"  [{label}] {q['name']}: avg={avg_ms:.2f}ms (min={min_ms:.2f}, max={max_ms:.2f}) [{row_count} rows]")

    return results


def render_markdown(sqlite_results: list[dict], pg_results: list[dict] | None, info: dict) -> str:
    lines = [
        "# AgriGuard Database Performance Benchmark",
        "",
        f"- Generated at: {info['generated_at']}",
        f"- Rounds: {info['rounds']}",
        f"- SQLite DB: `{info['sqlite_path']}`",
    ]

    if pg_results:
        lines.append(f"- PostgreSQL: `{info.get('pg_url_masked', 'N/A')}`")

    lines.extend([
        "",
        "## Results",
        "",
    ])

    if pg_results:
        lines.extend([
            "| Query | Category | SQLite (ms) | PostgreSQL (ms) | Speedup |",
            "|-------|----------|-------------|-----------------|---------|",
        ])
        for sq, pq in zip(sqlite_results, pg_results):
            speedup = sq["avg_ms"] / pq["avg_ms"] if pq["avg_ms"] > 0 else float("inf")
            sign = "🟢" if speedup > 1 else "🔴"
            lines.append(
                f"| {sq['query']} | {sq['category']} | {sq['avg_ms']:.2f} | {pq['avg_ms']:.2f} | {sign} {speedup:.1f}x |"
            )
    else:
        lines.extend([
            "| Query | Category | SQLite (ms) | Rows |",
            "|-------|----------|-------------|------|",
        ])
        for sq in sqlite_results:
            lines.append(f"| {sq['query']} | {sq['category']} | {sq['avg_ms']:.2f} | {sq['rows']} |")

    lines.extend([
        "",
        "## Notes",
        "",
        "- Speedup > 1x means PostgreSQL is faster",
        "- Results depend on data volume, indexing, and connection latency",
        f"- Current data volume: {info.get('total_rows', 'N/A')} rows",
    ])

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()

    if not args.sqlite_db.exists():
        print(f"❌ SQLite database not found: {args.sqlite_db}")
        return 1

    print(f"\n{'='*60}")
    print("AgriGuard Database Performance Benchmark")
    print(f"{'='*60}\n")

    # SQLite benchmark
    sqlite_url = f"sqlite:///{args.sqlite_db}"
    sqlite_engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

    # Get row count for report
    with sqlite_engine.connect() as conn:
        total_rows = conn.execute(
            text("SELECT SUM(cnt) FROM (SELECT COUNT(*) AS cnt FROM products UNION ALL SELECT COUNT(*) FROM tracking_events UNION ALL SELECT COUNT(*) FROM users)")
        ).scalar() or 0

    print(f"📊 SQLite ({args.sqlite_db.name}, {total_rows:,} rows):")
    sqlite_results = run_benchmark(sqlite_engine, "SQLite", args.rounds)

    # PostgreSQL benchmark (optional)
    pg_results = None
    if args.pg_url:
        print(f"\n📊 PostgreSQL:")
        try:
            pg_engine = create_engine(args.pg_url, pool_pre_ping=True)
            with pg_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            pg_results = run_benchmark(pg_engine, "PostgreSQL", args.rounds)
        except Exception as e:
            print(f"  ❌ PostgreSQL benchmark failed: {e}")

    # Build info
    pg_masked = ""
    if args.pg_url:
        # Mask password in URL
        parts = args.pg_url.split("@")
        pg_masked = parts[0].rsplit(":", 1)[0] + ":***@" + parts[-1] if len(parts) > 1 else args.pg_url

    info = {
        "generated_at": datetime.now(UTC).isoformat(),
        "sqlite_path": str(args.sqlite_db),
        "pg_url_masked": pg_masked,
        "rounds": args.rounds,
        "total_rows": total_rows,
    }

    # Output
    all_results = {"info": info, "sqlite": sqlite_results}
    if pg_results:
        all_results["postgresql"] = pg_results

    if args.json_out:
        args.json_out.write_text(json.dumps(all_results, indent=2), encoding="utf-8")
        print(f"\n💾 JSON saved: {args.json_out}")

    if args.markdown_out:
        md = render_markdown(sqlite_results, pg_results, info)
        args.markdown_out.write_text(md, encoding="utf-8")
        print(f"💾 Markdown saved: {args.markdown_out}")

    print(f"\n✅ Benchmark complete ({args.rounds} rounds)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
