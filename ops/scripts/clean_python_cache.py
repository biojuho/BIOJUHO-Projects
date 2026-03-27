#!/usr/bin/env python3
"""
Clean Python cache files and directories.

Usage:
    python scripts/clean_python_cache.py [--dry-run] [--verbose]

This script removes:
- __pycache__ directories
- *.pyc files
- *.pyo files
- .pytest_cache directories
"""

import argparse
import shutil
from pathlib import Path


def clean_cache(root_dir: Path, dry_run: bool = False, verbose: bool = False) -> dict:
    """Remove Python cache files and directories.

    Args:
        root_dir: Root directory to search from
        dry_run: If True, only report what would be deleted
        verbose: If True, print each item being deleted

    Returns:
        Dictionary with counts of deleted items
    """
    stats = {
        "__pycache__": 0,
        ".pytest_cache": 0,
        "*.pyc": 0,
        "*.pyo": 0,
    }

    # Directories to skip (node_modules, .venv, etc.)
    skip_dirs = {
        "node_modules",
        ".venv",
        "venv",
        ".git",
        ".mypy_cache",
        ".tox",
        "dist",
        "build",
        ".eggs",
    }

    print(f"Scanning {root_dir}...")

    # Remove __pycache__ directories
    for pycache in root_dir.rglob("__pycache__"):
        # Skip if inside excluded directory
        if any(excluded in pycache.parts for excluded in skip_dirs):
            continue

        if dry_run:
            print(f"[DRY RUN] Would remove: {pycache}")
        else:
            if verbose:
                print(f"Removing: {pycache}")
            shutil.rmtree(pycache, ignore_errors=True)
        stats["__pycache__"] += 1

    # Remove .pytest_cache directories
    for pytest_cache in root_dir.rglob(".pytest_cache"):
        if any(excluded in pytest_cache.parts for excluded in skip_dirs):
            continue

        if dry_run:
            print(f"[DRY RUN] Would remove: {pytest_cache}")
        else:
            if verbose:
                print(f"Removing: {pytest_cache}")
            shutil.rmtree(pytest_cache, ignore_errors=True)
        stats[".pytest_cache"] += 1

    # Remove .pyc and .pyo files
    for pattern in ["*.pyc", "*.pyo"]:
        for cache_file in root_dir.rglob(pattern):
            if any(excluded in cache_file.parts for excluded in skip_dirs):
                continue

            if dry_run:
                print(f"[DRY RUN] Would remove: {cache_file}")
            else:
                if verbose:
                    print(f"Removing: {cache_file}")
                cache_file.unlink(missing_ok=True)
            stats[pattern] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(description="Clean Python cache files")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print each file/directory being deleted",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).parent.parent,
        help="Root directory to clean (default: project root)",
    )

    args = parser.parse_args()

    print("Python Cache Cleaner")
    print("=" * 50)

    if args.dry_run:
        print("[DRY RUN] No files will be deleted")
    else:
        print("[LIVE MODE] Files will be permanently deleted")

    print()

    stats = clean_cache(
        root_dir=args.root,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    print()
    print("Summary:")
    print("-" * 50)
    for item_type, count in stats.items():
        action = "would be" if args.dry_run else "were"
        print(f"  {item_type:20s}: {count:5d} items {action} removed")

    print()
    if args.dry_run:
        print("[OK] Dry run complete. Run without --dry-run to delete files.")
    else:
        print("[OK] Cache cleaning complete!")


if __name__ == "__main__":
    main()
