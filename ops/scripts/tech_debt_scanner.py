#!/usr/bin/env python3
"""
VibeDebt Scanner -기술 부채 자동 진단 CLI

기존 healthcheck.py / run_workspace_smoke.py 패턴을 따르는 워크스페이스 부채 측정 도구.
radon(복잡도), TODO/FIXME 밀도, 코드 중복, 타입 어노테이션 비율을 종합해
프로젝트별 Debt Score와 TDR을 산출합니다.

Usage:
    python ops/scripts/tech_debt_scanner.py
    python ops/scripts/tech_debt_scanner.py --unit dailynews
    python ops/scripts/tech_debt_scanner.py --json-out var/debt/2026-03-31.json
    python ops/scripts/tech_debt_scanner.py --fail-on-grade C
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from workspace_paths import find_workspace_root, iter_active_units

WORKSPACE = find_workspace_root()

EXCLUDE_DIRS = {
    ".venv", "venv", "__pycache__", "node_modules", ".git",
    "archive", "var", "output", "dist", "build", ".next",
}

# 부채 등급 임계값 (Debt Score 0-100, 낮을수록 건강)
GRADE_THRESHOLDS = {"A": 15, "B": 30, "C": 50, "D": 101}

# 가중치
WEIGHT_COMPLEXITY = 0.30
WEIGHT_COVERAGE_GAP = 0.25
WEIGHT_DUPLICATION = 0.20
WEIGHT_TODO_DENSITY = 0.15
WEIGHT_TYPE_SAFETY = 0.10

# 복잡도 임계값
CC_WARN = 10   # warning
CC_CRIT = 15   # critical


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FunctionMetric:
    name: str
    file: str
    line: int
    complexity: int


@dataclass
class UnitDebtReport:
    unit_id: str
    unit_path: str
    python_files: int
    total_lines: int
    # complexity
    avg_complexity: float
    max_complexity: int
    high_complexity_functions: list[FunctionMetric]  # CC > CC_WARN
    # duplication
    duplicate_block_count: int
    duplication_ratio: float  # 0.0 ~ 1.0
    # todos
    todo_count: int
    todo_density: float  # per 1000 LOC
    # type annotations
    annotated_functions: int
    total_functions: int
    type_annotation_ratio: float  # 0.0 ~ 1.0
    # score
    debt_score: float  # 0-100
    grade: str  # A/B/C/D
    estimated_remediation_hours: float
    errors: list[str] = field(default_factory=list)


@dataclass
class WorkspaceDebtReport:
    generated_at: str
    workspace_root: str
    units: list[UnitDebtReport]
    workspace_debt_score: float
    workspace_grade: str
    total_remediation_hours: float
    summary: dict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def collect_python_files(root: Path) -> list[Path]:
    """워크스페이스 유닛 내 Python 파일 수집 (제외 디렉토리 스킵)."""
    files: list[Path] = []
    for path in root.rglob("*.py"):
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def count_lines(files: list[Path]) -> int:
    total = 0
    for f in files:
        try:
            total += sum(1 for _ in f.open(encoding="utf-8", errors="replace"))
        except OSError:
            pass
    return total


# ---------------------------------------------------------------------------
# Complexity analysis (radon 우선, fallback to ast-based)
# ---------------------------------------------------------------------------

def _radon_available() -> bool:
    try:
        import importlib.util
        return importlib.util.find_spec("radon") is not None
    except Exception:
        return False


def analyze_complexity_radon(files: list[Path]) -> list[FunctionMetric]:
    """radon cc를 subprocess로 호출해 함수별 복잡도 수집."""
    if not files:
        return []
    metrics: list[FunctionMetric] = []
    try:
        result = subprocess.run(
            [sys.executable, "-m", "radon", "cc", "--json", "-s", "--",
             *[str(f) for f in files]],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        data = json.loads(result.stdout)
        for filepath, blocks in data.items():
            for block in blocks:
                if block.get("type") in ("function", "method"):
                    metrics.append(FunctionMetric(
                        name=block["name"],
                        file=filepath,
                        line=block["lineno"],
                        complexity=block["complexity"],
                    ))
    except Exception:
        pass
    return metrics


def analyze_complexity_ast(files: list[Path]) -> list[FunctionMetric]:
    """radon 없을 때: AST 기반 단순 복잡도 근사 (분기 수 카운팅)."""
    metrics: list[FunctionMetric] = []
    branch_nodes = (
        ast.If, ast.For, ast.While, ast.ExceptHandler,
        ast.With, ast.Assert, ast.comprehension,
    )
    for filepath in files:
        try:
            tree = ast.parse(filepath.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                cc = 1 + sum(
                    1 for child in ast.walk(node)
                    if isinstance(child, branch_nodes)
                )
                metrics.append(FunctionMetric(
                    name=node.name,
                    file=str(filepath),
                    line=node.lineno,
                    complexity=cc,
                ))
    return metrics


def analyze_complexity(files: list[Path]) -> list[FunctionMetric]:
    if _radon_available():
        result = analyze_complexity_radon(files)
        if result:
            return result
    return analyze_complexity_ast(files)


# ---------------------------------------------------------------------------
# Duplication detection (5-line sliding window hash)
# ---------------------------------------------------------------------------

def analyze_duplication(files: list[Path], window: int = 5) -> tuple[int, float]:
    """5줄 슬라이딩 윈도우 해시로 중복 블록 탐지."""
    seen: dict[str, int] = {}
    duplicates = 0
    total_blocks = 0

    for filepath in files:
        try:
            lines = filepath.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        # 공백/주석 정규화
        norm = [re.sub(r"\s+", " ", ln.split("#")[0]).strip() for ln in lines]
        norm = [ln for ln in norm if ln]

        for i in range(len(norm) - window + 1):
            block = "\n".join(norm[i: i + window])
            digest = hashlib.md5(block.encode()).hexdigest()
            total_blocks += 1
            if digest in seen:
                duplicates += 1
            else:
                seen[digest] = i

    ratio = duplicates / total_blocks if total_blocks else 0.0
    return duplicates, ratio


# ---------------------------------------------------------------------------
# TODO/FIXME density
# ---------------------------------------------------------------------------

def analyze_todos(files: list[Path], total_lines: int) -> tuple[int, float]:
    """TODO / FIXME / HACK / XXX 카운트 + 1000 LOC 당 밀도."""
    pattern = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)
    count = 0
    for filepath in files:
        try:
            text = filepath.read_text(encoding="utf-8", errors="replace")
            count += len(pattern.findall(text))
        except OSError:
            pass
    density = (count / total_lines * 1000) if total_lines else 0.0
    return count, density


# ---------------------------------------------------------------------------
# Type annotation ratio
# ---------------------------------------------------------------------------

def analyze_type_annotations(files: list[Path]) -> tuple[int, int]:
    """함수 중 반환 타입 어노테이션이 있는 비율."""
    annotated = total = 0
    for filepath in files:
        try:
            tree = ast.parse(filepath.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                total += 1
                if node.returns is not None:
                    annotated += 1
    return annotated, total


# ---------------------------------------------------------------------------
# Debt score calculation
# ---------------------------------------------------------------------------

def compute_debt_score(
    avg_complexity: float,
    coverage_pct: float,
    duplication_ratio: float,
    todo_density: float,
    type_annotation_ratio: float,
) -> float:
    """가중 합산 부채 점수 (0-100, 낮을수록 건강)."""
    # 각 지표를 0-1 위반 비율로 정규화
    complexity_violation = min(max(avg_complexity - 5, 0) / 20, 1.0)  # 5~25 범위 정규화
    coverage_gap = max(0.0, 1.0 - coverage_pct / 100.0)
    dup_norm = min(duplication_ratio * 10, 1.0)  # 10% 중복 = 최대
    todo_norm = min(todo_density / 10.0, 1.0)   # 10/1000 LOC = 최대
    type_gap = max(0.0, 1.0 - type_annotation_ratio)

    raw = (
        WEIGHT_COMPLEXITY * complexity_violation
        + WEIGHT_COVERAGE_GAP * coverage_gap
        + WEIGHT_DUPLICATION * dup_norm
        + WEIGHT_TODO_DENSITY * todo_norm
        + WEIGHT_TYPE_SAFETY * type_gap
    )
    return round(raw * 100, 1)


def score_to_grade(score: float) -> str:
    for grade, threshold in GRADE_THRESHOLDS.items():
        if score < threshold:
            return grade
    return "D"


def estimate_remediation_hours(
    high_cc_functions: int,
    todo_count: int,
    unannotated_functions: int,
) -> float:
    """원금(Principal) 추정 -수정에 필요한 총 인시."""
    return round(
        high_cc_functions * 0.5    # 고복잡도 함수당 30분
        + todo_count * 1.0          # TODO 항목당 1시간
        + unannotated_functions * 0.25  # 타입 미비 함수당 15분
    , 1)


# ---------------------------------------------------------------------------
# Per-unit scan
# ---------------------------------------------------------------------------

def scan_unit(unit: dict, coverage_map: dict[str, float]) -> UnitDebtReport:
    unit_id = unit["id"]
    unit_root = WORKSPACE / unit["canonical_path"]
    errors: list[str] = []

    if not unit_root.exists():
        return UnitDebtReport(
            unit_id=unit_id, unit_path=str(unit_root),
            python_files=0, total_lines=0,
            avg_complexity=0, max_complexity=0, high_complexity_functions=[],
            duplicate_block_count=0, duplication_ratio=0,
            todo_count=0, todo_density=0,
            annotated_functions=0, total_functions=0, type_annotation_ratio=0,
            debt_score=0, grade="A", estimated_remediation_hours=0,
            errors=[f"Unit path not found: {unit_root}"],
        )

    files = collect_python_files(unit_root)
    if not files:
        return UnitDebtReport(
            unit_id=unit_id, unit_path=str(unit_root),
            python_files=0, total_lines=0,
            avg_complexity=0, max_complexity=0, high_complexity_functions=[],
            duplicate_block_count=0, duplication_ratio=0,
            todo_count=0, todo_density=0,
            annotated_functions=0, total_functions=0, type_annotation_ratio=0,
            debt_score=0, grade="A", estimated_remediation_hours=0,
            errors=["No Python files found (may be a JS/TS-only unit)"],
        )

    total_lines = count_lines(files)

    # Complexity
    all_metrics = analyze_complexity(files)
    if all_metrics:
        avg_cc = sum(m.complexity for m in all_metrics) / len(all_metrics)
        max_cc = max(m.complexity for m in all_metrics)
    else:
        avg_cc = max_cc = 0.0
    high_cc = [m for m in all_metrics if m.complexity > CC_WARN]

    # Duplication
    dup_count, dup_ratio = analyze_duplication(files)

    # TODO density
    todo_count, todo_density = analyze_todos(files, total_lines)

    # Type annotations
    annotated, total_funcs = analyze_type_annotations(files)
    type_ratio = annotated / total_funcs if total_funcs else 1.0

    # Coverage (외부 map에서 조회, 없으면 0%)
    coverage_pct = coverage_map.get(unit_id, 0.0)

    # Score
    score = compute_debt_score(avg_cc, coverage_pct, dup_ratio, todo_density, type_ratio)
    grade = score_to_grade(score)

    unannotated = total_funcs - annotated
    remediation_h = estimate_remediation_hours(len(high_cc), todo_count, unannotated)

    return UnitDebtReport(
        unit_id=unit_id,
        unit_path=str(unit_root.relative_to(WORKSPACE)),
        python_files=len(files),
        total_lines=total_lines,
        avg_complexity=round(avg_cc, 2),
        max_complexity=int(max_cc),
        high_complexity_functions=high_cc,
        duplicate_block_count=dup_count,
        duplication_ratio=round(dup_ratio, 4),
        todo_count=todo_count,
        todo_density=round(todo_density, 2),
        annotated_functions=annotated,
        total_functions=total_funcs,
        type_annotation_ratio=round(type_ratio, 4),
        debt_score=score,
        grade=grade,
        estimated_remediation_hours=remediation_h,
        errors=errors,
    )


# ---------------------------------------------------------------------------
# Workspace-level aggregation
# ---------------------------------------------------------------------------

def build_workspace_report(
    unit_reports: list[UnitDebtReport],
) -> WorkspaceDebtReport:
    valid = [r for r in unit_reports if r.python_files > 0]
    if valid:
        ws_score = round(sum(r.debt_score for r in valid) / len(valid), 1)
    else:
        ws_score = 0.0

    ws_grade = score_to_grade(ws_score)
    total_hours = round(sum(r.estimated_remediation_hours for r in unit_reports), 1)

    # 등급 분포
    grade_dist: dict[str, int] = {"A": 0, "B": 0, "C": 0, "D": 0}
    for r in unit_reports:
        grade_dist[r.grade] = grade_dist.get(r.grade, 0) + 1

    worst = sorted(valid, key=lambda r: r.debt_score, reverse=True)[:3]

    summary = {
        "total_units_scanned": len(unit_reports),
        "python_units": len(valid),
        "grade_distribution": grade_dist,
        "top_3_worst": [r.unit_id for r in worst],
        "total_python_files": sum(r.python_files for r in unit_reports),
        "total_lines": sum(r.total_lines for r in unit_reports),
        "total_todo_count": sum(r.todo_count for r in unit_reports),
        "radon_available": _radon_available(),
    }

    return WorkspaceDebtReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        workspace_root=str(WORKSPACE),
        units=unit_reports,
        workspace_debt_score=ws_score,
        workspace_grade=ws_grade,
        total_remediation_hours=total_hours,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

GRADE_COLOR = {"A": "\033[92m", "B": "\033[93m", "C": "\033[33m", "D": "\033[91m"}
RESET = "\033[0m"


def grade_colored(grade: str) -> str:
    return f"{GRADE_COLOR.get(grade, '')}{grade}{RESET}"


def print_report(report: WorkspaceDebtReport, verbose: bool = False) -> None:
    ws = report
    print(f"\n{'='*64}")
    print(f"  VibeDebt Scanner - {ws.generated_at[:10]}")
    print(f"  Workspace Score: {ws.workspace_debt_score:.1f}  Grade: {grade_colored(ws.workspace_grade)}")
    print(f"  Estimated Remediation: {ws.total_remediation_hours:.1f}h")
    print(f"{'='*64}")

    print(f"\n{'Unit':<24} {'Files':>5} {'Lines':>6} {'Score':>6} {'Grade':>6} {'CC Avg':>7} {'TODO':>5} {'Est.h':>6}")
    print("-" * 72)

    for r in sorted(ws.units, key=lambda x: x.debt_score, reverse=True):
        if r.python_files == 0:
            continue
        print(
            f"{r.unit_id:<24} {r.python_files:>5} {r.total_lines:>6} "
            f"{r.debt_score:>6.1f} {grade_colored(r.grade):>14} "
            f"{r.avg_complexity:>7.1f} {r.todo_count:>5} {r.estimated_remediation_hours:>6.1f}"
        )

    if verbose:
        print(f"\n{'--- High Complexity Functions (CC > ' + str(CC_WARN) + ') ---'}")
        for r in ws.units:
            for fn in r.high_complexity_functions:
                rel = Path(fn.file).name
                flag = " [CRITICAL]" if fn.complexity > CC_CRIT else ""
                print(f"  [{r.unit_id}] {fn.name} (CC={fn.complexity}) @ {rel}:{fn.line}{flag}")

    print(f"\nGrade distribution: {ws.summary['grade_distribution']}")
    if ws.summary["top_3_worst"]:
        print(f"Worst units: {', '.join(ws.summary['top_3_worst'])}")
    if not ws.summary["radon_available"]:
        print("\n[WARN] radon not installed - using AST-based complexity (less accurate).")
        print("   Run: pip install radon  for full analysis.")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="VibeDebt Scanner -기술 부채 자동 진단")
    parser.add_argument("--unit", help="특정 unit ID만 스캔 (미지정 시 전체)")
    parser.add_argument("--json-out", metavar="PATH", help="JSON 리포트 출력 경로")
    parser.add_argument("--fail-on-grade", metavar="GRADE", choices=["B", "C", "D"],
                        help="워크스페이스 등급이 이 이상이면 non-zero exit (예: C)")
    parser.add_argument("--verbose", action="store_true", help="고복잡도 함수 목록 출력")
    parser.add_argument("--coverage-json", metavar="PATH",
                        help="coverage.json 경로 (pytest-cov --json-report 출력)")
    args = parser.parse_args()

    # 커버리지 맵 로드
    coverage_map: dict[str, float] = {}
    if args.coverage_json:
        try:
            cov_data = json.loads(Path(args.coverage_json).read_text())
            # pytest-cov json 형식에서 유닛별 커버리지 추출 (단순화)
            for k, v in cov_data.get("totals", {}).items():
                coverage_map[k] = float(v)
        except Exception:
            pass

    # 스캔 대상 결정
    all_units = iter_active_units()
    if args.unit:
        units = [u for u in all_units if u["id"] == args.unit]
        if not units:
            print(f"Unknown unit: {args.unit}", file=sys.stderr)
            return 1
    else:
        units = all_units

    print(f"Scanning {len(units)} unit(s)...", file=sys.stderr)
    unit_reports = [scan_unit(u, coverage_map) for u in units]
    report = build_workspace_report(unit_reports)

    print_report(report, verbose=args.verbose)

    # JSON 출력
    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        def _serialize(obj: object) -> object:
            if hasattr(obj, "__dataclass_fields__"):
                return asdict(obj)  # type: ignore[arg-type]
            raise TypeError(f"Not serializable: {type(obj)}")

        out_path.write_text(
            json.dumps(asdict(report), indent=2, default=str),
            encoding="utf-8",
        )
        print(f"JSON report saved: {out_path}", file=sys.stderr)

    # Exit code
    if args.fail_on_grade:
        grade_order = {"A": 0, "B": 1, "C": 2, "D": 3}
        fail_level = grade_order[args.fail_on_grade]
        ws_level = grade_order.get(report.workspace_grade, 0)
        if ws_level >= fail_level:
            print(
                f"[FAIL] Workspace grade {report.workspace_grade} >= fail threshold {args.fail_on_grade}",
                file=sys.stderr,
            )
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
