"""session_bootstrap.py — Quick workspace health snapshot for session startup.

Run at the beginning of each work session to get an instant overview
of the workspace state without reading through multiple files.

Usage::

    python ops/scripts/session_bootstrap.py
    python ops/scripts/session_bootstrap.py --json-out var/session-snapshot.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Force UTF-8 stdout on Windows to avoid cp949 encoding errors
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    """Run a command and return stdout, empty string on failure."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or WORKSPACE_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def git_status() -> dict:
    """Gather git state: branch, uncommitted changes, ahead/behind."""
    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    status_lines = _run(["git", "status", "--porcelain"]).splitlines()
    log_lines = _run(["git", "log", "--oneline", "-5"]).splitlines()

    # Ahead/behind
    tracking = _run(["git", "rev-list", "--left-right", "--count", "HEAD...@{upstream}"])
    ahead, behind = 0, 0
    if tracking:
        parts = tracking.split()
        if len(parts) == 2:
            ahead, behind = int(parts[0]), int(parts[1])

    return {
        "branch": branch,
        "uncommitted_files": len(status_lines),
        "uncommitted_summary": status_lines[:10],
        "ahead": ahead,
        "behind": behind,
        "recent_commits": log_lines,
    }


def backlog_summary() -> dict:
    """Read next-actions.md for incomplete items."""
    next_actions = WORKSPACE_ROOT / "next-actions.md"
    if not next_actions.exists():
        return {"pending": 0, "items": []}

    content = next_actions.read_text(encoding="utf-8")
    pending = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("- [ ]"):
            pending.append(stripped[6:].strip())

    return {"pending": len(pending), "items": pending[:10]}


def test_suite_summary() -> dict:
    """Check if workspace venv exists and last smoke result."""
    venv_exists = (WORKSPACE_ROOT / ".venv" / "Scripts" / "python.exe").exists() or (
        WORKSPACE_ROOT / ".venv" / "bin" / "python"
    ).exists()

    # Try to read latest smoke report
    smoke_dir = WORKSPACE_ROOT / "var" / "smoke"
    latest_smoke = "no report found"
    if smoke_dir.exists():
        reports = sorted(smoke_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if reports:
            try:
                data = json.loads(reports[0].read_text(encoding="utf-8"))
                passed = sum(1 for r in data if r.get("ok"))
                total = len(data)
                latest_smoke = f"{passed}/{total} PASS ({reports[0].name})"
            except (json.JSONDecodeError, KeyError):
                latest_smoke = f"corrupt ({reports[0].name})"

    return {
        "venv_exists": venv_exists,
        "latest_smoke": latest_smoke,
    }


def disk_health() -> dict:
    """Basic workspace size and key directory checks."""
    key_dirs = {
        "automation/getdaytrends": "getdaytrends",
        "automation/DailyNews": "dailynews",
        "automation/content-intelligence": "cie",
        "apps/AgriGuard": "agriguard",
        "apps/desci-platform": "desci",
        "packages/shared": "shared",
    }
    status = {}
    for path, name in key_dirs.items():
        full = WORKSPACE_ROOT / path
        status[name] = "exists" if full.exists() else "MISSING"

    return status


def format_report(snapshot: dict) -> str:
    """Format a human-readable session bootstrap report."""
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append(f"  SESSION BOOTSTRAP — {snapshot['timestamp']}")
    lines.append("=" * 60)

    # Git
    git = snapshot["git"]
    lines.append(f"\n📦 Git: {git['branch']}")
    if git["ahead"] or git["behind"]:
        lines.append(f"   ↑ ahead: {git['ahead']}  ↓ behind: {git['behind']}")
    lines.append(f"   Uncommitted: {git['uncommitted_files']} files")
    if git["uncommitted_summary"]:
        for f in git["uncommitted_summary"][:5]:
            lines.append(f"     {f}")
    lines.append("\n   Recent commits:")
    for c in git["recent_commits"]:
        lines.append(f"     {c}")

    # Tests
    tests = snapshot["tests"]
    lines.append(f"\n🧪 Tests: venv={'✅' if tests['venv_exists'] else '❌'}")
    lines.append(f"   Last smoke: {tests['latest_smoke']}")

    # Backlog
    backlog = snapshot["backlog"]
    lines.append(f"\n📋 Backlog: {backlog['pending']} pending items")
    for item in backlog["items"][:5]:
        lines.append(f"   - {item[:80]}")

    # Projects
    projects = snapshot["projects"]
    lines.append("\n🗂️ Projects:")
    for name, status in projects.items():
        icon = "✅" if status == "exists" else "❌"
        lines.append(f"   {icon} {name}: {status}")

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Session bootstrap: workspace health snapshot")
    parser.add_argument("--json-out", type=str, help="Write JSON report to file")
    args = parser.parse_args()

    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git": git_status(),
        "tests": test_suite_summary(),
        "backlog": backlog_summary(),
        "projects": disk_health(),
    }

    print(format_report(snapshot))

    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n📄 JSON report saved: {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
