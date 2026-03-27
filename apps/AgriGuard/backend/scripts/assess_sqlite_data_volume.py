from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assess the current AgriGuard SQLite database volume.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "agriguard.db",
        help="Path to the SQLite database file.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        help="Optional path to save the assessment as JSON.",
    )
    parser.add_argument(
        "--markdown-out",
        type=Path,
        help="Optional path to save the assessment as Markdown.",
    )
    return parser.parse_args()


def gather_stats(db_path: Path) -> dict:
    db_path = db_path.resolve()
    if not db_path.exists():
        raise FileNotFoundError(f"Database file not found: {db_path}")

    with sqlite3.connect(db_path) as connection:
        cursor = connection.cursor()
        table_names = [
            row[0]
            for row in cursor.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()
        ]

        tables = []
        total_rows = 0
        for table_name in table_names:
            row_count = cursor.execute(
                f'SELECT COUNT(*) FROM "{table_name}"'
            ).fetchone()[0]
            tables.append({"name": table_name, "rows": row_count})
            total_rows += row_count

        page_count = cursor.execute("PRAGMA page_count").fetchone()[0]
        page_size = cursor.execute("PRAGMA page_size").fetchone()[0]
        freelist_count = cursor.execute("PRAGMA freelist_count").fetchone()[0]

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "database_path": str(db_path),
        "file_size_bytes": db_path.stat().st_size,
        "page_count": page_count,
        "page_size_bytes": page_size,
        "freelist_pages": freelist_count,
        "table_count": len(tables),
        "total_rows": total_rows,
        "tables": tables,
    }


def render_markdown(stats: dict) -> str:
    lines = [
        "# AgriGuard SQLite Data Volume Report",
        "",
        f"- Generated at: {stats['generated_at']}",
        f"- Database path: `{stats['database_path']}`",
        f"- File size: {stats['file_size_bytes']:,} bytes",
        f"- Total rows: {stats['total_rows']:,}",
        f"- Table count: {stats['table_count']}",
        f"- SQLite pages: {stats['page_count']:,}",
        f"- Page size: {stats['page_size_bytes']:,} bytes",
        f"- Free pages: {stats['freelist_pages']:,}",
        "",
        "| Table | Rows |",
        "|-------|------|",
    ]

    for table in stats["tables"]:
        lines.append(f"| {table['name']} | {table['rows']:,} |")

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    stats = gather_stats(args.db)
    markdown = render_markdown(stats)

    if args.json_out:
        args.json_out.write_text(json.dumps(stats, indent=2), encoding="utf-8")

    if args.markdown_out:
        args.markdown_out.write_text(markdown, encoding="utf-8")

    print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
