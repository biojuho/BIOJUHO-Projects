# Fix GetDayTrends Task Scheduler - must run as Administrator
# Run: powershell -ExecutionPolicy Bypass -File "d:\AI 프로젝트\scripts\fix_scheduler_logon.ps1"

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: Run as Administrator!" -ForegroundColor Red
    exit 1
}

Write-Host "=== Fix GetDayTrends Scheduler ===" -ForegroundColor Cyan

# Export current task XML
$xmlPath = "$env:TEMP\gdt_fix.xml"
schtasks /query /tn "GetDayTrends" /xml | Out-File -FilePath $xmlPath -Encoding unicode -Force

# Read and fix LogonType: InteractiveToken -> S4U (run without user logged in)
$content = Get-Content $xmlPath -Raw
$content = $content -replace '<LogonType>InteractiveToken</LogonType>', '<LogonType>S4U</LogonType>'
$content | Out-File -FilePath $xmlPath -Encoding unicode -Force

# Re-register task
Write-Host "Deleting old task..." -ForegroundColor Yellow
schtasks /delete /tn "GetDayTrends" /f

Write-Host "Creating fixed task..." -ForegroundColor Yellow
schtasks /create /tn "GetDayTrends" /xml $xmlPath

if ($LASTEXITCODE -eq 0) {
    Write-Host "SUCCESS! GetDayTrends will now run without user login." -ForegroundColor Green
    schtasks /query /tn "GetDayTrends" /fo LIST | Select-String "Status|Next Run|Logon"
} else {
    Write-Host "FAILED. Error: $LASTEXITCODE" -ForegroundColor Red
}
