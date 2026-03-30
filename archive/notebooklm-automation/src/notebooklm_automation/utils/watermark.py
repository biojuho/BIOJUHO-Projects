"""Watermark utility — overlay branding on infographic PNGs.

Adds a semi-transparent watermark bar with logo text (e.g. "JooPark 쥬팍")
to the bottom-right corner of downloaded infographic images.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# ── Default branding config ──────────────────────────────
DEFAULT_BRAND_TEXT = "JooPark 쥬팍"
DEFAULT_OPACITY = 180  # 0-255 (255 = fully opaque)
DEFAULT_FONT_SIZE = 28
DEFAULT_PADDING = 16
DEFAULT_BG_COLOR = (30, 30, 30)  # Dark grey
DEFAULT_TEXT_COLOR = (255, 255, 255)  # White


def add_watermark(
    image_path: str | Path,
    *,
    brand_text: str = DEFAULT_BRAND_TEXT,
    output_path: str | Path | None = None,
    opacity: int = DEFAULT_OPACITY,
    font_size: int = DEFAULT_FONT_SIZE,
    padding: int = DEFAULT_PADDING,
    bg_color: tuple[int, int, int] = DEFAULT_BG_COLOR,
    text_color: tuple[int, int, int] = DEFAULT_TEXT_COLOR,
    position: str = "bottom-right",
) -> Path:
    """Overlay a branded watermark on an image.

    Args:
        image_path: Source PNG/JPEG file.
        brand_text: Text to display (e.g. ``"JooPark 쥬팍"``).
        output_path: Where to save. Defaults to overwriting the source.
        opacity: Alpha value for the watermark overlay (0-255).
        font_size: Base font size. Auto-scales if image is very large.
        padding: Pixel padding around the text.
        bg_color: RGB background colour for the watermark pill.
        text_color: RGB text colour.
        position: One of ``"bottom-right"``, ``"bottom-left"``,
            ``"top-right"``, ``"top-left"``.

    Returns:
        Path to the watermarked image file.
    """
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    output_path = Path(output_path) if output_path else image_path

    img = Image.open(image_path).convert("RGBA")
    img_w, img_h = img.size

    # Auto-scale font for large images
    scale = max(1.0, min(img_w, img_h) / 1000.0)
    actual_font_size = int(font_size * scale)
    actual_padding = int(padding * scale)

    # Try to load a nice font, fall back to default
    font = _get_font(actual_font_size)

    # Measure text
    dummy = Image.new("RGBA", (1, 1))
    draw_dummy = ImageDraw.Draw(dummy)
    bbox = draw_dummy.textbbox((0, 0), brand_text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # Create watermark overlay
    pill_w = text_w + actual_padding * 2
    pill_h = text_h + actual_padding * 2
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Position
    margin = int(20 * scale)
    if position == "bottom-right":
        x = img_w - pill_w - margin
        y = img_h - pill_h - margin
    elif position == "bottom-left":
        x = margin
        y = img_h - pill_h - margin
    elif position == "top-right":
        x = img_w - pill_w - margin
        y = margin
    else:  # top-left
        x = margin
        y = margin

    # Draw rounded-rect background pill
    r = int(8 * scale)  # corner radius
    draw.rounded_rectangle(
        [x, y, x + pill_w, y + pill_h],
        radius=r,
        fill=(*bg_color, opacity),
    )

    # Draw text
    text_x = x + actual_padding
    text_y = y + actual_padding
    draw.text(
        (text_x, text_y),
        brand_text,
        font=font,
        fill=(*text_color, 255),
    )

    # Composite
    watermarked = Image.alpha_composite(img, overlay)

    # Save as PNG (preserve quality)
    if output_path.suffix.lower() in (".jpg", ".jpeg"):
        watermarked = watermarked.convert("RGB")
    watermarked.save(str(output_path))
    logger.info("Watermark added: %s → %s", image_path.name, output_path.name)

    return output_path


def _get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try to load a Korean-capable font, fall back to default."""
    font_candidates = [
        # Windows Korean fonts
        "C:/Windows/Fonts/malgunbd.ttf",  # Malgun Gothic Bold
        "C:/Windows/Fonts/malgun.ttf",  # Malgun Gothic
        "C:/Windows/Fonts/NanumGothicBold.ttf",
        "C:/Windows/Fonts/NanumGothic.ttf",
        # macOS
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        # Linux
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    ]
    for fp in font_candidates:
        try:
            return ImageFont.truetype(fp, size)
        except OSError:
            continue

    logger.warning("No Korean font found, using Pillow default")
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()
