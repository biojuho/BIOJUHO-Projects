from __future__ import annotations

from collections import Counter
from typing import Any

from antigravity_mcp.domain.models import ContentReport
from antigravity_mcp.evals.frozen_eval_dataset import FrozenEvalCase
from antigravity_mcp.integrations.llm_prompts import resolve_prompt_mode


def _extract_x_draft(report: ContentReport) -> dict[str, Any]:
    draft = next((draft for draft in report.channel_drafts if draft.channel == "x"), None)
    if draft is None:
        return {"source": "", "is_fallback": False, "length": 0}
    return {
        "source": draft.source,
        "is_fallback": draft.is_fallback,
        "length": len(draft.content or ""),
    }


def build_case_result(
    *,
    case: FrozenEvalCase,
    report: ContentReport | None,
    status: str,
    warnings: list[str],
    run_id: str,
) -> dict[str, Any]:
    expected_mode = case.expected_generation_mode or resolve_prompt_mode(case.window_name, len(case.items))
    if report is None:
        return {
            "case_id": case.case_id,
            "category": case.category,
            "window_name": case.window_name,
            "description": case.description,
            "run_id": run_id,
            "status": status,
            "report_id": "",
            "expected_generation_mode": expected_mode,
            "actual_generation_mode": "",
            "mode_matches": False,
            "quality_state": "missing",
            "fact_check_score": 0.0,
            "summary_line_count": 0,
            "insight_count": 0,
            "summary_preview": "",
            "quality_warning_count": 0,
            "quality_warnings": [],
            "pipeline_warning_count": len(warnings),
            "pipeline_warnings": list(warnings),
            "x_draft": {"source": "", "is_fallback": False, "length": 0},
            "evidence": {
                "line_count": 0,
                "tagged_line_count": 0,
                "missing_line_count": 0,
                "article_ref_count": 0,
                "background_line_count": 0,
                "coverage_ratio": None,
            },
            "used_parse_fallback": False,
        }

    parser_meta = report.analysis_meta.get("parser", {}) if isinstance(report.analysis_meta, dict) else {}
    evidence = parser_meta.get("evidence", {}) if isinstance(parser_meta, dict) else {}
    line_count = int(evidence.get("line_count", 0) or 0)
    tagged_line_count = int(evidence.get("tagged_line_count", 0) or 0)
    quality_review = report.analysis_meta.get("quality_review", {}) if isinstance(report.analysis_meta, dict) else {}
    quality_warnings = quality_review.get("warnings", []) if isinstance(quality_review, dict) else []

    return {
        "case_id": case.case_id,
        "category": case.category,
        "window_name": case.window_name,
        "description": case.description,
        "run_id": run_id,
        "report_id": report.report_id,
        "status": status,
        "expected_generation_mode": expected_mode,
        "actual_generation_mode": report.generation_mode,
        "mode_matches": report.generation_mode == expected_mode,
        "quality_state": report.quality_state,
        "fact_check_score": round(float(report.fact_check_score or 0.0), 4),
        "summary_line_count": len(report.summary_lines),
        "insight_count": len(report.insights),
        "summary_preview": report.summary_lines[0] if report.summary_lines else "",
        "quality_warning_count": len(quality_warnings),
        "quality_warnings": list(quality_warnings),
        "pipeline_warning_count": len(warnings),
        "pipeline_warnings": list(warnings),
        "x_draft": _extract_x_draft(report),
        "evidence": {
            "line_count": line_count,
            "tagged_line_count": tagged_line_count,
            "missing_line_count": int(evidence.get("missing_line_count", 0) or 0),
            "article_ref_count": int(evidence.get("article_ref_count", 0) or 0),
            "background_line_count": int(evidence.get("background_line_count", 0) or 0),
            "coverage_ratio": round(tagged_line_count / line_count, 4) if line_count else None,
        },
        "used_parse_fallback": bool(parser_meta.get("used_fallback")),
    }


def summarize_case_results(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    report_count = sum(1 for case in case_results if case["report_id"])
    quality_counts = Counter(str(case["quality_state"] or "missing") for case in case_results)
    status_counts = Counter(str(case["status"] or "unknown") for case in case_results)
    generation_modes = Counter(
        str(case["actual_generation_mode"] or "unknown") for case in case_results if case["report_id"]
    )
    draft_sources = Counter(str(case["x_draft"]["source"] or "missing") for case in case_results)

    evidence_cases = [case for case in case_results if int(case["evidence"]["line_count"]) > 0]
    total_evidence_lines = sum(int(case["evidence"]["line_count"]) for case in evidence_cases)
    tagged_evidence_lines = sum(int(case["evidence"]["tagged_line_count"]) for case in evidence_cases)
    direct_ref_cases = sum(1 for case in evidence_cases if int(case["evidence"]["article_ref_count"]) > 0)

    fact_check_scores = [
        float(case["fact_check_score"]) for case in case_results if float(case["fact_check_score"]) > 0
    ]
    mode_scored_cases = [case for case in case_results if case["expected_generation_mode"]]
    matched_modes = sum(1 for case in mode_scored_cases if case["mode_matches"])
    edit_needed_count = sum(
        1 for case in case_results if case["quality_state"] != "ok" or case["quality_warning_count"] > 0
    )
    x_fallback_count = sum(1 for case in case_results if bool(case["x_draft"]["is_fallback"]))
    insight_override_count = sum(1 for case in case_results if case["x_draft"]["source"] == "insight_generator")

    warning_counter = Counter()
    for case in case_results:
        warning_counter.update(case["pipeline_warnings"])
        warning_counter.update(case["quality_warnings"])

    return {
        "case_count": len(case_results),
        "report_count": report_count,
        "status_counts": dict(status_counts),
        "quality_counts": dict(quality_counts),
        "generation_modes": dict(generation_modes),
        "draft_source_counts": dict(draft_sources),
        "fallback_rate": round(quality_counts.get("fallback", 0) / max(report_count, 1), 4),
        "needs_review_rate": round(quality_counts.get("needs_review", 0) / max(report_count, 1), 4),
        "edit_needed_rate": round(edit_needed_count / max(report_count, 1), 4),
        "x_fallback_rate": round(x_fallback_count / max(report_count, 1), 4),
        "draft_override_rate": round(insight_override_count / max(report_count, 1), 4),
        "evidence_coverage_ratio": round(tagged_evidence_lines / max(total_evidence_lines, 1), 4)
        if total_evidence_lines
        else None,
        "direct_article_ref_rate": round(direct_ref_cases / max(len(evidence_cases), 1), 4) if evidence_cases else None,
        "avg_fact_check_score": round(sum(fact_check_scores) / len(fact_check_scores), 4)
        if fact_check_scores
        else None,
        "fact_check_coverage_rate": round(len(fact_check_scores) / max(report_count, 1), 4) if report_count else None,
        "prompt_mode_match_rate": round(matched_modes / max(len(mode_scored_cases), 1), 4)
        if mode_scored_cases
        else None,
        "top_warnings": [{"message": message, "count": count} for message, count in warning_counter.most_common(10)],
    }


def render_frozen_eval_markdown(result: dict[str, Any]) -> str:
    summary = result.get("summary", {})
    cases = result.get("cases", [])
    top_warnings = summary.get("top_warnings", [])

    lines = [
        "# Frozen Eval Report",
        "",
        f"- Generated at: {result.get('generated_at', '')}",
        f"- Dataset: `{result.get('dataset_path', '')}`",
        f"- Eval state DB: `{result.get('state_db_path', '')}`",
        f"- Cases: {summary.get('case_count', 0)}",
        f"- Reports: {summary.get('report_count', 0)}",
        f"- Fallback rate: {summary.get('fallback_rate', 0.0):.1%}",
        f"- Needs review rate: {summary.get('needs_review_rate', 0.0):.1%}",
        f"- Edit needed rate: {summary.get('edit_needed_rate', 0.0):.1%}",
        "",
        "## Aggregate Metrics",
        "",
        f"- Prompt mode match rate: {summary.get('prompt_mode_match_rate', 0.0) or 0.0:.1%}",
        f"- Evidence coverage ratio: {summary.get('evidence_coverage_ratio', 0.0) or 0.0:.1%}",
        f"- Direct article ref rate: {summary.get('direct_article_ref_rate', 0.0) or 0.0:.1%}",
        f"- X fallback rate: {summary.get('x_fallback_rate', 0.0):.1%}",
        f"- Draft override rate: {summary.get('draft_override_rate', 0.0):.1%}",
        f"- Avg fact-check score: {summary.get('avg_fact_check_score', 0.0) or 0.0:.3f}",
        "",
        "## Case Results",
        "",
    ]

    for case in cases:
        lines.append(
            "- "
            f"`{case['case_id']}` | {case['category']} / {case['window_name']} | "
            f"mode={case['actual_generation_mode'] or 'n/a'} | "
            f"quality={case['quality_state']} | "
            f"evidence={case['evidence']['coverage_ratio'] if case['evidence']['coverage_ratio'] is not None else 'n/a'} | "
            f"x={case['x_draft']['source'] or 'n/a'}"
        )

    lines.extend(["", "## Top Warnings", ""])
    if top_warnings:
        for warning in top_warnings:
            lines.append(f"- {warning['count']}x {warning['message']}")
    else:
        lines.append("- No warnings recorded.")
    lines.append("")
    return "\n".join(lines)
