from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from antigravity_mcp.config import get_settings
from antigravity_mcp.domain.models import ContentReport

logger = logging.getLogger(__name__)

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None
    ImageDraw = None
    ImageFont = None


class CanvaAdapter:
    def __init__(self) -> None:
        self.settings = get_settings()

    def create_draft(self, report: ContentReport) -> dict[str, str]:
        if not self.settings.canva_client_id or not self.settings.canva_client_secret:
            return {"status": "disabled", "edit_url": ""}
        return {
            "status": "draft",
            "edit_url": "",
        }

    def generate_infographic(
        self,
        category: str,
        articles: list[dict[str, Any]],
        output_dir: Path | None = None,
    ) -> Path | None:
        """Generate a 1080x1080 dark-themed infographic card using PIL.

        Returns the path to the generated PNG, or None if PIL is unavailable.
        """
        if Image is None:
            logger.info("PIL unavailable; skipping infographic generation")
            return None

        output_dir = output_dir or self.settings.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        path = output_dir / f"infographic_{category}_{ts}.png"

        try:
            font_title = ImageFont.truetype("malgunbd.ttf", 60)
            font_date = ImageFont.truetype("malgun.ttf", 30)
            font_body_bold = ImageFont.truetype("malgunbd.ttf", 35)
            font_body = ImageFont.truetype("malgun.ttf", 28)
        except Exception:
            font_title = font_date = font_body_bold = font_body = ImageFont.load_default()

        img = Image.new("RGB", (1080, 1080), "#1a1a2e")
        draw = ImageDraw.Draw(img)
        draw.rectangle([(0, 0), (1080, 180)], fill="#16213e")
        draw.text((60, 45), f"{category.upper()} NEWS", font=font_title, fill="#e94560")
        draw.text((60, 125), datetime.now().strftime("%Y-%m-%d"), font=font_date, fill="#aaaaaa")

        y_pos = 220
        for idx, a in enumerate(articles[:5]):
            draw.rectangle([(40, y_pos), (1040, y_pos + 140)], fill="#0f3460", outline="#e94560")
            title_text = a.get("title", "")[:40] + ("..." if len(a.get("title", "")) > 40 else "")
            draw.text((70, y_pos + 30), f"{idx + 1}. {title_text}", font=font_body_bold, fill="white")
            source = a.get("source", "Unknown")
            sentiment = a.get("sentiment", "NEUTRAL")
            draw.text((70, y_pos + 90), f"    출처: {source} | 감성: {sentiment}", font=font_body, fill="#b5b5c3")
            y_pos += 160

        img.save(path)
        logger.info("Infographic saved: %s", path)
        return path
