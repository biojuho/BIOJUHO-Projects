from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OLD_ROOT_MARKERS = (
    r"d:\AI 프로젝트",
    r"D:\AI 프로젝트",
    "d:/AI 프로젝트",
    "D:/AI 프로젝트",
)
RUNTIME_FILES = [
    "apps/dashboard/api.py",
    "apps/desci-platform/biolinker/mcp_server.py",
    "apps/desci-platform/biolinker/services/analyzer.py",
    "automation/content-intelligence/config.py",
    "automation/getdaytrends/main.py",
    "automation/getdaytrends/GetDayTrends_NewTask.xml",
    "automation/getdaytrends/run_scheduler.bat",
    "automation/getdaytrends/start_services.bat",
    "automation/DailyNews/fix_morning_task.ps1",
    "automation/DailyNews/run_auto_log.bat",
    "automation/DailyNews/setup_schedule.ps1",
    "mcp/github-mcp/daily_backup.bat",
    "ops/scripts/gdrive_sync_setup.ps1",
    "ops/scripts/register_sync_task.bat",
    "ops/scripts/run_cost_dashboard.bat",
    "ops/scripts/run_evening_insights.bat",
    "ops/scripts/run_healthcheck.bat",
    "ops/scripts/run_morning_insights.bat",
    "ops/scripts/setup_scheduled_tasks.ps1",
    "ops/scripts/sync_gdrive.py",
    "ops/scripts/sync_to_gdrive.ps1",
    "ops/scripts/test_insight_generation.bat",
    "packages/shared/config.py",
    "packages/shared/llm/config.py",
]


def test_runtime_files_do_not_hardcode_old_workspace_root() -> None:
    offenders: list[str] = []

    for rel_path in RUNTIME_FILES:
        content = (PROJECT_ROOT / rel_path).read_text(encoding="utf-8")
        if any(marker in content for marker in OLD_ROOT_MARKERS):
            offenders.append(rel_path)

    assert offenders == []


def test_workspace_map_preserves_legacy_workspace_alias() -> None:
    workspace_map = json.loads((PROJECT_ROOT / "workspace-map.json").read_text(encoding="utf-8"))
    aliases = workspace_map.get("workspace_aliases", [])

    assert any(alias.get("legacy_name") == "AI 프로젝트" for alias in aliases)
