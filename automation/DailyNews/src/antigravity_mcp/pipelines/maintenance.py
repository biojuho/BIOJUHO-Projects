"""Daily maintenance pipeline — DB backup, cache pruning, log rotation."""
from __future__ import annotations

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from antigravity_mcp.config import get_settings
from antigravity_mcp.state.events import generate_run_id
from antigravity_mcp.state.store import PipelineStateStore

logger = logging.getLogger(__name__)


def backup_db(
    *,
    state_store: PipelineStateStore | None = None,
    dest_dir: Path | None = None,
) -> str:
    """Create a SQLite backup using the backup() API.

    Returns the path to the backup file.
    """
    store = state_store or PipelineStateStore()
    settings = get_settings()
    dest_dir = dest_dir or settings.data_dir / "backups"
    dest_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = dest_dir / f"pipeline_state_{timestamp}.db"

    import sqlite3
    src_conn = store._connect()
    dst_conn = sqlite3.connect(str(backup_path))
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()

    logger.info("Database backed up to %s", backup_path)
    return str(backup_path)


async def run_daily_maintenance(
    *,
    state_store: PipelineStateStore | None = None,
    prune_articles_days: int = 30,
    keep_backups: int = 7,
) -> dict:
    """Run all daily maintenance tasks.

    - Backup database
    - Prune old articles (>30 days)
    - Prune expired LLM cache
    - Clean up old backups
    """
    store = state_store or PipelineStateStore()
    run_id = generate_run_id("maintenance")
    store.record_job_start(run_id, "daily_maintenance")

    results: dict = {"run_id": run_id}

    # 1. Backup DB
    try:
        backup_path = backup_db(state_store=store)
        results["backup_path"] = backup_path
    except Exception as exc:
        results["backup_error"] = str(exc)
        logger.error("DB backup failed: %s", exc)

    # 2. Prune old articles
    articles_pruned = store.prune_old_articles(days=prune_articles_days)
    results["articles_pruned"] = articles_pruned

    # 3. Prune LLM cache
    cache_pruned = store.prune_llm_cache()
    results["llm_cache_pruned"] = cache_pruned

    # 4. Clean old backups
    settings = get_settings()
    backup_dir = settings.data_dir / "backups"
    if backup_dir.exists():
        backups = sorted(backup_dir.glob("pipeline_state_*.db"), reverse=True)
        removed = 0
        for old_backup in backups[keep_backups:]:
            try:
                old_backup.unlink()
                removed += 1
            except OSError:
                pass
        results["old_backups_removed"] = removed

    store.record_job_finish(
        run_id,
        status="success",
        summary=results,
    )
    return results
