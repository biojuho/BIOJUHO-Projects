#!/usr/bin/env python3
"""
VibeDebt Metrics Pusher

tech_debt_scanner.py가 생성한 JSON 리포트를 Prometheus Pushgateway에 전송합니다.
Grafana 대시보드가 이 메트릭을 시각화합니다.

Usage:
    # 최신 리포트를 Pushgateway에 전송
    python ops/scripts/push_debt_metrics.py

    # 특정 JSON 파일 지정
    python ops/scripts/push_debt_metrics.py --report-file var/debt/2026-03-31.json

    # Pushgateway 주소 지정 (기본: localhost:9091)
    python ops/scripts/push_debt_metrics.py --gateway http://pushgateway:9091

    # 스캔 + 즉시 푸시 (파이프라인용)
    python ops/scripts/tech_debt_scanner.py --json-out var/debt/latest.json && \
    python ops/scripts/push_debt_metrics.py --report-file var/debt/latest.json
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from workspace_paths import find_workspace_root

WORKSPACE = find_workspace_root()
DEFAULT_GATEWAY = "http://localhost:9091"
JOB_NAME = "vibedebt"


# ---------------------------------------------------------------------------
# Prometheus text format builder
# ---------------------------------------------------------------------------

def _metric(name: str, labels: dict[str, str], value: float) -> str:
    """단일 Prometheus 메트릭 텍스트 라인 생성."""
    label_str = ",".join(f'{k}="{v}"' for k, v in labels.items())
    label_part = f"{{{label_str}}}" if label_str else ""
    return f"{name}{label_part} {value}"


def build_metrics(report: dict) -> str:
    """JSON 리포트에서 Prometheus 텍스트 포맷 메트릭 문자열 생성."""
    lines: list[str] = []

    def emit(name: str, help_text: str, mtype: str, entries: list[tuple[dict, float]]) -> None:
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} {mtype}")
        for labels, value in entries:
            lines.append(_metric(name, labels, value))

    summary = report.get("summary", {})

    # --- 워크스페이스 집계 ---
    emit("vibedebt_workspace_score",
         "Workspace-level tech debt score (0=healthy, 100=critical)", "gauge",
         [({}, report.get("workspace_debt_score", 0))])

    emit("vibedebt_remediation_hours_total",
         "Total estimated remediation hours (principal debt)", "gauge",
         [({}, report.get("total_remediation_hours", 0))])

    emit("vibedebt_todo_count_total",
         "Total TODO/FIXME/HACK/XXX count across workspace", "gauge",
         [({}, summary.get("total_todo_count", 0))])

    emit("vibedebt_python_files_total",
         "Total Python files scanned", "gauge",
         [({}, summary.get("total_python_files", 0))])

    emit("vibedebt_radon_available",
         "1 if radon is available for complexity analysis, 0 if using AST fallback", "gauge",
         [({}, 1 if summary.get("radon_available") else 0)])

    # 등급 분포
    grade_dist = summary.get("grade_distribution", {})
    emit("vibedebt_grade_d_units",
         "Number of workspace units with grade D (critical debt)", "gauge",
         [({}, grade_dist.get("D", 0))])

    emit("vibedebt_grade_distribution",
         "Unit count per debt grade", "gauge",
         [
             ({"grade": "A"}, grade_dist.get("A", 0)),
             ({"grade": "B"}, grade_dist.get("B", 0)),
             ({"grade": "C"}, grade_dist.get("C", 0)),
             ({"grade": "D"}, grade_dist.get("D", 0)),
         ])

    # --- 프로젝트별 메트릭 ---
    units = report.get("units", [])

    unit_score_entries: list[tuple[dict, float]] = []
    unit_cc_entries: list[tuple[dict, float]] = []
    unit_todo_entries: list[tuple[dict, float]] = []
    unit_type_entries: list[tuple[dict, float]] = []
    unit_dup_entries: list[tuple[dict, float]] = []
    unit_high_cc_entries: list[tuple[dict, float]] = []
    unit_lines_entries: list[tuple[dict, float]] = []

    for unit in units:
        if unit.get("python_files", 0) == 0:
            continue
        uid = unit["unit_id"]
        lbl = {"unit_id": uid}
        unit_score_entries.append((lbl, unit.get("debt_score", 0)))
        unit_cc_entries.append((lbl, unit.get("avg_complexity", 0)))
        unit_todo_entries.append((lbl, unit.get("todo_count", 0)))
        unit_type_entries.append((lbl, unit.get("type_annotation_ratio", 0)))
        unit_dup_entries.append((lbl, unit.get("duplication_ratio", 0)))
        unit_high_cc_entries.append((lbl, len(unit.get("high_complexity_functions", []))))
        unit_lines_entries.append((lbl, unit.get("total_lines", 0)))

    if unit_score_entries:
        emit("vibedebt_unit_score", "Per-unit debt score", "gauge", unit_score_entries)
        emit("vibedebt_unit_avg_complexity", "Per-unit average cyclomatic complexity", "gauge", unit_cc_entries)
        emit("vibedebt_unit_todo_count", "Per-unit TODO/FIXME count", "gauge", unit_todo_entries)
        emit("vibedebt_unit_type_annotation_ratio", "Per-unit function return type annotation ratio (0-1)", "gauge", unit_type_entries)
        emit("vibedebt_unit_duplication_ratio", "Per-unit code duplication ratio (0-1)", "gauge", unit_dup_entries)
        emit("vibedebt_unit_high_complexity_count", "Per-unit high-complexity function count (CC>10)", "gauge", unit_high_cc_entries)
        emit("vibedebt_unit_lines", "Per-unit total Python lines", "gauge", unit_lines_entries)

    # 집계용 요약
    if unit_dup_entries:
        avg_dup = sum(v for _, v in unit_dup_entries) / len(unit_dup_entries)
        emit("vibedebt_duplication_ratio_avg", "Average duplication ratio across workspace units", "gauge",
             [({}, avg_dup)])

    total_high_cc = sum(v for _, v in unit_high_cc_entries)
    emit("vibedebt_high_complexity_functions_total", "Total high-complexity functions (CC>10) in workspace", "gauge",
         [({}, total_high_cc)])

    # 이자 비용 추정 (주간 디버깅 오버헤드 = 총 부채점수 / 20 × 1h)
    ws_score = report.get("workspace_debt_score", 0)
    weekly_interest = round(ws_score / 20, 1)  # 단순 추정
    emit("vibedebt_weekly_interest_hours", "Estimated weekly interest cost (extra debugging/context hours)", "gauge",
         [({}, weekly_interest)])

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Pushgateway client
# ---------------------------------------------------------------------------

def push_to_gateway(metrics_text: str, gateway: str, job: str = JOB_NAME) -> bool:
    """Prometheus Pushgateway에 PUT 요청으로 메트릭 전송."""
    url = f"{gateway.rstrip('/')}/metrics/job/{job}"
    data = metrics_text.encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="PUT",
        headers={"Content-Type": "text/plain; version=0.0.4; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 202)
    except urllib.error.URLError as exc:
        print(f"⚠️  Pushgateway 연결 실패: {exc}", file=sys.stderr)
        return False


def find_latest_report() -> Path | None:
    """var/debt/ 디렉토리에서 가장 최근 JSON 파일 반환."""
    debt_dir = WORKSPACE / "var" / "debt"
    if not debt_dir.exists():
        return None
    reports = sorted(debt_dir.glob("*.json"), reverse=True)
    return reports[0] if reports else None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="VibeDebt 메트릭 Pushgateway 전송")
    parser.add_argument("--report-file", metavar="PATH",
                        help="사용할 JSON 리포트 경로 (미지정 시 var/debt/ 최신 파일)")
    parser.add_argument("--gateway", default=DEFAULT_GATEWAY,
                        help=f"Prometheus Pushgateway 주소 (기본: {DEFAULT_GATEWAY})")
    parser.add_argument("--dry-run", action="store_true",
                        help="메트릭 텍스트만 출력하고 실제 전송 안 함")
    args = parser.parse_args()

    # 리포트 파일 결정
    if args.report_file:
        report_path = Path(args.report_file)
    else:
        report_path = find_latest_report()

    if not report_path or not report_path.exists():
        print("[ERROR] 리포트 파일을 찾을 수 없습니다.", file=sys.stderr)
        print("   먼저 실행하세요: python ops/scripts/tech_debt_scanner.py --json-out var/debt/latest.json",
              file=sys.stderr)
        return 1

    print(f"[INFO] 리포트: {report_path}", file=sys.stderr)

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[ERROR] JSON 파싱 실패: {exc}", file=sys.stderr)
        return 1

    metrics_text = build_metrics(report)

    if args.dry_run:
        print(metrics_text)
        print("(dry-run: Pushgateway 전송 생략)", file=sys.stderr)
        return 0

    print(f"[INFO] Pushgateway: {args.gateway}", file=sys.stderr)
    success = push_to_gateway(metrics_text, args.gateway)

    if success:
        ws_score = report.get("workspace_debt_score", "?")
        ws_grade = report.get("workspace_grade", "?")
        print(f"[OK] 메트릭 전송 완료 - Score: {ws_score}, Grade: {ws_grade}", file=sys.stderr)
        return 0
    else:
        print("[ERROR] Pushgateway 전송 실패. --dry-run 옵션으로 메트릭 내용을 확인하세요.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
