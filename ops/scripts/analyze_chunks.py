from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize JS bundles in a dist/assets directory.")
    parser.add_argument(
        "--dist-assets",
        type=Path,
        required=True,
        help="Path to the dist/assets directory to inspect.",
    )
    parser.add_argument(
        "--max-chunk-kb",
        type=float,
        default=450.0,
        help="Fail if any JS chunk exceeds this size in KB.",
    )
    parser.add_argument(
        "--max-entry-kb",
        type=float,
        default=400.0,
        help="Fail if the main index-*.js entry chunk exceeds this size in KB.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Maximum number of assets to print.",
    )
    return parser.parse_args()


def collect_assets(dist_assets: Path) -> list[tuple[str, int, float]]:
    if not dist_assets.exists():
        raise FileNotFoundError(f"{dist_assets} does not exist")

    assets: list[tuple[str, int, float]] = []
    for asset in sorted(dist_assets.glob("*.js")):
        size_bytes = asset.stat().st_size
        size_kb = round(size_bytes / 1024, 2)
        assets.append((asset.name, size_bytes, size_kb))

    if not assets:
        raise FileNotFoundError(f"No JS assets found in {dist_assets}")

    return sorted(assets, key=lambda item: item[1], reverse=True)


def main() -> int:
    args = parse_args()
    assets = collect_assets(args.dist_assets)

    print("[chunk-analysis] JS bundle summary (KB):")
    for filename, _, size_kb in assets[: args.top]:
        print(f"- {filename}: {size_kb}")

    oversized_chunks = [asset for asset in assets if asset[2] > args.max_chunk_kb]
    entry_chunk = next((asset for asset in assets if asset[0].startswith("index-")), None)
    entry_too_large = entry_chunk is not None and entry_chunk[2] > args.max_entry_kb

    if oversized_chunks:
        print(
            f"[chunk-analysis] Found chunk(s) larger than {args.max_chunk_kb}KB:",
            file=sys.stderr,
        )
        for filename, _, size_kb in oversized_chunks:
            print(f"  - {filename}: {size_kb}KB", file=sys.stderr)

    if entry_too_large and entry_chunk is not None:
        print(
            "[chunk-analysis] Entry chunk too large "
            f"(> {args.max_entry_kb}KB): {entry_chunk[0]} ({entry_chunk[2]}KB)",
            file=sys.stderr,
        )

    return 1 if oversized_chunks or entry_too_large else 0


if __name__ == "__main__":
    raise SystemExit(main())
