"""
통합 대시보드 — Python Data API
FastAPI 서버: 5개 프로젝트 DB에서 데이터를 읽어 JSON으로 제공한다.

Usage:
    python api.py          # port 8080
    python api.py --port 9090
"""

from __future__ import annotations

import argparse
import io
import logging
import os
import sqlite3
import sys
from datetime import datetime

# Windows cp949 인코딩 문제 해결
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ── 경로 설정 ──
WORKSPACE = Path(__file__).resolve().parents[2]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))
for candidate in (
    WORKSPACE / "packages",
    WORKSPACE / "automation",
    WORKSPACE / "apps" / "desci-platform",
):
    candidate_text = str(candidate)
    if candidate_text not in sys.path:
        sys.path.insert(0, candidate_text)

app = FastAPI(title="AI Projects Dashboard API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Prometheus Metrics (/metrics) ──────────────────────────
try:
    from shared.metrics import setup_metrics
    setup_metrics(app, service_name="dashboard")
except ImportError:
    pass

# ── Structured Logging (JSON for Loki) ─────────────────────
try:
    from shared.structured_logging import setup_logging as setup_structured_logging
    setup_structured_logging(service_name="dashboard")
except ImportError:
    pass

# ── Audit Log ──────────────────────────────────────────────
try:
    from shared.audit import setup_audit_log
    setup_audit_log(app, service_name="dashboard")
except ImportError:
    pass

# ── DB 경로 ──
GDT_DB = WORKSPACE / "automation" / "getdaytrends" / "data" / "getdaytrends.db"
CIE_DB = WORKSPACE / "automation" / "content-intelligence" / "data" / "cie.db"
DN_DB = WORKSPACE / "automation" / "DailyNews" / "data" / "pipeline_state.db"
AG_PG_URL = os.environ.get(
    "AGRIGUARD_DATABASE_URL",
    "postgresql://agriguard:agriguard_secret@localhost:5432/agriguard",
)


log = logging.getLogger("dashboard")


def _sqlite_read(db_path: Path, query: str, params: tuple = ()) -> list[dict]:
    """SQLite에서 읽어 dict 리스트로 반환."""
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:  # [QA 수정] 예외 로깅 추가
        log.warning("SQLite read failed (%s): %s", db_path.name, e)
        return []
    finally:
        conn.close()


def _sqlite_scalar(db_path: Path, query: str, params: tuple = ()):
    if not db_path.exists():
        return None
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute(query, params).fetchone()[0]
    except Exception as e:  # [QA 수정] 예외 로깅 추가
        log.warning("SQLite scalar failed (%s): %s", db_path.name, e)
        return None
    finally:
        conn.close()


# [QA 수정] 엔진 싱글톤 — 매 요청마다 create_engine 호출 방지
_pg_engine = None


def _get_pg_engine():
    """Lazy singleton SQLAlchemy engine."""
    global _pg_engine
    if _pg_engine is None:
        try:
            from sqlalchemy import create_engine
            _pg_engine = create_engine(AG_PG_URL, pool_pre_ping=True, pool_size=3)
        except Exception as e:
            log.warning("PostgreSQL engine creation failed: %s", e)
            return None
    return _pg_engine


def _pg_read(query: str) -> list[dict]:
    """PostgreSQL에서 읽어 dict 리스트로 반환."""
    try:
        from sqlalchemy import text
        engine = _get_pg_engine()
        if engine is None:
            return [{"error": "PostgreSQL not available"}]
        with engine.connect() as conn:
            result = conn.execute(text(query))
            columns = result.keys()
            return [dict(zip(columns, row, strict=True)) for row in result.fetchall()]
    except Exception as e:
        log.warning("PostgreSQL read failed: %s", e)
        return [{"error": str(e)}]


def _pg_scalar(query: str):
    try:
        from sqlalchemy import text
        engine = _get_pg_engine()
        if engine is None:
            return None
        with engine.connect() as conn:
            return conn.execute(text(query)).scalar()
    except Exception as e:
        log.warning("PostgreSQL scalar failed: %s", e)
        return None


# ══════════════════════════════════════════════
#  API Endpoints
# ══════════════════════════════════════════════


@app.get("/api/overview")
def overview():
    """전체 프로젝트 건강 상태 종합."""
    gdt_runs = _sqlite_scalar(GDT_DB, "SELECT COUNT(*) FROM runs") or 0
    gdt_latest = _sqlite_read(
        GDT_DB,
        "SELECT started_at, trends_collected, tweets_generated FROM runs ORDER BY id DESC LIMIT 1",
    )

    cie_contents = _sqlite_scalar(CIE_DB, "SELECT COUNT(*) FROM generated_contents") or 0
    cie_avg_qa = _sqlite_scalar(CIE_DB, "SELECT AVG(qa_total_score) FROM generated_contents") or 0

    ag_sensors = _pg_scalar("SELECT COUNT(*) FROM sensor_readings") or 0
    ag_products = _pg_scalar("SELECT COUNT(*) FROM products") or 0

    dn_exists = DN_DB.exists()

    # Cost
    cost_data = _get_cost_summary()

    return {
        "timestamp": datetime.now().isoformat(),
        "projects": {
            "getdaytrends": {
                "status": "OK" if gdt_runs > 0 else "WARN",
                "total_runs": gdt_runs,
                "latest_run": gdt_latest[0] if gdt_latest else None,
            },
            "cie": {
                "status": "OK" if cie_contents > 0 else "WARN",
                "total_contents": cie_contents,
                "avg_qa_score": round(cie_avg_qa, 1),
            },
            "agriguard": {
                "status": "OK" if ag_sensors > 0 else "ERROR",
                "sensor_readings": ag_sensors,
                "products": ag_products,
            },
            "dailynews": {
                "status": "OK" if dn_exists else "WARN",
                "db_exists": dn_exists,
            },
            "costs": cost_data,
        },
    }


@app.get("/api/getdaytrends")
def getdaytrends():
    """GetDayTrends 실행 현황."""
    recent_runs = _sqlite_read(
        GDT_DB,
        """SELECT id, country, started_at, ended_at, trends_collected,
                  tweets_generated, total_duration_sec
           FROM runs ORDER BY id DESC LIMIT 30""",
    )

    # 일별 실행 수 (최근 14일)
    daily_runs = _sqlite_read(
        GDT_DB,
        """SELECT DATE(started_at) as date, COUNT(*) as count,
                  SUM(trends_collected) as trends, SUM(tweets_generated) as tweets
           FROM runs
           WHERE started_at >= date('now', '-14 days')
           GROUP BY DATE(started_at)
           ORDER BY date""",
    )

    # 인기 트렌드 Top 10
    top_trends = _sqlite_read(
        GDT_DB,
        """SELECT keyword, viral_potential, tweet_volume
           FROM trends
           ORDER BY id DESC LIMIT 10""",
    )

    total_runs = _sqlite_scalar(GDT_DB, "SELECT COUNT(*) FROM runs") or 0
    total_trends = _sqlite_scalar(GDT_DB, "SELECT COUNT(*) FROM trends") or 0
    total_tweets = _sqlite_scalar(GDT_DB, "SELECT COUNT(*) FROM tweets") or 0

    return {
        "total_runs": total_runs,
        "total_trends": total_trends,
        "total_tweets": total_tweets,
        "recent_runs": recent_runs,
        "daily_runs": daily_runs,
        "top_trends": top_trends,
    }


@app.get("/api/cie")
def cie():
    """Content Intelligence Engine 현황."""
    contents = _sqlite_read(
        CIE_DB,
        """SELECT platform, content_type, title, qa_total_score,
                  regulation_ok, algorithm_ok, published,
                  publish_target, created_at
           FROM generated_contents
           ORDER BY created_at DESC LIMIT 20""",
    )

    # 플랫폼별 분포
    by_platform = _sqlite_read(
        CIE_DB,
        """SELECT platform, COUNT(*) as count, AVG(qa_total_score) as avg_qa
           FROM generated_contents GROUP BY platform""",
    )

    # QA 점수 분포
    qa_distribution = _sqlite_read(
        CIE_DB,
        """SELECT
             CASE
               WHEN qa_total_score >= 90 THEN 'A (90+)'
               WHEN qa_total_score >= 80 THEN 'B (80-89)'
               WHEN qa_total_score >= 70 THEN 'C (70-79)'
               ELSE 'D (<70)'
             END as grade,
             COUNT(*) as count
           FROM generated_contents
           GROUP BY grade
           ORDER BY grade""",
    )

    # 트렌드 수집 현황
    trend_count = _sqlite_scalar(CIE_DB, "SELECT COUNT(*) FROM trend_reports") or 0

    return {
        "total_contents": len(contents),
        "total_trends": trend_count,
        "contents": contents,
        "by_platform": by_platform,
        "qa_distribution": qa_distribution,
    }


@app.get("/api/agriguard")
def agriguard():
    """AgriGuard 센서 및 제품 현황."""
    # [QA 수정] 테이블 화이트리스트로 SQL injection 방지
    _AG_TABLES = ("users", "products", "tracking_events", "certificates", "sensor_readings")
    tables = {}
    for table in _AG_TABLES:
        tables[table] = _pg_scalar(f'SELECT COUNT(*) FROM "{table}"') or 0

    # 최근 센서 데이터 (최신 20건)
    recent_sensors = _pg_read(
        """SELECT id, product_id, value, unit, recorded_at
           FROM sensor_readings
           ORDER BY id DESC LIMIT 20"""
    )

    # 제품 현황
    product_stats = _pg_read(
        """SELECT
             COUNT(*) as total,
             COUNT(CASE WHEN is_verified = true THEN 1 END) as verified,
             COUNT(CASE WHEN requires_cold_chain = true THEN 1 END) as cold_chain
           FROM products"""
    )

    return {
        "tables": tables,
        "recent_sensors": recent_sensors,
        "product_stats": product_stats[0] if product_stats else {},
    }


@app.get("/api/dailynews")
def dailynews():
    """DailyNews 파이프라인 현황."""
    if not DN_DB.exists():
        return {"status": "DB not found", "runs": []}

    # 테이블 목록 확인
    tables = _sqlite_read(
        DN_DB,
        "SELECT name FROM sqlite_master WHERE type='table'",
    )
    table_names = [t["name"] for t in tables]

    result = {"tables": table_names}

    # runs 테이블이 있으면 조회
    if "pipeline_runs" in table_names:
        recent = _sqlite_read(
            DN_DB,
            "SELECT * FROM pipeline_runs ORDER BY rowid DESC LIMIT 10",
        )
        result["recent_runs"] = recent
    elif "runs" in table_names:
        recent = _sqlite_read(
            DN_DB,
            "SELECT * FROM runs ORDER BY rowid DESC LIMIT 10",
        )
        result["recent_runs"] = recent

    # 각 테이블 행수
    table_counts = {}
    for name in table_names:
        if not name.startswith("sqlite_"):
            count = _sqlite_scalar(DN_DB, f'SELECT COUNT(*) FROM "{name}"')
            table_counts[name] = count or 0
    result["table_counts"] = table_counts

    return result


@app.get("/api/costs")
def costs():
    """LLM API 비용 요약."""
    return _get_cost_summary()


def _get_cost_summary() -> dict:
    """shared/telemetry에서 비용 데이터를 가져온다."""
    try:
        from shared.telemetry.cost_tracker import get_daily_cost_summary
        summary = get_daily_cost_summary(days=7)
        return summary
    except Exception as e:
        return {"error": str(e), "total_cost": 0, "total_calls": 0, "projects": {}}


# ══════════════════════════════════════════════
#  Entry Point
# ══════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    print(f"🚀 Dashboard API starting on http://{args.host}:{args.port}")
    print(f"   GDT DB: {GDT_DB} ({'✅' if GDT_DB.exists() else '❌'})")
    print(f"   CIE DB: {CIE_DB} ({'✅' if CIE_DB.exists() else '❌'})")
    print(f"   DN  DB: {DN_DB} ({'✅' if DN_DB.exists() else '❌'})")
    print(f"   AG  PG: {AG_PG_URL[:50]}...")
    uvicorn.run(app, host=args.host, port=args.port)
