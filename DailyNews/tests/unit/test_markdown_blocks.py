from __future__ import annotations

from antigravity_mcp.domain.markdown_blocks import block_to_text, markdown_to_blocks


def test_markdown_to_blocks_handles_headings_lists_and_paragraphs():
    blocks = markdown_to_blocks("# Title\n## Subtitle\n- Item\n1. Step\nBody")

    assert [block["type"] for block in blocks] == [
        "heading_1",
        "heading_2",
        "bulleted_list_item",
        "numbered_list_item",
        "paragraph",
    ]
    assert block_to_text(blocks[0]) == "# Title"
    assert block_to_text(blocks[2]) == "- Item"
    assert block_to_text(blocks[4]) == "Body"
