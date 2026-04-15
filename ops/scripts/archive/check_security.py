"""
Security scanner for pre-commit and Claude Code Hooks.

Scans files for hardcoded secrets, API keys, and sensitive patterns.
Exit code 0 = clean, 1 = issues found.

Usage:
    python scripts/check_security.py <file_path>
    python scripts/check_security.py --scan-all
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from workspace_paths import find_workspace_root

# Patterns that indicate hardcoded secrets
SECRET_PATTERNS: list[tuple[str, re.Pattern]] = [
    (
        "API Key assignment",
        re.compile(
            r"""(?:api[_-]?key|apikey|secret[_-]?key|auth[_-]?token|access[_-]?token|bearer)\s*[:=]\s*["'][A-Za-z0-9_\-/.]{20,}["']""",
            re.IGNORECASE,
        ),
    ),
    ("AWS Key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Anthropic Key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("OpenAI Key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("Google API Key", re.compile(r"AIzaSy[A-Za-z0-9_\-]{33}")),
    ("Slack Token", re.compile(r"xox[bprs]-[A-Za-z0-9\-]+")),
    ("GitHub Token", re.compile(r"ghp_[A-Za-z0-9]{36}")),
    (
        "Generic password",
        re.compile(
            r"""(?:password|passwd|pwd)\s*[:=]\s*["'][^"'\s]{8,}["']""",
            re.IGNORECASE,
        ),
    ),
    ("Private Key Block", re.compile(r"-----BEGIN (?:RSA |DSA |EC )?PRIVATE KEY-----")),
    ("Telegram Token", re.compile(r"\d{8,10}:[A-Za-z0-9_\-]{35}")),
]

# File extensions to scan
SCANNABLE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".cfg",
    ".ini",
    ".env",
    ".sh",
    ".bat",
    ".ps1",
    ".md",
}

# Files/dirs to skip
SKIP_PATTERNS = {
    "node_modules",
    ".git",
    "__pycache__",
    "venv",
    ".venv",
    ".env.example",
    "check_security.py",  # Don't flag ourselves
    "package-lock.json",
}


def should_skip(path: Path) -> bool:
    """Check if path should be excluded from scanning."""
    parts = path.parts
    return any(skip in parts for skip in SKIP_PATTERNS)


def scan_file(filepath: Path) -> list[dict]:
    """Scan a single file for secret patterns."""
    issues: list[dict] = []

    if filepath.suffix not in SCANNABLE_EXTENSIONS:
        return issues

    if should_skip(filepath):
        return issues

    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except (OSError, PermissionError):
        return issues

    for line_num, line in enumerate(content.splitlines(), start=1):
        # Skip commented lines
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("<!--"):
            continue
        # Skip env.example placeholder patterns
        if "your_" in line.lower() or "xxx" in line.lower() or "placeholder" in line.lower():
            continue

        for name, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                issues.append(
                    {
                        "file": str(filepath),
                        "line": line_num,
                        "pattern": name,
                        "content": stripped[:120] + ("..." if len(stripped) > 120 else ""),
                    }
                )

    return issues


def scan_directory(root: Path) -> list[dict]:
    """Recursively scan all files in a directory."""
    all_issues: list[dict] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skippable directories
        dirnames[:] = [d for d in dirnames if d not in SKIP_PATTERNS]
        for fname in filenames:
            fpath = Path(dirpath) / fname
            all_issues.extend(scan_file(fpath))
    return all_issues


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python check_security.py <file_or_dir>")
        print("       python check_security.py --scan-all")
        return 0

    target = sys.argv[1]

    if target == "--scan-all":
        # Scan entire workspace
        workspace = find_workspace_root()
        issues = scan_directory(workspace)
    else:
        path = Path(target)
        if not path.exists():
            return 0  # File doesn't exist yet (being created), skip
        if path.is_dir():
            issues = scan_directory(path)
        else:
            issues = scan_file(path)

    if not issues:
        return 0

    print(f"\n{'=' * 60}")
    print(f"  SECURITY SCAN: {len(issues)} potential issue(s) found")
    print(f"{'=' * 60}\n")

    for issue in issues:
        print(f"  [{issue['pattern']}]")
        print(f"  File: {issue['file']}:{issue['line']}")
        print(f"  Content: {issue['content']}")
        print()

    print("TIP: Move secrets to .env files and use os.getenv()")
    print(f"{'=' * 60}\n")

    return 1


if __name__ == "__main__":
    sys.exit(main())
