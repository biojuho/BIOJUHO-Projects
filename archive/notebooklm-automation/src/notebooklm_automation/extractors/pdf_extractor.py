"""PDF text extraction — PyMuPDF (fitz) with fallback to pdfplumber.

Usage:
    from notebooklm_automation.extractors import extract_pdf_text

    text = extract_pdf_text(pdf_bytes)               # bytes
    text = extract_pdf_text_from_path("/tmp/a.pdf")  # file path
"""

from __future__ import annotations

import io
from pathlib import Path

from loguru import logger as log


def extract_pdf_text(data: bytes, *, max_pages: int = 50) -> str:
    """Extract text from PDF binary data.

    Tries PyMuPDF first (fast, accurate), falls back to pdfplumber.

    Args:
        data: Raw PDF bytes.
        max_pages: Safety cap on number of pages to process.

    Returns:
        Concatenated text from all pages (up to *max_pages*).
    """
    text = _try_pymupdf(data, max_pages)
    if text:
        return text

    text = _try_pdfplumber(data, max_pages)
    if text:
        return text

    log.warning("[PDFExtractor] Both extractors failed — returning empty string")
    return ""


def extract_pdf_text_from_path(path: str | Path, *, max_pages: int = 50) -> str:
    """Convenience wrapper — read a file and extract text."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"PDF not found: {p}")
    return extract_pdf_text(p.read_bytes(), max_pages=max_pages)


# ──────────────────────────────────────────────────
#  Backend: PyMuPDF (fitz)
# ──────────────────────────────────────────────────

def _try_pymupdf(data: bytes, max_pages: int) -> str:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        log.debug("[PDFExtractor] PyMuPDF not installed — skipping")
        return ""

    try:
        doc = fitz.open(stream=data, filetype="pdf")
        pages: list[str] = []
        for i, page in enumerate(doc):
            if i >= max_pages:
                log.info("[PDFExtractor] max_pages (%d) reached", max_pages)
                break
            pages.append(page.get_text("text"))
        doc.close()
        text = "\n\n".join(pages).strip()
        log.info("[PDFExtractor] PyMuPDF extracted %d chars from %d pages", len(text), len(pages))
        return text
    except Exception as e:
        log.warning("[PDFExtractor] PyMuPDF failed: %s", e)
        return ""


# ──────────────────────────────────────────────────
#  Backend: pdfplumber (fallback)
# ──────────────────────────────────────────────────

def _try_pdfplumber(data: bytes, max_pages: int) -> str:
    try:
        import pdfplumber
    except ImportError:
        log.debug("[PDFExtractor] pdfplumber not installed — skipping")
        return ""

    try:
        pdf = pdfplumber.open(io.BytesIO(data))
        pages: list[str] = []
        for i, page in enumerate(pdf.pages):
            if i >= max_pages:
                break
            text = page.extract_text() or ""
            pages.append(text)
        pdf.close()
        text = "\n\n".join(pages).strip()
        log.info("[PDFExtractor] pdfplumber extracted %d chars from %d pages", len(text), len(pages))
        return text
    except Exception as e:
        log.warning("[PDFExtractor] pdfplumber failed: %s", e)
        return ""
