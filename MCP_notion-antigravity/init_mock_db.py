from __future__ import annotations

import argparse
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS post_history (
            id INTEGER PRIMARY KEY,
            generated_at TEXT,
            post_type TEXT,
            keyword TEXT,
            viral_score INTEGER,
            status TEXT,
            hook TEXT
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS trend_analytics (
            id INTEGER PRIMARY KEY,
            timestamp TEXT,
            keyword TEXT,
            viral_potential INTEGER,
            search_volume INTEGER
        )
        """
    )


def seed_posts(connection: sqlite3.Connection, count: int) -> int:
    now = datetime.now()
    inserted = 0
    for _ in range(count):
        generated_at = now - timedelta(days=random.randint(0, 14), hours=random.randint(0, 24))
        connection.execute(
            """
            INSERT INTO post_history (generated_at, post_type, keyword, viral_score, status, hook)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                generated_at.strftime("%Y-%m-%d %H:%M:%S"),
                "tweet",
                "AI",
                random.randint(40, 95),
                "published" if random.random() > 0.2 else "draft",
                "The future varies by perspective.",
            ),
        )
        inserted += 1
    return inserted


def seed_trends(connection: sqlite3.Connection, count: int) -> int:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    inserted = 0
    for index in range(count):
        connection.execute(
            """
            INSERT INTO trend_analytics (timestamp, keyword, viral_potential, search_volume)
            VALUES (?, ?, ?, ?)
            """,
            (
                now,
                f"Tech Trend {index}",
                random.randint(50, 100),
                random.randint(1000, 5000),
            ),
        )
        inserted += 1
    return inserted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Populate the analytics database with mock data.")
    parser.add_argument("--reset", action="store_true", help="Delete existing rows before seeding")
    parser.add_argument("--posts", type=int, default=25, help="Number of post_history rows to insert")
    parser.add_argument("--trends", type=int, default=8, help="Number of trend_analytics rows to insert")
    parser.add_argument("--db-path", default="data/analytics.db", help="SQLite database path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db_path)
    if not db_path.is_absolute():
        db_path = Path(__file__).resolve().parent / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        ensure_schema(connection)
        if args.reset:
            connection.execute("DELETE FROM post_history")
            connection.execute("DELETE FROM trend_analytics")

        inserted_posts = seed_posts(connection, max(0, args.posts))
        inserted_trends = seed_trends(connection, max(0, args.trends))
        connection.commit()

    print(
        "Mock DB populated "
        f"db_path={db_path} reset={int(args.reset)} inserted_posts={inserted_posts} inserted_trends={inserted_trends}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
