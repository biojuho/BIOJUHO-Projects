"""Image generation service for Instagram posts.

Supports:
1. Google Gemini image generation (via Imagen model)
2. Image upload to cloud storage for public URL
3. JPEG format enforcement (Meta API requires JPEG, rejects PNG)
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

logger = logging.getLogger(__name__)

# Aspect ratios for Instagram
ASPECT_RATIOS = {
    "feed": "1:1",  # 1080x1080
    "portrait": "4:5",  # 1080x1350
    "reels": "9:16",  # 1080x1920
    "stories": "9:16",
    "landscape": "1.91:1",  # 1080x566
}

IMAGE_PROMPT_TEMPLATE = """\
Create an Instagram-ready image for the following topic.

Topic: {topic}
Style: {style}
Aspect Ratio: {aspect_ratio}

Requirements:
- Clean, modern design suitable for social media
- No text overlays (caption will be separate)
- High contrast, vibrant colors
- Professional quality
- Visually engaging for scroll-stopping effect"""

# ---- Gemini Image Generation ----


def _get_gemini_api_key() -> str:
    """Get Gemini API key from environment."""
    key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not key:
        raise ValueError("No Google API key found. Set GOOGLE_API_KEY or GEMINI_API_KEY")
    return key


class ImageGenerator:
    """Generate images for Instagram posts using Google Gemini."""

    def __init__(self):
        self._client = None
        self._output_dir = Path(__file__).resolve().parent.parent / "data" / "images"
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def _get_client(self):
        """Lazy-initialize Google GenAI client."""
        if self._client is None:
            try:
                from google import genai

                self._client = genai.Client(api_key=_get_gemini_api_key())
            except ImportError:
                logger.error("google-genai package not installed. Run: pip install google-genai")
                raise
        return self._client

    async def generate_image_prompt(self, topic: str, style: str = "modern") -> str:
        """Generate an optimized image creation prompt using LLM."""
        from shared.llm import TaskTier, get_client

        llm = get_client()
        resp = await llm.acreate(
            tier=TaskTier.LIGHTWEIGHT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"주제 '{topic}'에 대한 인스타그램 이미지를 만들기 위한 "
                        f"영어 이미지 프롬프트를 작성하세요. "
                        f"스타일: {style}. 프롬프트만 출력."
                    ),
                }
            ],
            system="Image prompt engineer. Output prompt text only.",
        )
        return resp.text.strip()

    async def generate_image(
        self,
        topic: str,
        *,
        style: str = "modern",
        format_type: str = "feed",
    ) -> str | None:
        """Generate an image using Gemini Imagen and return local file path.

        The image is saved as JPEG (Meta API requirement) in the data/images dir.
        Returns the file path, or None if generation fails.
        """
        try:
            prompt = await self.generate_image_prompt(topic, style)
            aspect = ASPECT_RATIOS.get(format_type, "1:1")

            full_prompt = IMAGE_PROMPT_TEMPLATE.format(topic=topic, style=style, aspect_ratio=aspect)
            # Combine LLM prompt with structural template
            final_prompt = f"{prompt}\n\n{full_prompt}"

            client = self._get_client()
            from google import genai

            # Use Imagen 3 for image generation
            response = client.models.generate_images(
                model="imagen-3.0-generate-002",
                prompt=final_prompt,
                config=genai.types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio=aspect,
                    output_mime_type="image/jpeg",
                ),
            )

            if not response.generated_images:
                logger.warning("Imagen returned no images for topic: %s", topic)
                return None

            # Save as JPEG
            image_data = response.generated_images[0].image.image_bytes
            filename = self._make_filename(topic)
            filepath = self._output_dir / filename

            filepath.write_bytes(image_data)
            logger.info("Generated image saved: %s (%d bytes)", filepath, len(image_data))
            return str(filepath)

        except ImportError:
            logger.error("google-genai not installed — image generation unavailable")
            return None
        except Exception as e:
            logger.error("Image generation failed: %s", e)
            return None

    def _make_filename(self, topic: str) -> str:
        """Generate a safe filename from topic."""
        import hashlib
        import time

        safe = "".join(c if c.isalnum() else "_" for c in topic[:30])
        ts = int(time.time())
        short_hash = hashlib.md5(topic.encode()).hexdigest()[:6]
        return f"ig_{safe}_{ts}_{short_hash}.jpg"

    @staticmethod
    def ensure_jpeg(image_path: str) -> str:
        """Convert image to JPEG if not already.

        Meta Graph API rejects PNG images.
        Returns path to JPEG file.
        """
        path = Path(image_path)
        if path.suffix.lower() in (".jpg", ".jpeg"):
            return image_path

        try:
            from PIL import Image

            img = Image.open(path)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            jpeg_path = path.with_suffix(".jpg")
            img.save(jpeg_path, "JPEG", quality=95)
            logger.info("Converted %s → %s", path.name, jpeg_path.name)
            return str(jpeg_path)
        except ImportError:
            logger.error("Pillow not installed — cannot convert to JPEG")
            return image_path

    @staticmethod
    def validate_image_url(url: str) -> bool:
        """Check if URL meets Meta Graph API requirements.

        Requirements:
        - Must be a public, direct URL to the image file
        - No redirects or authentication
        - Supported formats: JPEG only (PNG rejected since 2025)
        - Max size: 8MB for images
        """
        if not url.startswith("https://"):
            return False
        # Must end with JPEG extension or be a known CDN
        valid_extensions = (".jpg", ".jpeg")
        known_cdns = (
            "blob.vercel-storage.com",
            "res.cloudinary.com",
            "s3.amazonaws.com",
            "storage.googleapis.com",
            "firebasestorage.googleapis.com",
        )
        url_lower = url.lower().split("?")[0]
        has_extension = any(url_lower.endswith(ext) for ext in valid_extensions)
        is_cdn = any(cdn in url_lower for cdn in known_cdns)
        return has_extension or is_cdn
