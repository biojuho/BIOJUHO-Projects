from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import aiosqlite
import httpx


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    project_dir = script_dir.parent
    parser = argparse.ArgumentParser(description="Publish queued GetDayTrends tweets through the local /publish-x API.")
    parser.add_argument(
        "--db-path",
        default=str(project_dir / "data" / "getdaytrends.db"),
        help="Path to the GetDayTrends SQLite database.",
    )
    parser.add_argument(
        "--api-base",
        default="http://127.0.0.1:8788",
        help="Base URL for the local NotebookLM API service.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum number of queued tweets to publish in one run.",
    )
    parser.add_argument(
        "--content-type",
        default="short",
        help="Only publish tweets with this content_type.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which rows would be published without making API calls.",
    )
    parser.add_argument(
        "--json-out",
        help="Optional JSON summary output path.",
    )
    return parser.parse_args()


async def fetch_queued_rows(db_path: str, *, content_type: str, limit: int) -> list[dict]:
    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row
    try:
        cursor = await conn.execute(
            """SELECT id, trend_id, run_id, content, content_type, generated_at
               FROM tweets
               WHERE (posted_at IS NULL OR posted_at = '')
                 AND content_type = ?
               ORDER BY generated_at ASC, id ASC
               LIMIT ?""",
            (content_type, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def publish_rows(args: argparse.Namespace) -> dict:
    rows = await fetch_queued_rows(args.db_path, content_type=args.content_type, limit=args.limit)
    results: list[dict] = []

    if args.dry_run:
        for row in rows:
            results.append(
                {
                    "tweet_id": row["id"],
                    "trend_id": row["trend_id"],
                    "run_id": row["run_id"],
                    "status": "dry_run",
                    "content_preview": row["content"][:80],
                }
            )
        return {"queued_count": len(rows), "results": results}

    async with httpx.AsyncClient(timeout=60.0) as client:
        for row in rows:
            payload = {
                "tweet_text": row["content"],
                "local_tweet_id": row["id"],
                "trend_row_id": row["trend_id"],
                "run_row_id": row["run_id"],
                "db_path": args.db_path,
            }
            response = await client.post(f"{args.api_base}/publish-x", json=payload)
            response.raise_for_status()
            body = response.json()
            results.append(
                {
                    "tweet_id": row["id"],
                    "trend_id": row["trend_id"],
                    "run_id": row["run_id"],
                    "ok": bool(body.get("ok")),
                    "tweet_url": body.get("tweet_url", ""),
                    "publish_recorded": bool(body.get("publish_recorded")),
                    "publish_record_error": body.get("publish_record_error", ""),
                }
            )

    return {"queued_count": len(rows), "results": results}


def write_json(path_str: str, payload: dict) -> Path:
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def main() -> int:
    args = parse_args()
    payload = asyncio.run(publish_rows(args))
    if args.json_out:
        output_path = write_json(args.json_out, payload)
        print(f"json_out: {output_path}")
    print(f"queued_count: {payload['queued_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
