from __future__ import annotations

import sys
from pathlib import Path

# Support legacy absolute imports such as `from config import ...` when
# callers import modules via `getdaytrends.*` from the repository root.
_PACKAGE_DIR = Path(__file__).resolve().parent
_PACKAGE_PATH = str(_PACKAGE_DIR)

if _PACKAGE_PATH not in sys.path:
    sys.path.insert(0, _PACKAGE_PATH)
