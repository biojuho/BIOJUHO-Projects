"""CIE 테스트 공통 fixture."""

from __future__ import annotations

import sys
from pathlib import Path

# CIE 디렉토리와 workspace를 PYTHONPATH에 추가
_CIE_DIR = Path(__file__).resolve().parents[1]
_WORKSPACE_ROOT = _CIE_DIR.parents[1]

for p in (_CIE_DIR, _WORKSPACE_ROOT, _WORKSPACE_ROOT / "packages"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
