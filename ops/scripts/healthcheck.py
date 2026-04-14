#!/usr/bin/env python3
from __future__ import annotations

import importlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from workspace_paths import find_workspace_root, rel_unit_path

WORKSPACE = find_workspace_root()
REPORT_HISTORY = SCRIPT_DIR / ".healthcheck-history.json"

CHECKS = [
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
        "checks": [("server", rel_unit_path("dailynews", "server.py"))],
        "key_imports": ["notion_client"],
        "requirements": None,
    },
    {
        "name": "desci-backend",
        "type": "python",
        "checks": [
            ("main", rel_unit_path("desci-platform", "biolinker", "main.py")),
            ("packaging", rel_unit_path("desci-platform", "biolinker", "pyproject.toml")),
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
        "build_check": rel_unit_path("agriguard", "frontend"),
    },
]


def check_file_exists(rel_path: str) -> tuple[bool, str]:
    full = WORKSPACE / rel_path
    if full.exists():
        return True, f"OK {rel_path}"
    return False, f"MISSING {rel_path}"


def check_git_status() -> dict:
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


def check_env_files() -> list[dict]:
    results = []
    for example in WORKSPACE.rglob(".env.example"):
        env_file = example.parent / ".env"
        rel = example.relative_to(WORKSPACE)
        results.append({"example": str(rel), "env_exists": env_file.exists()})
    return results


def check_python_imports(packages: list[str]) -> list[dict]:
    results = []
    for package in packages:
        try:
            importlib.import_module(package)
            results.append({"package": package, "ok": True, "message": f"OK {package}"})
        except ImportError as exc:
            results.append({"package": package, "ok": False, "message": f"MISSING {package}: {exc}"})
    return results


def check_dependency_drift(req_path: str) -> list[dict]:
    results = []
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
        installed: dict[str, str] = {}
        if proc.returncode == 0:
            for package in json.loads(proc.stdout):
                installed[package["name"].lower().replace("-", "_")] = package["version"]

        for line in full_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            match = re.match(r"^([a-zA-Z0-9_-]+)", line)
            if not match:
                continue
            package_name = match.group(1).lower().replace("-", "_")
            req_version = re.search(r"==([0-9.]+)", line)
            if package_name in installed and req_version:
                installed_major = installed[package_name].split(".")[0]
                required_major = req_version.group(1).split(".")[0]
                if installed_major != required_major:
                    results.append(
                        {
                            "package": package_name,
                            "required": req_version.group(1),
                            "installed": installed[package_name],
                            "drift": "MAJOR",
                        }
                    )
            elif package_name not in installed:
                results.append(
                    {
                        "package": package_name,
                        "required": req_version.group(1) if req_version else "any",
                        "installed": "NOT FOUND",
                        "drift": "MISSING",
                    }
                )
    except Exception:
        return results

    return results


def check_npm_build(rel_path: str) -> dict:
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


def run_healthcheck() -> dict:
    report = {
        "timestamp": datetime.now().isoformat(),
        "version": "3.0",
        "workspace": str(WORKSPACE),
        "projects": [],
        "git": check_git_status(),
        "env_files": check_env_files(),
    }

    for project in CHECKS:
        project_result = {
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


def detect_status_changes(current: dict) -> list[str]:
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


def format_report(report: dict) -> str:
    lines = ["=" * 55, f"Health Check Report v{report['version']} @ {report['timestamp'][:19]}", "=" * 55]

    for project in report["projects"]:
        status = "OK" if project["healthy"] else "FAIL"
        lines.append(f"\n[{status}] {project['name']} ({project['type']})")
        for check in project["checks"]:
            lines.append(f"  - {check['message']}")
        if project["imports"]:
            failed_imports = [item for item in project["imports"] if not item["ok"]]
            lines.append(f"  - imports: {len(project['imports']) - len(failed_imports)}/{len(project['imports'])} OK")
        if project["drift"]:
            lines.append(f"  - dependency drift: {len(project['drift'])}")

    git_info = report.get("git", {})
    lines.append(f"\nGit dirty files: {git_info.get('uncommitted_changes', 0)}")
    missing_env = [item for item in report.get("env_files", []) if not item["env_exists"]]
    if missing_env:
        lines.append(f"Missing .env files: {len(missing_env)}")
    if report.get("status_changes"):
        lines.append("Status changes:")
        lines.extend([f"  - {change}" for change in report["status_changes"]])

    healthy_count = sum(1 for project in report["projects"] if project["healthy"])
    lines.append(f"\nOverall: {healthy_count}/{len(report['projects'])} projects healthy")
    return "\n".join(lines)


def send_webhook(url: str, report: dict) -> None:
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
    urllib.request.urlopen(request, timeout=10)


def main() -> None:
    import argparse

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
