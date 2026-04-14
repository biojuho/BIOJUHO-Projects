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
if sys.stdout and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

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

_raw_origins = os.environ.get("DASHBOARD_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
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


# ── Predictive Engagement Engine ──────────────────────────
try:
    from shared.prediction.api import router as prediction_router

    app.include_router(prediction_router, prefix="/api/prediction")
    log.info("PEE (Predictive Engagement Engine) mounted at /api/prediction")
except ImportError:
    log.info("PEE not available (shared.prediction not installed)")

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
        """SELECT id, country, started_at, finished_at, trends_collected,
                  tweets_generated
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
        """SELECT keyword, viral_potential, volume_raw
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
        """SELECT id, sensor_id, temperature, humidity, timestamp
           FROM sensor_readings
           ORDER BY timestamp DESC LIMIT 20"""
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


@app.get("/api/ab_performance")
def ab_performance():
    """A/B 패턴 성과 — hook/kick/angle 패턴별 평균 참여율 및 역피드백 현황."""
    # hook 패턴별 성과
    hook_stats = _sqlite_read(
        GDT_DB,
        """SELECT hook_pattern, COUNT(*) as count,
                  AVG(engagement_rate) as avg_eng,
                  AVG(impressions) as avg_imp
           FROM tweet_performance
           WHERE hook_pattern != '' AND collected_at >= datetime('now', '-30 days')
           GROUP BY hook_pattern
           ORDER BY avg_eng DESC""",
    )

    # kick 패턴별 성과
    kick_stats = _sqlite_read(
        GDT_DB,
        """SELECT kick_pattern, COUNT(*) as count,
                  AVG(engagement_rate) as avg_eng
           FROM tweet_performance
           WHERE kick_pattern != '' AND collected_at >= datetime('now', '-30 days')
           GROUP BY kick_pattern
           ORDER BY avg_eng DESC""",
    )

    # angle 타입별 성과
    angle_stats = _sqlite_read(
        GDT_DB,
        """SELECT angle_type, COUNT(*) as count,
                  AVG(engagement_rate) as avg_eng
           FROM tweet_performance
           WHERE angle_type != '' AND collected_at >= datetime('now', '-30 days')
           GROUP BY angle_type
           ORDER BY avg_eng DESC""",
    )

    # 총 성과 데이터 포인트 수
    total_samples = _sqlite_scalar(GDT_DB, "SELECT COUNT(*) FROM tweet_performance") or 0

    # CIE → GDT 역피드백 현황 (content_feedback)
    feedback_stats = _sqlite_read(
        GDT_DB,
        """SELECT
             COUNT(*) as total,
             AVG(qa_score) as avg_qa,
             SUM(CASE WHEN regenerated = 1 THEN 1 ELSE 0 END) as regenerated_count
           FROM content_feedback
           WHERE created_at >= datetime('now', '-30 days')""",
    )

    # 역피드백 일별 추이 (최근 7일)
    feedback_trend = _sqlite_read(
        GDT_DB,
        """SELECT DATE(created_at) as date, COUNT(*) as count, AVG(qa_score) as avg_qa
           FROM content_feedback
           WHERE created_at >= datetime('now', '-7 days')
           GROUP BY DATE(created_at)
           ORDER BY date""",
    )

    return {
        "total_samples": total_samples,
        "hook_stats": hook_stats,
        "kick_stats": kick_stats,
        "angle_stats": angle_stats,
        "feedback": feedback_stats[0] if feedback_stats else {},
        "feedback_trend": feedback_trend,
    }


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


@app.get("/api/qa_reports")
def qa_reports(limit: int = 50):
    """QA 리포트 상세 — qa_report_first_pass + fact_check_report 시각화용.

    draft_bundles와 qa_reports를 JOIN하여 트렌드별 QA 점수,
    통과/탈락, 차단 사유를 반환한다. Metabase/외부 대시보드에서
    직접 연동 가능한 구조.
    """
    import json as _json

    # QA 리포트 + 드래프트 번들 JOIN
    rows = _sqlite_read(
        GDT_DB,
        """SELECT
             q.id, q.draft_id, q.total_score, q.passed,
             q.warnings, q.blocking_reasons, q.report_payload, q.created_at,
             d.trend_id, d.platform, d.content_type,
             d.lifecycle_status, d.review_status,
             t.keyword
           FROM qa_reports q
           LEFT JOIN draft_bundles d ON q.draft_id = d.draft_id
           LEFT JOIN validated_trends v ON d.trend_id = v.trend_id
           LEFT JOIN trends t ON v.trend_row_id = t.id
           ORDER BY q.created_at DESC
           LIMIT ?""",
        (min(limit, 200),),
    )

    # JSON 문자열 필드를 파싱
    for row in rows:
        for field in ("warnings", "blocking_reasons", "report_payload"):
            val = row.get(field)
            if isinstance(val, str):
                try:
                    row[field] = _json.loads(val)
                except (ValueError, TypeError):
                    pass

    # 집계 통계
    total = _sqlite_scalar(GDT_DB, "SELECT COUNT(*) FROM qa_reports") or 0
    passed = _sqlite_scalar(GDT_DB, "SELECT COUNT(*) FROM qa_reports WHERE passed = 1") or 0
    avg_score = _sqlite_scalar(GDT_DB, "SELECT AVG(total_score) FROM qa_reports") or 0

    # 플랫폼별 통과율
    platform_stats = _sqlite_read(
        GDT_DB,
        """SELECT d.platform,
                  COUNT(*) as total,
                  SUM(CASE WHEN q.passed = 1 THEN 1 ELSE 0 END) as passed,
                  ROUND(AVG(q.total_score), 1) as avg_score
           FROM qa_reports q
           LEFT JOIN draft_bundles d ON q.draft_id = d.draft_id
           GROUP BY d.platform""",
    )

    # 일별 QA 추이 (최근 14일)
    daily_trend = _sqlite_read(
        GDT_DB,
        """SELECT DATE(q.created_at) as date,
                  COUNT(*) as total,
                  SUM(CASE WHEN q.passed = 1 THEN 1 ELSE 0 END) as passed,
                  ROUND(AVG(q.total_score), 1) as avg_score
           FROM qa_reports q
           WHERE q.created_at >= date('now', '-14 days')
           GROUP BY DATE(q.created_at)
           ORDER BY date""",
    )

    return {
        "summary": {
            "total_reports": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": round(passed / total * 100, 1) if total else 0,
            "avg_score": round(avg_score, 1),
        },
        "platform_stats": platform_stats,
        "daily_trend": daily_trend,
        "reports": rows,
    }


@app.get("/api/quality_overview")
def quality_overview():
    """품질 종합 대시보드 — QA + FactCheck + 다양성 통합 뷰.

    getdaytrends의 콘텐츠 품질 지표를 한 화면에 보여주기 위한
    종합 엔드포인트. Metabase 대시보드의 메인 패널용.
    """
    # QA 점수 분포 (등급별)
    qa_grade_dist = _sqlite_read(
        GDT_DB,
        """SELECT
             CASE
               WHEN total_score >= 90 THEN 'A (90+)'
               WHEN total_score >= 80 THEN 'B (80-89)'
               WHEN total_score >= 70 THEN 'C (70-79)'
               ELSE 'D (<70)'
             END as grade,
             COUNT(*) as count,
             ROUND(AVG(total_score), 1) as avg_score
           FROM qa_reports
           GROUP BY grade
           ORDER BY grade""",
    )

    # 차단 사유 Top 10
    blocking_reasons_raw = _sqlite_read(
        GDT_DB,
        """SELECT blocking_reasons
           FROM qa_reports
           WHERE passed = 0 AND blocking_reasons IS NOT NULL AND blocking_reasons != '[]'
           ORDER BY created_at DESC LIMIT 100""",
    )
    reason_counter: dict[str, int] = {}
    import json as _json
    for row in blocking_reasons_raw:
        val = row.get("blocking_reasons", "")
        if isinstance(val, str):
            try:
                reasons = _json.loads(val)
            except (ValueError, TypeError):
                reasons = []
        else:
            reasons = val or []
        for r in reasons:
            reason_counter[str(r)[:80]] = reason_counter.get(str(r)[:80], 0) + 1
    top_blockers = sorted(reason_counter.items(), key=lambda x: x[1], reverse=True)[:10]

    # 드래프트 파이프라인 현황 (lifecycle_status 분포)
    lifecycle_dist = _sqlite_read(
        GDT_DB,
        """SELECT lifecycle_status, review_status, COUNT(*) as count
           FROM draft_bundles
           GROUP BY lifecycle_status, review_status
           ORDER BY count DESC""",
    )

    # 최근 7일간 일별 생산량
    daily_production = _sqlite_read(
        GDT_DB,
        """SELECT DATE(created_at) as date,
                  COUNT(*) as drafts,
                  SUM(CASE WHEN review_status = 'Approved' THEN 1 ELSE 0 END) as approved,
                  SUM(CASE WHEN review_status = 'Rejected' THEN 1 ELSE 0 END) as rejected
           FROM draft_bundles
           WHERE created_at >= date('now', '-7 days')
           GROUP BY DATE(created_at)
           ORDER BY date""",
    )

    # 검증된 트렌드 신뢰도 분포
    confidence_dist = _sqlite_read(
        GDT_DB,
        """SELECT
             CASE
               WHEN confidence_score >= 0.9 THEN 'Very High (0.9+)'
               WHEN confidence_score >= 0.7 THEN 'High (0.7-0.9)'
               WHEN confidence_score >= 0.5 THEN 'Medium (0.5-0.7)'
               ELSE 'Low (<0.5)'
             END as tier,
             COUNT(*) as count
           FROM validated_trends
           GROUP BY tier
           ORDER BY tier""",
    )

    return {
        "qa_grades": qa_grade_dist,
        "top_blocking_reasons": [{"reason": r, "count": c} for r, c in top_blockers],
        "lifecycle_distribution": lifecycle_dist,
        "daily_production": daily_production,
        "confidence_distribution": confidence_dist,
    }

@app.get("/api/sla_status")
def sla_status():
    """파이프라인 SLA 현황 — 성공률, 평균 실행 시간, 최근 장애."""
    from datetime import datetime, timedelta

    sla_target = float(os.environ.get("SLA_TARGET_PERCENT", "99.0"))
    lookback_days = int(os.environ.get("SLA_LOOKBACK_DAYS", "30"))

    pipelines = []

    # ── GetDayTrends SLA ──
    gdt_runs = _sqlite_read(
        GDT_DB,
        """SELECT started_at, finished_at, errors
           FROM runs
           WHERE started_at >= date('now', ?)
           ORDER BY id DESC""",
        (f"-{lookback_days} days",),
    )
    if gdt_runs:
        gdt_total = len(gdt_runs)
        gdt_success = sum(
            1 for r in gdt_runs
            if r.get("errors", "[]") in ("[]", "", None)
        )
        gdt_success_rate = round(gdt_success / gdt_total * 100, 2) if gdt_total else 0

        # 평균 실행 시간 (분)
        durations = []
        for r in gdt_runs:
            if r.get("started_at") and r.get("finished_at"):
                try:
                    start = datetime.fromisoformat(r["started_at"].replace("Z", "+00:00"))
                    end = datetime.fromisoformat(r["finished_at"].replace("Z", "+00:00"))
                    durations.append((end - start).total_seconds() / 60)
                except (ValueError, TypeError):
                    pass
        avg_duration = round(sum(durations) / len(durations), 1) if durations else 0

        recent_failures = [
            {
                "time": r.get("started_at", ""),
                "errors": r.get("errors", ""),
            }
            for r in gdt_runs[:5]
            if r.get("errors", "[]") not in ("[]", "", None)
        ]

        pipelines.append({
            "name": "GetDayTrends",
            "total_runs": gdt_total,
            "successful_runs": gdt_success,
            "success_rate": gdt_success_rate,
            "sla_met": gdt_success_rate >= sla_target,
            "avg_duration_min": avg_duration,
            "recent_failures": recent_failures[:3],
        })

    # ── DailyNews SLA ──
    dn_runs = _sqlite_read(
        DN_DB,
        """SELECT run_id, job_name, started_at, finished_at, status, error_text
           FROM job_runs
           WHERE started_at >= date('now', ?)
           ORDER BY started_at DESC""",
        (f"-{lookback_days} days",),
    )
    if dn_runs:
        dn_total = len(dn_runs)
        dn_success = sum(1 for r in dn_runs if r.get("status") in ("success", "partial"))
        dn_success_rate = round(dn_success / dn_total * 100, 2) if dn_total else 0

        dn_durations = []
        for r in dn_runs:
            if r.get("started_at") and r.get("finished_at"):
                try:
                    start = datetime.fromisoformat(r["started_at"].replace("Z", "+00:00"))
                    end = datetime.fromisoformat(r["finished_at"].replace("Z", "+00:00"))
                    dn_durations.append((end - start).total_seconds() / 60)
                except (ValueError, TypeError):
                    pass
        dn_avg = round(sum(dn_durations) / len(dn_durations), 1) if dn_durations else 0

        dn_failures = [
            {
                "job": r.get("job_name", ""),
                "time": r.get("started_at", ""),
                "error": (r.get("error_text") or "")[:200],
            }
            for r in dn_runs[:10]
            if r.get("status") == "failed"
        ]

        pipelines.append({
            "name": "DailyNews",
            "total_runs": dn_total,
            "successful_runs": dn_success,
            "success_rate": dn_success_rate,
            "sla_met": dn_success_rate >= sla_target,
            "avg_duration_min": dn_avg,
            "recent_failures": dn_failures[:3],
        })

    # ── Content Intelligence SLA ──
    cie_contents = _sqlite_read(
        CIE_DB,
        """SELECT created_at, qa_total_score
           FROM generated_contents
           WHERE created_at >= date('now', ?)
           ORDER BY created_at DESC""",
        (f"-{lookback_days} days",),
    )
    if cie_contents:
        cie_total = len(cie_contents)
        cie_pass = sum(1 for c in cie_contents if (c.get("qa_total_score") or 0) >= 3.0)
        cie_rate = round(cie_pass / cie_total * 100, 2) if cie_total else 0
        pipelines.append({
            "name": "ContentIntelligence",
            "total_runs": cie_total,
            "successful_runs": cie_pass,
            "success_rate": cie_rate,
            "sla_met": cie_rate >= sla_target,
            "avg_duration_min": 0,
            "recent_failures": [],
        })

    # ── Overall ──
    overall_runs = sum(p["total_runs"] for p in pipelines)
    overall_success = sum(p["successful_runs"] for p in pipelines)
    overall_rate = round(overall_success / overall_runs * 100, 2) if overall_runs else 0

    return {
        "sla_target": sla_target,
        "lookback_days": lookback_days,
        "overall_success_rate": overall_rate,
        "overall_sla_met": overall_rate >= sla_target,
        "pipelines": pipelines,
    }

@app.get("/api/mcp_health")
def mcp_health():
    """MCP 서버 헬스 체크 — 설정/바이너리 존재 여부 + 최근 수정일."""
    import json as _json
    from datetime import datetime

    mcp_dir = WORKSPACE / "mcp"
    servers = []

    # Read from workspace-map.json
    ws_map = WORKSPACE / "workspace-map.json"
    mcp_units = []
    if ws_map.exists():
        try:
            with open(ws_map, "r", encoding="utf-8") as f:
                data = _json.load(f)
            mcp_units = [u for u in data.get("units", []) if u.get("category") == "mcp"]
        except Exception:
            pass

    for unit in mcp_units:
        unit_id = unit["id"]
        unit_path = WORKSPACE / unit.get("canonical_path", f"mcp/{unit_id}")

        info = {
            "name": unit_id,
            "path": str(unit_path.relative_to(WORKSPACE)),
            "exists": unit_path.exists(),
            "has_package_json": (unit_path / "package.json").exists(),
            "has_src": (unit_path / "src").exists(),
            "has_dist": (unit_path / "dist").exists(),
            "has_dockerfile": (unit_path / "Dockerfile").exists(),
            "last_modified": None,
            "status": "unknown",
        }

        if unit_path.exists():
            # Find most recently modified file
            try:
                src_files = list(unit_path.glob("src/**/*"))
                if src_files:
                    latest = max(f.stat().st_mtime for f in src_files if f.is_file())
                    info["last_modified"] = datetime.fromtimestamp(latest).isoformat()
            except Exception:
                pass

            # Status logic
            if info["has_dist"] and info["has_src"]:
                info["status"] = "ready"
            elif info["has_src"]:
                info["status"] = "needs_build"
            else:
                info["status"] = "incomplete"
        else:
            info["status"] = "missing"

        servers.append(info)

    ready = sum(1 for s in servers if s["status"] == "ready")
    total = len(servers)

    return {
        "total_servers": total,
        "ready": ready,
        "needs_attention": total - ready,
        "servers": servers,
    }


# ══════════════════════════════════════════════
#  Static Files (SPA)
# ══════════════════════════════════════════════

_DIST_DIR = Path(__file__).resolve().parent / "dist"
if _DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(_DIST_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        """SPA fallback — serve index.html for all non-API routes."""
        file_path = _DIST_DIR / full_path
        if full_path and file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(_DIST_DIR / "index.html"))


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
