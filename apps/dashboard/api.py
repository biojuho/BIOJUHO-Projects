"""
통합 대시보드 — Python Data API
FastAPI 서버: 5개 프로젝트 DB에서 데이터를 읽어 JSON으로 제공한다.

Usage:
    python api.py          # port 8080
    python api.py --port 9090

Route modules:
    routers/gdt.py        — GetDayTrends, A/B, QA, Quality
    routers/projects.py   — CIE, AgriGuard, DailyNews, Costs, SLA, MCP
    db_utils.py           — SQLite/PostgreSQL helpers
"""

from __future__ import annotations

import argparse
import io
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Windows cp949 인코딩 문제 해결 — pytest capture와 충돌하므로
# 서버 직접 실행 시에만 적용 (테스트에서는 스킵)
if "pytest" not in sys.modules:
    if sys.stdout and hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if sys.stderr and hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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

# Ensure dashboard dir is in path for db_utils / routers
_DASHBOARD_DIR = str(Path(__file__).resolve().parent)
if _DASHBOARD_DIR not in sys.path:
    sys.path.insert(0, _DASHBOARD_DIR)

app = FastAPI(title="AI Projects Dashboard API", version="1.0")

_raw_origins = os.environ.get("DASHBOARD_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# ── Prometheus Metrics ──
try:
    from shared.metrics import setup_metrics

    setup_metrics(app, service_name="dashboard")
except ImportError:
    pass

# ── Structured Logging ──
try:
    from shared.structured_logging import setup_logging as setup_structured_logging

    setup_structured_logging(service_name="dashboard")
except ImportError:
    pass

# ── Audit Log ──
try:
    from shared.audit import setup_audit_log

    setup_audit_log(app, service_name="dashboard")
except ImportError:
    pass

# ── Predictive Engagement Engine ──
log = logging.getLogger("dashboard")
try:
    from shared.prediction.api import router as prediction_router

    app.include_router(prediction_router, prefix="/api/prediction")
    log.info("PEE (Predictive Engagement Engine) mounted at /api/prediction")
except ImportError:
    log.info("PEE not available (shared.prediction not installed)")

# ── Route modules ──
from routers.gdt import router as gdt_router
from routers.projects import router as projects_router

app.include_router(gdt_router)
app.include_router(projects_router)

# ── DB imports for overview endpoint ──
from db_utils import (
    CIE_DB,
    DN_DB,
    GDT_DB,
    _pg_scalar,
    _sqlite_read,
    _sqlite_scalar,
)


@app.get("/api/overview")
async def overview():
    """전체 프로젝트 건강 상태 종합."""
    gdt_runs = await _sqlite_scalar(GDT_DB, "SELECT COUNT(*) FROM runs") or 0
    gdt_latest = await _sqlite_read(
        GDT_DB,
        "SELECT started_at, trends_collected, tweets_generated FROM runs ORDER BY id DESC LIMIT 1",
    )
    cie_contents = await _sqlite_scalar(CIE_DB, "SELECT COUNT(*) FROM generated_contents") or 0
    cie_avg_qa = await _sqlite_scalar(CIE_DB, "SELECT AVG(qa_total_score) FROM generated_contents") or 0
    ag_sensors = await _pg_scalar("SELECT COUNT(*) FROM sensor_readings") or 0
    ag_products = await _pg_scalar("SELECT COUNT(*) FROM products") or 0
    dn_exists = DN_DB.exists()

    # Cost
    try:
        from routers.projects import _get_cost_summary

        cost_data = _get_cost_summary()
    except Exception:
        cost_data = {"total_cost": 0, "total_calls": 0}

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
    uvicorn.run(app, host=args.host, port=args.port)
