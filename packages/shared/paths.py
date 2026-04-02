"""
shared.paths — 워크스페이스 경로 통합 관리.

sys.path 설정을 1곳에서 관리합니다.
tests/conftest.py 및 scripts에서 개별적으로 sys.path.insert를 하지 않고
이 모듈을 import하면 필요한 경로가 자동으로 추가됩니다.

Usage::
    # conftest.py 또는 script 엔트리포인트에서
    import shared.paths  # noqa: F401  — 사이드 이펙트 import

또는::
    from shared.paths import WORKSPACE_ROOT, ensure_importable
    ensure_importable()
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# [QA 수정] Root 탐색 마커를 상수로 통일 — env_loader.py도 이것을 참조
ROOT_MARKERS = ("workspace-map.json", "CLAUDE.md")


def find_workspace_root(start: Path | None = None) -> Path | None:
    """Walk up from `start` to find the workspace root.

    Checks for known marker files (workspace-map.json, CLAUDE.md).
    Returns None if no marker found within 10 levels.
    """
    # [QA 수정] 기존 private → public. env_loader에서도 호출하도록 통합
    current = (start or Path(__file__)).resolve().parent
    for _ in range(10):  # safety limit
        if any((current / marker).exists() for marker in ROOT_MARKERS):
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


# [QA 수정] fallback 시 None 반환 대신 명시적 에러
_root = find_workspace_root()
if _root is None:
    import warnings

    _root = Path(__file__).resolve().parents[2]
    warnings.warn(
        f"[shared.paths] Could not find workspace root via markers {ROOT_MARKERS}. "
        f"Falling back to: {_root}",
        UserWarning,
        stacklevel=1,
    )

WORKSPACE_ROOT: Path = _root

# Canonical paths that should be importable
_CANONICAL = (
    WORKSPACE_ROOT,
    WORKSPACE_ROOT / "packages",
    WORKSPACE_ROOT / "automation",
    WORKSPACE_ROOT / "apps" / "desci-platform",
)

# [QA 수정] Windows case-insensitive 대응
_IS_WINDOWS = os.name == "nt"


def _normalize(p: str) -> str:
    """Normalize path for case-insensitive comparison on Windows."""
    return p.lower() if _IS_WINDOWS else p


def _already_in_sys_path(candidate: str) -> bool:
    """Check if a path is already in sys.path (case-insensitive on Windows)."""
    normalized = _normalize(candidate)
    return any(_normalize(existing) == normalized for existing in sys.path)


def ensure_importable(*, include_dailynews: bool = False) -> None:
    """Add workspace canonical paths to sys.path if not already present.

    Args:
        include_dailynews: Also add DailyNews src/scripts paths.
    """
    targets = list(_CANONICAL)

    if include_dailynews:
        targets.extend([
            WORKSPACE_ROOT / "automation" / "DailyNews" / "src",
            WORKSPACE_ROOT / "automation" / "DailyNews" / "scripts",
        ])

    for candidate in targets:
        candidate_text = str(candidate)
        # [QA 수정] Windows case-insensitive 중복 방지
        if candidate.exists() and not _already_in_sys_path(candidate_text):
            sys.path.insert(0, candidate_text)


# Auto-setup on import for convenience
ensure_importable()
