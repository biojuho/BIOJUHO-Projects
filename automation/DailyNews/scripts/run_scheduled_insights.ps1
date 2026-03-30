param(
    [ValidateSet("morning", "evening")]
    [string]$Window = "morning"
)

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$WorkspaceRoot = (Resolve-Path (Join-Path $ProjectRoot "..\..")).Path
$LogDir = Join-Path $ProjectRoot "logs\insights"
$PythonExe = Join-Path $WorkspaceRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = Join-Path $ProjectRoot "venv\Scripts\python.exe"
}
$Timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$LogFile = Join-Path $LogDir ("{0}_{1}.log" -f $Window, $Timestamp)

$WindowConfig = @{
    morning = @{
        PromptMode = "v2-deep"
        Categories = @("Tech", "AI_Deep", "Economy_KR", "Economy_Global", "Crypto", "Global_Affairs")
    }
    evening = @{
        PromptMode = "v2-multi"
        Categories = @("Tech", "AI_Deep", "Economy_KR", "Economy_Global", "Crypto", "Global_Affairs")
    }
}

$Config = $WindowConfig[$Window]

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-Log {
    param([string]$Message)
    Add-Content -Path $LogFile -Value $Message -Encoding utf8
}

function Invoke-PythonScriptText {
    param(
        [string]$ScriptText
    )

    $TempScript = Join-Path $env:TEMP ("dailynews_{0}.py" -f ([guid]::NewGuid().ToString("N")))
    try {
        Set-Content -Path $TempScript -Value $ScriptText -Encoding utf8
        & $PythonExe -X utf8 $TempScript 2>&1
        return
    }
    finally {
        Remove-Item $TempScript -Force -ErrorAction SilentlyContinue
    }
}

Write-Log "========================================="
Write-Log ("DailyNews {0} insight generation started" -f $Window)
Write-Log ("Mode: {0}" -f $Config.PromptMode)
Write-Log ("Started: {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
Write-Log ("ProjectRoot: {0}" -f $ProjectRoot)
Write-Log "========================================="

if (-not (Test-Path $PythonExe)) {
    Write-Log ("[ERROR] Python executable not found: {0}" -f $PythonExe)
    exit 1
}

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONPATH = "{0}\src;{1};{2}" -f $ProjectRoot, $WorkspaceRoot, $env:PYTHONPATH

# --- Step 0: Pre-run cleanup (stale locks) ---
Write-Log "[STEP 0] Cleaning stale locks..."
$LockFile = Join-Path $ProjectRoot "data\news_bot.lock"
if (Test-Path $LockFile) {
    try { Remove-Item $LockFile -Force; Write-Log "[CLEANUP] Removed stale lock file" }
    catch { Write-Log ("[CLEANUP] Could not remove lock file: {0}" -f $_.Exception.Message) }
}

$CleanupScript = @"
import sqlite3, datetime
db = r'$ProjectRoot\data\pipeline_state.db'
conn = sqlite3.connect(db)
cur = conn.cursor()
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
cur.execute("UPDATE job_runs SET status='failed', finished_at=?, error_text='Auto-cleaned stale lock (pre-run)' WHERE status='running' AND started_at < datetime('now', '-30 minutes')", (now,))
cleaned = cur.rowcount
conn.commit()
conn.close()
print(f'Cleaned {cleaned} stale DB lock(s)')
"@
Invoke-PythonScriptText -ScriptText $CleanupScript | ForEach-Object { Write-Log "[CLEANUP] $_" }

# --- Step 1: Generate briefs ---
Write-Log "[STEP 1] Generating briefs..."
$GenerateArgs = @(
    "-m", "antigravity_mcp",
    "jobs", "generate-brief",
    "--window", $Window,
    "--max-items", "10",
    "--categories"
) + $Config.Categories

Push-Location $ProjectRoot
try {
    Write-Log ("Python: {0}" -f (& $PythonExe --version))
    Write-Log ("Command: {0} {1}" -f $PythonExe, ($GenerateArgs -join " "))

    $GenerateOutput = & $PythonExe @GenerateArgs 2>&1
    $GenerateOutput | ForEach-Object { Add-Content -Path $LogFile -Value $_ -Encoding utf8 }
    $GenerateExitCode = $LASTEXITCODE

    # Extract report IDs — Method 1: regex (encoding-safe)
    $ReportIds = @()
    try {
        $GenerateText = ($GenerateOutput | ForEach-Object { [string]$_ }) -join [Environment]::NewLine
        $RegexResult = [regex]::Matches($GenerateText, '"(report-[a-z_]+-\d{8}T\d{6}Z)"')
        $Seen = @{}
        foreach ($m in $RegexResult) {
            $rid = $m.Groups[1].Value
            if (-not $Seen.ContainsKey($rid)) {
                $ReportIds += $rid
                $Seen[$rid] = $true
            }
        }
        if ($ReportIds.Count -gt 0) {
            Write-Log ("[EXTRACT] Regex extracted {0} report ID(s)" -f $ReportIds.Count)
        }
    } catch {
        Write-Log ("[WARNING] Regex extraction failed: {0}" -f $_.Exception.Message)
    }

    # Extract report IDs — Method 2: DB fallback (if regex found nothing)
    if ($ReportIds.Count -eq 0) {
        Write-Log "[EXTRACT] Regex found 0 IDs; querying DB for recent draft reports..."
        $DbFallbackScript = @"
import sqlite3, datetime
db = r'$ProjectRoot\data\pipeline_state.db'
conn = sqlite3.connect(db)
cur = conn.cursor()
cutoff = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=15)).isoformat()
cur.execute("SELECT report_id FROM content_reports WHERE status='draft' AND approval_state='manual' AND (notion_page_id IS NULL OR notion_page_id = '') AND created_at >= ?", (cutoff,))
ids = [r[0] for r in cur.fetchall()]
conn.close()
for rid in ids:
    print(rid)
"@
        $DbResult = Invoke-PythonScriptText -ScriptText $DbFallbackScript
        if ($DbResult) {
            $ReportIds = @($DbResult | ForEach-Object { $_.Trim() } | Where-Object { $_ -match '^report-' })
            Write-Log ("[EXTRACT] DB fallback found {0} draft report(s)" -f $ReportIds.Count)
        }
    }

    if ($ReportIds.Count -gt 0) {
        Write-Log ("[SUCCESS] Generated {0} report(s): {1}" -f $ReportIds.Count, ($ReportIds -join ", "))
    } elseif ($GenerateExitCode -eq 0) {
        Write-Log "[SUCCESS] Brief generation completed (no new reports)"
    } else {
        Write-Log ("[WARNING] Brief generation exit code {0}, attempting publish of any created reports" -f $GenerateExitCode)
    }

    # --- Step 2: Auto-publish generated reports ---
    Write-Log "[STEP 2] Auto-publishing draft reports..."
    if ($ReportIds.Count -eq 0) {
        Write-Log "[PUBLISH] No report_ids parsed from generate-brief output; skipping auto-publish."
    } else {
        Write-Log ("[PUBLISH] Publishing {0} report(s): {1}" -f $ReportIds.Count, ($ReportIds -join ", "))
        foreach ($ReportId in $ReportIds) {
            $PublishArgs = @(
                "-m", "antigravity_mcp",
                "jobs", "publish-report",
                "--report-id", $ReportId,
                "--approval-mode", "auto"
            )
            $PublishOutput = & $PythonExe @PublishArgs 2>&1
            $PublishOutput | ForEach-Object { Add-Content -Path $LogFile -Value ("[PUBLISH-DETAIL] {0}" -f $_) -Encoding utf8 }
            if ($LASTEXITCODE -eq 0) {
                Write-Log ("[PUBLISH] OK: {0} published" -f $ReportId)
            } else {
                Write-Log ("[PUBLISH] WARN: {0} publish exit {1}" -f $ReportId, $LASTEXITCODE)
            }
        }
    }

    # --- Step 3: Refresh dashboard ---
    Write-Log "[STEP 3] Refreshing dashboard..."
    $RefreshArgs = @("-m", "antigravity_mcp", "ops", "refresh-dashboard")
    & $PythonExe @RefreshArgs *>> $LogFile
    if ($LASTEXITCODE -eq 0) {
        Write-Log "[SUCCESS] Dashboard refresh completed"
    } else {
        Write-Log "[WARNING] Dashboard refresh failed"
    }

    # --- Step 3.5: Export to NotebookLM ---
    Write-Log "[STEP 3.5] Exporting to NotebookLM..."
    $NlmArgs = @("-X", "utf8", (Join-Path $ProjectRoot "scripts\export_to_notebooklm.py"))
    & $PythonExe @NlmArgs *>> $LogFile
    if ($LASTEXITCODE -eq 0) {
        Write-Log "[SUCCESS] NotebookLM export completed"
    } else {
        Write-Log "[WARNING] NotebookLM export failed (non-blocking)"
    }

    # --- Step 4: Final stale lock cleanup ---
    Invoke-PythonScriptText -ScriptText $CleanupScript | ForEach-Object { Write-Log "[POST-CLEANUP] $_" }

    Write-Log ("Finished: {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
    exit 0
}
finally {
    Pop-Location
}
