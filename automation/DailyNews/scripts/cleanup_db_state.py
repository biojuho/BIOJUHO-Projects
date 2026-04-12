"""Clean orphaned drafts and stuck jobs from pipeline_state.db."""
import sqlite3
import os

db = os.path.join(os.path.dirname(__file__), "..", "data", "pipeline_state.db")
conn = sqlite3.connect(db)
c = conn.cursor()

# Orphaned drafts
c.execute(
    "UPDATE content_reports SET status = 'abandoned' "
    "WHERE status = 'draft' AND (notion_page_id IS NULL OR notion_page_id = '')"
)
orphans = c.rowcount

# Stuck running jobs
c.execute(
    "UPDATE job_runs SET status = 'failed' "
    "WHERE status = 'running'"
)
stuck = c.rowcount

conn.commit()
conn.close()
print(f"Cleaned: {orphans} orphaned drafts, {stuck} stuck jobs")
