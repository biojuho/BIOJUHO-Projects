from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_MANIFEST = WORKSPACE_ROOT / "ops" / "references" / "agent_workflows.json"
DEFAULT_TIMEOUT_SECONDS = 600.0
SIDE_EFFECT_HINTS = (
    ("dev_server_start", "dev_server_control.py start"),
    ("npm_dev_server", "npm.cmd run dev"),
    ("npm_dev_server", "npm run dev"),
    ("preview_server", "dev:preview"),
    ("wait_ready_process", "--wait-ready"),
)

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import agent_workflow_manifest as workflow_manifest  # noqa: E402


def resolve_python_executable() -> str:
    venv_rel = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    candidates = [
        WORKSPACE_ROOT / ".venv" / venv_rel,
        WORKSPACE_ROOT / "venv" / venv_rel,
        Path(sys.executable),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def select_workflow(payload: dict[str, Any], workflow_id: str) -> dict[str, Any]:
    for workflow in payload.get("workflows", []):
        if workflow.get("id") == workflow_id:
            return workflow
    raise ValueError(f"unknown workflow id: {workflow_id}")


def select_workflows(payload: dict[str, Any], workflow_id: str | None, *, all_workflows: bool) -> list[dict[str, Any]]:
    if all_workflows:
        return list(payload.get("workflows", []))
    if workflow_id:
        return [select_workflow(payload, workflow_id)]
    raise ValueError("provide --workflow or --all-workflows")


def build_gate_steps(
    workflow: dict[str, Any],
    *,
    max_gates: int | None = None,
    gate_index: int | None = None,
) -> list[dict[str, Any]]:
    gates = workflow.get("quality_gates", [])
    if gate_index is not None:
        if gate_index < 1 or gate_index > len(gates):
            raise ValueError(f"gate index must be between 1 and {len(gates)}")
        indexed_gates = [(gate_index, gates[gate_index - 1])]
    else:
        if max_gates is not None:
            gates = gates[: max(max_gates, 0)]
        indexed_gates = list(enumerate(gates, start=1))
    steps: list[dict[str, Any]] = []
    for index, gate in indexed_gates:
        command_text, cwd = workflow_manifest.split_quality_gate_command(gate)
        steps.append(
            {
                "index": index,
                "workflow_id": workflow["id"],
                "command": normalize_command(command_text),
                "cwd": cwd,
                "source": gate,
                "safety": classify_gate_safety(command_text),
            }
        )
    return steps


def classify_gate_safety(command_text: str) -> dict[str, Any]:
    normalized = " ".join(command_text.lower().split())
    reasons = [
        hint_name
        for hint_name, needle in SIDE_EFFECT_HINTS
        if needle in normalized
    ]
    return {
        "risk": "side_effecting" if reasons else "deterministic",
        "requires_approval": bool(reasons),
        "reasons": sorted(set(reasons)),
    }


def normalize_command(command_text: str, *, python_exe: str | None = None) -> list[str]:
    parts = command_text.split()
    if not parts:
        raise ValueError("quality gate command must not be empty")
    if parts[0].lower() in {"python", "python.exe"}:
        parts[0] = python_exe or resolve_python_executable()
    return parts


def build_env() -> dict[str, str]:
    env = os.environ.copy()
    candidates = [
        WORKSPACE_ROOT,
        WORKSPACE_ROOT / "packages",
        WORKSPACE_ROOT / "automation",
        WORKSPACE_ROOT / "automation" / "DailyNews" / "src",
        WORKSPACE_ROOT / "automation" / "DailyNews" / "scripts",
        WORKSPACE_ROOT / "apps" / "desci-platform",
        WORKSPACE_ROOT / "apps" / "AgriGuard" / "backend",
    ]
    entries = [str(path) for path in candidates if path.exists()]
    if env.get("PYTHONPATH"):
        entries.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(entries)
    return env


def run_gate_step(step: dict[str, Any], *, timeout_seconds: float) -> dict[str, Any]:
    started = time.perf_counter()
    cwd = WORKSPACE_ROOT / step["cwd"]
    if not cwd.exists():
        return {
            **step,
            "status": "fail",
            "returncode": 2,
            "elapsed_seconds": 0.0,
            "stdout_tail": "",
            "stderr_tail": "working directory missing",
        }
    try:
        process = subprocess.run(
            step["command"],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
            env=build_env(),
        )
        return {
            **step,
            "status": "pass" if process.returncode == 0 else "fail",
            "returncode": process.returncode,
            "elapsed_seconds": round(max(time.perf_counter() - started, 0.0), 3),
            "stdout_tail": tail_text(process.stdout),
            "stderr_tail": tail_text(process.stderr),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            **step,
            "status": "fail",
            "returncode": 124,
            "elapsed_seconds": round(max(time.perf_counter() - started, 0.0), 3),
            "stdout_tail": tail_text(exc.stdout or ""),
            "stderr_tail": f"Command timed out after {timeout_seconds}s\n{tail_text(exc.stderr or '')}".strip(),
        }


def skip_gate_step(step: dict[str, Any]) -> dict[str, Any]:
    safety = step.get("safety", {})
    reasons = ", ".join(safety.get("reasons", [])) or "approval_required"
    return {
        **step,
        "status": "skipped",
        "returncode": None,
        "elapsed_seconds": 0.0,
        "stdout_tail": "",
        "stderr_tail": "",
        "skip_reason": f"side-effecting gate requires --allow-side-effect-gates ({reasons})",
    }


def gate_cache_key(step: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    return step["cwd"], tuple(step["command"])


def reuse_gate_step(step: dict[str, Any], cached_result: dict[str, Any]) -> dict[str, Any]:
    status = "fail" if cached_result["status"] == "fail" else "reused"
    return {
        **step,
        "status": status,
        "returncode": cached_result.get("returncode"),
        "elapsed_seconds": 0.0,
        "stdout_tail": cached_result.get("stdout_tail", ""),
        "stderr_tail": cached_result.get("stderr_tail", ""),
        "skip_reason": "",
        "reused_from": {
            "workflow_id": cached_result.get("workflow_id"),
            "gate_index": cached_result.get("index"),
            "status": cached_result.get("status"),
        },
    }


def execute_or_plan_steps(
    steps: list[dict[str, Any]],
    *,
    execute: bool,
    allow_side_effect_gates: bool,
    timeout_seconds: float,
) -> list[dict[str, Any]]:
    if execute:
        return [
            run_gate_step(step, timeout_seconds=timeout_seconds)
            if allow_side_effect_gates or not step["safety"]["requires_approval"]
            else skip_gate_step(step)
            for step in steps
        ]
    return [
        {
            **step,
            "status": "planned",
            "returncode": None,
            "elapsed_seconds": 0.0,
            "stdout_tail": "",
            "stderr_tail": "",
            "skip_reason": "",
        }
        for step in steps
    ]


def run_workflow_gates(
    manifest_path: Path,
    workflow_id: str,
    *,
    execute: bool,
    max_gates: int | None,
    timeout_seconds: float,
    gate_index: int | None = None,
    allow_side_effect_gates: bool = False,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
) -> dict[str, Any]:
    payload = workflow_manifest.load_manifest(manifest_path)
    errors = workflow_manifest.validate_manifest(payload, workspace_root=WORKSPACE_ROOT)
    if errors:
        raise ValueError("\n".join(errors))
    if max_gates is not None and gate_index is not None:
        raise ValueError("--max-gates and --gate-index cannot be combined")
    workflow = select_workflow(payload, workflow_id)
    steps = build_gate_steps(workflow, max_gates=max_gates, gate_index=gate_index)
    results = execute_or_plan_steps(
        steps,
        execute=execute,
        allow_side_effect_gates=allow_side_effect_gates,
        timeout_seconds=timeout_seconds,
    )
    report = build_report(
        payload,
        workflow,
        results,
        execute=execute,
        allow_side_effect_gates=allow_side_effect_gates,
        max_gates=max_gates,
        gate_index=gate_index,
    )
    if json_out:
        write_json_atomic(json_out, report)
    if markdown_out:
        write_text_atomic(markdown_out, render_markdown(report))
    if report["status"] == "fail":
        raise ValueError("\n".join(report["errors"]))
    return report


def run_workflow_matrix(
    manifest_path: Path,
    *,
    execute: bool,
    max_gates: int | None,
    timeout_seconds: float,
    allow_side_effect_gates: bool = False,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
) -> dict[str, Any]:
    payload = workflow_manifest.load_manifest(manifest_path)
    errors = workflow_manifest.validate_manifest(payload, workspace_root=WORKSPACE_ROOT)
    if errors:
        raise ValueError("\n".join(errors))
    workflow_reports: list[dict[str, Any]] = []
    gate_cache: dict[tuple[str, tuple[str, ...]], dict[str, Any]] = {}
    for workflow in select_workflows(payload, None, all_workflows=True):
        steps = build_gate_steps(workflow, max_gates=max_gates)
        if execute:
            results = []
            for step in steps:
                if not allow_side_effect_gates and step["safety"]["requires_approval"]:
                    results.append(skip_gate_step(step))
                    continue
                key = gate_cache_key(step)
                if key in gate_cache:
                    results.append(reuse_gate_step(step, gate_cache[key]))
                    continue
                result = run_gate_step(step, timeout_seconds=timeout_seconds)
                if not step["safety"]["requires_approval"]:
                    gate_cache[key] = result
                results.append(result)
        else:
            results = execute_or_plan_steps(
                steps,
                execute=False,
                allow_side_effect_gates=allow_side_effect_gates,
                timeout_seconds=timeout_seconds,
            )
        workflow_reports.append(
            build_report(
                payload,
                workflow,
                results,
                execute=execute,
                allow_side_effect_gates=allow_side_effect_gates,
                max_gates=max_gates,
                gate_index=None,
            )
        )
    report = build_matrix_report(
        payload,
        workflow_reports,
        execute=execute,
        allow_side_effect_gates=allow_side_effect_gates,
        max_gates=max_gates,
    )
    if json_out:
        write_json_atomic(json_out, report)
    if markdown_out:
        write_text_atomic(markdown_out, render_matrix_markdown(report))
    if report["status"] == "fail":
        raise ValueError("\n".join(report["errors"]))
    return report


def build_report(
    payload: dict[str, Any],
    workflow: dict[str, Any],
    results: list[dict[str, Any]],
    *,
    execute: bool,
    allow_side_effect_gates: bool,
    max_gates: int | None,
    gate_index: int | None,
) -> dict[str, Any]:
    counts = Counter(result["status"] for result in results)
    errors = [
        f"gate {result['index']} failed with return code {result['returncode']}: {result['stderr_tail'] or result['stdout_tail']}"
        for result in results
        if result["status"] == "fail"
    ]
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "fail" if errors else "pass",
        "execution_mode": "execute" if execute else "dry_run",
        "will_execute": execute,
        "allow_side_effect_gates": allow_side_effect_gates,
        "manifest_generated_at": payload.get("generated_at"),
        "source_context": payload.get("source_context"),
        "workflow": {
            "id": workflow["id"],
            "project": workflow["project"],
            "goal": workflow["goal"],
            "smoke_scope": workflow["smoke_scope"],
            "launch_status": workflow["launch_status"],
            "agent_roles": workflow["agent_roles"],
            "mcp_servers": workflow["mcp_servers"],
            "quality_gate_count": len(workflow.get("quality_gates", [])),
        },
        "summary": {
            "requested_max_gates": max_gates,
            "requested_gate_index": gate_index,
            "selected_gates": len(results),
            "passed_gates": counts.get("pass", 0),
            "failed_gates": counts.get("fail", 0),
            "skipped_gates": counts.get("skipped", 0),
            "reused_gates": counts.get("reused", 0),
            "planned_gates": counts.get("planned", 0),
            "approval_required_gates": sum(
                1 for result in results if result.get("safety", {}).get("requires_approval")
            ),
            "elapsed_seconds": round(sum(result.get("elapsed_seconds", 0.0) for result in results), 3),
        },
        "gates": results,
        "errors": errors,
    }


def build_matrix_report(
    payload: dict[str, Any],
    workflow_reports: list[dict[str, Any]],
    *,
    execute: bool,
    allow_side_effect_gates: bool,
    max_gates: int | None,
) -> dict[str, Any]:
    workflow_counts = Counter(report["status"] for report in workflow_reports)
    gate_counts: Counter[str] = Counter()
    elapsed_seconds = 0.0
    approval_required = 0
    errors: list[str] = []
    for report in workflow_reports:
        summary = report["summary"]
        gate_counts["selected_gates"] += summary["selected_gates"]
        gate_counts["passed_gates"] += summary["passed_gates"]
        gate_counts["failed_gates"] += summary["failed_gates"]
        gate_counts["skipped_gates"] += summary["skipped_gates"]
        gate_counts["reused_gates"] += summary["reused_gates"]
        gate_counts["planned_gates"] += summary["planned_gates"]
        approval_required += summary["approval_required_gates"]
        elapsed_seconds += summary["elapsed_seconds"]
        errors.extend(f"{report['workflow']['id']}: {error}" for error in report["errors"])
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "fail" if errors else "pass",
        "execution_mode": "execute" if execute else "dry_run",
        "will_execute": execute,
        "allow_side_effect_gates": allow_side_effect_gates,
        "manifest_generated_at": payload.get("generated_at"),
        "source_context": payload.get("source_context"),
        "summary": {
            "requested_max_gates": max_gates,
            "workflow_count": len(workflow_reports),
            "passed_workflows": workflow_counts.get("pass", 0),
            "failed_workflows": workflow_counts.get("fail", 0),
            "selected_gates": gate_counts["selected_gates"],
            "passed_gates": gate_counts["passed_gates"],
            "failed_gates": gate_counts["failed_gates"],
            "skipped_gates": gate_counts["skipped_gates"],
            "reused_gates": gate_counts["reused_gates"],
            "planned_gates": gate_counts["planned_gates"],
            "approval_required_gates": approval_required,
            "elapsed_seconds": round(elapsed_seconds, 3),
        },
        "workflows": workflow_reports,
        "errors": errors,
    }


def render_markdown(report: dict[str, Any]) -> str:
    workflow = report["workflow"]
    summary = report["summary"]
    lines = [
        f"# Agent Workflow Gate Runner - {workflow['id']}",
        "",
        f"- Status: `{report['status']}`",
        f"- Execution mode: `{report['execution_mode']}`",
        f"- Will execute: `{str(report['will_execute']).lower()}`",
        f"- Allow side-effect gates: `{str(report['allow_side_effect_gates']).lower()}`",
        f"- Project: `{workflow['project']}`",
        f"- Smoke scope: `{workflow['smoke_scope']}`",
        f"- Selected gates: `{summary['selected_gates']}`",
        f"- Passed gates: `{summary['passed_gates']}`",
        f"- Failed gates: `{summary['failed_gates']}`",
        f"- Skipped gates: `{summary['skipped_gates']}`",
        f"- Reused gates: `{summary['reused_gates']}`",
        f"- Planned gates: `{summary['planned_gates']}`",
        f"- Approval-required gates: `{summary['approval_required_gates']}`",
        f"- Elapsed seconds: `{summary['elapsed_seconds']}`",
        "",
        "## Gates",
        "",
    ]
    for gate in report["gates"]:
        lines.extend(
            [
                f"### Gate {gate['index']}",
                "",
                f"- Status: `{gate['status']}`",
                f"- CWD: `{gate['cwd']}`",
                f"- Command: `{format_command(gate['command'])}`",
                f"- Safety: `{gate['safety']['risk']}`",
                f"- Safety reasons: `{', '.join(gate['safety']['reasons']) or '-'}`",
                f"- Return code: `{gate['returncode']}`",
                f"- Elapsed seconds: `{gate['elapsed_seconds']}`",
                f"- Skip reason: `{gate.get('skip_reason') or '-'}`",
                "",
            ]
        )
    lines.extend(["## Errors", ""])
    if report["errors"]:
        lines.extend(f"- {error}" for error in report["errors"])
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def render_matrix_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Agent Workflow Gate Matrix",
        "",
        f"- Status: `{report['status']}`",
        f"- Execution mode: `{report['execution_mode']}`",
        f"- Will execute: `{str(report['will_execute']).lower()}`",
        f"- Allow side-effect gates: `{str(report['allow_side_effect_gates']).lower()}`",
        f"- Workflows: `{summary['workflow_count']}`",
        f"- Passed workflows: `{summary['passed_workflows']}`",
        f"- Failed workflows: `{summary['failed_workflows']}`",
        f"- Selected gates: `{summary['selected_gates']}`",
        f"- Passed gates: `{summary['passed_gates']}`",
        f"- Failed gates: `{summary['failed_gates']}`",
        f"- Skipped gates: `{summary['skipped_gates']}`",
        f"- Reused gates: `{summary['reused_gates']}`",
        f"- Planned gates: `{summary['planned_gates']}`",
        f"- Approval-required gates: `{summary['approval_required_gates']}`",
        f"- Elapsed seconds: `{summary['elapsed_seconds']}`",
        "",
        "## Workflows",
        "",
    ]
    for workflow_report in report["workflows"]:
        workflow = workflow_report["workflow"]
        workflow_summary = workflow_report["summary"]
        lines.extend(
            [
                f"### {workflow['id']}",
                "",
                f"- Status: `{workflow_report['status']}`",
                f"- Project: `{workflow['project']}`",
                f"- Smoke scope: `{workflow['smoke_scope']}`",
                f"- Selected gates: `{workflow_summary['selected_gates']}`",
                f"- Passed gates: `{workflow_summary['passed_gates']}`",
                f"- Failed gates: `{workflow_summary['failed_gates']}`",
                f"- Skipped gates: `{workflow_summary['skipped_gates']}`",
                f"- Reused gates: `{workflow_summary['reused_gates']}`",
                f"- Planned gates: `{workflow_summary['planned_gates']}`",
                f"- Approval-required gates: `{workflow_summary['approval_required_gates']}`",
                "",
            ]
        )
    lines.extend(["## Errors", ""])
    if report["errors"]:
        lines.extend(f"- {error}" for error in report["errors"])
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def format_command(command: list[str]) -> str:
    return " ".join(f'"{part}"' if any(ch.isspace() for ch in part) else part for part in command)


def tail_text(text: str, *, line_count: int = 12) -> str:
    lines = text.strip().splitlines()
    return "\n".join(lines[-line_count:])


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run or plan declared agent workflow quality gates.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--workflow")
    parser.add_argument("--all-workflows", action="store_true", help="Run or plan selected gates for every workflow.")
    parser.add_argument("--execute", action="store_true", help="Run selected quality gates. Default only plans them.")
    parser.add_argument(
        "--allow-side-effect-gates",
        action="store_true",
        help="Allow gates that can start long-running local services or otherwise require operator approval.",
    )
    parser.add_argument("--max-gates", type=int)
    parser.add_argument("--gate-index", type=int, help="Select exactly one 1-based quality gate index.")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.all_workflows and args.workflow:
            raise ValueError("--workflow and --all-workflows cannot be combined")
        if args.all_workflows and args.gate_index is not None:
            raise ValueError("--gate-index cannot be used with --all-workflows")
        if args.all_workflows:
            report = run_workflow_matrix(
                args.manifest,
                execute=args.execute,
                allow_side_effect_gates=args.allow_side_effect_gates,
                max_gates=args.max_gates,
                timeout_seconds=args.timeout,
                json_out=args.json_out,
                markdown_out=args.markdown_out,
            )
        else:
            if not args.workflow:
                raise ValueError("provide --workflow or --all-workflows")
            report = run_workflow_gates(
                args.manifest,
                args.workflow,
                execute=args.execute,
                allow_side_effect_gates=args.allow_side_effect_gates,
                max_gates=args.max_gates,
                gate_index=args.gate_index,
                timeout_seconds=args.timeout,
                json_out=args.json_out,
                markdown_out=args.markdown_out,
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"agent workflow gate runner failed: {exc}", file=sys.stderr)
        return 1
    if args.all_workflows:
        print(
            "agent workflow gate matrix valid: "
            f"workflows={report['summary']['workflow_count']}, "
            f"mode={report['execution_mode']}, "
            f"selected={report['summary']['selected_gates']}, "
            f"passed={report['summary']['passed_gates']}, "
            f"failed={report['summary']['failed_gates']}, "
            f"skipped={report['summary']['skipped_gates']}, "
            f"reused={report['summary']['reused_gates']}"
        )
        return 0
    print(
        "agent workflow gate runner valid: "
        f"workflow={report['workflow']['id']}, "
        f"mode={report['execution_mode']}, "
        f"selected={report['summary']['selected_gates']}, "
        f"passed={report['summary']['passed_gates']}, "
        f"failed={report['summary']['failed_gates']}, "
        f"skipped={report['summary']['skipped_gates']}, "
        f"reused={report['summary']['reused_gates']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
