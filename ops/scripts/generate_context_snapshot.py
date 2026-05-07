"""generate_context_snapshot.py — Auto-update CONTEXT.md Daily Snapshot section.

Appends or overwrites the '## Daily Snapshot' section at the bottom of
CONTEXT.md with a fresh summary of workspace state including git status,
test results, and active project health.

Usage::

    python ops/scripts/generate_context_snapshot.py
    python ops/scripts/generate_context_snapshot.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Force UTF-8 stdout on Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
CONTEXT_PATH = WORKSPACE_ROOT / "CONTEXT.md"


def _run(cmd: list[str]) -> str:
    try:
        r = subprocess.run(
            cmd, cwd=WORKSPACE_ROOT, capture_output=True,
            text=True, timeout=30, encoding="utf-8", errors="replace",
        )
        return r.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def _git_info() -> dict:
    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    short_sha = _run(["git", "rev-parse", "--short", "HEAD"])
    status = _run(["git", "status", "--porcelain"])
    dirty = len(status.splitlines()) if status else 0
    return {"branch": branch, "sha": short_sha, "dirty": dirty}


def _test_status() -> str:
    smoke_dir = WORKSPACE_ROOT / "var" / "smoke"
    if not smoke_dir.exists():
        return "no smoke reports"
    reports = sorted(smoke_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not reports:
        return "no smoke reports"
    try:
        data = json.loads(reports[0].read_text(encoding="utf-8"))
        passed = sum(1 for r in data if r.get("ok"))
        return f"{passed}/{len(data)} PASS ({reports[0].stem})"
    except (json.JSONDecodeError, KeyError):
        return "corrupt report"


def _project_status() -> list[tuple[str, str]]:
    projects = [
        ("getdaytrends", "automation/getdaytrends"),
        ("DailyNews", "automation/DailyNews"),
        ("CIE", "automation/content-intelligence"),
        ("AgriGuard", "apps/AgriGuard"),
        ("DeSci", "apps/desci-platform"),
        ("Dashboard", "apps/dashboard"),
        ("shared", "packages/shared"),
    ]
    result = []
    for name, path in projects:
        full = WORKSPACE_ROOT / path
        result.append((name, "✅" if full.exists() else "❌"))
    return result


def generate_snapshot() -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    git = _git_info()
    tests = _test_status()
    projects = _project_status()

    lines = [
        f"## Daily Snapshot",
        f"",
        f"> Auto-generated on **{now}**",
        f"",
        f"| Item | Status |",
        f"|:-----|:-------|",
        f"| Branch | `{git['branch']}` @ `{git['sha']}` |",
        f"| Uncommitted | {git['dirty']} files |",
        f"| Last Smoke | {tests} |",
    ]
    for name, status in projects:
        lines.append(f"| {name} | {status} |")

    return "\n".join(lines) + "\n"


def update_context(snapshot: str, *, dry_run: bool = False) -> None:
    if not CONTEXT_PATH.exists():
        print(f"❌ CONTEXT.md not found at {CONTEXT_PATH}")
        return

    content = CONTEXT_PATH.read_text(encoding="utf-8")

    # Remove existing Daily Snapshot section if present
    pattern = r"\n## Daily Snapshot\n.*"
    cleaned = re.sub(pattern, "", content, flags=re.DOTALL)
    cleaned = cleaned.rstrip() + "\n\n"

    new_content = cleaned + snapshot

    if dry_run:
        print("--- DRY RUN: would write ---")
        print(snapshot)
        return

    CONTEXT_PATH.write_text(new_content, encoding="utf-8")
    print(f"✅ CONTEXT.md updated with fresh snapshot ({len(snapshot)} chars)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Update CONTEXT.md Daily Snapshot")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    snapshot = generate_snapshot()
    update_context(snapshot, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
