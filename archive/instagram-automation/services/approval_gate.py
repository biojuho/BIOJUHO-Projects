"""Human-in-the-Loop approval gate via Telegram.

Sends post previews to a Telegram chat for approval before publishing.
Auto-approves after timeout if no response.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_APPROVED = "auto_approved"


@dataclass
class ApprovalRequest:
    """A pending approval request."""

    post_id: str
    caption_preview: str
    topic: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: float = field(default_factory=time.time)
    telegram_message_id: int = 0


class ApprovalGate:
    """Telegram-based approval gate for content publishing.

    Flow:
    1. send_for_approval(post) → sends preview to Telegram
    2. User replies ✅ or ❌
    3. check_approval() returns status
    4. auto-approve after timeout (default 4 hours)
    """

    DEFAULT_TIMEOUT = 4 * 60 * 60  # 4 hours

    def __init__(
        self,
        bot_token: str = "",
        chat_id: str = "",
        auto_approve_timeout: int = DEFAULT_TIMEOUT,
    ):
        self.bot_token = bot_token or TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or TELEGRAM_CHAT_ID
        self.auto_approve_timeout = auto_approve_timeout
        self._pending: dict[str, ApprovalRequest] = {}

    @property
    def is_configured(self) -> bool:
        """Check if Telegram credentials are set."""
        return bool(self.bot_token and self.chat_id)

    async def send_for_approval(
        self,
        post_id: str,
        caption: str,
        topic: str,
        hashtags: str = "",
    ) -> ApprovalRequest:
        """Send a post preview to Telegram for approval."""
        preview = (
            f"📝 *새 포스트 승인 요청*\n\n"
            f"📌 주제: {topic}\n\n"
            f"💬 캡션:\n{caption[:500]}\n\n"
            f"# {hashtags[:200]}\n\n"
            f"👉 승인: /approve_{post_id}\n"
            f"❌ 거절: /reject_{post_id}\n\n"
            f"⏰ 4시간 내 무응답 시 자동 승인"
        )

        req = ApprovalRequest(
            post_id=post_id,
            caption_preview=caption[:200],
            topic=topic,
        )

        if self.is_configured:
            msg_id = await self._send_telegram(preview)
            req.telegram_message_id = msg_id

        self._pending[post_id] = req
        logger.info("Approval request sent for post %s", post_id)
        return req

    async def _send_telegram(self, text: str) -> int:
        """Send a message to Telegram. Returns message ID."""
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                })
                data = resp.json()
                if data.get("ok"):
                    return data["result"]["message_id"]
                logger.warning("Telegram send failed: %s", data)
                return 0
        except Exception as e:
            logger.error("Telegram error: %s", e)
            return 0

    def approve(self, post_id: str) -> bool:
        """Manually approve a post."""
        if post_id in self._pending:
            self._pending[post_id].status = ApprovalStatus.APPROVED
            logger.info("Post %s APPROVED", post_id)
            return True
        return False

    def reject(self, post_id: str) -> bool:
        """Manually reject a post."""
        if post_id in self._pending:
            self._pending[post_id].status = ApprovalStatus.REJECTED
            logger.info("Post %s REJECTED", post_id)
            return True
        return False

    def check_approval(self, post_id: str) -> ApprovalStatus:
        """Check approval status, auto-approving if timed out."""
        req = self._pending.get(post_id)
        if not req:
            return ApprovalStatus.APPROVED  # Unknown = allow

        # Auto-approve after timeout
        if req.status == ApprovalStatus.PENDING:
            elapsed = time.time() - req.created_at
            if elapsed >= self.auto_approve_timeout:
                req.status = ApprovalStatus.AUTO_APPROVED
                logger.info(
                    "Post %s AUTO-APPROVED (%.0f min elapsed)",
                    post_id,
                    elapsed / 60,
                )

        return req.status

    def get_pending(self) -> list[ApprovalRequest]:
        """Get all pending approval requests."""
        self._check_auto_approvals()
        return [
            r for r in self._pending.values()
            if r.status == ApprovalStatus.PENDING
        ]

    def _check_auto_approvals(self) -> None:
        """Check and auto-approve timed-out requests."""
        for post_id in list(self._pending.keys()):
            self.check_approval(post_id)

    def get_stats(self) -> dict:
        """Get approval statistics."""
        statuses = [r.status for r in self._pending.values()]
        return {
            "total": len(statuses),
            "pending": statuses.count(ApprovalStatus.PENDING),
            "approved": statuses.count(ApprovalStatus.APPROVED),
            "auto_approved": statuses.count(ApprovalStatus.AUTO_APPROVED),
            "rejected": statuses.count(ApprovalStatus.REJECTED),
        }
