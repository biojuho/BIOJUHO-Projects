from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path


EXCLUDE_DIRS = {
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".git",
    ".agent",
    ".agents",
    "artifacts",
    "cache",
    "chroma_db",
    "test-results",
    "output",
    "data",
    "ignition",
    "typechain-types",
    "coverage",
    ".hardhat",
    ".nyc_output",
    "htmlcov",
}
EXCLUDE_EXTS = {".pyc", ".log", ".db", ".sqlite", ".tmp", ".class"}
EXCLUDE_FILES = {
    ".env",
    "credentials.json",
    "token.json",
    "serviceAccountKey.json",
    "canva_url.txt",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "sync_log.txt",
}


def parse_args() -> argparse.Namespace:
    workspace_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Mirror the workspace into a Google Drive backup folder.")
    parser.add_argument("--src", default=str(workspace_root))
    parser.add_argument("--dst", default="I:/My Drive/AI-Projects-Backup")
    return parser.parse_args()


def copy_filtered(source: Path, dest: Path, stats: dict[str, int]) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        if item.is_dir():
            if item.name in EXCLUDE_DIRS or item.name.startswith("."):
                stats["skipped"] += 1
                continue
            copy_filtered(item, dest / item.name, stats)
            continue

        if item.name in EXCLUDE_FILES or item.suffix in EXCLUDE_EXTS:
            stats["skipped"] += 1
            continue

        try:
            target = dest / item.name
            if target.exists():
                src_mtime = item.stat().st_mtime
                dst_mtime = target.stat().st_mtime
                if abs(src_mtime - dst_mtime) < 1:
                    stats["skipped"] += 1
                    continue
            shutil.copy2(item, target)
            stats["copied"] += 1
        except Exception as exc:  # pragma: no cover - best effort utility
            print(f"  [SKIP] {item}: {exc}")
            stats["errors"] += 1


def main() -> int:
    args = parse_args()
    src = Path(args.src).expanduser().resolve()
    dst = Path(args.dst).expanduser()

    if not src.exists():
        print(f"Source path not found: {src}")
        return 1

    stats = {"copied": 0, "skipped": 0, "errors": 0}

    print("=" * 45)
    print("  AI Projects -> Google Drive sync")
    print("=" * 45)
    print(f"Source: {src}")
    print(f"Target: {dst}")
    print()

    start = time.time()
    copy_filtered(src, dst, stats)
    elapsed = round(time.time() - start, 1)

    file_count = sum(1 for item in dst.rglob("*") if item.is_file())
    total_bytes = sum(item.stat().st_size for item in dst.rglob("*") if item.is_file())
    total_mb = round(total_bytes / 1024 / 1024, 1)

    print()
    print("=" * 45)
    print("  Done")
    print(f"  Copied : {stats['copied']}")
    print(f"  Skipped: {stats['skipped']}")
    print(f"  Errors : {stats['errors']}")
    print(f"  Total  : {file_count} files / {total_mb} MB")
    print(f"  Elapsed: {elapsed}s")
    print("=" * 45)
    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
