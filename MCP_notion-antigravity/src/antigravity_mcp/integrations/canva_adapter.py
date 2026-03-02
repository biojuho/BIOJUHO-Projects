from __future__ import annotations

from antigravity_mcp.config import get_settings
from antigravity_mcp.domain.models import ContentReport


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
