from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = REPO_ROOT / "skills" / "x-article-publisher" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import validate_article  # noqa: E402


class ValidateArticleTests(unittest.TestCase):
    def test_build_dry_run_report_includes_selector_manifest_and_sorted_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            images_dir = root / "assets"
            images_dir.mkdir()
            (images_dir / "cover.jpg").write_bytes(b"cover")
            (images_dir / "chart.png").write_bytes(b"chart")
            (images_dir / "detail.png").write_bytes(b"detail")

            markdown = root / "article.md"
            markdown.write_text(
                "# Report Title\n\n"
                "![cover](./assets/cover.jpg)\n\n"
                "Intro paragraph.\n\n"
                "![chart](./assets/chart.png)\n\n"
                "Second paragraph.\n\n"
                "![detail](./assets/detail.png)\n\n"
                "---\n\n"
                "Done.\n",
                encoding="utf-8",
            )

            report = validate_article.build_dry_run_report(str(markdown), allow_global_image_search=False)

            self.assertEqual(report["status"], "ok")
            self.assertEqual(report["selectors"]["status"], "ok")
            self.assertEqual(report["article"]["content_image_count"], 2)
            self.assertEqual(report["workflow_plan"][-1]["step"], "save_draft")
            image_order = report["workflow_plan"][5]["details"]["order"]
            self.assertEqual(
                [item["block_index"] for item in image_order],
                sorted([item["block_index"] for item in image_order], reverse=True),
            )


if __name__ == "__main__":
    unittest.main()
