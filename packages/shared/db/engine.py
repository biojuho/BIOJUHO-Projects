"""
shared.db.engine — 데이터베이스 엔진 팩토리

SQLite ↔ PostgreSQL(Supabase) 전환을 투명하게 처리하는 추상화 레이어.
환경변수 DATABASE_URL이 설정되면 PostgreSQL, 아니면 로컬 SQLite를 사용합니다.

P2 로드맵: SQLite → Supabase PostgreSQL 이전
- Phase 1: 엔진 팩토리 구축 (현재)
- Phase 2: AgriGuard DB 마이그레이션
- Phase 3: LLM Costs DB 마이그레이션

Usage:
    from shared.db.engine import get_engine, get_connection

    # 자동 감지: DATABASE_URL이 있으면 PostgreSQL, 없으면 SQLite
    engine = get_engine("agriguard")

    # 직접 지정
    engine = get_engine("agriguard", backend="sqlite", path="agriguard.db")
"""

import os
import sqlite3
from pathlib import Path
from typing import Literal

WORKSPACE = Path(__file__).resolve().parents[2]

# Supabase 연결 정보 (환경변수에서 로드)
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

# 프로젝트별 기본 SQLite 경로 매핑
SQLITE_PATHS = {
    "agriguard": WORKSPACE / "AgriGuard" / "backend" / "agriguard.db",
    "getdaytrends": WORKSPACE / "getdaytrends" / "data" / "getdaytrends.db",
    "llm_costs": WORKSPACE / "shared" / "llm" / "data" / "llm_costs.db",
    "dailynews_analytics": WORKSPACE / "DailyNews" / "data" / "analytics.db",
    "dailynews_pipeline": WORKSPACE / "DailyNews" / "data" / "pipeline_state.db",
    "cie": WORKSPACE / "content-intelligence" / "data" / "cie.db",
}


def get_backend() -> Literal["sqlite", "postgresql"]:
    """현재 활성화된 DB 백엔드를 반환합니다."""
    if DATABASE_URL and DATABASE_URL.startswith("postgresql"):
        return "postgresql"
    return "sqlite"


def get_sqlite_connection(db_name: str, path: Path | None = None) -> sqlite3.Connection:
    """SQLite 연결을 반환합니다.

    Args:
        db_name: SQLITE_PATHS 키 또는 커스텀 이름
        path: 직접 경로 지정 (None이면 SQLITE_PATHS에서 조회)

    Returns:
        sqlite3.Connection
    """
    db_path = path or SQLITE_PATHS.get(db_name)
    if db_path is None:
        raise ValueError(f"Unknown database: {db_name}. Available: {list(SQLITE_PATHS.keys())}")

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(db_path))


def get_connection(db_name: str, **kwargs):
    """데이터베이스 연결을 반환합니다.

    현재는 SQLite만 지원합니다.
    DATABASE_URL이 설정되면 PostgreSQL로 자동 전환됩니다 (Phase 2에서 구현).

    Args:
        db_name: 데이터베이스 식별자
        **kwargs: 추가 연결 옵션

    Returns:
        DB 연결 객체
    """
    backend = get_backend()

    if backend == "postgresql":
        # Phase 2: Supabase PostgreSQL 지원
        # psycopg2 또는 sqlalchemy로 연결
        raise NotImplementedError(
            "PostgreSQL backend is not yet implemented. "
            "Set DATABASE_URL to a PostgreSQL connection string and install psycopg2. "
            "Coming in P2 Phase 2."
        )

    return get_sqlite_connection(db_name, path=kwargs.get("path"))


def check_health() -> dict:
    """모든 등록된 DB의 건강 상태를 확인합니다."""
    results = {}
    for name, path in SQLITE_PATHS.items():
        try:
            if path.exists():
                conn = sqlite3.connect(str(path))
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                table_count = cursor.fetchone()[0]
                size_kb = path.stat().st_size / 1024
                conn.close()
                results[name] = {
                    "status": "ok",
                    "tables": table_count,
                    "size_kb": round(size_kb, 1),
                    "backend": "sqlite",
                }
            else:
                results[name] = {"status": "missing", "path": str(path)}
        except Exception as e:
            results[name] = {"status": "error", "error": str(e)}

    results["_backend"] = get_backend()
    results["_database_url"] = bool(DATABASE_URL)
    return results
