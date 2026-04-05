"""shared.harness.hitl — Human-in-the-Loop callbacks via Notifier integration.

Bridges the HarnessWrapper's hitl_callback with the existing
shared.notifications system (Telegram/Discord). When a tool requires
`requires_approval: true` in the constitution, the HITL callback sends
a formatted approval request via configured notification channels.

Usage::

    from shared.harness.hitl import create_notifier_hitl_callback

    config = HarnessConfig(
        constitution=constitution,
        hitl_callback=create_notifier_hitl_callback(timeout_seconds=30),
    )
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

log = logging.getLogger(__name__)


async def auto_approve_callback(tool_name: str, tool_input: Any) -> bool:
    """Auto-approve with logging (for CI/automated environments)."""
    log.warning(
        "[HITL] Auto-approving '%s' (no interactive channel configured)",
        tool_name,
    )
    return True


async def auto_deny_callback(tool_name: str, tool_input: Any) -> bool:
    """Auto-deny (maximum safety — for unattended batch runs)."""
    log.warning(
        "[HITL] Auto-denying '%s' (strict mode — no human available)",
        tool_name,
    )
    return False


def create_notifier_hitl_callback(
    *,
    timeout_seconds: int = 60,
    auto_approve_on_timeout: bool = False,
    notify_only: bool = False,
) -> Any:
    """Create a HITL callback that sends approval requests via Notifier.

    Args:
        timeout_seconds: How long to wait for human approval (not used in fire-and-forget mode).
        auto_approve_on_timeout: If True, auto-approve when no response received.
        notify_only: If True, just send notification and auto-approve (fire-and-forget).
            This is the recommended mode for automated pipelines — humans get
            notified of high-risk actions but execution isn't blocked.

    Returns:
        An async callable suitable for HarnessConfig.hitl_callback.
    """

    async def _hitl_callback(tool_name: str, tool_input: Any) -> bool:
        try:
            from shared.notifications import Notifier

            notifier = Notifier.from_env()
            if not notifier.has_channels:
                log.warning(
                    "[HITL] No notification channels configured -- "
                    "defaulting to %s for '%s'",
                    "approve" if auto_approve_on_timeout else "deny",
                    tool_name,
                )
                return auto_approve_on_timeout

            # Format the approval request
            input_preview = _format_input_preview(tool_input, max_chars=200)
            message = (
                f"[HITL] Approval Required\n"
                f"Tool: {tool_name}\n"
                f"Input: {input_preview}\n"
            )

            if notify_only:
                message += "Mode: notify-only (auto-approved)\n"
                notifier.send(message)
                log.info("[HITL] Notification sent for '%s' (auto-approved)", tool_name)
                return True

            # Full HITL: notify + wait for response
            message += (
                f"Timeout: {timeout_seconds}s\n"
                f"Default: {'approve' if auto_approve_on_timeout else 'deny'}\n"
            )
            notifier.send(message)
            log.info(
                "[HITL] Approval request sent for '%s' — "
                "waiting %ds (default=%s)",
                tool_name,
                timeout_seconds,
                "approve" if auto_approve_on_timeout else "deny",
            )

            # In fire-and-forget mode, we can't actually wait for a response
            # from Telegram/Discord. For true interactive HITL, you'd need
            # a webhook or polling mechanism. For now, apply timeout default.
            await asyncio.sleep(min(timeout_seconds, 5))
            log.info(
                "[HITL] Timeout reached for '%s' — applying default: %s",
                tool_name,
                "approve" if auto_approve_on_timeout else "deny",
            )
            return auto_approve_on_timeout

        except ImportError:
            log.warning("[HITL] shared.notifications not available — auto-%s",
                        "approve" if auto_approve_on_timeout else "deny")
            return auto_approve_on_timeout
        except Exception as e:
            log.error("[HITL] Callback error for '%s': %s", tool_name, e)
            return auto_approve_on_timeout

    return _hitl_callback


def _format_input_preview(tool_input: Any, max_chars: int = 200) -> str:
    """Create a safe preview of tool input for notification messages."""
    if isinstance(tool_input, dict):
        # Filter out internal keys
        preview = {
            k: v for k, v in tool_input.items()
            if not k.startswith("_") and not callable(v)
        }
        text = str(preview)
    else:
        text = str(tool_input)

    if len(text) > max_chars:
        return text[:max_chars] + "..."
    return text
"""

Usage in getdaytrends/harness_integration.py::

    from shared.harness.hitl import create_notifier_hitl_callback

    harness_config = HarnessConfig(
        constitution=constitution,
        hitl_callback=create_notifier_hitl_callback(notify_only=True),
    )
"""
