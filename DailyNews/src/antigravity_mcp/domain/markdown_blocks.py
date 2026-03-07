from __future__ import annotations

from typing import Any


def _rich_text(content: str) -> list[dict[str, Any]]:
    return [{"type": "text", "text": {"content": content}}]


def markdown_to_blocks(markdown: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("### "):
            blocks.append(
                {
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {"rich_text": _rich_text(line[4:])},
                }
            )
            continue
        if line.startswith("## "):
            blocks.append(
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {"rich_text": _rich_text(line[3:])},
                }
            )
            continue
        if line.startswith("# "):
            blocks.append(
                {
                    "object": "block",
                    "type": "heading_1",
                    "heading_1": {"rich_text": _rich_text(line[2:])},
                }
            )
            continue
        if line.startswith("- "):
            blocks.append(
                {
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {"rich_text": _rich_text(line[2:])},
                }
            )
            continue
        if len(line) > 3 and line[0].isdigit() and line[1:3] == ". ":
            blocks.append(
                {
                    "object": "block",
                    "type": "numbered_list_item",
                    "numbered_list_item": {"rich_text": _rich_text(line[3:])},
                }
            )
            continue
        blocks.append(
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": _rich_text(line)},
            }
        )
    return blocks


def block_to_text(block: dict[str, Any]) -> str:
    block_type = block.get("type", "")
    payload = block.get(block_type, {})
    rich_text = payload.get("rich_text", [])
    plain_text = "".join(item.get("plain_text") or item.get("text", {}).get("content", "") for item in rich_text)
    if block_type == "heading_1":
        return f"# {plain_text}"
    if block_type == "heading_2":
        return f"## {plain_text}"
    if block_type == "heading_3":
        return f"### {plain_text}"
    if block_type == "bulleted_list_item":
        return f"- {plain_text}"
    if block_type == "numbered_list_item":
        return f"1. {plain_text}"
    return plain_text
