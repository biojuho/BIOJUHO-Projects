from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = REPO_ROOT / "skills" / "x-article-publisher" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import parse_markdown  # noqa: E402


class ParseMarkdownTests(unittest.TestCase):
    def test_parse_markdown_file_returns_validation_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            images_dir = root / "images"
            images_dir.mkdir()
            (images_dir / "cover.jpg").write_bytes(b"cover")
            (images_dir / "detail.png").write_bytes(b"detail")
            markdown = root / "article.md"
            markdown.write_text(
                "# Test Title\n\n"
                "![cover](./images/cover.jpg)\n\n"
                "Intro paragraph.\n\n"
                "## Section\n\n"
                "More detail.\n\n"
                "![detail](./images/detail.png)\n\n"
                "---\n\n"
                "Closing paragraph.\n",
                encoding="utf-8",
            )

            result = parse_markdown.parse_markdown_file(str(markdown), allow_global_image_search=False)

            self.assertEqual(result["title"], "Test Title")
            self.assertTrue(result["cover_exists"])
            self.assertEqual(len(result["content_images"]), 1)
            self.assertEqual(len(result["dividers"]), 1)
            self.assertEqual(result["validation"]["status"], "ok")
            self.assertGreater(result["total_blocks"], 0)
            self.assertIn("resolution_strategy", result["content_images"][0])

    def test_global_search_can_be_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            markdown = root / "article.md"
            markdown.write_text(
                "# Missing Image\n\n"
                "![cover](./missing/cover.jpg)\n\n"
                "Body.\n",
                encoding="utf-8",
            )

            fallback_dir = root / "Downloads"
            fallback_dir.mkdir()
            (fallback_dir / "cover.jpg").write_bytes(b"cover")
            original_dirs = list(parse_markdown.SEARCH_DIRS)
            parse_markdown.SEARCH_DIRS[:] = [fallback_dir]
            try:
                result = parse_markdown.parse_markdown_file(str(markdown), allow_global_image_search=False)
            finally:
                parse_markdown.SEARCH_DIRS[:] = original_dirs

            self.assertEqual(result["missing_images"], 1)
            self.assertEqual(result["validation"]["status"], "error")
            self.assertIn("Cover image does not exist", result["validation"]["errors"][0])


if __name__ == "__main__":
    unittest.main()
