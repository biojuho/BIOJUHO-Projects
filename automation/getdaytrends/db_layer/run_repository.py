"""Run Repository"""

import json

from . import RunResult, sqlite_write_lock

async def save_run(conn, run: RunResult) -> int:
    async with sqlite_write_lock(conn):
        cursor = await conn.execute(
            """INSERT INTO runs (run_uuid, started_at, country, trends_collected,
               trends_scored, tweets_generated, tweets_saved, alerts_sent, errors)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run.run_id,
                run.started_at.isoformat(),
                run.country,
                run.trends_collected,
                run.trends_scored,
                run.tweets_generated,
                run.tweets_saved,
                run.alerts_sent,
                json.dumps(run.errors, ensure_ascii=False),
            ),
        )
        await conn.commit()
        return cursor.lastrowid

async def update_run(conn, run: RunResult, row_id: int) -> None:
    async with sqlite_write_lock(conn):
        await conn.execute(
            """UPDATE runs SET finished_at=?, trends_collected=?, trends_scored=?,
               tweets_generated=?, tweets_saved=?, alerts_sent=?, errors=? WHERE id=?""",
            (
                run.finished_at.isoformat() if run.finished_at else None,
                run.trends_collected,
                run.trends_scored,
                run.tweets_generated,
                run.tweets_saved,
                run.alerts_sent,
                json.dumps(run.errors, ensure_ascii=False),
                row_id,
            ),
        )
        await conn.commit()
