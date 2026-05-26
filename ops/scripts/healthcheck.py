#!/usr/bin/env python3
"""
Workspace healthcheck diagnostic script.
Validates the structural integrity and basic health of multiple packages and UI applications within the monorepo workspace.
Checks include package existence, basic imports, structural dependency drifts, NPM builds, etc.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from workspace_paths import find_workspace_root, iter_active_units, rel_unit_path

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = find_workspace_root()
REPORT_HISTORY = SCRIPT_DIR / ".healthcheck-history.json"

CHECKS: list[dict[str, Any]] = [
    {
        "name": "getdaytrends",
        "type": "python",
        "checks": [
            ("config", rel_unit_path("getdaytrends", "config.py")),
            ("main", rel_unit_path("getdaytrends", "main.py")),
            ("packaging", rel_unit_path("getdaytrends", "pyproject.toml")),
        ],
        "key_imports": ["anthropic", "httpx", "aiosqlite"],
        "requirements": None,
    },
    {
        "name": "DailyNews",
        "type": "python",
        "checks": [("server", rel_unit_path("dailynews", "src/antigravity_mcp/server.py"))],
        "key_imports": ["notion_client"],
        "requirements": None,
    },
    {
        "name": "desci-backend",
        "type": "python",
        "checks": [
            ("main", rel_unit_path("desci-platform", "backend", "main.py")),
            ("packaging", rel_unit_path("desci-platform", "backend", "pyproject.toml")),
        ],
        "key_imports": ["fastapi", "uvicorn"],
        "requirements": None,
    },
    {
        "name": "desci-frontend",
        "type": "node",
        "checks": [
            ("package", rel_unit_path("desci-platform", "frontend", "package.json")),
            ("src", rel_unit_path("desci-platform", "frontend", "src")),
        ],
        "key_imports": [],
        "requirements": None,
    },
    {
        "name": "AgriGuard-backend",
        "type": "python",
        "checks": [
            ("main", rel_unit_path("agriguard", "backend", "main.py")),
            ("packaging", rel_unit_path("agriguard", "backend", "pyproject.toml")),
        ],
        "key_imports": ["fastapi", "sqlalchemy"],
        "requirements": None,
    },
    {
        "name": "AgriGuard-frontend",
        "type": "node",
        "checks": [
            ("package", rel_unit_path("agriguard", "frontend", "package.json")),
            ("src", rel_unit_path("agriguard", "frontend", "src")),
        ],
        "key_imports": [],
        "requirements": None,
    },
]


def check_file_exists(rel_path: str) -> tuple[bool, str]:
    full = WORKSPACE / rel_path
    if full.exists():
        return True, f"OK {rel_path}"
    return False, f"MISSING {rel_path}"


def check_python_syntax(rel_path: str) -> tuple[bool, str]:
    full = WORKSPACE / rel_path
    try:
        source = full.read_text(encoding="utf-8")
        compile(source, str(full), "exec")
    except SyntaxError as exc:
        return False, f"SYNTAX {rel_path}: line {exc.lineno}: {exc.msg}"
    except UnicodeDecodeError as exc:
        return False, f"ENCODING {rel_path}: {exc}"
    except OSError as exc:
        return False, f"ERROR {rel_path}: {exc}"
    return True, f"OK syntax {rel_path}"


def check_git_status() -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=WORKSPACE,
            timeout=10,
        )
        lines = [line for line in result.stdout.strip().splitlines() if line.strip()]
        return {"uncommitted_changes": len(lines), "files": lines[:10]}
    except Exception as exc:
        return {"error": str(exc)}


def check_env_files() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    # root .env check
    root_example = WORKSPACE / ".env.example"
    if root_example.exists():
        results.append({"example": ".env.example", "env_exists": (WORKSPACE / ".env").exists()})

    for unit in iter_active_units():
        example_path = WORKSPACE / unit["canonical_path"] / ".env.example"
        if example_path.exists():
            env_path = example_path.parent / ".env"
            rel = example_path.relative_to(WORKSPACE)
            results.append({"example": str(rel), "env_exists": env_path.exists()})
    return results


def check_python_imports(packages: list[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for package in packages:
        try:
            # Keep this high enough for cold imports under parallel workspace load.
            proc = subprocess.run(
                [sys.executable, "-c", f"import {package}"], capture_output=True, text=True, timeout=20
            )
            if proc.returncode == 0:
                results.append({"package": package, "ok": True, "message": f"OK {package}"})
            else:
                results.append({"package": package, "ok": False, "message": f"FAIL {package}: {proc.stderr.strip()}"})
        except subprocess.TimeoutExpired:
            results.append({"package": package, "ok": False, "message": f"TIMEOUT {package} (20s)"})
        except Exception as exc:
            results.append({"package": package, "ok": False, "message": f"ERROR {package}: {exc}"})
    return results


def check_dependency_drift(req_path: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    full_path = WORKSPACE / req_path
    if not full_path.exists():
        return results

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
        installed = _installed_package_map(proc.stdout) if proc.returncode == 0 else {}
        for requirement in _parse_requirement_lines(full_path.read_text(encoding="utf-8").splitlines()):
            drift = _dependency_drift(requirement, installed)
            if drift:
                results.append(drift)
    except Exception:
        return results

    return results


def _normalize_package_name(name: str) -> str:
    return name.lower().replace("-", "_")


def _installed_package_map(pip_list_json: str) -> dict[str, str]:
    return {
        _normalize_package_name(package["name"]): package["version"]
        for package in json.loads(pip_list_json)
        if "name" in package and "version" in package
    }


def _parse_requirement_line(line: str) -> dict[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or stripped.startswith("-"):
        return None

    match = re.match(r"^([a-zA-Z0-9_-]+)", stripped)
    if not match:
        return None

    req_version = re.search(r"==([0-9.]+)", stripped)
    return {
        "package": _normalize_package_name(match.group(1)),
        "required": req_version.group(1) if req_version else "any",
    }


def _parse_requirement_lines(lines: list[str]) -> list[dict[str, str]]:
    return [requirement for line in lines if (requirement := _parse_requirement_line(line))]


def _dependency_drift(requirement: dict[str, str], installed: dict[str, str]) -> dict[str, str] | None:
    package_name = requirement["package"]
    required_version = requirement["required"]
    installed_version = installed.get(package_name)

    if installed_version is None:
        return {
            "package": package_name,
            "required": required_version,
            "installed": "NOT FOUND",
            "drift": "MISSING",
        }

    if required_version != "any" and installed_version.split(".")[0] != required_version.split(".")[0]:
        return {
            "package": package_name,
            "required": required_version,
            "installed": installed_version,
            "drift": "MAJOR",
        }
    return None


def check_npm_build(rel_path: str) -> dict[str, Any]:
    full_path = WORKSPACE / rel_path
    if not full_path.exists():
        return {"ok": False, "message": f"MISSING {rel_path}"}

    try:
        npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
        proc = subprocess.run(
            [npm_cmd, "run", "build:dry"],
            cwd=full_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        if proc.returncode == 0:
            return {"ok": True, "message": "OK build dry-run"}
        stderr = next(
            (line.strip() for line in proc.stderr.splitlines() if "error" in line.lower() or "failed" in line.lower()),
            "",
        )
        return {"ok": False, "message": f"FAILED build dry-run: {stderr or 'unknown error'}"}
    except Exception as exc:
        return {"ok": False, "message": f"FAILED build dry-run: {exc}"}


def check_observability_endpoints() -> list[dict[str, Any]]:
    """Optional probes for Phase 1 observability stack.

    Activated when the env vars are set. When unset the probes return empty so
    the default healthcheck output is unchanged. See ``ops/litellm/config.yaml``
    and ``docker-compose.dev.yml --profile observability``.
    """
    targets: list[tuple[str, str]] = []
    proxy_url = os.environ.get("LITELLM_PROXY_URL", "").strip()
    if proxy_url:
        targets.append(("litellm-proxy", f"{proxy_url.rstrip('/')}/health/liveliness"))
    langfuse_host = os.environ.get("LANGFUSE_HOST", "").strip()
    if langfuse_host:
        targets.append(("langfuse", f"{langfuse_host.rstrip('/')}/api/public/health"))
    results: list[dict[str, Any]] = []
    for name, url in targets:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:  # nosec B310
                ok = 200 <= resp.status < 300
                results.append(
                    {"name": name, "ok": ok, "url": url, "message": f"HTTP {resp.status}"}
                )
        except Exception as exc:
            results.append({"name": name, "ok": False, "url": url, "message": str(exc)})
    return results


def run_healthcheck() -> dict[str, Any]:
    git_status = check_git_status()
    env_files = check_env_files()
    observability = check_observability_endpoints()
    report: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "version": "3.0",
        "workspace": str(WORKSPACE),
        "projects": [],
        "git": git_status,
        "env_files": env_files,
        "observability": observability,
    }

    for project in CHECKS:
        project_result: dict[str, Any] = {
            "name": project["name"],
            "type": project["type"],
            "checks": [],
            "imports": [],
            "drift": [],
            "healthy": True,
        }

        for check_name, check_path in project["checks"]:
            ok, message = check_file_exists(check_path)
            project_result["checks"].append({"name": check_name, "ok": ok, "message": message})
            if not ok:
                project_result["healthy"] = False
                continue
            if project["type"] == "python" and check_path.endswith(".py"):
                syntax_ok, syntax_message = check_python_syntax(check_path)
                project_result["checks"].append(
                    {"name": f"{check_name}_syntax", "ok": syntax_ok, "message": syntax_message}
                )
                if not syntax_ok:
                    project_result["healthy"] = False

        if project.get("key_imports"):
            project_result["imports"] = check_python_imports(project["key_imports"])

        if project.get("requirements"):
            project_result["drift"] = check_dependency_drift(project["requirements"])

        if project.get("build_check"):
            build_result = check_npm_build(project["build_check"])
            project_result["checks"].append(
                {"name": "build_check", "ok": build_result["ok"], "message": build_result["message"]}
            )
            if not build_result["ok"]:
                project_result["healthy"] = False

        report["projects"].append(project_result)

    report["status_changes"] = detect_status_changes(report)
    return report


def detect_status_changes(current: dict[str, Any]) -> list[str]:
    changes: list[str] = []
    if not REPORT_HISTORY.exists():
        return changes

    try:
        previous = json.loads(REPORT_HISTORY.read_text(encoding="utf-8"))
        previous_status = {project["name"]: project["healthy"] for project in previous.get("projects", [])}
        for project in current["projects"]:
            old = previous_status.get(project["name"])
            if old is True and not project["healthy"]:
                changes.append(f"REGRESSION {project['name']}: healthy -> unhealthy")
            elif old is False and project["healthy"]:
                changes.append(f"RECOVERY {project['name']}: unhealthy -> healthy")
    except Exception:
        return changes

    return changes


def format_report(report: dict[str, Any]) -> str:
    lines = ["=" * 55, f"Health Check Report v{report['version']} @ {report['timestamp'][:19]}", "=" * 55]

    for project in report["projects"]:
        lines.extend(_format_project_lines(project))

    git_info = report.get("git", {})
    lines.append(f"\nGit dirty files: {git_info.get('uncommitted_changes', 0)}")
    lines.extend(_format_missing_env_lines(report.get("env_files", [])))
    lines.extend(_format_observability_lines(report.get("observability", [])))
    lines.extend(_format_status_change_lines(report.get("status_changes", [])))

    healthy_count = sum(1 for project in report["projects"] if project["healthy"])
    lines.append(f"\nOverall: {healthy_count}/{len(report['projects'])} projects healthy")
    return "\n".join(lines)


def _format_project_lines(project: dict[str, Any]) -> list[str]:
    status = "OK" if project["healthy"] else "FAIL"
    lines = [f"\n[{status}] {project['name']} ({project['type']})"]
    lines.extend(f"  - {check['message']}" for check in project["checks"])
    lines.extend(_format_import_lines(project.get("imports", [])))
    if project.get("drift"):
        lines.append(f"  - dependency drift: {len(project['drift'])}")
    return lines


def _format_import_lines(imports: list[dict[str, Any]]) -> list[str]:
    if not imports:
        return []
    failed_imports = [item for item in imports if not item["ok"]]
    lines = [f"  - imports: {len(imports) - len(failed_imports)}/{len(imports)} OK"]
    lines.extend(f"    * {item['message']}" for item in failed_imports)
    return lines


def _format_missing_env_lines(env_files: list[dict[str, Any]]) -> list[str]:
    missing_env = [item for item in env_files if not item["env_exists"]]
    if not missing_env:
        return []
    lines = [f"Missing .env files: {len(missing_env)}"]
    lines.extend(f"  * {item['example']}" for item in missing_env)
    return lines


def _format_status_change_lines(status_changes: list[str]) -> list[str]:
    if not status_changes:
        return []
    return ["Status changes:", *[f"  - {change}" for change in status_changes]]


def _format_observability_lines(probes: list[dict[str, Any]]) -> list[str]:
    if not probes:
        return []
    lines = ["Observability probes:"]
    for probe in probes:
        flag = "OK" if probe["ok"] else "FAIL"
        lines.append(f"  - [{flag}] {probe['name']}: {probe['message']}")
    return lines


def send_webhook(url: str, report: dict[str, Any]) -> None:
    healthy = sum(1 for project in report["projects"] if project["healthy"])
    total = len(report["projects"])
    unhealthy = [project["name"] for project in report["projects"] if not project["healthy"]]
    title = f"Health Check: {healthy}/{total} healthy"
    description = "All projects healthy" if not unhealthy else f"Issues: {', '.join(unhealthy)}"
    payload = {
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": 0x2ECC71 if not unhealthy else 0xFF6B35,
                "timestamp": report["timestamp"],
                "footer": {"text": "AI Projects Healthcheck"},
            }
        ]
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(request, timeout=10)  # nosec B310


def main() -> None:
    import argparse

    # Windows stdout UTF-8 설정
    if sys.platform == "win32":
        try:
            stdout_reconfigure = getattr(sys.stdout, "reconfigure", None)
            stderr_reconfigure = getattr(sys.stderr, "reconfigure", None)
            if callable(stdout_reconfigure) and callable(stderr_reconfigure):
                stdout_reconfigure(encoding="utf-8", errors="replace")
                stderr_reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Workspace healthcheck")
    parser.add_argument("--webhook", help="Discord/Slack webhook URL")
    parser.add_argument("--json-out", help="Path to write JSON report")
    args = parser.parse_args()

    report = run_healthcheck()
    print(format_report(report))

    REPORT_HISTORY.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON report written to {args.json_out}")

    if args.webhook:
        send_webhook(args.webhook, report)

    unhealthy = [project for project in report["projects"] if not project["healthy"]]
    raise SystemExit(1 if unhealthy else 0)


if __name__ == "__main__":
    main()
