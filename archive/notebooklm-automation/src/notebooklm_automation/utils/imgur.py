"""Image hosting upload utility — Imgur / imgbb.

Uploads infographic PNGs to a free image hosting service and returns
a public direct-link URL suitable for Notion image blocks.

Supports:
  • **Imgur** — set ``IMGUR_CLIENT_ID`` env var
  • **imgbb** — set ``IMGBB_API_KEY`` env var (easier: https://api.imgbb.com)

If both are set, Imgur is preferred.
"""
from __future__ import annotations

import base64
import logging
import os
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# ── API endpoints ────────────────────────────────
IMGUR_UPLOAD_URL = "https://api.imgur.com/3/image"
IMGBB_UPLOAD_URL = "https://api.imgbb.com/1/upload"


async def upload_image(
    image_path: str | Path,
    *,
    title: str = "",
    description: str = "",
    client_id: str | None = None,
) -> dict[str, str]:
    """Upload an image to a free hosting service.

    Auto-detects which service to use based on available env vars:
      - ``IMGUR_CLIENT_ID`` → Imgur (anonymous)
      - ``IMGBB_API_KEY`` → imgbb

    Returns:
        ``{"url": "https://i.imgur.com/xxx.png",  # or imgbb URL
           "link": "...",  "delete_hash": "...",  "id": "...",
           "service": "imgur" | "imgbb"}``
    """
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    imgur_cid = client_id or os.getenv("IMGUR_CLIENT_ID", "")
    imgbb_key = os.getenv("IMGBB_API_KEY", "")

    if imgur_cid:
        return await _upload_imgur(image_path, imgur_cid, title, description)
    elif imgbb_key:
        return await _upload_imgbb(image_path, imgbb_key, title)
    else:
        raise RuntimeError(
            "No image hosting API key configured. Set one of:\n"
            "  • IMGUR_CLIENT_ID  (https://api.imgur.com/oauth2/addclient)\n"
            "  • IMGBB_API_KEY   (https://api.imgbb.com — simpler, no login)"
        )


async def _upload_imgur(
    image_path: Path, client_id: str, title: str, description: str,
) -> dict[str, str]:
    """Upload to Imgur anonymous API."""
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    headers = {"Authorization": f"Client-ID {client_id}"}
    payload = {"image": image_data, "type": "base64"}
    if title:
        payload["title"] = title
    if description:
        payload["description"] = description

    async with httpx.AsyncClient(timeout=60.0) as c:
        resp = await c.post(IMGUR_UPLOAD_URL, headers=headers, data=payload)

    if resp.status_code != 200:
        logger.error("Imgur upload failed: %s %s", resp.status_code, resp.text[:200])
        resp.raise_for_status()

    data = resp.json().get("data", {})
    result = {
        "url": data.get("link", ""),
        "link": f"https://imgur.com/{data.get('id', '')}",
        "delete_hash": data.get("deletehash", ""),
        "id": data.get("id", ""),
        "service": "imgur",
    }
    logger.info("Imgur ↑ %s → %s", image_path.name, result["url"])
    return result


async def _upload_imgbb(
    image_path: Path, api_key: str, title: str,
) -> dict[str, str]:
    """Upload to imgbb.com API."""
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    payload = {"key": api_key, "image": image_data}
    if title:
        payload["name"] = title

    async with httpx.AsyncClient(timeout=60.0) as c:
        resp = await c.post(IMGBB_UPLOAD_URL, data=payload)

    if resp.status_code != 200:
        logger.error("imgbb upload failed: %s %s", resp.status_code, resp.text[:200])
        resp.raise_for_status()

    data = resp.json().get("data", {})
    result = {
        "url": data.get("display_url", "") or data.get("url", ""),
        "link": data.get("url_viewer", ""),
        "delete_hash": data.get("delete_url", ""),
        "id": data.get("id", ""),
        "service": "imgbb",
    }
    logger.info("imgbb ↑ %s → %s", image_path.name, result["url"])
    return result


def upload_image_sync(
    image_path: str | Path,
    *,
    title: str = "",
    description: str = "",
    client_id: str | None = None,
) -> dict[str, str]:
    """Synchronous wrapper for ``upload_image``."""
    import asyncio
    return asyncio.run(upload_image(
        image_path, title=title, description=description, client_id=client_id,
    ))
