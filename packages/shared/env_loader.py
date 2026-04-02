"""
shared.env_loader — 워크스페이스 환경변수 통합 로더.

단일 소스 원칙:
  1) 프로젝트 루트의 .env를 우선 로드 (API 키 등 공통 시크릿)
  2) 현재 디렉토리의 .env는 보조적으로 로드 (override=False)
  3) 이미 설정된 환경변수는 덮어쓰지 않음

Usage::
    from shared.env_loader import load_workspace_env
    load_workspace_env()  # 자동으로 워크스페이스 루트 탐색
"""

from __future__ import annotations

import os
import threading
import warnings
from pathlib import Path

# [QA 수정] Root 탐색 로직을 shared.paths 에서 재사용 — 이원화 제거
_lock = threading.Lock()
_loaded = False

# Keys that should only exist in root .env — warn if found in subproject .env
_ROOT_ONLY_KEYS = frozenset({
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
    "OPENAI_API_KEY",
    "DEEPSEEK_API_KEY",
    "OPENROUTER_API_KEY",
})


def _find_workspace_root(start: Path | None = None) -> Path | None:
    """Find workspace root using shared.paths canonical logic.

    Falls back to local marker search if shared.paths is not importable.
    """
    # [QA 수정] paths.py의 find_workspace_root를 재사용하여 이원화 제거
    try:
        from shared.paths import find_workspace_root

        return find_workspace_root(start)
    except ImportError:
        pass

    # Fallback: standalone marker search (when shared.paths itself isn't loadable)
    current = (start or Path.cwd()).resolve()
    for parent in [current, *current.parents]:
        if (parent / "workspace-map.json").exists() or (parent / "CLAUDE.md").is_file():
            return parent
    return None


def load_workspace_env(
    *,
    project_dir: Path | str | None = None,
    warn_duplicates: bool = True,
) -> bool:
    """Load environment variables with workspace-root-first priority.

    Args:
        project_dir: Explicit project directory. If None, uses CWD.
        warn_duplicates: Warn if subproject .env contains root-only keys.

    Returns:
        True if workspace root .env was found and loaded.
    """
    global _loaded

    try:
        from dotenv import load_dotenv
    except ImportError:
        return False

    start = Path(project_dir) if project_dir else Path.cwd()
    root = _find_workspace_root(start)

    # 1) Load workspace root .env first (API keys, shared secrets)
    root_loaded = False
    if root is not None:
        root_env = root / ".env"
        if root_env.is_file():
            load_dotenv(root_env, override=False)
            root_loaded = True

    # 2) Load local .env as supplement (project-specific settings only)
    local_env = start.resolve() / ".env"
    if local_env.is_file() and (root is None or local_env != (root / ".env").resolve()):
        # [QA 수정] thread-safe 중복 경고 방지
        with _lock:
            should_check = warn_duplicates and not _loaded
        if should_check:
            _check_duplicate_keys(local_env)
        load_dotenv(local_env, override=False)

    # [QA 수정] thread-safe 플래그 갱신
    with _lock:
        _loaded = True
    return root_loaded


def _check_duplicate_keys(env_path: Path) -> None:
    """Warn if subproject .env contains keys that belong in root .env only."""
    try:
        content = env_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return

    found = []
    for raw_line in content.splitlines():  # [QA 수정] 변수 섀도잉 제거
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in _ROOT_ONLY_KEYS and os.environ.get(key):
            found.append(key)

    if found:
        warnings.warn(
            # [QA 수정] 절대경로 표시로 모호성 제거
            f"[shared.env_loader] Subproject .env ({env_path}) contains root-only keys: "
            f"{', '.join(found)}. Consider removing them and using the workspace root .env instead.",
            UserWarning,
            stacklevel=4,
        )
