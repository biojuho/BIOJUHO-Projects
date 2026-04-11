from __future__ import annotations

import argparse
import copy
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
WORKSPACE_ROOT = PROJECT_ROOT.parent.parent
for path in (WORKSPACE_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from antigravity_mcp.domain.models import ContentItem, ContentReport, GeneratedPayload
from antigravity_mcp.integrations.llm.draft_generators import DraftGenerator
from antigravity_mcp.integrations.llm.response_parser import ResponseParser, is_meta_response
from antigravity_mcp.pipelines.qa_steps import _check_category_contract_for_content
from antigravity_mcp.state.events import utc_now_iso
from antigravity_mcp.state.store import PipelineStateStore

DB_PATH = PROJECT_ROOT / "data" / "pipeline_state.db"
BACKUP_DIR = PROJECT_ROOT / "data" / "repair_backups"
MAX_PARTIAL_DISTANCE_SECONDS = 900
BROKEN_PHRASES = (
    "critical quality issue",
    "lack of source citations",
    "이전 대화 기록이 없어서",
    "이전 리포트에 대한 기록이 없습니다",
    "기존 리포트를 공유해주신다면",
)


@dataclass(slots=True)
class CandidateMatch:
    prompt_hash: str
    created_at: str
    model_name: str
    payload: GeneratedPayload
    warnings: list[str]
    violations: list[str]
    citation_count: int
    distance_seconds: float
    repair_mode: str


def _allows_partial_violation_tradeoff(
    current_violations: list[str],
    candidate_violations: list[str],
) -> bool:
    """Allow a near-time content restore when broken fallback text only hid one extra contract issue."""
    if len(current_violations) != 1 or len(candidate_violations) != 2:
        return False
    return any("source citations" in violation for violation in current_violations) and any(
        "source citations" in violation for violation in candidate_violations
    )


def _parse_iso(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _summary_text(report: ContentReport) -> str:
    return "\n".join(report.summary_lines + report.insights)


def _is_suspicious_report(report: ContentReport) -> bool:
    text = _summary_text(report).lower()
    if any(phrase in text for phrase in BROKEN_PHRASES):
        return True
    parser = (report.analysis_meta or {}).get("parser", {})
    auto_heal = (report.analysis_meta or {}).get("auto_heal", {})
    return (
        parser.get("reason") == "v1_parse_failure"
        and auto_heal.get("applied") is True
        and report.quality_state in {"fallback", "needs_review"}
    )


def _contains_broken_phrase(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in BROKEN_PHRASES)


def _is_contentful_candidate(payload: GeneratedPayload) -> bool:
    combined = "\n".join(payload.summary_lines + payload.insights).strip()
    brief_body = str(payload.parse_meta.get("brief_body", "") or "").strip()
    if not combined:
        return False
    if _contains_broken_phrase(combined) or _contains_broken_phrase(brief_body):
        return False
    if any(
        marker in (combined + "\n" + brief_body).lower()
        for marker in (
            "category contract",
            "source citation",
            "출처 인용",
            "수정 제안",
            "기존 리포트",
            "공유해주",
            "action required",
            "문제점",
        )
    ):
        return False
    return len(combined) >= 120 or len(brief_body) >= 240


def _build_items(report: ContentReport, conn: sqlite3.Connection) -> list[ContentItem]:
    source_map: dict[str, str] = {}
    for link in report.source_links:
        row = conn.execute(
            """
            SELECT source
            FROM article_cache
            WHERE link = ? AND category = ? AND window_name = ?
            ORDER BY first_seen_at DESC
            LIMIT 1
            """,
            (link, report.category, report.window_name),
        ).fetchone()
        source_map[link] = (row["source"] if row else "") or "Unknown"

    full_items = copy.deepcopy(report.analysis_meta.get("insight_generator", {}).get("full_items", []))
    items: list[ContentItem] = []
    for index, item in enumerate(full_items):
        link = report.source_links[index] if index < len(report.source_links) else ""
        title = str(item.get("title", "")).strip() or f"Item {index + 1}"
        body = str(item.get("content", "")).strip()
        items.append(
            ContentItem(
                source_name=source_map.get(link, "Unknown"),
                category=report.category,
                title=title,
                link=link,
                summary=body,
                full_text=body,
            )
        )

    if items:
        return items

    for index, link in enumerate(report.source_links[:3]):
        items.append(
            ContentItem(
                source_name=source_map.get(link, "Unknown"),
                category=report.category,
                title=f"Story {index + 1}",
                link=link,
                summary="",
                full_text="",
            )
        )
    return items


def _candidate_rows(
    conn: sqlite3.Connection,
    *,
    report: ContentReport,
    lookback_minutes: int,
    max_candidates: int,
) -> list[sqlite3.Row]:
    report_time = _parse_iso(report.created_at)
    start = (report_time - timedelta(minutes=lookback_minutes)).isoformat()
    end = (report_time + timedelta(minutes=1)).isoformat()
    rows = conn.execute(
        """
        SELECT prompt_hash, response_text, model_name, created_at
        FROM llm_cache
        WHERE created_at >= ? AND created_at <= ?
        ORDER BY created_at DESC
        """,
        (start, end),
    ).fetchall()
    sorted_rows = sorted(
        rows,
        key=lambda row: abs((_parse_iso(row["created_at"]) - report_time).total_seconds()),
    )
    return sorted_rows[:max_candidates]


def _count_citations(payload: GeneratedPayload) -> int:
    combined = "\n".join(payload.summary_lines + payload.insights)
    return combined.count("[A") + combined.count("[Inference:")


def _matches_category(category: str, text: str) -> bool:
    normalized = text.casefold()
    category_variants = {
        category.casefold(),
        category.replace("_", " ").casefold(),
        category.replace("_", "").casefold(),
    }
    return any(variant and variant in normalized for variant in category_variants)


def _find_best_candidate(
    *,
    report: ContentReport,
    items: list[ContentItem],
    rows: Iterable[sqlite3.Row],
) -> CandidateMatch | None:
    parser = ResponseParser(DraftGenerator())
    current_violations = _check_category_contract_for_content(report.category, report.summary_lines, report.insights)
    report_time = _parse_iso(report.created_at)
    current_is_suspicious = _is_suspicious_report(report)

    best: CandidateMatch | None = None
    best_score: tuple[int, int, int, int, float] | None = None

    for row in rows:
        raw_text = row["response_text"]
        if not _matches_category(report.category, raw_text):
            continue
        payload, warnings = parser.parse_response(
            category=report.category,
            text=raw_text,
            items=items,
            window_name=report.window_name,
            generation_mode=report.generation_mode,
        )
        if payload.parse_meta.get("used_fallback"):
            continue
        if not payload.summary_lines or not payload.insights:
            continue
        if is_meta_response("\n".join(payload.summary_lines + payload.insights), check_line_count=False):
            continue
        if not _is_contentful_candidate(payload):
            continue

        violations = _check_category_contract_for_content(report.category, payload.summary_lines, payload.insights)
        citation_count = _count_citations(payload)
        distance_seconds = abs((_parse_iso(row["created_at"]) - report_time).total_seconds())
        if len(violations) < len(current_violations):
            repair_mode = "strict"
        elif (
            current_is_suspicious
            and distance_seconds <= MAX_PARTIAL_DISTANCE_SECONDS
            and (
                len(violations) == len(current_violations)
                or _allows_partial_violation_tradeoff(current_violations, violations)
            )
        ):
            repair_mode = "partial"
        else:
            continue

        score = (
            1 if repair_mode == "strict" else 0,
            -len(violations),
            citation_count,
            len(payload.summary_lines) + len(payload.insights),
            -distance_seconds,
        )
        if best is None or score > best_score:
            best = CandidateMatch(
                prompt_hash=row["prompt_hash"],
                created_at=row["created_at"],
                model_name=row["model_name"] or "",
                payload=payload,
                warnings=list(warnings),
                violations=violations,
                citation_count=citation_count,
                distance_seconds=distance_seconds,
                repair_mode=repair_mode,
            )
            best_score = score

    return best


def _repair_report(
    *,
    store: PipelineStateStore,
    report: ContentReport,
    candidate: CandidateMatch,
) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"{report.report_id}.before-cache-repair.json"
    backup_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    payload = candidate.payload
    parser_meta = copy.deepcopy(payload.parse_meta)
    previous_parser_meta = copy.deepcopy(report.analysis_meta.get("parser", {}))
    previous_provider = str(previous_parser_meta.get("provider", "") or "").strip()
    previous_model = str(previous_parser_meta.get("model_name", "") or "").strip()
    parser_meta["model_name"] = candidate.model_name or parser_meta.get("model_name", "")
    parser_meta["provider"] = "sqlite-cache"
    if previous_provider:
        parser_meta["upstream_provider"] = previous_provider
    if previous_model:
        parser_meta["previous_model_name"] = previous_model

    analysis_meta = copy.deepcopy(report.analysis_meta)
    analysis_meta["parser"] = parser_meta
    brief_body = str(parser_meta.get("brief_body", "")).strip()
    if brief_body:
        analysis_meta["brief_body"] = brief_body
    analysis_meta["fact_check"] = {
        "skipped": True,
        "reason": "manual_cache_restore",
    }
    analysis_meta["contract_violations"] = list(candidate.violations)
    analysis_meta["quality_review"] = {
        "warnings": [],
        "evidence": parser_meta.get("evidence", {}),
    }
    analysis_meta["auto_heal"] = {
        "applied": False,
        "reason": "historical_cache_restore",
        "restored_from_prompt_hash": candidate.prompt_hash,
    }
    analysis_meta["manual_repair"] = {
        "restored_from_prompt_hash": candidate.prompt_hash,
        "restored_cache_created_at": candidate.created_at,
        "restored_at": utc_now_iso(),
        "backup_path": str(backup_path),
        "repair_script": "scripts/repair_historical_reports.py",
        "source_provider_before_restore": previous_provider,
        "source_model_before_restore": previous_model,
    }

    report.summary_lines = list(payload.summary_lines)
    report.insights = list(payload.insights)
    report.channel_drafts = list(payload.channel_drafts)
    report.generation_mode = payload.generation_mode or report.generation_mode
    report.fact_check_score = 0.0
    report.quality_state = "ok" if not candidate.violations else "needs_review"
    report.analysis_meta = analysis_meta

    store.save_report(report)
    return backup_path


def _load_reports(store: PipelineStateStore, report_id: str | None, limit: int) -> list[ContentReport]:
    if report_id:
        report = store.get_report(report_id)
        return [report] if report is not None else []

    reports = store.list_reports(limit=500)
    broken = [report for report in reports if _is_suspicious_report(report)]
    return broken[:limit]


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair suspicious DailyNews reports from cached LLM responses.")
    parser.add_argument("--report-id", help="Repair a single report ID.")
    parser.add_argument("--limit", type=int, default=25, help="Max suspicious reports to inspect.")
    parser.add_argument("--lookback-minutes", type=int, default=15, help="Cache lookback window before report creation.")
    parser.add_argument("--max-candidates", type=int, default=20, help="Max nearby cache entries to score per report.")
    parser.add_argument("--apply", action="store_true", help="Write repaired reports back to the DB.")
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Apply candidates that still have contract violations after repair.",
    )
    args = parser.parse_args()

    store = PipelineStateStore(path=DB_PATH)
    reports = _load_reports(store, args.report_id, args.limit)
    if not reports:
        print("No suspicious reports found.")
        return 0

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    repaired = 0
    inspected = 0
    try:
        for report in reports:
            inspected += 1
            items = _build_items(report, conn)
            rows = _candidate_rows(
                conn,
                report=report,
                lookback_minutes=args.lookback_minutes,
                max_candidates=args.max_candidates,
            )
            candidate = _find_best_candidate(report=report, items=items, rows=rows)
            current_violations = _check_category_contract_for_content(
                report.category,
                report.summary_lines,
                report.insights,
            )

            print(f"\n[{report.report_id}]")
            print(f"  category={report.category} quality_state={report.quality_state} current_violations={len(current_violations)}")
            print(f"  notion_page_id={report.notion_page_id or '-'}")

            if candidate is None:
                print("  status=no_candidate_found")
                continue

            print(
                "  candidate="
                f"{candidate.prompt_hash[:12]} created_at={candidate.created_at} "
                f"mode={candidate.repair_mode} "
                f"citations={candidate.citation_count} violations={len(candidate.violations)} "
                f"distance_s={candidate.distance_seconds:.1f}"
            )
            print(f"  summary_preview={candidate.payload.summary_lines[:2]}")

            if not args.apply:
                print("  action=dry_run")
                continue

            if candidate.violations and not args.allow_partial:
                print("  action=skipped_partial_candidate")
                continue

            backup_path = _repair_report(store=store, report=report, candidate=candidate)
            repaired += 1
            print(f"  action=repaired backup={backup_path}")

    finally:
        conn.close()

    print(f"\ninspected={inspected} repaired={repaired} apply={args.apply}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
