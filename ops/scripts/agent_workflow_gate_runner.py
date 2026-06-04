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


def build_gate_steps(workflow: dict[str, Any], *, max_gates: int | None = None) -> list[dict[str, Any]]:
    gates = workflow.get("quality_gates", [])
    if max_gates is not None:
        gates = gates[: max(max_gates, 0)]
    steps: list[dict[str, Any]] = []
    for index, gate in enumerate(gates, start=1):
        command_text, cwd = workflow_manifest.split_quality_gate_command(gate)
        steps.append(
            {
                "index": index,
                "workflow_id": workflow["id"],
                "command": normalize_command(command_text),
                "cwd": cwd,
                "source": gate,
            }
        )
    return steps


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


def run_workflow_gates(
    manifest_path: Path,
    workflow_id: str,
    *,
    execute: bool,
    max_gates: int | None,
    timeout_seconds: float,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
) -> dict[str, Any]:
    payload = workflow_manifest.load_manifest(manifest_path)
    errors = workflow_manifest.validate_manifest(payload, workspace_root=WORKSPACE_ROOT)
    if errors:
        raise ValueError("\n".join(errors))
    workflow = select_workflow(payload, workflow_id)
    steps = build_gate_steps(workflow, max_gates=max_gates)
    if execute:
        results = [run_gate_step(step, timeout_seconds=timeout_seconds) for step in steps]
    else:
        results = [
            {
                **step,
                "status": "planned",
                "returncode": None,
                "elapsed_seconds": 0.0,
                "stdout_tail": "",
                "stderr_tail": "",
            }
            for step in steps
        ]
    report = build_report(payload, workflow, results, execute=execute, max_gates=max_gates)
    if json_out:
        write_json_atomic(json_out, report)
    if markdown_out:
        write_text_atomic(markdown_out, render_markdown(report))
    if report["status"] == "fail":
        raise ValueError("\n".join(report["errors"]))
    return report


def build_report(
    payload: dict[str, Any],
    workflow: dict[str, Any],
    results: list[dict[str, Any]],
    *,
    execute: bool,
    max_gates: int | None,
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
            "selected_gates": len(results),
            "passed_gates": counts.get("pass", 0),
            "failed_gates": counts.get("fail", 0),
            "planned_gates": counts.get("planned", 0),
            "elapsed_seconds": round(sum(result.get("elapsed_seconds", 0.0) for result in results), 3),
        },
        "gates": results,
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
        f"- Project: `{workflow['project']}`",
        f"- Smoke scope: `{workflow['smoke_scope']}`",
        f"- Selected gates: `{summary['selected_gates']}`",
        f"- Passed gates: `{summary['passed_gates']}`",
        f"- Failed gates: `{summary['failed_gates']}`",
        f"- Planned gates: `{summary['planned_gates']}`",
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
                f"- Return code: `{gate['returncode']}`",
                f"- Elapsed seconds: `{gate['elapsed_seconds']}`",
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
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--execute", action="store_true", help="Run selected quality gates. Default only plans them.")
    parser.add_argument("--max-gates", type=int)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args(argv)
    try:
        report = run_workflow_gates(
            args.manifest,
            args.workflow,
            execute=args.execute,
            max_gates=args.max_gates,
            timeout_seconds=args.timeout,
            json_out=args.json_out,
            markdown_out=args.markdown_out,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"agent workflow gate runner failed: {exc}", file=sys.stderr)
        return 1
    print(
        "agent workflow gate runner valid: "
        f"workflow={report['workflow']['id']}, "
        f"mode={report['execution_mode']}, "
        f"selected={report['summary']['selected_gates']}, "
        f"passed={report['summary']['passed_gates']}, "
        f"failed={report['summary']['failed_gates']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
