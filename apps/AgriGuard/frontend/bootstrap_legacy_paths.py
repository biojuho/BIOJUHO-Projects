"""Run the workspace legacy-path bootstrap from the AgriGuard frontend cwd.

The AgriGuard quality workflow executes commands with this directory as the
working directory, so this wrapper preserves the existing root bootstrap
contract without changing the workflow file.
"""

from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

runpy.run_path(str(ROOT / "bootstrap_legacy_paths.py"), run_name="__main__")
