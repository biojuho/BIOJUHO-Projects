#!/usr/bin/env python3
"""
Session log cleanup script - Retains last 7 days, archives older logs.

Usage:
    python .sessions/cleanup.py
"""

from datetime import datetime, timedelta
from pathlib import Path

SESSIONS_DIR = Path(__file__).parent
ARCHIVE_DIR = SESSIONS_DIR / "archive"
RETENTION_DAYS = 7


def cleanup_old_logs():
    """Move session logs older than 7 days to archive."""
    ARCHIVE_DIR.mkdir(exist_ok=True)

    cutoff_date = datetime.now() - timedelta(days=RETENTION_DAYS)
    archived_count = 0

    for log_file in SESSIONS_DIR.glob("SESSION_LOG_*.md"):
        # Extract date from filename: SESSION_LOG_2026-03-23.md
        try:
            date_str = log_file.stem.replace("SESSION_LOG_", "")
            log_date = datetime.strptime(date_str, "%Y-%m-%d")

            if log_date < cutoff_date:
                # Move to archive
                archive_path = ARCHIVE_DIR / log_file.name
                log_file.rename(archive_path)
                archived_count += 1
                print(f"✅ Archived: {log_file.name} (Age: {(datetime.now() - log_date).days} days)")
        except ValueError:
            print(f"⚠️  Skipping invalid filename: {log_file.name}")

    print(f"\n📦 Total archived: {archived_count} logs")
    print(f"📁 Active logs: {len(list(SESSIONS_DIR.glob('SESSION_LOG_*.md')))} (last {RETENTION_DAYS} days)")


if __name__ == "__main__":
    cleanup_old_logs()
