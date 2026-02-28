"""Canva Connect API client for the news pipeline.

Workflow:
1. Import a locally generated image (PIL infographic) as a PDF into Canva,
   creating an editable Canva design the user can further customise.
2. Export the Canva design as a PNG for embedding in Notion pages.

OAuth2 tokens are managed via rotating refresh_token stored in .env.
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
from pathlib import Path
from typing import Any

import requests
from dotenv import set_key

from settings import (
    CANVA_CLIENT_ID,
    CANVA_CLIENT_SECRET,
    CANVA_ENABLED,
    CANVA_REFRESH_TOKEN,
    OUTPUT_DIR,
)

# .env path for persisting rotating refresh tokens
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

# Mutable holder for refresh token (Canva rotates on each use)
_current_refresh_token = CANVA_REFRESH_TOKEN

CANVA_API_BASE = "https://api.canva.com/rest/v1"

# In-memory token cache
_token_cache: dict[str, Any] = {}


class CanvaAuthError(Exception):
    """Raised when Canva authentication fails."""


class CanvaAPIError(Exception):
    """Raised when a Canva API call fails."""


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _refresh_access_token() -> str:
    """Exchange a refresh token for a new access token.

    IMPORTANT: Canva uses rotating refresh tokens. Each refresh returns a NEW
    refresh token and invalidates the old one. We must persist the new token
    to .env and update the in-memory variable for subsequent calls.
    """
    global _current_refresh_token

    if not CANVA_CLIENT_ID or not CANVA_CLIENT_SECRET:
        raise CanvaAuthError("CANVA_CLIENT_ID or CANVA_CLIENT_SECRET missing in .env")
    if not _current_refresh_token:
        raise CanvaAuthError(
            "CANVA_REFRESH_TOKEN missing. Run canva_auth_server.py first to obtain one."
        )

    resp = requests.post(
        f"{CANVA_API_BASE}/oauth/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "refresh_token",
            "refresh_token": _current_refresh_token,
            "client_id": CANVA_CLIENT_ID,
            "client_secret": CANVA_CLIENT_SECRET,
        },
        timeout=15,
    )
    if resp.status_code != 200:
        raise CanvaAuthError(f"Token refresh failed ({resp.status_code}): {resp.text}")

    data = resp.json()
    _token_cache["access_token"] = data["access_token"]
    _token_cache["expires_at"] = time.time() + data.get("expires_in", 3600)

    # Canva rotating refresh token: save the new one
    new_refresh = data.get("refresh_token")
    if new_refresh:
        _current_refresh_token = new_refresh
        try:
            set_key(str(_ENV_PATH), "CANVA_REFRESH_TOKEN", new_refresh)
        except Exception:
            pass  # non-fatal: token is still in memory for this session

    return data["access_token"]


def get_access_token() -> str:
    """Return a valid access token, refreshing if needed."""
    cached = _token_cache.get("access_token")
    expires_at = _token_cache.get("expires_at", 0)
    if cached and time.time() < expires_at - 300:
        return cached
    return _refresh_access_token()


def _api_request(
    endpoint: str,
    method: str = "GET",
    body: dict | None = None,
    timeout: int = 30,
) -> dict:
    """Make an authenticated request to the Canva API."""
    token = get_access_token()
    headers: dict[str, str] = {"Authorization": f"Bearer {token}"}
    if body and method != "GET":
        headers["Content-Type"] = "application/json"

    resp = requests.request(
        method,
        f"{CANVA_API_BASE}{endpoint}",
        headers=headers,
        json=body if method != "GET" else None,
        timeout=timeout,
    )
    if resp.status_code not in (200, 201, 202):
        raise CanvaAPIError(
            f"Canva API {method} {endpoint} failed ({resp.status_code}): {resp.text}"
        )
    return resp.json()


# ---------------------------------------------------------------------------
# Design Import (PIL image -> PDF -> Canva Design)
# ---------------------------------------------------------------------------

def import_image_as_design(image_path: Path, title: str = "Infographic") -> dict:
    """Convert a local image to PDF and import it as a Canva design.

    Canva's import API supports PDF but not PNG/JPG, so we convert first.
    Returns the import job result containing design id and urls.
    """
    from PIL import Image

    # Convert image to PDF
    pdf_path = image_path.with_suffix(".pdf")
    img = Image.open(image_path)
    if img.mode == "RGBA":
        img = img.convert("RGB")
    img.save(pdf_path, "PDF")

    # Upload to Canva
    token = get_access_token()
    title_b64 = base64.b64encode(title[:50].encode()).decode()
    metadata = json.dumps({"title_base64": title_b64, "mime_type": "application/pdf"})

    with open(pdf_path, "rb") as f:
        resp = requests.post(
            f"{CANVA_API_BASE}/imports",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/octet-stream",
                "Import-Metadata": metadata,
            },
            data=f.read(),
            timeout=30,
        )

    if resp.status_code not in (200, 201, 202):
        raise CanvaAPIError(f"Import failed ({resp.status_code}): {resp.text}")

    job_id = resp.json().get("job", {}).get("id")
    if not job_id:
        raise CanvaAPIError(f"No job ID in import response: {resp.text}")

    # Poll until complete
    deadline = time.time() + 60
    while time.time() < deadline:
        poll_resp = _api_request(f"/imports/{job_id}")
        job = poll_resp.get("job", {})
        status = job.get("status")
        if status == "success":
            # Clean up temp PDF
            try:
                pdf_path.unlink()
            except OSError:
                pass
            return job
        if status == "failed":
            raise CanvaAPIError(f"Import failed: {job}")
        time.sleep(2)

    raise CanvaAPIError("Import timed out after 60s")


# ---------------------------------------------------------------------------
# Design Export
# ---------------------------------------------------------------------------

def export_design(design_id: str, fmt: str = "png") -> dict:
    """Request an export of a design. Returns export job info."""
    body: dict[str, Any] = {
        "design_id": design_id,
        "format": {"type": fmt},
    }
    return _api_request("/exports", "POST", body)


def poll_export(export_id: str, max_wait: int = 60) -> dict:
    """Poll until the export is complete or timeout."""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        data = _api_request(f"/exports/{export_id}")
        job = data.get("job", {})
        status = job.get("status") or data.get("status")
        if status in ("success", "completed"):
            return data
        if status == "failed":
            raise CanvaAPIError(f"Export failed: {data}")
        time.sleep(2)
    raise CanvaAPIError(f"Export timed out after {max_wait}s")


def download_export(url: str, output_path: Path) -> Path:
    """Download an exported image to a local file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    output_path.write_bytes(resp.content)
    return output_path


# ---------------------------------------------------------------------------
# High-level pipeline helpers
# ---------------------------------------------------------------------------

def import_and_export(
    image_path: Path,
    title: str = "Infographic",
    output_path: Path | None = None,
) -> dict:
    """Import a local image as a Canva design and export it as PNG.

    Returns a dict with:
      - design_id: Canva design ID
      - edit_url: URL to edit the design in Canva
      - view_url: URL to view the design
      - png_path: local path of exported PNG (if export succeeded)
    """
    # Import
    job = import_image_as_design(image_path, title)
    designs = job.get("result", {}).get("designs", [])
    if not designs:
        raise CanvaAPIError("Import succeeded but no designs returned")

    design = designs[0]
    design_id = design["id"]
    result: dict[str, Any] = {
        "design_id": design_id,
        "edit_url": design.get("urls", {}).get("edit_url", ""),
        "view_url": design.get("urls", {}).get("view_url", ""),
        "png_path": None,
    }

    # Export as PNG
    export_result = export_design(design_id, "png")
    export_id = export_result.get("job", {}).get("id")
    if not export_id:
        return result

    completed = poll_export(export_id)
    urls = completed.get("job", {}).get("urls", [])
    if not urls:
        return result

    out = output_path or (OUTPUT_DIR / f"canva_{design_id}.png")
    download_export(urls[0], out)
    result["png_path"] = out
    return result


async def async_import_and_export(
    image_path: Path,
    title: str = "Infographic",
    output_path: Path | None = None,
) -> dict | None:
    """Async wrapper for import_and_export, for use in the news pipeline."""
    if not CANVA_ENABLED:
        return None
    try:
        return await asyncio.to_thread(import_and_export, image_path, title, output_path)
    except (CanvaAuthError, CanvaAPIError) as exc:
        print(f"[canva_generator] {type(exc).__name__}: {exc}")
        return None
    except Exception as exc:
        print(f"[canva_generator] Unexpected error: {exc}")
        return None


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=== Canva Generator Test ===")

    if not CANVA_ENABLED:
        print("[SKIP] Canva not configured.")
        print("  Set CANVA_CLIENT_ID, CANVA_CLIENT_SECRET, CANVA_REFRESH_TOKEN in .env")
        sys.exit(0)

    print("[1/3] Testing access token refresh...")
    try:
        token = get_access_token()
        print(f"  Access token: {token[:20]}...")
    except CanvaAuthError as e:
        print(f"  Auth failed: {e}")
        sys.exit(1)

    print("[2/3] Creating sample infographic with PIL...")
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1080, 1080), "#1a1a2e")
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0, 0), (1080, 200)], fill="#16213e")
    draw.text((50, 80), "AI & Tech Daily News", fill="#e94560")
    y = 260
    for i, text in enumerate(["AI breakthroughs", "Market trends", "Policy updates"]):
        draw.rectangle([(40, y), (1040, y + 120)], fill="#0f3460", outline="#e94560")
        draw.text((70, y + 45), f"{i+1}. {text}", fill="white")
        y += 160
    test_png = OUTPUT_DIR / "canva_test_infographic.png"
    test_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(test_png)
    print(f"  Saved: {test_png}")

    print("[3/3] Import to Canva + Export PNG...")
    result = asyncio.run(
        async_import_and_export(test_png, "Test Infographic")
    )
    if result:
        print(f"  Design ID: {result['design_id']}")
        print(f"  Edit URL: {result['edit_url'][:80]}...")
        print(f"  PNG: {result['png_path']}")
    else:
        print("  Failed.")
