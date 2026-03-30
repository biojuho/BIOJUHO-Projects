from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from antigravity_mcp.config import get_settings
from antigravity_mcp.evals.frozen_eval_dataset import (
    FrozenEvalCase,
    default_dataset_path,
    load_frozen_eval_cases,
)
from antigravity_mcp.evals.frozen_eval_report import (
    build_case_result,
    render_frozen_eval_markdown,
    summarize_case_results,
)
from antigravity_mcp.integrations.llm_adapter import LLMAdapter
from antigravity_mcp.pipelines.analyze import generate_briefs
from antigravity_mcp.pipelines.collect import get_window
from antigravity_mcp.state.events import generate_run_id, utc_now_iso
from antigravity_mcp.state.store import PipelineStateStore

__all__ = [
    "FrozenEvalCase",
    "default_dataset_path",
    "load_frozen_eval_cases",
    "render_frozen_eval_markdown",
    "run_frozen_eval",
]


def _resolve_path(value: str | Path | None, *, base_dir: Path) -> Path | None:
    if value in (None, ""):
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


def _default_output_path() -> Path:
    settings = get_settings()
    timestamp = utc_now_iso().replace(":", "").replace("-", "").replace("+00:00", "Z")
    return settings.output_dir / "frozen_eval" / f"frozen_eval_{timestamp}.json"


def _ensure_case_window(case: FrozenEvalCase) -> tuple[str, str]:
    if case.window_start and case.window_end:
        return case.window_start, case.window_end
    start, end = get_window(case.window_name)
    return start.isoformat(), end.isoformat()


async def run_frozen_eval(
    *,
    dataset_path: str | Path | None = None,
    output_path: str | Path | None = None,
    state_db_path: str | Path | None = None,
    llm_adapter: LLMAdapter | Any | None = None,
    pipeline_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    resolved_dataset_path = _resolve_path(dataset_path, base_dir=settings.project_root) or default_dataset_path()
    resolved_output_path = _resolve_path(output_path, base_dir=settings.project_root) or _default_output_path()
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_state_db_path = _resolve_path(
        state_db_path, base_dir=settings.project_root
    ) or resolved_output_path.with_suffix(".db")
    resolved_state_db_path.parent.mkdir(parents=True, exist_ok=True)

    metadata, cases = load_frozen_eval_cases(resolved_dataset_path)
    eval_run_id = generate_run_id("frozen_eval")
    case_results: list[dict[str, Any]] = []
    top_level_warnings: list[str] = []

    state_store = PipelineStateStore(path=resolved_state_db_path)
    try:
        active_llm = llm_adapter or LLMAdapter(state_store=state_store)
        overrides = dict(pipeline_overrides or {})

        for case in cases:
            case_window_start, case_window_end = _ensure_case_window(case)
            case_run_id = f"{eval_run_id}-{case.case_id}"
            run_id, reports, warnings, status = await generate_briefs(
                items=case.items,
                window_name=case.window_name,
                window_start=case_window_start,
                window_end=case_window_end,
                state_store=state_store,
                llm_adapter=active_llm,
                run_id=case_run_id,
                **overrides,
            )
            report = next(
                (report for report in reports if report.category == case.category), reports[0] if reports else None
            )
            case_results.append(
                build_case_result(
                    case=case,
                    report=report,
                    status=status,
                    warnings=warnings,
                    run_id=run_id,
                )
            )
    finally:
        state_store.close()

    summary = summarize_case_results(case_results)
    if summary["fallback_rate"]:
        top_level_warnings.append(
            f"{summary['quality_counts'].get('fallback', 0)} case(s) fell back to deterministic generation."
        )
    if summary["needs_review_rate"]:
        top_level_warnings.append(
            f"{summary['quality_counts'].get('needs_review', 0)} case(s) require editorial review."
        )
    if summary.get("evidence_coverage_ratio") is not None and summary["evidence_coverage_ratio"] < 0.8:
        top_level_warnings.append("Evidence coverage dropped below 80% across analytic lines.")
    if summary.get("prompt_mode_match_rate") is not None and summary["prompt_mode_match_rate"] < 1.0:
        top_level_warnings.append("At least one case did not match its expected prompt mode.")

    result = {
        "run_id": eval_run_id,
        "generated_at": utc_now_iso(),
        "dataset_path": str(resolved_dataset_path),
        "dataset_version": metadata["version"],
        "dataset_description": metadata["description"],
        "output_path": str(resolved_output_path),
        "markdown_path": str(resolved_output_path.with_suffix(".md")),
        "state_db_path": str(resolved_state_db_path),
        "summary": summary,
        "cases": case_results,
        "warnings": top_level_warnings,
    }

    resolved_output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    resolved_output_path.with_suffix(".md").write_text(render_frozen_eval_markdown(result), encoding="utf-8")
    return result
