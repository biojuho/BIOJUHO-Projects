import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# WIN FIX
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "desci-platform"))

from biolinker.services.pdf_parser import PDFParser


class TestPDFParser(unittest.TestCase):
    @patch("biolinker.services.pdf_parser.pypdf.PdfReader")
    def test_parse_success(self, mock_reader_class):
        # Setup mock
        mock_reader = MagicMock()
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "Page 1 Text"
        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = "Page 2 Text"

        mock_reader.pages = [mock_page1, mock_page2]
        mock_reader_class.return_value = mock_reader

        # Test
        parser = PDFParser()
        result = parser.parse(b"dummy pdf content")

        # Verify
        self.assertIn("Page 1 Text", result)
        self.assertIn("Page 2 Text", result)
        print("✅ Parser extraction verified")

    @patch("biolinker.services.pdf_parser.pypdf.PdfReader")
    def test_parse_error(self, mock_reader_class):
        # Setup mock to raise exception
        mock_reader_class.side_effect = Exception("Invalid PDF")

        # Test
        parser = PDFParser()
        result = parser.parse(b"invalid content")

        # Verify empty string on error
        self.assertEqual(result, "")
        print("✅ Parser error handling verified")


if __name__ == "__main__":
    unittest.main()
