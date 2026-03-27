"""shared.config - Unified environment loading and project detection utilities."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Workspace root detection
# ---------------------------------------------------------------------------
WORKSPACE_ROOT = Path(__file__).resolve().parents[2]


def load_env(project_dir: Path | None = None) -> dict[str, str]:
    """Load environment variables from .env files.

    Priority (highest first):
    1. Project-specific .env (if project_dir given)
    2. Workspace root .env
    3. Already-set OS environment variables
    """
    root_env = WORKSPACE_ROOT / ".env"
    if root_env.exists():
        load_dotenv(root_env, override=False)

    if project_dir:
        project_env = Path(project_dir) / ".env"
        if project_env.exists():
            load_dotenv(project_env, override=True)

    return dict(os.environ)


def get_project_root(name: str) -> Path:
    """Return the absolute path for a known project directory."""
    known_projects = {
        "agriguard": WORKSPACE_ROOT / "apps" / "AgriGuard",
        "desci": WORKSPACE_ROOT / "apps" / "desci-platform",
        "mcp_notion": WORKSPACE_ROOT / "automation" / "DailyNews",
        "getdaytrends": WORKSPACE_ROOT / "automation" / "getdaytrends",
        "canva_mcp": WORKSPACE_ROOT / "mcp" / "canva-mcp",
        "notebooklm": WORKSPACE_ROOT / "mcp" / "notebooklm-mcp",
        "github_mcp": WORKSPACE_ROOT / "mcp" / "github-mcp",
        "content_intelligence": WORKSPACE_ROOT / "automation" / "content-intelligence",
    }
    key = name.lower().replace("-", "_").replace(" ", "_")
    if key not in known_projects:
        raise ValueError(f"Unknown project: {name}. Known: {list(known_projects.keys())}")
    return known_projects[key]


def require_env(name: str) -> str:
    """Get an environment variable or raise with a clear message."""
    value = os.getenv(name, "").strip()
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{name}' is not set. "
            f"Check your .env file at {WORKSPACE_ROOT / '.env'}"
        )
    return value
