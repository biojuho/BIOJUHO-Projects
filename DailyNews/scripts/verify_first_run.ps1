# =========================================================================
# DailyNews - 첫 자동 실행 검증 스크립트
# =========================================================================
#
# 용도: 스케줄된 작업의 첫 실행 후 결과를 자동으로 검증합니다.
#
# 사용법:
#   1. 첫 실행 예정 시간 10분 후 실행
#   2. PowerShell에서: .\verify_first_run.ps1
#
# 작성일: 2026-03-21
# =========================================================================

param(
    [string]$TaskType = "auto"  # "morning", "evening", "auto"
)

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "DailyNews First Run Verification" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

$ProjectRoot = "d:\AI 프로젝트\DailyNews"
$LogDir = "$ProjectRoot\logs\insights"

# =========================================================================
# 1. Task Scheduler 상태 확인
# =========================================================================

Write-Host "[1/5] Checking Task Scheduler Status..." -ForegroundColor Yellow

$MorningTask = Get-ScheduledTask -TaskName "DailyNews_Morning_Insights" -ErrorAction SilentlyContinue
$EveningTask = Get-ScheduledTask -TaskName "DailyNews_Evening_Insights" -ErrorAction SilentlyContinue

if (-not $MorningTask -and -not $EveningTask) {
    Write-Host "❌ ERROR: No scheduled tasks found!" -ForegroundColor Red
    Write-Host "Please run setup_scheduled_tasks.ps1 first." -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Tasks found" -ForegroundColor Green

if ($MorningTask) {
    $MorningInfo = Get-ScheduledTaskInfo -TaskName "DailyNews_Morning_Insights"
    Write-Host "   Morning Task:" -ForegroundColor Gray
    Write-Host "     State: $($MorningTask.State)" -ForegroundColor Gray
    Write-Host "     Last Run: $($MorningInfo.LastRunTime)" -ForegroundColor Gray
    Write-Host "     Last Result: $($MorningInfo.LastTaskResult)" -ForegroundColor Gray
    Write-Host "     Next Run: $($MorningInfo.NextRunTime)" -ForegroundColor Gray
}

if ($EveningTask) {
    $EveningInfo = Get-ScheduledTaskInfo -TaskName "DailyNews_Evening_Insights"
    Write-Host "   Evening Task:" -ForegroundColor Gray
    Write-Host "     State: $($EveningTask.State)" -ForegroundColor Gray
    Write-Host "     Last Run: $($EveningInfo.LastRunTime)" -ForegroundColor Gray
    Write-Host "     Last Result: $($EveningInfo.LastTaskResult)" -ForegroundColor Gray
    Write-Host "     Next Run: $($EveningInfo.NextRunTime)" -ForegroundColor Gray
}

Write-Host ""

# =========================================================================
# 2. 로그 파일 확인
# =========================================================================

Write-Host "[2/5] Checking Log Files..." -ForegroundColor Yellow

if (-not (Test-Path $LogDir)) {
    Write-Host "❌ ERROR: Log directory not found: $LogDir" -ForegroundColor Red
    exit 1
}

$LogFiles = Get-ChildItem -Path $LogDir -Filter "*.log" | Sort-Object LastWriteTime -Descending

if ($LogFiles.Count -eq 0) {
    Write-Host "⚠️  WARNING: No log files found yet" -ForegroundColor Yellow
    Write-Host "   This is normal if the first run hasn't occurred." -ForegroundColor Gray
} else {
    Write-Host "✅ Found $($LogFiles.Count) log file(s)" -ForegroundColor Green

    $LatestLog = $LogFiles[0]
    Write-Host "   Latest log: $($LatestLog.Name)" -ForegroundColor Gray
    Write-Host "   Created: $($LatestLog.LastWriteTime)" -ForegroundColor Gray
    Write-Host "   Size: $($LatestLog.Length) bytes" -ForegroundColor Gray
}

Write-Host ""

# =========================================================================
# 3. 최신 로그 내용 분석
# =========================================================================

Write-Host "[3/5] Analyzing Latest Log..." -ForegroundColor Yellow

if ($LogFiles.Count -gt 0) {
    $LatestLog = $LogFiles[0]
    $LogContent = Get-Content $LatestLog.FullName -Raw

    # 성공 여부 확인
    if ($LogContent -match "SUCCESS") {
        Write-Host "✅ Log contains SUCCESS message" -ForegroundColor Green
        $HasSuccess = $true
    } else {
        Write-Host "⚠️  No SUCCESS message found in log" -ForegroundColor Yellow
        $HasSuccess = $false
    }

    # 에러 확인
    $ErrorLines = $LogContent -split "`n" | Where-Object { $_ -match "ERROR|FAIL|Exception" }
    if ($ErrorLines.Count -gt 0) {
        Write-Host "⚠️  Found $($ErrorLines.Count) error line(s):" -ForegroundColor Yellow
        $ErrorLines | ForEach-Object {
            Write-Host "     $_" -ForegroundColor Red
        }
        $HasErrors = $true
    } else {
        Write-Host "✅ No errors found in log" -ForegroundColor Green
        $HasErrors = $false
    }

    # 마지막 20줄 표시
    Write-Host ""
    Write-Host "   Last 20 lines of log:" -ForegroundColor Gray
    Write-Host "   ---" -ForegroundColor Gray
    $LastLines = Get-Content $LatestLog.FullName -Tail 20
    $LastLines | ForEach-Object {
        Write-Host "   $_" -ForegroundColor Gray
    }
} else {
    Write-Host "⚠️  No logs to analyze yet" -ForegroundColor Yellow
    $HasSuccess = $false
    $HasErrors = $false
}

Write-Host ""

# =========================================================================
# 4. 데이터베이스 확인
# =========================================================================

Write-Host "[4/5] Checking Database..." -ForegroundColor Yellow

$DbPath = "$ProjectRoot\data\pipeline_state.db"

if (-not (Test-Path $DbPath)) {
    Write-Host "⚠️  WARNING: Database not found: $DbPath" -ForegroundColor Yellow
} else {
    try {
        $DbSize = (Get-Item $DbPath).Length / 1KB
        Write-Host "✅ Database found ($($DbSize.ToString('F2')) KB)" -ForegroundColor Green

        # Python으로 최근 실행 조회
        $RecentRuns = python -c @"
import sys
sys.path.insert(0, 'src')
import sqlite3
conn = sqlite3.connect('data/pipeline_state.db')
cursor = conn.cursor()
cursor.execute('SELECT run_id, status, started_at FROM job_runs ORDER BY started_at DESC LIMIT 3')
for row in cursor.fetchall():
    print(f'{row[0][:35]} | {row[1]:8s} | {row[2][:19]}')
conn.close()
"@ -WorkingDirectory $ProjectRoot

        if ($RecentRuns) {
            Write-Host "   Recent runs:" -ForegroundColor Gray
            $RecentRuns -split "`n" | ForEach-Object {
                Write-Host "     $_" -ForegroundColor Gray
            }
        }
    } catch {
        Write-Host "⚠️  Could not query database: $_" -ForegroundColor Yellow
    }
}

Write-Host ""

# =========================================================================
# 5. Notion 연결 확인 (선택사항)
# =========================================================================

Write-Host "[5/5] Checking Notion Integration (optional)..." -ForegroundColor Yellow

$NotionApiKey = $env:NOTION_API_KEY
if (-not $NotionApiKey) {
    Write-Host "⚠️  NOTION_API_KEY not set in environment" -ForegroundColor Yellow
} else {
    Write-Host "✅ NOTION_API_KEY is configured" -ForegroundColor Green
}

Write-Host ""

# =========================================================================
# 종합 평가
# =========================================================================

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Verification Summary" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

$Score = 0
$MaxScore = 5

# 1. Tasks registered
if ($MorningTask -or $EveningTask) {
    Write-Host "✅ Scheduled tasks registered" -ForegroundColor Green
    $Score++
} else {
    Write-Host "❌ No scheduled tasks" -ForegroundColor Red
}

# 2. Log files exist
if ($LogFiles.Count -gt 0) {
    Write-Host "✅ Log files generated" -ForegroundColor Green
    $Score++
} else {
    Write-Host "⏳ Waiting for first run..." -ForegroundColor Yellow
}

# 3. Success message in log
if ($HasSuccess) {
    Write-Host "✅ Execution successful" -ForegroundColor Green
    $Score++
} else {
    Write-Host "⏳ No successful execution yet" -ForegroundColor Yellow
}

# 4. No errors
if (-not $HasErrors -and $LogFiles.Count -gt 0) {
    Write-Host "✅ No errors detected" -ForegroundColor Green
    $Score++
} elseif ($LogFiles.Count -eq 0) {
    Write-Host "⏳ No logs to check for errors" -ForegroundColor Yellow
} else {
    Write-Host "⚠️  Errors detected in log" -ForegroundColor Yellow
}

# 5. Database accessible
if (Test-Path $DbPath) {
    Write-Host "✅ Database accessible" -ForegroundColor Green
    $Score++
} else {
    Write-Host "❌ Database not found" -ForegroundColor Red
}

Write-Host ""
Write-Host "Overall Score: $Score / $MaxScore" -ForegroundColor $(if ($Score -ge 4) { "Green" } elseif ($Score -ge 3) { "Yellow" } else { "Red" })

if ($Score -eq 5) {
    Write-Host "🎉 Perfect! Everything is working as expected." -ForegroundColor Green
} elseif ($Score -ge 3) {
    Write-Host "👍 Looking good! Check warnings above." -ForegroundColor Yellow
} else {
    Write-Host "⚠️  Issues detected. Please review the output above." -ForegroundColor Red
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow

if ($Score -lt 2) {
    Write-Host "  1. Run setup_scheduled_tasks.ps1 if tasks are not registered" -ForegroundColor Gray
    Write-Host "  2. Wait for the next scheduled time (7 AM or 6 PM)" -ForegroundColor Gray
} elseif ($LogFiles.Count -eq 0) {
    Write-Host "  1. Wait for next scheduled execution" -ForegroundColor Gray
    Write-Host "  2. Or manually run: scripts\test_insight_generation.bat morning" -ForegroundColor Gray
} elseif ($HasErrors) {
    Write-Host "  1. Review error messages in the log" -ForegroundColor Gray
    Write-Host "  2. Check environment variables (.env file)" -ForegroundColor Gray
    Write-Host "  3. Verify Notion database schema" -ForegroundColor Gray
} else {
    Write-Host "  1. Check Notion for new pages" -ForegroundColor Gray
    Write-Host "  2. Monitor logs directory regularly" -ForegroundColor Gray
    Write-Host "  3. Review weekly statistics" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
