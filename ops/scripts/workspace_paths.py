from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


WORKSPACE_MAP_FILENAME = "workspace-map.json"


def find_workspace_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__)).resolve()
    if current.is_file():
        current = current.parent

    for candidate in (current, *current.parents):
        if (candidate / WORKSPACE_MAP_FILENAME).exists():
            return candidate

    raise FileNotFoundError(f"Could not find {WORKSPACE_MAP_FILENAME} from {current}")


@lru_cache(maxsize=1)
def load_workspace_map() -> dict:
    root = find_workspace_root()
    return json.loads((root / WORKSPACE_MAP_FILENAME).read_text(encoding="utf-8"))


def get_unit(unit_id: str) -> dict:
    workspace_map = load_workspace_map()
    for unit in workspace_map["units"]:
        if unit["id"] == unit_id:
            return unit
    raise KeyError(f"Unknown workspace unit: {unit_id}")


def unit_path(unit_id: str, *, root: Path | None = None, prefer_legacy: bool = False) -> Path:
    workspace_root = root or find_workspace_root()
    unit = get_unit(unit_id)
    rel_path = unit["legacy_path"] if prefer_legacy else unit["canonical_path"]
    return workspace_root / rel_path


def rel_unit_path(unit_id: str, *parts: str, prefer_legacy: bool = False) -> str:
    workspace_root = find_workspace_root()
    path = unit_path(unit_id, root=workspace_root, prefer_legacy=prefer_legacy)
    if parts:
        path = path.joinpath(*parts)
    return str(path.relative_to(workspace_root))


def iter_active_units() -> list[dict]:
    return [unit for unit in load_workspace_map()["units"] if unit.get("active", False)]
