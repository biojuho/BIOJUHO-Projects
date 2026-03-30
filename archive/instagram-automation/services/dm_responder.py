"""DM and comment auto-responder.

Handles:
- Keyword-triggered auto DM from comments
- LLM-based DM conversation
- Webhook event parsing
"""

from __future__ import annotations

import hashlib
import hmac
import logging

from config import AppConfig
from models import DMTriggerRule, WebhookEvent

logger = logging.getLogger(__name__)


class DMResponder:
    """Processes webhook events and sends automated responses."""

    def __init__(self, config: AppConfig):
        self.config = config
        self._meta_api = None
        self._db = None
        self._content_gen = None
        self._business_context = ""

    def _get_meta_api(self):
        if self._meta_api is None:
            from services.meta_api import MetaGraphAPI

            self._meta_api = MetaGraphAPI(self.config.meta)
        return self._meta_api

    def _get_db(self):
        if self._db is None:
            from services.database import Database

            self._db = Database(self.config.db_path)
        return self._db

    def _get_content_gen(self):
        if self._content_gen is None:
            from services.content_generator import ContentGenerator

            self._content_gen = ContentGenerator(self.config.content)
        return self._content_gen

    def set_business_context(self, context: str) -> None:
        """Set business info for LLM-based DM responses."""
        self._business_context = context

    # ---- Webhook signature verification ----

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify Meta webhook X-Hub-Signature-256 header."""
        if not self.config.webhook.app_secret:
            logger.warning("No app_secret configured, skipping signature verification")
            return True

        expected = hmac.new(
            self.config.webhook.app_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(f"sha256={expected}", signature)

    # ---- Event parsing ----

    def parse_webhook_body(self, body: dict) -> list[WebhookEvent]:
        """Parse Meta webhook body into structured events."""
        events = []
        for entry in body.get("entry", []):
            # Comment/mention changes
            for change in entry.get("changes", []):
                field = change.get("field", "")
                value = change.get("value", {})

                if field == "comments":
                    events.append(
                        WebhookEvent(
                            event_type="comments",
                            sender_id=value.get("from", {}).get("id", ""),
                            text=value.get("text", ""),
                            media_id=value.get("media", {}).get("id"),
                            raw=value,
                        )
                    )
                elif field == "mentions":
                    events.append(
                        WebhookEvent(
                            event_type="mentions",
                            sender_id=value.get("from", {}).get("id", ""),
                            text=value.get("text", ""),
                            media_id=value.get("media_id"),
                            raw=value,
                        )
                    )

            # DM messages
            for msg in entry.get("messaging", []):
                if "message" in msg:
                    events.append(
                        WebhookEvent(
                            event_type="messages",
                            sender_id=msg.get("sender", {}).get("id", ""),
                            text=msg.get("message", {}).get("text", ""),
                            raw=msg,
                        )
                    )

        return events

    # ---- Event handlers ----

    async def handle_event(self, event: WebhookEvent) -> None:
        """Route event to the appropriate handler."""
        if event.event_type == "comments":
            await self._handle_comment(event)
        elif event.event_type == "messages":
            await self._handle_dm(event)
        elif event.event_type == "mentions":
            await self._handle_mention(event)
        else:
            logger.debug("Unhandled event type: %s", event.event_type)

    async def _handle_comment(self, event: WebhookEvent) -> None:
        """Check comment for trigger keywords and send DM."""
        db = self._get_db()
        rules = db.get_dm_rules()
        text_lower = event.text.lower()

        for rule in rules:
            if rule.keyword.lower() in text_lower:
                logger.info(
                    "Comment trigger matched: '%s' by user %s",
                    rule.keyword,
                    event.sender_id,
                )
                response = await self._build_response(rule, event.text)
                await self._send_dm(event.sender_id, response)
                db.log_dm(event.sender_id, event.text, response, rule.keyword)
                return

        logger.debug("No trigger matched for comment: %s", event.text[:50])

    async def _handle_dm(self, event: WebhookEvent) -> None:
        """Respond to incoming DM."""
        db = self._get_db()
        rules = db.get_dm_rules()
        text_lower = event.text.lower()

        # Check keyword rules first
        for rule in rules:
            if rule.keyword.lower() in text_lower:
                response = await self._build_response(rule, event.text)
                await self._send_dm(event.sender_id, response)
                db.log_dm(event.sender_id, event.text, response, rule.keyword)
                return

        # Fallback: LLM-based response
        gen = self._get_content_gen()
        response = await gen.generate_dm_response(event.text, self._business_context)
        await self._send_dm(event.sender_id, response)
        db.log_dm(event.sender_id, event.text, response, "llm_fallback")

    async def _handle_mention(self, event: WebhookEvent) -> None:
        """Log mentions for awareness (no auto-response by default)."""
        logger.info("Mentioned by %s: %s", event.sender_id, event.text[:100])

    async def _build_response(self, rule: DMTriggerRule, user_text: str) -> str:
        """Build response from rule template or LLM."""
        if rule.is_llm_response:
            gen = self._get_content_gen()
            return await gen.generate_dm_response(user_text, self._business_context)
        return rule.response_template

    async def _send_dm(self, recipient_id: str, message: str) -> None:
        """Send DM via Meta API."""
        api = self._get_meta_api()
        try:
            await api.send_dm(recipient_id, message)
            logger.info("DM sent to %s", recipient_id)
        except Exception as e:
            logger.error("Failed to send DM to %s: %s", recipient_id, e)

    # ---- Rule management ----

    def add_rule(
        self,
        keyword: str,
        response: str,
        *,
        use_llm: bool = False,
    ) -> None:
        """Add or update a DM trigger rule."""
        db = self._get_db()
        db.add_dm_rule(
            DMTriggerRule(
                keyword=keyword,
                response_template=response,
                is_llm_response=use_llm,
            )
        )
        logger.info("DM rule added: '%s'", keyword)
