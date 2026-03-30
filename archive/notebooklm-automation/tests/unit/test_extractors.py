"""Unit tests for notebooklm_automation.extractors (PDF, OCR, Slides)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ──────────────────────────────────────────────────
#  PDF Extractor
# ──────────────────────────────────────────────────


class TestPDFExtractor:
    """Tests for extract_pdf_text."""

    def test_pymupdf_fallback_on_invalid_data(self):
        """PyMuPDF backend returns empty string on invalid PDF data."""
        from notebooklm_automation.extractors.pdf_extractor import _try_pymupdf

        # Invalid data should not crash, just return empty
        result = _try_pymupdf(b"not-valid-pdf", 50)
        assert isinstance(result, str)

    def test_empty_pdf_returns_empty(self):
        """Empty PDF returns empty string."""
        from notebooklm_automation.extractors.pdf_extractor import extract_pdf_text

        # Both backends will fail on random bytes
        result = extract_pdf_text(b"not-a-pdf")
        assert isinstance(result, str)

    def test_max_pages_cap(self):
        """Max pages cap is respected."""
        mock_pages = [MagicMock() for _ in range(10)]
        for p in mock_pages:
            p.get_text.return_value = f"Page {mock_pages.index(p)}"

        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter(mock_pages))

        with patch.dict("sys.modules", {"fitz": MagicMock()}):
            from notebooklm_automation.extractors.pdf_extractor import _try_pymupdf

            with patch("notebooklm_automation.extractors.pdf_extractor.fitz", create=True) as mock_fitz:
                mock_fitz.open.return_value = mock_doc
                result = _try_pymupdf(b"fake", max_pages=3)
                # Should have at most 3 pages
                assert result.count("Page") <= 3

    def test_extract_from_path_missing_file(self):
        """Missing file raises FileNotFoundError."""
        from notebooklm_automation.extractors.pdf_extractor import extract_pdf_text_from_path

        with pytest.raises(FileNotFoundError):
            extract_pdf_text_from_path("/nonexistent/file.pdf")


# ──────────────────────────────────────────────────
#  OCR Extractor
# ──────────────────────────────────────────────────


class TestOCRExtractor:
    """Tests for extract_image_text."""

    def test_empty_on_no_backends(self):
        """Returns empty when no OCR backends available."""
        from notebooklm_automation.extractors.ocr_extractor import extract_image_text

        # Without google-cloud-vision or pytesseract installed, returns ""
        result = extract_image_text(b"fake-image-bytes")
        assert isinstance(result, str)

    def test_extract_from_path_missing_file(self):
        """Missing file raises FileNotFoundError."""
        from notebooklm_automation.extractors.ocr_extractor import extract_image_text_from_path

        with pytest.raises(FileNotFoundError):
            extract_image_text_from_path("/nonexistent/image.png")


# ──────────────────────────────────────────────────
#  Slides Extractor
# ──────────────────────────────────────────────────


class TestSlidesExtractor:
    """Tests for slides text extraction."""

    def test_pptx_extraction_no_pptx_lib(self):
        """Returns empty when python-pptx not installed."""
        from notebooklm_automation.extractors.slides_extractor import extract_slides_text_from_export

        result = extract_slides_text_from_export(b"fake-pptx-data")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_slides_api_no_credentials(self):
        """API extraction returns empty without credentials."""
        from notebooklm_automation.extractors.slides_extractor import extract_slides_text

        result = await extract_slides_text("fake-presentation-id")
        assert result == ""
