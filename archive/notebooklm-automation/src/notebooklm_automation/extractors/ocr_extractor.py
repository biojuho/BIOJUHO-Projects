"""Image OCR text extraction — Google Vision API with Tesseract fallback.

Usage:
    from notebooklm_automation.extractors.ocr_extractor import extract_image_text

    text = extract_image_text(image_bytes)
    text = extract_image_text_from_path("/tmp/infographic.png")
"""

from __future__ import annotations

import io
from pathlib import Path

from loguru import logger as log


def extract_image_text(data: bytes, *, language: str = "ko+en") -> str:
    """Extract text from image bytes via OCR.

    Tries Google Vision API first (cloud, high accuracy),
    falls back to Tesseract (local, free).

    Args:
        data: Raw image bytes (PNG, JPG, etc.).
        language: OCR language hint (Tesseract format).
    """
    text = _try_google_vision(data)
    if text:
        return text

    text = _try_tesseract(data, language)
    if text:
        return text

    log.warning("[OCR] Both backends failed — returning empty string")
    return ""


def extract_image_text_from_path(path: str | Path, **kwargs) -> str:
    """Convenience wrapper to read a file and extract text."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Image not found: {p}")
    return extract_image_text(p.read_bytes(), **kwargs)


# ──────────────────────────────────────────────────
#  Backend: Google Cloud Vision API
# ──────────────────────────────────────────────────

def _try_google_vision(data: bytes) -> str:
    """OCR via Google Cloud Vision API (requires GOOGLE_APPLICATION_CREDENTIALS)."""
    try:
        from google.cloud import vision  # type: ignore[import-untyped]
    except ImportError:
        log.debug("[OCR] google-cloud-vision not installed — skipping")
        return ""

    try:
        client = vision.ImageAnnotatorClient()
        image = vision.Image(content=data)
        response = client.text_detection(image=image)

        if response.error.message:
            log.warning("[OCR] Vision API error: %s", response.error.message)
            return ""

        texts = response.text_annotations
        if not texts:
            return ""

        full_text = texts[0].description.strip()
        log.info("[OCR] Vision API extracted %d chars", len(full_text))
        return full_text

    except Exception as e:
        log.warning("[OCR] Vision API failed: %s", e)
        return ""


# ──────────────────────────────────────────────────
#  Backend: Tesseract OCR (local fallback)
# ──────────────────────────────────────────────────

def _try_tesseract(data: bytes, language: str) -> str:
    """OCR via pytesseract + Pillow (requires tesseract binary)."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        log.debug("[OCR] pytesseract/Pillow not installed — skipping")
        return ""

    try:
        image = Image.open(io.BytesIO(data))
        # Convert to RGB if necessary (handles RGBA, P mode, etc.)
        if image.mode not in ("L", "RGB"):
            image = image.convert("RGB")

        text = pytesseract.image_to_string(image, lang=language).strip()
        log.info("[OCR] Tesseract extracted %d chars", len(text))
        return text

    except Exception as e:
        log.warning("[OCR] Tesseract failed: %s", e)
        return ""
