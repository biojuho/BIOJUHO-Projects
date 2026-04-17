"""Dashboard — CIE, AgriGuard, DailyNews, Costs, SLA, MCP routes."""

from __future__ import annotations

import json as _json
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter

from db_utils import (
    CIE_DB,
    DN_DB,
    WORKSPACE,
    _pg_read,
    _pg_scalar,
    _sqlite_read,
    _sqlite_scalar,
)

router = APIRouter()


@router.get("/api/cie")
async def cie():
    """Content Intelligence Engine 현황."""
    contents = await _sqlite_read(
        CIE_DB,
        """SELECT platform, content_type, title, qa_total_score,
                  regulation_ok, algorithm_ok, published,
                  publish_target, created_at
           FROM generated_contents
           ORDER BY created_at DESC LIMIT 20""",
    )
    by_platform = await _sqlite_read(
        CIE_DB,
        """SELECT platform, COUNT(*) as count, AVG(qa_total_score) as avg_qa
           FROM generated_contents GROUP BY platform""",
    )
    qa_distribution = await _sqlite_read(
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
    trend_count = await _sqlite_scalar(CIE_DB, "SELECT COUNT(*) FROM trend_reports") or 0
    return {
        "total_contents": len(contents),
        "total_trends": trend_count,
        "contents": contents,
        "by_platform": by_platform,
        "qa_distribution": qa_distribution,
    }


@router.get("/api/agriguard")
async def agriguard():
    """AgriGuard 센서 및 제품 현황."""
    _AG_TABLES = ("users", "products", "tracking_events", "certificates", "sensor_readings")
    tables = {}
    for table in _AG_TABLES:
        tables[table] = await _pg_scalar(f'SELECT COUNT(*) FROM "{table}"') or 0
    recent_sensors = await _pg_read(
        """SELECT id, sensor_id, temperature, humidity, timestamp
           FROM sensor_readings
           ORDER BY timestamp DESC LIMIT 20"""
    )
    product_stats = await _pg_read(
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


@router.get("/api/dailynews")
async def dailynews():
    """DailyNews 파이프라인 현황."""
    if not DN_DB.exists():
        return {"status": "DB not found", "runs": []}
    tables = await _sqlite_read(DN_DB, "SELECT name FROM sqlite_master WHERE type='table'")
    table_names = [t["name"] for t in tables]
    result: dict = {"tables": table_names}
    if "pipeline_runs" in table_names:
        result["recent_runs"] = await _sqlite_read(DN_DB, "SELECT * FROM pipeline_runs ORDER BY rowid DESC LIMIT 10")
    elif "runs" in table_names:
        result["recent_runs"] = await _sqlite_read(DN_DB, "SELECT * FROM runs ORDER BY rowid DESC LIMIT 10")
    table_counts: dict[str, int] = {}
    for name in table_names:
        if not name.startswith("sqlite_"):
            table_counts[name] = await _sqlite_scalar(DN_DB, f'SELECT COUNT(*) FROM "{name}"') or 0
    result["table_counts"] = table_counts
    return result


@router.get("/api/costs")
async def costs():
    """LLM API 비용 요약."""
    return _get_cost_summary()


def _get_cost_summary() -> dict:
    """shared/telemetry에서 비용 데이터를 가져온다."""
    try:
        from shared.telemetry.cost_tracker import get_daily_cost_summary

        return get_daily_cost_summary(days=7)
    except Exception as e:
        return {"error": str(e), "total_cost": 0, "total_calls": 0, "projects": {}}


@router.get("/api/sla_status")
async def sla_status():
    """파이프라인 SLA 현황."""
    from db_utils import GDT_DB

    sla_target = float(os.environ.get("SLA_TARGET_PERCENT", "99.0"))
    lookback_days = int(os.environ.get("SLA_LOOKBACK_DAYS", "30"))
    pipelines = []

    # ── GetDayTrends SLA ──
    gdt_runs = await _sqlite_read(
        GDT_DB,
        """SELECT started_at, finished_at, errors
           FROM runs WHERE started_at >= date('now', ?)
           ORDER BY id DESC""",
        (f"-{lookback_days} days",),
    )
    if gdt_runs:
        gdt_total = len(gdt_runs)
        gdt_success = sum(
            1 for r in gdt_runs
            if r.get("errors", "[]") in ("[]", "", None)
            or (r.get("errors", "[]").startswith("[") and "생성 실패" in r.get("errors", ""))
        )
        gdt_success_rate = round(gdt_success / gdt_total * 100, 2) if gdt_total else 0
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
            {"time": r.get("started_at", ""), "errors": r.get("errors", "")}
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
    dn_runs = await _sqlite_read(
        DN_DB,
        """SELECT run_id, job_name, started_at, finished_at, status, error_text
           FROM job_runs WHERE started_at >= date('now', ?)
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
            {"job": r.get("job_name", ""), "time": r.get("started_at", ""), "error": (r.get("error_text") or "")[:200]}
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
    cie_contents = await _sqlite_read(
        CIE_DB,
        """SELECT created_at, qa_total_score
           FROM generated_contents WHERE created_at >= date('now', ?)
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


@router.get("/api/mcp_health")
async def mcp_health():
    """MCP 서버 헬스 체크."""
    mcp_dir = WORKSPACE / "mcp"
    servers = []
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
            try:
                src_files = list(unit_path.glob("src/**/*"))
                if src_files:
                    latest = max(f.stat().st_mtime for f in src_files if f.is_file())
                    info["last_modified"] = datetime.fromtimestamp(latest).isoformat()
            except Exception:
                pass
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
