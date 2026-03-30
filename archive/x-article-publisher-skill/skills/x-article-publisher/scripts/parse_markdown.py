#!/usr/bin/env python3
"""
Parse Markdown for X Articles publishing.

Extracts:
- Title (from first H1/H2 or first line)
- Cover image (first image)
- Content images with block index for precise positioning
- Dividers (---) with block index for menu insertion
- HTML content (images and dividers stripped)

Usage:
    python parse_markdown.py <markdown_file> [--output json|html]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
from pathlib import Path
from typing import Any

SEARCH_DIRS = [
    Path.home() / "Downloads",
    Path.home() / "Desktop",
    Path.home() / "Pictures",
]
LOCAL_IMAGE_HINT_DIRS = ("images", "image", "assets", "media", "uploads")
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def _normalize_markdown_path(raw_path: str) -> str:
    cleaned = raw_path.strip().strip('"').strip("'")
    return urllib.parse.unquote(cleaned)


def _candidate_image_paths(base_path: Path, raw_path: str) -> list[tuple[Path, str]]:
    normalized = _normalize_markdown_path(raw_path)
    candidate_paths: list[tuple[Path, str]] = []
    seen: set[str] = set()

    def add_candidate(path: Path, strategy: str) -> None:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            return
        seen.add(key)
        candidate_paths.append((path, strategy))

    path_obj = Path(normalized)
    if path_obj.is_absolute():
        add_candidate(path_obj, "absolute")
    else:
        add_candidate(base_path / path_obj, "relative")

    filename = path_obj.name
    if filename:
        add_candidate(base_path / filename, "base_filename")
        for hint_dir in LOCAL_IMAGE_HINT_DIRS:
            add_candidate(base_path / hint_dir / filename, f"local_hint:{hint_dir}")

    return candidate_paths


def find_image_file(raw_path: str, base_path: Path, allow_global_search: bool = True) -> dict[str, Any]:
    """Find an image file and return resolution metadata."""
    candidate_paths = _candidate_image_paths(base_path, raw_path)

    for candidate, strategy in candidate_paths:
        if candidate.is_file():
            return {
                "path": str(candidate.resolve()),
                "exists": True,
                "resolution_strategy": strategy,
                "searched_paths": [str(path) for path, _ in candidate_paths],
            }

    filename = Path(_normalize_markdown_path(raw_path)).name
    if allow_global_search and filename:
        for search_dir in SEARCH_DIRS:
            candidate = search_dir / filename
            if candidate.is_file():
                print(
                    f"[parse_markdown] Image not found near document, using global fallback '{candidate}'",
                    file=sys.stderr,
                )
                return {
                    "path": str(candidate.resolve()),
                    "exists": True,
                    "resolution_strategy": "global_search",
                    "searched_paths": [str(path) for path, _ in candidate_paths]
                    + [str(search_dir / filename) for search_dir in SEARCH_DIRS],
                }

    unresolved = candidate_paths[0][0] if candidate_paths else base_path / _normalize_markdown_path(raw_path)
    print(
        f"[parse_markdown] WARNING: Image not found: '{raw_path}'",
        file=sys.stderr,
    )
    return {
        "path": str(unresolved),
        "exists": False,
        "resolution_strategy": "missing",
        "searched_paths": [str(path) for path, _ in candidate_paths],
    }


def split_into_blocks(markdown: str) -> list[str]:
    """Split markdown into logical blocks."""
    blocks: list[str] = []
    current_block: list[str] = []
    in_code_block = False
    code_block_lines: list[str] = []

    for line in markdown.split("\n"):
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code_block:
                in_code_block = False
                if code_block_lines:
                    blocks.append("___CODE_BLOCK_START___" + "\n".join(code_block_lines) + "___CODE_BLOCK_END___")
                code_block_lines = []
            else:
                if current_block:
                    blocks.append("\n".join(current_block))
                    current_block = []
                in_code_block = True
            continue

        if in_code_block:
            code_block_lines.append(line)
            continue

        if not stripped:
            if current_block:
                blocks.append("\n".join(current_block))
                current_block = []
            continue

        if re.match(r"^---+$", stripped):
            if current_block:
                blocks.append("\n".join(current_block))
                current_block = []
            blocks.append("___DIVIDER___")
            continue

        if stripped.startswith(("#", ">")):
            if current_block:
                blocks.append("\n".join(current_block))
                current_block = []
            blocks.append(stripped)
            continue

        if re.match(r"^!\[.*\]\(.*\)$", stripped):
            if current_block:
                blocks.append("\n".join(current_block))
                current_block = []
            blocks.append(stripped)
            continue

        current_block.append(line)

    if current_block:
        blocks.append("\n".join(current_block))
    if code_block_lines:
        blocks.append("___CODE_BLOCK_START___" + "\n".join(code_block_lines) + "___CODE_BLOCK_END___")
    return blocks


def extract_images_and_dividers(
    markdown: str,
    base_path: Path,
    *,
    allow_global_image_search: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str, int]:
    """Extract images and dividers with block index positions."""
    blocks = split_into_blocks(markdown)
    images: list[dict[str, Any]] = []
    dividers: list[dict[str, Any]] = []
    clean_blocks: list[str] = []

    img_pattern = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)$")

    for block in blocks:
        block_stripped = block.strip()

        if block_stripped == "___DIVIDER___":
            block_index = len(clean_blocks)
            after_text = ""
            if clean_blocks:
                prev_block = clean_blocks[-1].strip()
                lines = [line for line in prev_block.split("\n") if line.strip()]
                after_text = lines[-1][:80] if lines else ""
            dividers.append(
                {
                    "block_index": block_index,
                    "after_text": after_text,
                }
            )
            continue

        match = img_pattern.match(block_stripped)
        if not match:
            clean_blocks.append(block)
            continue

        alt_text = match.group(1)
        raw_img_path = match.group(2)
        resolved = find_image_file(raw_img_path, base_path, allow_global_search=allow_global_image_search)
        full_path = resolved["path"]
        suffix = Path(full_path).suffix.lower()

        block_index = len(clean_blocks)
        after_text = ""
        if clean_blocks:
            prev_block = clean_blocks[-1].strip()
            lines = [line for line in prev_block.split("\n") if line.strip()]
            after_text = lines[-1][:80] if lines else ""

        images.append(
            {
                "path": full_path,
                "original_path": str((base_path / _normalize_markdown_path(raw_img_path)).resolve())
                if not Path(_normalize_markdown_path(raw_img_path)).is_absolute()
                else _normalize_markdown_path(raw_img_path),
                "exists": resolved["exists"],
                "alt": alt_text,
                "block_index": block_index,
                "after_text": after_text,
                "resolution_strategy": resolved["resolution_strategy"],
                "supported_format": suffix in SUPPORTED_IMAGE_EXTENSIONS if suffix else False,
                "searched_paths": resolved["searched_paths"],
            }
        )

    clean_markdown = "\n\n".join(clean_blocks)
    return images, dividers, clean_markdown, len(clean_blocks)


def extract_title(markdown: str) -> tuple[str, str]:
    """Extract title and remove H1 from body."""
    lines = markdown.strip().split("\n")
    title = "Untitled"
    title_line_idx = None

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            title_line_idx = idx
            break
        if stripped.startswith("## "):
            title = stripped[3:].strip()
            break
        if not stripped.startswith("!["):
            title = stripped[:100]
            break

    if title_line_idx is not None:
        lines.pop(title_line_idx)
        markdown = "\n".join(lines)
    return title, markdown


def markdown_to_html(markdown: str) -> str:
    """Convert markdown to HTML for X Articles rich text paste."""
    html = markdown

    def convert_code_block(match: re.Match[str]) -> str:
        code_content = match.group(1)
        lines = code_content.strip().split("\n")
        formatted = "<br>".join(line for line in lines if line.strip())
        return f"<blockquote>{formatted}</blockquote>"

    html = re.sub(r"___CODE_BLOCK_START___(.*?)___CODE_BLOCK_END___", convert_code_block, html, flags=re.DOTALL)
    html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", html)
    html = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', html)
    html = re.sub(r"^> (.+)$", r"<blockquote>\1</blockquote>", html, flags=re.MULTILINE)
    html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
    html = re.sub(r"^\d+\. (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
    html = re.sub(r"((?:<li>.*?</li>\n?)+)", r"<ul>\1</ul>", html)

    processed_parts: list[str] = []
    for part in html.split("\n\n"):
        part = part.strip()
        if not part:
            continue
        if part.startswith(("<h2>", "<h3>", "<blockquote>", "<ul>", "<ol>")):
            processed_parts.append(part)
        else:
            processed_parts.append(f"<p>{part.replace('\n', '<br>')}</p>")

    return "".join(processed_parts)


def validate_parsed_article(result: dict[str, Any]) -> dict[str, Any]:
    """Validate parsed article output for dry-run and CI usage."""
    errors: list[str] = []
    warnings: list[str] = []
    total_blocks = int(result.get("total_blocks", 0) or 0)
    title = (result.get("title") or "").strip()

    if not title or title == "Untitled":
        errors.append("Article title could not be resolved.")
    if not result.get("html"):
        errors.append("HTML body is empty after parsing.")
    if total_blocks <= 0:
        errors.append("Article body contains no block content.")

    cover_image = result.get("cover_image")
    if cover_image and not result.get("cover_exists", False):
        errors.append(f"Cover image does not exist: {cover_image}")

    for image in [*result.get("content_images", [])]:
        block_index = int(image.get("block_index", -1))
        if block_index < 0 or block_index > total_blocks:
            errors.append(f"Image block_index out of range: {block_index}")
        if not image.get("exists", False):
            errors.append(f"Content image missing: {image.get('path')}")
        if not image.get("supported_format", False):
            warnings.append(f"Content image format may not be supported by X: {image.get('path')}")
        if image.get("resolution_strategy") == "global_search":
            warnings.append(f"Image resolved via global search fallback: {image.get('path')}")

    for divider in result.get("dividers", []):
        block_index = int(divider.get("block_index", -1))
        if block_index < 0 or block_index > total_blocks:
            errors.append(f"Divider block_index out of range: {block_index}")

    if len(result.get("html", "")) > 120_000:
        warnings.append("HTML payload is large and may paste unreliably into the X editor.")
    if total_blocks > 120:
        warnings.append("Article has more than 120 blocks; browser automation may be slower and harder to recover.")

    return {
        "status": "ok" if not errors else "error",
        "errors": errors,
        "warnings": warnings,
    }


def build_workflow_plan(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Build a deterministic dry-run step plan for operators and tests."""
    content_images = sorted(
        result.get("content_images", []),
        key=lambda item: int(item.get("block_index", 0)),
        reverse=True,
    )
    dividers = sorted(
        result.get("dividers", []),
        key=lambda item: int(item.get("block_index", 0)),
        reverse=True,
    )
    return [
        {"step": "parse_markdown", "status": "ready", "details": {"total_blocks": result.get("total_blocks", 0)}},
        {"step": "open_editor", "status": "ready", "details": {"target_url": "https://x.com/compose/articles"}},
        {"step": "upload_cover", "status": "ready", "details": {"cover_image": result.get("cover_image")}},
        {"step": "fill_title", "status": "ready", "details": {"title": result.get("title", "")}},
        {"step": "paste_html", "status": "ready", "details": {"html_chars": len(result.get("html", ""))}},
        {
            "step": "insert_content_images",
            "status": "ready",
            "details": {
                "count": len(content_images),
                "order": [{"path": img.get("path"), "block_index": img.get("block_index")} for img in content_images],
            },
        },
        {
            "step": "insert_dividers",
            "status": "ready",
            "details": {
                "count": len(dividers),
                "order": [{"block_index": divider.get("block_index")} for divider in dividers],
            },
        },
        {"step": "save_draft", "status": "ready", "details": {"publish_mode": "draft_only"}},
    ]


def parse_markdown_file(filepath: str, *, allow_global_image_search: bool = True) -> dict[str, Any]:
    """Parse a markdown file and return structured data."""
    path = Path(filepath)
    base_path = path.parent
    content = path.read_text(encoding="utf-8")

    if content.startswith("---"):
        end_marker = content.find("---", 3)
        if end_marker != -1:
            content = content[end_marker + 3 :].strip()

    title, content = extract_title(content)
    images, dividers, clean_markdown, total_blocks = extract_images_and_dividers(
        content,
        base_path,
        allow_global_image_search=allow_global_image_search,
    )
    html = markdown_to_html(clean_markdown)

    cover_image = images[0]["path"] if images else None
    cover_exists = images[0]["exists"] if images else True
    content_images = images[1:] if len(images) > 1 else []
    missing = [image for image in images if not image["exists"]]
    if missing:
        print(f"[parse_markdown] WARNING: {len(missing)} image(s) not found", file=sys.stderr)

    result = {
        "title": title,
        "cover_image": cover_image,
        "cover_exists": cover_exists,
        "content_images": content_images,
        "dividers": dividers,
        "html": html,
        "total_blocks": total_blocks,
        "source_file": str(path.resolve()),
        "missing_images": len(missing),
        "image_resolution_mode": "global" if allow_global_image_search else "local_only",
    }
    result["validation"] = validate_parsed_article(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse Markdown for X Articles")
    parser.add_argument("file", help="Markdown file to parse")
    parser.add_argument("--output", choices=["json", "html"], default="json", help="Output format")
    parser.add_argument("--html-only", action="store_true", help="Output only HTML content")
    parser.add_argument(
        "--no-global-image-search", action="store_true", help="Disable fallback search in Downloads/Desktop/Pictures"
    )
    parser.add_argument("--validate", action="store_true", help="Exit with code 1 if parse validation fails")
    parser.add_argument("--dry-run", action="store_true", help="Include a step-by-step workflow plan in JSON output")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    result = parse_markdown_file(
        args.file,
        allow_global_image_search=not args.no_global_image_search,
    )

    if args.dry_run:
        result["workflow_plan"] = build_workflow_plan(result)

    if args.html_only:
        print(result["html"])
        sys.exit(0)

    if args.output == "html":
        print(result["html"])
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.validate and result["validation"]["status"] != "ok":
        sys.exit(1)


if __name__ == "__main__":
    main()
