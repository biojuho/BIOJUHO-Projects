"""Run getdaytrends CLI smoke checks and emit a machine-readable report."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_PY = PROJECT_ROOT / "main.py"
DEFAULT_REPORT = PROJECT_ROOT / "logs" / "smoke" / "cli_smoke_latest.json"
DRY_RUN_TIMEOUT_SECONDS = 360
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
POSTGRES_URL_RE = re.compile(r"\b(postgres(?:ql)?://)[^\s\"'<>]+", re.IGNORECASE)
SUPABASE_USER_RE = re.compile(r"\bpostgres\.[A-Za-z0-9_.-]+")
TENANT_USER_RE = re.compile(r"(\btenant/user\s+)[^\s),;]+", re.IGNORECASE)
OPENAI_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b")
GOOGLE_API_KEY_RE = re.compile(r"\bAIza[0-9A-Za-z_-]{16,}\b")
PROVIDER_TEAM_ID_RE = re.compile(
    r"(\bteam\s+)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
RUNTIME_FALLBACK_PATTERNS: tuple[tuple[str, str], ...] = (
    ("database.sqlite_fallback", "postgresql connection failed; falling back to local sqlite"),
    ("cost_db.in_memory_fallback", "failed to init cost db:"),
    ("cost_db.in_memory_fallback", "falling back to in-memory"),
)


@dataclass(frozen=True)
class SmokeCase:
    name: str
    args: tuple[str, ...]
    timeout: int


def _mask_sensitive_text(text: str) -> str:
    masked = POSTGRES_URL_RE.sub(r"\1***", text)
    masked = SUPABASE_USER_RE.sub("postgres.<project_ref>", masked)
    masked = TENANT_USER_RE.sub(r"\1***", masked)
    masked = OPENAI_KEY_RE.sub("sk-***", masked)
    masked = GOOGLE_API_KEY_RE.sub("AIza***", masked)
    return PROVIDER_TEAM_ID_RE.sub(r"\1***", masked)


def _output_tail(text: str, *, limit: int = 3000) -> str:
    normalized = ANSI_ESCAPE_RE.sub("", text)
    return _mask_sensitive_text(normalized)[-limit:]


def _child_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("NO_COLOR", "1")
    env.setdefault("LOGURU_COLORIZE", "false")
    return env


def _matching_line(text: str, needle: str) -> str:
    for line in text.splitlines():
        if needle in line.lower():
            return line.strip()
    return text.strip()[:500]


def _runtime_fallbacks(results: list[dict[str, Any]]) -> list[dict[str, str]]:
    fallbacks: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for result in results:
        check_name = str(result.get("name") or "unknown")
        for stream_name in ("stdout_tail", "stderr_tail"):
            value = result.get(stream_name)
            if not isinstance(value, str) or not value:
                continue
            lower_value = value.lower()
            for kind, needle in RUNTIME_FALLBACK_PATTERNS:
                if needle not in lower_value:
                    continue
                key = (check_name, stream_name, kind)
                if key in seen:
                    continue
                seen.add(key)
                fallbacks.append(
                    {
                        "check": check_name,
                        "stream": stream_name,
                        "kind": kind,
                        "snippet": _matching_line(value, needle),
                    }
                )
    return fallbacks


def _build_cases(include_dry_run: bool) -> list[SmokeCase]:
    cases = [
        SmokeCase("version", ("--version",), 30),
        SmokeCase("doctor", ("--doctor",), 60),
        SmokeCase("health_check", ("--health-check",), 60),
        SmokeCase("stats", ("--one-shot", "--stats",), 90),
    ]
    if include_dry_run:
        cases.append(
            SmokeCase(
                "dry_run",
                ("--one-shot", "--dry-run", "--limit", "1", "--no-alerts"),
                DRY_RUN_TIMEOUT_SECONDS,
            )
        )
    return cases


def _run_case(case: SmokeCase, python_exe: str) -> dict[str, Any]:
    started = time.perf_counter()
    cmd = [python_exe, str(MAIN_PY), *case.args]
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            env=_child_env(),
            timeout=case.timeout,
            check=False,
        )
        elapsed = round(time.perf_counter() - started, 3)
        return {
            "name": case.name,
            "command": " ".join(cmd),
            "timeout_seconds": case.timeout,
            "duration_seconds": elapsed,
            "exit_code": completed.returncode,
            "ok": completed.returncode == 0,
            "stdout_tail": _output_tail(completed.stdout),
            "stderr_tail": _output_tail(completed.stderr),
        }
    except subprocess.TimeoutExpired as exc:
        elapsed = round(time.perf_counter() - started, 3)
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return {
            "name": case.name,
            "command": " ".join(cmd),
            "timeout_seconds": case.timeout,
            "duration_seconds": elapsed,
            "exit_code": None,
            "ok": False,
            "timeout": True,
            "stdout_tail": _output_tail(stdout),
            "stderr_tail": _output_tail(stderr),
        }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_smoke(*, include_dry_run: bool, report_path: Path, python_exe: str) -> dict[str, Any]:
    cases = _build_cases(include_dry_run)
    results = [_run_case(case, python_exe) for case in cases]
    runtime_fallbacks = _runtime_fallbacks(results)
    summary = {
        "total": len(results),
        "passed": sum(1 for result in results if result["ok"]),
        "failed": sum(1 for result in results if not result["ok"]),
    }
    payload = {
        "schema_version": 1,
        "status": "pass" if summary["failed"] == 0 else "fail",
        "generated_at": datetime.now().astimezone().isoformat(),
        "project_root": str(PROJECT_ROOT),
        "python": python_exe,
        "include_dry_run": include_dry_run,
        "summary": summary,
        "runtime_fallback_count": len(runtime_fallbacks),
        "runtime_fallbacks": runtime_fallbacks,
        "results": results,
    }
    _write_report(report_path, payload)
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run getdaytrends CLI smoke checks.")
    parser.add_argument("--include-dry-run", action="store_true", help="Also run the slower one-shot dry-run path.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT, help="Path to write the JSON smoke report.")
    parser.add_argument("--python", default=sys.executable, help="Python executable used to run main.py.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    payload = run_smoke(include_dry_run=args.include_dry_run, report_path=args.report, python_exe=args.python)
    print(f"getdaytrends CLI smoke: {payload['status']}")
    print(f"report: {args.report}")
    for result in payload["results"]:
        marker = "OK" if result["ok"] else "FAIL"
        print(f"{marker} {result['name']} ({result['duration_seconds']}s)")
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
