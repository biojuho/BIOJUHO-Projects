"""
프로젝트 헬스체크 & 알림 스크립트 (v2.0)
각 프로젝트의 핵심 상태를 점검하고 결과를 JSON + 콘솔 리포트로 출력합니다.

v2.0 추가 기능:
  - Python 핵심 패키지 import 검증
  - requirements.txt vs 실제 설치 버전 drift 감지
  - 이전 리포트 대비 상태 변화 추적

사용법:
    python scripts/healthcheck.py
    python scripts/healthcheck.py --webhook DISCORD_WEBHOOK_URL
    python scripts/healthcheck.py --json-out health-report.json
"""

import importlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
REPORT_HISTORY = WORKSPACE / "scripts" / ".healthcheck-history.json"

# ─── 프로젝트별 헬스체크 정의 ─────────────────────────
CHECKS = [
    {
        "name": "getdaytrends",
        "type": "python",
        "checks": [
            ("config", "getdaytrends/config.py"),
            ("main", "getdaytrends/main.py"),
            ("db_dir", "getdaytrends/data"),
        ],
        "key_imports": ["anthropic", "httpx", "aiosqlite"],
        "requirements": "getdaytrends/requirements.txt",
    },
    {
        "name": "DailyNews",
        "type": "python",
        "checks": [
            ("server", "DailyNews/server.py"),
            ("config", "DailyNews/config"),
        ],
        "key_imports": ["notion_client"],
        "requirements": None,
    },
    {
        "name": "desci-backend",
        "type": "python",
        "checks": [
            ("main", "desci-platform/biolinker/main.py"),
            ("requirements", "desci-platform/biolinker/requirements.txt"),
        ],
        "key_imports": ["fastapi", "uvicorn"],
        "requirements": "desci-platform/biolinker/requirements.txt",
    },
    {
        "name": "desci-frontend",
        "type": "node",
        "checks": [
            ("package", "desci-platform/frontend/package.json"),
            ("src", "desci-platform/frontend/src"),
        ],
        "key_imports": [],
        "requirements": None,
    },
    {
        "name": "AgriGuard-backend",
        "type": "python",
        "checks": [
            ("main", "AgriGuard/backend/main.py"),
            ("requirements", "AgriGuard/backend/requirements.txt"),
        ],
        "key_imports": ["fastapi", "sqlalchemy"],
        "requirements": "AgriGuard/backend/requirements.txt",
    },
    {
        "name": "AgriGuard-frontend",
        "type": "node",
        "checks": [
            ("package", "AgriGuard/frontend/package.json"),
            ("src", "AgriGuard/frontend/src"),
        ],
        "key_imports": [],
        "requirements": None,
        "build_check": "AgriGuard/frontend",
    },
]


def check_file_exists(rel_path: str) -> tuple[bool, str]:
    full = WORKSPACE / rel_path
    if full.exists():
        return True, f"✅ {rel_path}"
    return False, f"❌ {rel_path} 없음"


def check_git_status() -> dict:
    """워크스페이스 Git 상태 요약."""
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True, text=True, cwd=WORKSPACE, timeout=10
        )
        lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
        return {
            "uncommitted_changes": len(lines),
            "files": lines[:10],
        }
    except Exception as e:
        return {"error": str(e)}


def check_env_files() -> list[dict]:
    """모든 .env.example 파일이 대응하는 .env를 가지고 있는지 확인."""
    results = []
    for example in WORKSPACE.rglob(".env.example"):
        env_file = example.parent / ".env"
        rel = example.relative_to(WORKSPACE)
        results.append({
            "example": str(rel),
            "env_exists": env_file.exists(),
        })
    return results


def check_python_imports(packages: list[str]) -> list[dict]:
    """핵심 Python 패키지 import 가능 여부 확인."""
    results = []
    for pkg in packages:
        try:
            importlib.import_module(pkg)
            results.append({"package": pkg, "ok": True, "message": f"✅ {pkg}"})
        except ImportError as e:
            results.append({"package": pkg, "ok": False, "message": f"❌ {pkg}: {e}"})
    return results


def check_dependency_drift(req_path: str) -> list[dict]:
    """requirements.txt의 핵심 패키지 vs 실제 설치 버전 비교."""
    results = []
    full_path = WORKSPACE / req_path
    if not full_path.exists():
        return results

    try:
        # 설치된 패키지 목록
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=json"],
            capture_output=True, text=True, timeout=15
        )
        installed = {}
        if proc.returncode == 0:
            for pkg in json.loads(proc.stdout):
                installed[pkg["name"].lower().replace("-", "_")] = pkg["version"]

        # requirements.txt 파싱
        for line in full_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            # 패키지명 추출 (버전 지정자 제거)
            match = re.match(r"^([a-zA-Z0-9_-]+)", line)
            if not match:
                continue
            pkg_name = match.group(1).lower().replace("-", "_")
            req_version = re.search(r"==([0-9.]+)", line)

            if pkg_name in installed:
                inst_ver = installed[pkg_name]
                if req_version:
                    req_ver = req_version.group(1)
                    # major 버전 비교
                    inst_major = inst_ver.split(".")[0]
                    req_major = req_ver.split(".")[0]
                    if inst_major != req_major:
                        results.append({
                            "package": pkg_name,
                            "required": req_ver,
                            "installed": inst_ver,
                            "drift": "MAJOR",
                        })
            else:
                results.append({
                    "package": pkg_name,
                    "required": req_version.group(1) if req_version else "any",
                    "installed": "NOT FOUND",
                    "drift": "MISSING",
                })
    except Exception:
        pass

    return results


def check_npm_build(rel_path: str) -> dict:
    """프론트엔드 빌드 건전성(Sanity Check) 검증 (Dry-run)."""
    full_path = WORKSPACE / rel_path
    if not full_path.exists():
        return {"ok": False, "message": f"❌ {rel_path} 없음"}

    try:
        npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
        # package.json에 선언된 build:dry 태스크 실행
        proc = subprocess.run(
            [npm_cmd, "run", "build:dry"],
            cwd=full_path, capture_output=True, text=True, timeout=45
        )
        if proc.returncode == 0:
            return {"ok": True, "message": f"✅ 빌드 체크 성공"}
        else:
            err_msg = ""
            for line in proc.stderr.splitlines():
                if "error" in line.lower() or "failed" in line.lower():
                    err_msg = line.strip()
                    break
            if not err_msg:
                err_msg = "빌드 실패 (원인 불분명)"
            return {"ok": False, "message": f"❌ 빌드 체크 실패: {err_msg}"}
    except Exception as e:
        return {"ok": False, "message": f"❌ 빌드 체크 오류: {e}"}


def run_healthcheck() -> dict:
    """전체 헬스체크 실행."""
    report = {
        "timestamp": datetime.now().isoformat(),
        "version": "2.0",
        "workspace": str(WORKSPACE),
        "projects": [],
        "git": check_git_status(),
        "env_files": check_env_files(),
    }

    for project in CHECKS:
        proj_result = {
            "name": project["name"],
            "type": project["type"],
            "checks": [],
            "imports": [],
            "drift": [],
            "healthy": True,
        }

        # 파일 존재 검사
        for check_name, check_path in project["checks"]:
            ok, msg = check_file_exists(check_path)
            proj_result["checks"].append({
                "name": check_name,
                "ok": ok,
                "message": msg,
            })
            if not ok:
                proj_result["healthy"] = False

        # Python import 검증
        if project.get("key_imports"):
            proj_result["imports"] = check_python_imports(project["key_imports"])

        # 의존성 drift 감지
        if project.get("requirements"):
            proj_result["drift"] = check_dependency_drift(project["requirements"])

        # 프론트엔드 빌드 체크
        if project.get("build_check"):
            b_res = check_npm_build(project["build_check"])
            proj_result["checks"].append({
                "name": "build_check",
                "ok": b_res["ok"],
                "message": b_res["message"]
            })
            if not b_res["ok"]:
                proj_result["healthy"] = False

        report["projects"].append(proj_result)

    # 이전 리포트와 비교
    report["status_changes"] = _detect_status_changes(report)

    return report


def _detect_status_changes(current: dict) -> list[str]:
    """이전 리포트 대비 상태 변화 감지."""
    changes = []
    if not REPORT_HISTORY.exists():
        return changes

    try:
        prev = json.loads(REPORT_HISTORY.read_text(encoding="utf-8"))
        prev_health = {p["name"]: p["healthy"] for p in prev.get("projects", [])}
        for proj in current["projects"]:
            name = proj["name"]
            if name in prev_health:
                if prev_health[name] and not proj["healthy"]:
                    changes.append(f"⚠️ {name}: healthy → UNHEALTHY")
                elif not prev_health[name] and proj["healthy"]:
                    changes.append(f"🎉 {name}: unhealthy → HEALTHY")
    except Exception:
        pass
    return changes


def format_report(report: dict) -> str:
    """콘솔 출력용 포맷."""
    lines = []
    lines.append("=" * 55)
    lines.append(f"🏥 Health Check Report v{report.get('version', '1.0')} — {report['timestamp'][:19]}")
    lines.append("=" * 55)

    for proj in report["projects"]:
        status = "✅" if proj["healthy"] else "❌"
        lines.append(f"\n{status} {proj['name']} ({proj['type']})")
        for check in proj["checks"]:
            lines.append(f"   {check['message']}")

        # Import 결과
        if proj.get("imports"):
            failed = [i for i in proj["imports"] if not i["ok"]]
            if failed:
                lines.append(f"   📦 Import 실패: {len(failed)}건")
                for f in failed:
                    lines.append(f"      {f['message']}")
            else:
                lines.append(f"   📦 핵심 패키지 import: {len(proj['imports'])}건 모두 OK")

        # Drift 결과
        if proj.get("drift"):
            lines.append(f"   📐 의존성 drift: {len(proj['drift'])}건")
            for d in proj["drift"][:3]:
                lines.append(f"      ⚠️ {d['package']}: req={d['required']} → installed={d['installed']} ({d['drift']})")

    # Git 상태
    git = report.get("git", {})
    changes = git.get("uncommitted_changes", 0)
    lines.append(f"\n📦 Git: {changes} uncommitted change(s)")

    # Env 상태
    env_files = report.get("env_files", [])
    missing = [e for e in env_files if not e["env_exists"]]
    if missing:
        lines.append(f"\n⚠️ {len(missing)} .env file(s) missing:")
        for m in missing[:5]:
            lines.append(f"   - {m['example']} → .env 없음")

    # 상태 변화
    if report.get("status_changes"):
        lines.append("\n🔄 상태 변화 감지:")
        for ch in report["status_changes"]:
            lines.append(f"   {ch}")

    lines.append("\n" + "=" * 55)

    healthy_count = sum(1 for p in report["projects"] if p["healthy"])
    total = len(report["projects"])
    lines.append(f"Overall: {healthy_count}/{total} projects healthy")

    return "\n".join(lines)


def send_webhook(url: str, report: dict):
    """Discord/Slack Webhook으로 알림 전송."""
    healthy = sum(1 for p in report["projects"] if p["healthy"])
    total = len(report["projects"])
    unhealthy = [p["name"] for p in report["projects"] if not p["healthy"]]

    if unhealthy:
        title = f"⚠️ Health Check: {healthy}/{total} healthy"
        color = 0xFF6B35
        desc = f"문제 프로젝트: {', '.join(unhealthy)}"
    else:
        title = f"✅ Health Check: {total}/{total} all healthy"
        color = 0x2ECC71
        desc = "모든 프로젝트 정상"

    payload = {
        "embeds": [{
            "title": title,
            "description": desc,
            "color": color,
            "timestamp": report["timestamp"],
            "footer": {"text": "AI Projects Healthcheck v2"},
        }]
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        print("📤 Webhook 알림 전송 완료")
    except Exception as e:
        print(f"⚠️ Webhook 전송 실패: {e}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="프로젝트 헬스체크 v2")
    parser.add_argument("--webhook", help="Discord/Slack Webhook URL")
    parser.add_argument("--json-out", help="JSON 리포트 출력 경로")
    args = parser.parse_args()

    report = run_healthcheck()
    print(format_report(report))

    # 히스토리 저장 (다음 실행 시 상태 변화 비교용)
    try:
        REPORT_HISTORY.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n📄 JSON 리포트 저장: {args.json_out}")

    if args.webhook:
        send_webhook(args.webhook, report)

    unhealthy = [p for p in report["projects"] if not p["healthy"]]
    sys.exit(1 if unhealthy else 0)


if __name__ == "__main__":
    main()
