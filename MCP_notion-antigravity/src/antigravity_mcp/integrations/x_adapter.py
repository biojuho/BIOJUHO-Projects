from __future__ import annotations

from antigravity_mcp.domain.models import ContentReport


class XAdapter:
    def publish(self, report: ContentReport, content: str, *, approval_mode: str) -> dict[str, str]:
        if approval_mode != "manual":
            return {
                "status": "blocked",
                "message": "Automatic publishing is disabled in this release.",
            }
        return {
            "status": "draft",
            "message": "Draft prepared. Manual approval required before publishing.",
        }
