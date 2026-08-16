"""Runtime identity calculation for checkout path and git commit SHA."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import subprocess
from typing import Any

from fastapi import APIRouter

logger = logging.getLogger(__name__)

runtime_identity_router = APIRouter()


def get_checkout_path(base_file: str | Path | None = None) -> Path:
    """Return the absolute path to the repository checkout root."""
    if base_file is None:
        base_file = Path(__file__)
    else:
        base_file = Path(base_file)

    # getdaytrends is at <repo_root>/automation/getdaytrends
    # parents: [getdaytrends, automation, <repo_root>]
    resolved = base_file.resolve()
    try:
        if len(resolved.parents) >= 3:
            return resolved.parents[2]
        return resolved.parent
    except Exception:
        return Path.cwd().resolve()


def get_commit_sha(repo_root: Path | None = None) -> str:
    """Return the current HEAD commit SHA dynamically.

    Attempts git rev-parse HEAD first, then falls back to parsing .git/HEAD
    directly, then environment variable GIT_COMMIT, and finally 'unknown'.
    """
    if repo_root is None:
        repo_root = get_checkout_path()

    # 1. Try git rev-parse HEAD
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if res.returncode == 0:
            commit = res.stdout.strip()
            if commit:
                return commit
    except Exception as e:
        logger.debug("git rev-parse HEAD failed: %s", e)

    # 2. Fallback: Parse .git directly if git binary or subprocess is unavailable
    try:
        git_dir = repo_root / ".git"
        if git_dir.is_file():
            # git worktree / submodule pointer
            content = git_dir.read_text(encoding="utf-8").strip()
            if content.startswith("gitdir:"):
                git_dir = (repo_root / content.split(":", 1)[1].strip()).resolve()
        if git_dir.is_dir():
            head_file = git_dir / "HEAD"
            if head_file.exists():
                head_content = head_file.read_text(encoding="utf-8").strip()
                if head_content.startswith("ref:"):
                    ref_path = head_content.split(":", 1)[1].strip()
                    ref_file = git_dir / ref_path
                    if ref_file.exists():
                        return ref_file.read_text(encoding="utf-8").strip()
                    # Check packed-refs if ref file doesn't exist directly
                    packed_refs = git_dir / "packed-refs"
                    if packed_refs.exists():
                        for line in packed_refs.read_text(encoding="utf-8").splitlines():
                            line = line.strip()
                            if line and not line.startswith(("#", "^")):
                                parts = line.split(" ", 1)
                                if len(parts) == 2 and parts[1] == ref_path:
                                    return parts[0]
                elif len(head_content) == 40:
                    return head_content
    except Exception as e:
        logger.debug("Parsing .git failed: %s", e)

    # 3. Fallback: Environment variable
    env_commit = os.environ.get("GIT_COMMIT")
    if env_commit:
        return env_commit.strip()

    # 4. Unknown fallback
    return "unknown"


def get_runtime_identity(repo_root: Path | None = None) -> dict[str, Any]:
    """Build the runtime identity payload."""
    root = repo_root or get_checkout_path()
    return {
        "status": "ok",
        "checkout": str(root.resolve()),
        "commit": get_commit_sha(root),
    }


@runtime_identity_router.get("/health")
def health_endpoint() -> dict[str, Any]:
    """Health check returning checkout identity and commit SHA."""
    return get_runtime_identity()
