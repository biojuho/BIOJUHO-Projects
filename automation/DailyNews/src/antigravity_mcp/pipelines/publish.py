from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from antigravity_mcp.config import get_settings
from antigravity_mcp.domain.models import ContentReport
from antigravity_mcp.integrations.canva_adapter import CanvaAdapter
from antigravity_mcp.integrations.newsletter_adapter import NewsletterAdapter
from antigravity_mcp.integrations.notion_adapter import NotionAdapter, NotionAdapterError
from antigravity_mcp.integrations.subscriber_store import SubscriberStore
from antigravity_mcp.integrations.telegram_adapter import TelegramAdapter
from antigravity_mcp.integrations.x_adapter import XAdapter
from antigravity_mcp.state.events import generate_run_id, utc_now_iso
from antigravity_mcp.state.store import PipelineStateStore

logger = logging.getLogger(__name__)


def _notion_report_title(report: ContentReport, *, publish_date: str) -> str:
    window_label = str(report.window_name or "manual").replace("_", " ").title()
    return f"{report.category} {window_label} Brief {publish_date}"


def _notion_duplicate_filter(report: ContentReport, *, publish_date: str) -> dict[str, list[dict[str, dict[str, str]]]]:
    return {
        "and": [
            {"property": "Date", "date": {"equals": publish_date}},
            {"property": "Name", "title": {"equals": _notion_report_title(report, publish_date=publish_date)}},
        ]
    }


def _notion_report_properties(report: ContentReport, *, publish_date: str) -> dict:
    return {
        "Name": {"title": [{"type": "text", "text": {"content": _notion_report_title(report, publish_date=publish_date)}}]},
        "Date": {"date": {"start": publish_date}},
        "Type": {"select": {"name": "News"}},
    }


def _styled_brief_markdown(report: ContentReport) -> str:
    brief_body = str((report.analysis_meta or {}).get("brief_body", "") or "").strip()
    if not brief_body:
        return ""

    x_draft = next((draft.content for draft in report.channel_drafts if draft.channel == "x"), "")
    lines = [
        f"# {report.category} {report.window_name.title()} Brief",
        brief_body,
    ]
    if x_draft:
        lines.extend(
            [
                "## X Draft",
                x_draft,
            ]
        )
    lines.extend(
        [
            "## Approval",
            f"- Approval mode: {report.approval_state}",
            f"- Quality state: {report.quality_state}",
        ]
    )
    return "\n".join(lines)


def _analysis_meta_markdown(report: ContentReport) -> str:
    meta = report.analysis_meta or {}
    parser = meta.get("parser", {})
    quality_review = meta.get("quality_review", {})
    fact_check = meta.get("fact_check", {})
    insight_generator = meta.get("insight_generator", {})
    draft_overrides = meta.get("draft_overrides", {})

    lines = ["## Analysis Meta"]
    if parser:
        lines.append(f"- Parser fallback used: {'yes' if parser.get('used_fallback') else 'no'}")
        missing_sections = parser.get("missing_sections") or []
        if missing_sections:
            lines.append(f"- Missing sections: {', '.join(str(item) for item in missing_sections)}")
        evidence = parser.get("evidence", {})
        if evidence:
            lines.append(
                "- Evidence tags: "
                f"{evidence.get('tagged_line_count', 0)}/{evidence.get('line_count', 0)} analytic lines tagged"
            )
            if evidence.get("article_refs"):
                lines.append(
                    "- Direct article refs: " + ", ".join(str(item) for item in evidence.get("article_refs", []))
                )
    if draft_overrides:
        lines.append(
            "- Draft overrides: "
            + ", ".join(f"{channel}={source}" for channel, source in sorted(draft_overrides.items()))
        )
    if insight_generator:
        summary = insight_generator.get("validation_summary", {})
        if summary:
            lines.append(
                "- Insight validation: "
                f"passed={summary.get('passed', 0)} / failed={summary.get('failed', 0)} / total={summary.get('total_insights', 0)}"
            )
        if insight_generator.get("error"):
            lines.append(f"- Insight generator error: {insight_generator['error']}")
    if fact_check:
        lines.append(
            "- Fact check: "
            f"passed={'yes' if fact_check.get('passed', False) else 'no'}, "
            f"score={fact_check.get('fact_check_score', report.fact_check_score):.2f}"
        )
    warnings = quality_review.get("warnings", [])
    if warnings:
        lines.append("- Quality warnings:")
        lines.extend(f"  - {warning}" for warning in warnings[:5])
    return "\n".join(lines)


def _report_markdown(report: ContentReport) -> str:
    if report.generation_mode == "v1-brief":
        styled = _styled_brief_markdown(report)
        if styled:
            return styled

    summary_lines = "\n".join(f"- {line}" for line in report.summary_lines)
    insight_lines = "\n".join(f"- {line}" for line in report.insights)
    draft_lines = "\n\n".join(
        f"## {draft.channel.upper()}\n"
        f"- Source: {draft.source}\n"
        f"- Fallback: {'yes' if draft.is_fallback else 'no'}\n\n"
        f"{draft.content}"
        for draft in report.channel_drafts
    )
    return (
        f"# {report.category} {report.window_name.title()} Brief\n"
        "## Generation\n"
        f"- Generation mode: {report.generation_mode or 'unknown'}\n"
        f"- Quality state: {report.quality_state}\n"
        "## Summary\n"
        f"{summary_lines}\n"
        "## Insights\n"
        f"{insight_lines}\n"
        "## Drafts\n"
        f"{draft_lines}\n"
        f"{_analysis_meta_markdown(report)}\n"
        "## Approval\n"
        f"- Approval mode: {report.approval_state}\n"
        f"- Asset status: {report.asset_status}"
    )


def _build_telegram_message(report: ContentReport, publication: dict[str, str]) -> str:
    notion_url = publication.get("notion_url", "")
    summary = report.summary_lines[0] if report.summary_lines else "No summary."
    link_part = f'\n<a href="{notion_url}">Notion에서 보기</a>' if notion_url else ""
    return f"<b>[{report.category}] {report.window_name.title()} Brief 발행됨</b>\n" f"{summary}{link_part}"


def _has_notion_page_id(report: ContentReport) -> bool:
    return report.has_notion_sync()


def _resolve_approval_mode(report: ContentReport, settings, approval_mode: str, warnings: list[str]) -> str:
    """설정/품질 상태에 따라 approval_mode 확정."""
    if settings.content_approval_mode == "manual" and approval_mode != "manual":
        warnings.append("Automatic publishing is disabled. Falling back to manual approval.")
        return "manual"
    if approval_mode == "auto":
        fallback_x = any(d.channel == "x" and d.is_fallback for d in report.channel_drafts)
        if report.quality_state != "ok" or fallback_x:
            warnings.append(
                "Auto publishing downgraded to manual because the report quality state is not ok "
                "or the X draft is a fallback draft."
            )
            return "manual"
    return approval_mode


async def _publish_to_notion(
    report: ContentReport,
    notion_adapter: NotionAdapter,
    settings,
    publication: dict[str, str],
    warnings: list[str],
) -> None:
    """Notion 발행 (중복 방지 포함). 결과를 publication/report에 인플레이스로 기록."""
    if not (notion_adapter.is_configured() and settings.notion_reports_database_id):
        warnings.append("Notion reports database is not configured; report saved only to local state.")
        return

    today_iso = datetime.now().date().isoformat()
    notion_title = _notion_report_title(report, publish_date=today_iso)
    properties = _notion_report_properties(report, publish_date=today_iso)

    try:
        existing_pages, _ = await notion_adapter.query_database(
            database_id=settings.notion_reports_database_id,
            filter_payload=_notion_duplicate_filter(report, publish_date=today_iso),
            limit=1,
        )
    except NotionAdapterError as exc:
        publication["notion_status"] = "duplicate_check_failed"
        warnings.append(
            "Notion duplicate check failed; skipped creation to avoid duplicate publish: "
            f"{exc}"
        )
        return

    if existing_pages:
        report.notion_page_id = existing_pages[0].get("id", "")
        publication["notion_page_id"] = report.notion_page_id
        publication["notion_url"] = existing_pages[0].get("url", "")
        publication["notion_status"] = "existing"
        warnings.append(f"Notion record already exists for {notion_title}; skipped duplicate creation.")
        return

    try:
        created = await notion_adapter.create_record(
            database_id=settings.notion_reports_database_id,
            properties=properties,
            markdown=_report_markdown(report),
        )
        report.notion_page_id = created.get("id", "")
        publication["notion_page_id"] = report.notion_page_id
        publication["notion_url"] = created.get("url", "")
        publication["notion_status"] = "created"
    except NotionAdapterError as exc:
        publication["notion_status"] = "create_failed"
        warnings.append(str(exc))


def _write_notion_backup(*, report_id: str, backup_dir: Path, snapshot: dict) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"{report_id}.before-notion-resync-{timestamp}.json"
    backup_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return backup_path


async def resync_report_publication(
    *,
    report_id: str,
    state_store: PipelineStateStore,
    notion_adapter: NotionAdapter | None = None,
    run_id: str | None = None,
) -> tuple[str, dict[str, str], list[str], str]:
    settings = get_settings()
    notion_adapter = notion_adapter or NotionAdapter(settings=settings)
    run_id = run_id or generate_run_id("resync_report")
    state_store.record_job_start(run_id, "resync_report", summary={"report_id": report_id})

    report = state_store.get_report(report_id)
    if report is None:
        state_store.record_job_finish(run_id, status="failed", error_text=f"Unknown report_id: {report_id}")
        return run_id, {}, [f"Unknown report_id: {report_id}"], "error"

    warnings: list[str] = []
    payload: dict[str, str] = {"report_id": report_id}
    manual_meta = dict((report.analysis_meta or {}).get("manual_update", {}))

    if not report.notion_page_id:
        warnings.append("Report has no notion_page_id; skipping Notion overwrite.")
        payload["notion_status"] = "missing_page_id"
    elif not notion_adapter.is_configured():
        warnings.append("Notion is not configured; skipping page overwrite.")
        payload["notion_status"] = "not_configured"
    else:
        publish_date = datetime.now().date().isoformat()
        try:
            snapshot = await notion_adapter.get_page(page_id=report.notion_page_id, include_blocks=True, max_depth=1)
            backup_path = _write_notion_backup(
                report_id=report.report_id,
                backup_dir=settings.data_dir / "notion_backups",
                snapshot=snapshot,
            )
            await notion_adapter.update_page(
                page_id=report.notion_page_id,
                properties=_notion_report_properties(report, publish_date=publish_date),
            )
            replaced_blocks = await notion_adapter.replace_page_markdown(
                page_id=report.notion_page_id,
                markdown=_report_markdown(report),
            )
            payload["notion_status"] = "overwritten"
            payload["notion_page_id"] = report.notion_page_id
            payload["notion_backup_path"] = str(backup_path)
            payload["notion_blocks_replaced"] = str(replaced_blocks)
            manual_meta["notion_backup_path"] = str(backup_path)
            manual_meta["notion_resynced_at"] = utc_now_iso()
        except NotionAdapterError as exc:
            payload["notion_status"] = "overwrite_failed"
            warnings.append(str(exc))

    refreshed_channels = 0
    for draft in report.channel_drafts:
        _safe_db_write(
            state_store.set_channel_publication,
            report_id,
            draft.channel,
            draft.status or "draft",
            draft.external_url,
            warnings=warnings,
            label=f"set_channel_publication[{draft.channel}]",
        )
        refreshed_channels += 1

    payload["channel_refresh_count"] = str(refreshed_channels)
    if refreshed_channels:
        manual_meta["channel_metadata_refreshed_at"] = utc_now_iso()

    if manual_meta:
        report.analysis_meta = dict(report.analysis_meta or {})
        report.analysis_meta["manual_update"] = manual_meta
    report.status = "published" if _has_notion_page_id(report) else report.status
    payload["report_status"] = report.status
    payload["report_delivery_state"] = report.delivery_state

    _safe_db_write(state_store.save_report, report, warnings=warnings, label="save_report")
    _safe_db_write(
        state_store.record_job_finish,
        run_id,
        warnings=warnings,
        label="record_job_finish",
        **{
            "status": "partial" if warnings else "success",
            "summary": payload,
            "processed_count": 1,
            "published_count": 1 if _has_notion_page_id(report) else 0,
        },
    )
    return run_id, payload, warnings, "partial" if warnings else "ok"


def _safe_db_write(fn, *args, warnings: list[str], label: str = "DB write", **kwargs) -> None:
    """DB 쓰기를 안전하게 수행 — 잠금/오류 시 경고 기록 후 계속 진행."""
    try:
        fn(*args, **kwargs)
    except Exception as exc:
        msg = f"{label} failed: {type(exc).__name__}: {exc}"
        logger.error(msg)
        warnings.append(msg)


async def _publish_x_draft(
    draft,
    report: ContentReport,
    report_id: str,
    x_adapter: XAdapter,
    state_store: PipelineStateStore,
    approval_mode: str,
    publication: dict[str, str],
    warnings: list[str],
) -> None:
    """X 채널 발행: 길이에 따라 단일 트윗 또는 스레드 자동 분기."""
    if len(draft.content) > 280 and approval_mode == "auto":
        thread_tweets = XAdapter.split_to_thread(draft.content)
        thread_results = await x_adapter.post_thread(thread_tweets)
        published_ids = [r["tweet_id"] for r in thread_results if r.get("status") == "published"]
        failed_results = [r for r in thread_results if r.get("status") not in {"published"}]
        if published_ids and failed_results:
            x_status = "partial_thread"
            publication["x_thread_ids"] = ",".join(published_ids)
            publication["x_url"] = f"https://twitter.com/i/web/status/{published_ids[0]}"
            publication["x_published_count"] = str(len(published_ids))
            first_failure = failed_results[0]
            if first_failure.get("tweet_index"):
                publication["x_failed_index"] = first_failure["tweet_index"]
            publication["x_failed_status"] = first_failure.get("status", "error")
            for tid in published_ids:
                _safe_db_write(
                    state_store.record_published_tweet_id, report_id, tid, draft.content[:200],
                    warnings=warnings, label="record_published_tweet_id",
                )
            failure_msg = f"X thread partially published: {len(published_ids)}/{len(thread_tweets)} tweets posted"
            if first_failure.get("tweet_index"):
                failure_msg += f" before failure at item {first_failure['tweet_index']}"
            warnings.append(failure_msg + ".")
            if first_failure.get("message"):
                warnings.append(first_failure["message"])
        elif published_ids:
            x_status = "published"
            publication["x_thread_ids"] = ",".join(published_ids)
            publication["x_url"] = f"https://twitter.com/i/web/status/{published_ids[0]}"
            publication["x_published_count"] = str(len(published_ids))
            for tid in published_ids:
                _safe_db_write(
                    state_store.record_published_tweet_id, report_id, tid, draft.content[:200],
                    warnings=warnings, label="record_published_tweet_id",
                )
        else:
            x_status = thread_results[0].get("status", "error") if thread_results else "error"
            if thread_results and thread_results[0].get("message"):
                warnings.append(thread_results[0]["message"])
        _safe_db_write(
            state_store.set_channel_publication, report_id, draft.channel, x_status, publication.get("x_url", ""),
            warnings=warnings, label="set_channel_publication",
        )
        publication[f"{draft.channel}_status"] = x_status
    else:
        x_result = await x_adapter.publish(report, draft.content, approval_mode=approval_mode)
        _safe_db_write(
            state_store.set_channel_publication, report_id, draft.channel, x_result["status"], x_result.get("tweet_url", ""),
            warnings=warnings, label="set_channel_publication",
        )
        publication[f"{draft.channel}_status"] = x_result["status"]
        if x_result.get("tweet_url"):
            publication["x_url"] = x_result["tweet_url"]
            tweet_url = x_result["tweet_url"]
            if "/status/" in tweet_url:
                tid = tweet_url.rsplit("/status/", 1)[-1].split("?")[0]
                _safe_db_write(
                    state_store.record_published_tweet_id, report_id, tid, draft.content[:200],
                    warnings=warnings, label="record_published_tweet_id",
                )
        if x_result.get("message"):
            warnings.append(x_result["message"])


async def _publish_newsletter(
    report: ContentReport,
    newsletter_adapter: NewsletterAdapter | None,
    subscriber_store: SubscriberStore | None,
    publication: dict[str, str],
    warnings: list[str],
) -> None:
    """Deliver report as newsletter to matching subscribers (v2.0 channel)."""
    if newsletter_adapter is None:
        try:
            subscriber_store = subscriber_store or SubscriberStore()
            newsletter_adapter = NewsletterAdapter(subscriber_store=subscriber_store)
        except Exception as exc:
            warnings.append(f"Newsletter adapter init failed: {exc}")
            return

    if not newsletter_adapter.is_configured:
        warnings.append("Newsletter not configured (RESEND_API_KEY missing); skipping email delivery.")
        return

    if subscriber_store is None:
        try:
            subscriber_store = SubscriberStore()
        except Exception as exc:
            warnings.append(f"Subscriber store init failed: {exc}")
            return

    try:
        subscribers = subscriber_store.get_active_subscribers(
            categories=[report.category],
        )
        if not subscribers:
            warnings.append(f"No active subscribers for category '{report.category}'.")
            publication["newsletter_status"] = "no_subscribers"
            return

        result = await newsletter_adapter.send_daily_brief(
            reports=[report],
            subscribers=subscribers,
            edition=report.window_name,
        )
        publication["newsletter_sent"] = str(result.get("sent", 0))
        publication["newsletter_failed"] = str(result.get("failed", 0))
        publication["newsletter_status"] = "delivered" if result.get("sent", 0) > 0 else "failed"

    except Exception as exc:
        logger.warning("Newsletter delivery failed: %s", exc)
        warnings.append(f"Newsletter delivery error: {exc}")
        publication["newsletter_status"] = "error"


async def publish_report(
    *,
    report_id: str,
    channels: list[str],
    approval_mode: str,
    state_store: PipelineStateStore,
    notion_adapter: NotionAdapter | None = None,
    x_adapter: XAdapter | None = None,
    canva_adapter: CanvaAdapter | None = None,
    telegram_adapter: TelegramAdapter | None = None,
    newsletter_adapter: NewsletterAdapter | None = None,
    subscriber_store: SubscriberStore | None = None,
    run_id: str | None = None,
) -> tuple[str, dict[str, str], list[str], str]:
    settings = get_settings()
    notion_adapter = notion_adapter or NotionAdapter(settings=settings)
    x_adapter = x_adapter or XAdapter(state_store=state_store)
    canva_adapter = canva_adapter or CanvaAdapter()
    telegram_adapter = telegram_adapter or TelegramAdapter()
    run_id = run_id or generate_run_id("publish_report")
    state_store.record_job_start(
        run_id, "publish_report",
        summary={"report_id": report_id, "channels": channels, "approval_mode": approval_mode},
    )

    report = state_store.get_report(report_id)
    if report is None:
        state_store.record_job_finish(run_id, status="failed", error_text=f"Unknown report_id: {report_id}")
        return run_id, {}, [f"Unknown report_id: {report_id}"], "error"

    warnings: list[str] = []
    publication: dict[str, str] = {"report_id": report_id}

    approval_mode = _resolve_approval_mode(report, settings, approval_mode, warnings)

    if report.quality_state == "blocked":
        warnings.append(
            "Publishing blocked: report was generated by fallback template due to total LLM failure. "
            "Manual review required."
        )
        state_store.record_job_finish(run_id, status="blocked", summary={"report_id": report_id, "reason": "quality_blocked"})
        return run_id, {"report_id": report_id, "blocked": True}, warnings, "error"

    await _publish_to_notion(report, notion_adapter, settings, publication, warnings)

    canva_result = canva_adapter.create_draft(report)
    publication["canva_status"] = canva_result.get("status", "disabled")
    if canva_result.get("edit_url"):
        publication["canva_edit_url"] = canva_result["edit_url"]

    for draft in report.channel_drafts:
        if draft.channel not in channels:
            continue
        if draft.channel == "x":
            try:
                await _publish_x_draft(draft, report, report_id, x_adapter, state_store, approval_mode, publication, warnings)
            except Exception as exc:
                # X 발행 크래시가 전체 publish_report를 죽이지 않도록 방어
                logger.error("X draft publish crashed: %s: %s", type(exc).__name__, exc)
                warnings.append(f"X publish crashed: {type(exc).__name__}: {exc}")
                publication[f"{draft.channel}_status"] = "error"
        else:
            _safe_db_write(
                state_store.set_channel_publication, report_id, draft.channel, "draft",
                warnings=warnings, label="set_channel_publication",
            )
            publication[f"{draft.channel}_status"] = "draft"

    # ── Newsletter channel (v2.0) ──────────────────────────────────────
    if "newsletter" in channels:
        await _publish_newsletter(
            report=report,
            newsletter_adapter=newsletter_adapter,
            subscriber_store=subscriber_store,
            publication=publication,
            warnings=warnings,
        )

    try:
        await telegram_adapter.send_message(_build_telegram_message(report, publication))
    except Exception as exc:
        logger.warning("Telegram notification failed: %s", exc)

    report.status = "published" if _has_notion_page_id(report) else "draft"
    publication["report_status"] = report.status
    publication["report_delivery_state"] = report.delivery_state
    report.approval_state = approval_mode
    _safe_db_write(state_store.save_report, report, warnings=warnings, label="save_report")
    _safe_db_write(
        state_store.record_job_finish,
        run_id,
        warnings=warnings, label="record_job_finish",
        **{  # keyword args for record_job_finish
            "status": "partial" if warnings else "success",
            "summary": publication,
            "processed_count": 1,
            "published_count": 1 if _has_notion_page_id(report) else 0,
        },
    )
    return run_id, publication, warnings, "partial" if warnings else "ok"
