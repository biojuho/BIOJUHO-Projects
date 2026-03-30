"""
shared.telemetry.cost_tracker - 비용 추적 인터셉터 및 요약 생성기
기존 LLMClient 호출을 인터셉트하여 어떤 프로젝트(폴더)에서 발생한 호출인지
동적으로 감지하고 로깅합니다. 데몬을 위한 요약 기능도 제공합니다.
"""

import inspect
import sqlite3
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
LLM_DB_PATH = WORKSPACE / "shared" / "llm" / "data" / "llm_costs.db"


def detect_project_context() -> str:
    """호출 스택을 분석하여 어느 프로젝트에서 LLM을 호출했는지 감지합니다."""
    try:
        workspace_root = WORKSPACE.as_posix()
        for frame_info in inspect.stack():
            file_path = Path(frame_info.filename).resolve().as_posix()
            if file_path.startswith(workspace_root):
                rel_parts = Path(file_path).relative_to(workspace_root).parts
                if rel_parts and rel_parts[0] not in ("shared", "scripts", ".agent", ".agents"):
                    return rel_parts[0]
    except Exception:
        pass
    return "shared"


def get_daily_cost_summary(db_path: Path = LLM_DB_PATH, days: int = 1) -> dict:
    """최근 N일간의 프로젝트별/모델별 비용 합계 요약을 생성합니다."""
    if not db_path.exists():
        return {"total_cost": 0.0, "total_calls": 0, "projects": {}}

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # 전일(또는 최근 24시간) 기준 합산
        cursor.execute(
            """
            SELECT project, COUNT(*), SUM(cost_usd)
            FROM llm_calls
            WHERE timestamp >= datetime('now', ?)
            GROUP BY project
        """,
            (f"-{days} days",),
        )

        projects = {}
        total_cost = 0.0
        total_calls = 0

        for project, calls, cost in cursor.fetchall():
            proj_name = project or "unknown"
            projects[proj_name] = {"calls": calls, "cost_usd": round(cost or 0.0, 4)}
            total_calls += calls
            total_cost += cost or 0.0

        cursor.close()
        conn.close()

        return {"total_cost": round(total_cost, 4), "total_calls": total_calls, "projects": projects}
    except Exception as e:
        return {"error": str(e), "total_cost": 0.0, "total_calls": 0, "projects": {}}
