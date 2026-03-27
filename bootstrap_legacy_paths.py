from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def load_workspace_map(root: Path) -> dict:
    return json.loads((root / "workspace-map.json").read_text(encoding="utf-8"))


def ensure_removed(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    if path.exists():
        shutil.rmtree(path)


def create_windows_junction(link_path: Path, target_path: Path) -> None:
    subprocess.run(
        ["cmd", "/d", "/s", "/c", "mklink", "/J", str(link_path), str(target_path)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def create_alias(link_path: Path, target_path: Path, force: bool) -> str:
    if link_path.exists():
        if force:
            ensure_removed(link_path)
        else:
            return "skipped-existing"

    link_path.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        create_windows_junction(link_path, target_path)
    else:
        os.symlink(target_path, link_path, target_is_directory=True)
    return "created"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create legacy workspace path aliases from workspace-map.json.")
    parser.add_argument("--force", action="store_true", help="Replace existing aliases if present.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    workspace_map = load_workspace_map(root)
    created = 0
    skipped = 0

    for unit in workspace_map["units"]:
        legacy = unit["legacy_path"]
        canonical = unit["canonical_path"]
        if legacy == canonical:
            continue

        link_path = root / legacy
        target_path = root / canonical
        if not target_path.exists():
            print(f"[bootstrap] missing target: {canonical}", file=sys.stderr)
            continue

        result = create_alias(link_path, target_path, force=args.force)
        print(f"[bootstrap] {result}: {legacy} -> {canonical}")
        if result == "created":
            created += 1
        else:
            skipped += 1

    print(f"[bootstrap] summary: created={created}, skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
