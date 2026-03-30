#!/usr/bin/env python3
"""
Dry-run validation for X Articles publishing.

Produces a structured plan with:
- parse validation status
- selector manifest summary
- ordered browser steps
- actionable warnings/errors
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from parse_markdown import build_workflow_plan, parse_markdown_file

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
SELECTOR_MANIFEST = SKILL_DIR / "config" / "selectors.json"


def load_selector_manifest() -> dict[str, Any]:
    if not SELECTOR_MANIFEST.exists():
        return {
            "status": "missing",
            "path": str(SELECTOR_MANIFEST),
            "selectors": {},
        }
    return {
        "status": "ok",
        "path": str(SELECTOR_MANIFEST),
        "selectors": json.loads(SELECTOR_MANIFEST.read_text(encoding="utf-8")),
    }


def build_dry_run_report(markdown_file: str, *, allow_global_image_search: bool = True) -> dict[str, Any]:
    article = parse_markdown_file(markdown_file, allow_global_image_search=allow_global_image_search)
    selector_manifest = load_selector_manifest()
    validation = article.get("validation", {"status": "error", "errors": ["Missing validation output"], "warnings": []})

    warnings = list(validation.get("warnings", []))
    errors = list(validation.get("errors", []))
    if selector_manifest["status"] != "ok":
        warnings.append("Selector manifest is missing; automation instructions may drift from the X editor UI.")

    return {
        "status": "ok" if not errors else "error",
        "article": {
            "title": article.get("title", ""),
            "source_file": article.get("source_file", ""),
            "cover_image": article.get("cover_image"),
            "content_image_count": len(article.get("content_images", [])),
            "divider_count": len(article.get("dividers", [])),
            "total_blocks": article.get("total_blocks", 0),
        },
        "validation": validation,
        "selectors": selector_manifest,
        "workflow_plan": build_workflow_plan(article),
        "warnings": warnings,
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a Markdown article before X Articles automation")
    parser.add_argument("file", help="Markdown file to validate")
    parser.add_argument("--no-global-image-search", action="store_true", help="Disable global fallback image lookup")
    args = parser.parse_args()

    target = Path(args.file)
    if not target.exists():
        print(json.dumps({"status": "error", "errors": [f"File not found: {target}"]}, ensure_ascii=False, indent=2))
        sys.exit(1)

    report = build_dry_run_report(
        str(target),
        allow_global_image_search=not args.no_global_image_search,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "ok":
        sys.exit(1)


if __name__ == "__main__":
    main()
