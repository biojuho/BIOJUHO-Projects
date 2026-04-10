from __future__ import annotations

import logging

from antigravity_mcp.integrations.skill_adapter import SkillAdapter
from antigravity_mcp.integrations.telegram_adapter import TelegramAdapter
from antigravity_mcp.pipelines.analyze import generate_briefs
from antigravity_mcp.pipelines.collect import collect_content_items, get_window
from antigravity_mcp.pipelines.publish import publish_report
from antigravity_mcp.state.events import error_response, ok, partial
from antigravity_mcp.state.store import PipelineStateStore

logger = logging.getLogger(__name__)


def _get_notifier():
    """Lazy-import shared Notifier (never raises)."""
    try:
        from shared.notifications import Notifier
        return Notifier.from_env()
    except Exception:
        return None


def _notify_error(message: str, exc: Exception | None = None, *, source: str = "DailyNews") -> None:
    """Fire-and-forget Notifier error alert (never raises)."""
    try:
        notifier = _get_notifier()
        if notifier and notifier.has_channels:
            notifier.send_error(message, error=exc, source=source)
    except Exception as e:
        logger.debug("Notifier error send failed (ignored): %s", e)


def _normalize_categories(categories: list[str] | None) -> list[str] | None:
    if not categories:
        return None

    normalized: list[str] = []
    seen: set[str] = set()
    for raw in categories:
        for category in (part.strip() for part in raw.split(",")):
            if not category or category in seen:
                continue
            seen.add(category)
            normalized.append(category)
    return normalized or None


async def _alert_on_error(stage: str, error_type: str, message: str, run_id: str = "") -> None:
    """Fire-and-forget Telegram error alert (never raises)."""
    try:
        tg = TelegramAdapter()
        if tg.is_configured:
            await tg.send_error_alert(
                pipeline_stage=stage,
                error_type=error_type,
                error_message=message,
                run_id=run_id,
            )
    except Exception as exc:
        logger.debug("Telegram alert skipped: %s", exc)


async def content_generate_brief_tool(
    categories: list[str] | None = None,
    window: str = "manual",
    max_items: int = 5,
) -> dict:
    store = PipelineStateStore()
    try:
        normalized_categories = _normalize_categories(categories)
        try:
            items, warnings = await collect_content_items(
                categories=normalized_categories,
                window_name=window,
                max_items=max_items,
                state_store=store,
            )
        except Exception as exc:
            await _alert_on_error("collect", type(exc).__name__, str(exc))
            _notify_error("수집(collect) 실패", exc, source="DailyNews")
            return error_response("collect_failed", f"Collection failed: {exc}")

        if not items:
            if warnings:
                return partial({"reports": [], "report_ids": []}, warnings=warnings)
            return ok({"reports": [], "report_ids": []})

        window_start, window_end = get_window(window)
        skill = SkillAdapter(state_store=store)
        try:
            run_id, reports, llm_warnings, status = await generate_briefs(
                items=items,
                window_name=window,
                window_start=window_start.isoformat(),
                window_end=window_end.isoformat(),
                state_store=store,
                skill_adapter=skill,
            )
        except Exception as exc:
            await _alert_on_error("analyze", type(exc).__name__, str(exc))
            _notify_error("분석(analyze) 실패", exc, source="DailyNews")
            return error_response("analyze_failed", f"Analysis failed: {exc}")

        payload = {
            "run_id": run_id,
            "report_ids": [report.report_id for report in reports],
            "reports": [report.to_dict() for report in reports],
        }
        all_warnings = warnings + llm_warnings
        if status == "partial" or all_warnings:
            return partial(payload, warnings=all_warnings, meta={"run_id": run_id})
        return ok(payload, meta={"run_id": run_id})
    finally:
        store.close()


async def content_publish_report_tool(
    report_id: str,
    channels: list[str] | None = None,
    approval_mode: str = "manual",
) -> dict:
    store = PipelineStateStore()
    try:
        try:
            run_id, publication, warnings, status = await publish_report(
                report_id=report_id,
                channels=channels or ["x", "canva"],
                approval_mode=approval_mode,
                state_store=store,
            )
        except Exception as exc:
            await _alert_on_error("publish", type(exc).__name__, str(exc), report_id)
            _notify_error(f"발행(publish) 실패 (report={report_id})", exc, source="DailyNews")
            return error_response("publish_failed", f"Publish failed: {exc}")

        if status == "error":
            await _alert_on_error("publish", "publish_error", warnings[0] if warnings else "Unknown", report_id)
            return error_response(
                "publish_failed",
                warnings[0] if warnings else "Publish failed.",
                data={"run_id": run_id},
            )
        if warnings:
            return partial(publication, warnings=warnings, meta={"run_id": run_id})
        return ok(publication, meta={"run_id": run_id})
    finally:
        store.close()


async def content_invoke_skill_tool(
    skill_name: str,
    params: dict | None = None,
) -> dict:
    """Invoke a named pipeline skill.

    Built-in skills: summarize_category, market_snapshot, proofread,
    brain_analysis, sentiment_classify.
    """
    adapter = SkillAdapter()
    result = await adapter.invoke(skill_name, params or {})
    if result.get("status") == "error":
        return error_response("skill_error", result.get("message", "Skill failed."), data=result)
    return ok(result)
