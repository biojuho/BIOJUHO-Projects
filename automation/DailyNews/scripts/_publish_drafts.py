"""Publish all unpublished draft reports to Notion via CLI"""

import os
import sqlite3
import subprocess
import sys

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
DB_PATH = os.path.join(PROJECT_ROOT, "data", "pipeline_state.db")
PYTHON_EXE = os.path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Find all draft reports without Notion page
cur.execute("""
    SELECT report_id, category, window_name, created_at
    FROM content_reports
    WHERE status = 'draft' AND (notion_page_id IS NULL OR notion_page_id = '')
    ORDER BY created_at DESC
""")
drafts = cur.fetchall()
conn.close()

if not drafts:
    print("No unpublished draft reports found.")
    sys.exit(0)

print(f"Found {len(drafts)} unpublished draft reports:")
for d in drafts:
    print(f"  {d[0][:60]} | {d[1]:20s} | {d[2]:10s} | {d[3][:19]}")

print(f"\nPublishing {len(drafts)} reports via CLI...")

env = os.environ.copy()
env["PYTHONPATH"] = os.path.join(PROJECT_ROOT, "src") + os.pathsep + env.get("PYTHONPATH", "")
env["PYTHONUTF8"] = "1"
env["PYTHONIOENCODING"] = "utf-8"

success = 0
failed = 0
for report_id, category, window, created_at in drafts:
    cmd = [
        PYTHON_EXE,
        "-X",
        "utf8",
        "-m",
        "antigravity_mcp",
        "jobs",
        "publish-report",
        "--report-id",
        report_id,
        "--approval-mode",
        "auto",
    ]
    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0:
            print(f"  OK: {category}/{window} ({report_id[:40]})")
            success += 1
        else:
            err = (result.stderr or result.stdout or "unknown")[:100]
            print(f"  FAIL: {category}/{window} - exit {result.returncode}: {err}")
            failed += 1
    except Exception as e:
        print(f"  ERROR: {category}/{window} - {type(e).__name__}: {e}")
        failed += 1

print(f"\nDone: {success} published, {failed} failed")
