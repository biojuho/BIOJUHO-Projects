# ============================================================
# GitHub Secrets 설정 헬퍼 스크립트
# 
# 사용법:
#   1. 먼저 gh CLI 로그인: gh auth login
#   2. 이 스크립트 실행: .\scripts\export_secrets_for_github.ps1
#   
# 또는:
#   -ListOnly 플래그로 키 목록만 확인:
#   .\scripts\export_secrets_for_github.ps1 -ListOnly
# ============================================================

param(
    [switch]$ListOnly,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path "$ROOT\.env")) { $ROOT = "d:\AI project" }

$REPO = "biojuho/BIOJUHO-Projects"

# === Source files ===
$rootEnv = "$ROOT\.env"
$gdtEnv = "$ROOT\automation\getdaytrends\.env"

function Get-EnvValue($file, $key) {
    if (-not (Test-Path $file)) { return $null }
    $line = Get-Content $file | Where-Object { $_ -match "^$key=" }
    if ($line) { return ($line -split "=", 2)[1].Trim().Trim('"').Trim("'") }
    return $null
}

# === Secret definitions: [Name, Source file, Required level] ===
$secrets = @(
    @("ANTHROPIC_API_KEY",    $rootEnv, "REQUIRED"),
    @("GOOGLE_API_KEY",       $rootEnv, "REQUIRED"),
    @("NOTION_TOKEN",         $gdtEnv,  "REQUIRED"),
    @("NOTION_DATABASE_ID",   $gdtEnv,  "REQUIRED"),
    @("OPENAI_API_KEY",       $rootEnv, "RECOMMENDED"),
    @("XAI_API_KEY",          $rootEnv, "RECOMMENDED"),
    @("DEEPSEEK_API_KEY",     $rootEnv, "RECOMMENDED"),
    @("TELEGRAM_BOT_TOKEN",   $rootEnv, "RECOMMENDED"),
    @("TELEGRAM_CHAT_ID",     $rootEnv, "RECOMMENDED"),
    @("TWITTER_BEARER_TOKEN", $gdtEnv,  "RECOMMENDED"),
    @("CONTENT_HUB_DATABASE_ID", $gdtEnv, "OPTIONAL"),
    @("IMGBB_API_KEY",        $gdtEnv,  "OPTIONAL"),
    @("DISCORD_WEBHOOK_URL",  $gdtEnv,  "OPTIONAL")
)

Write-Host ""
Write-Host "=== GitHub Secrets Setup for $REPO ===" -ForegroundColor Cyan
Write-Host ""

if ($ListOnly) {
    Write-Host "Mode: LIST ONLY (no changes)" -ForegroundColor Yellow
    Write-Host ""
    foreach ($s in $secrets) {
        $name = $s[0]; $file = $s[1]; $level = $s[2]
        $val = Get-EnvValue $file $name
        $status = if ($val) { "FOUND (${$val.Length} chars)" } else { "MISSING" }
        $color = if ($val -and $level -eq "REQUIRED") { "Green" }
                 elseif ($val) { "Green" }
                 elseif ($level -eq "REQUIRED") { "Red" }
                 else { "Yellow" }
        Write-Host "  [$level] $name = $status" -ForegroundColor $color
    }
    Write-Host ""
    Write-Host "To set these secrets, run:" -ForegroundColor White
    Write-Host "  1. gh auth login" -ForegroundColor Gray
    Write-Host "  2. .\scripts\export_secrets_for_github.ps1" -ForegroundColor Gray
    exit 0
}

# === Check gh auth ===
$authOk = $false
try {
    gh auth status 2>&1 | Out-Null
    $authOk = ($LASTEXITCODE -eq 0)
} catch { }

if (-not $authOk) {
    Write-Host "ERROR: gh CLI not authenticated. Run 'gh auth login' first." -ForegroundColor Red
    exit 1
}

Write-Host "Mode: SET SECRETS via gh CLI" -ForegroundColor Green
Write-Host ""

$set = 0; $skip = 0; $fail = 0
foreach ($s in $secrets) {
    $name = $s[0]; $file = $s[1]; $level = $s[2]
    $val = Get-EnvValue $file $name
    
    if (-not $val) {
        Write-Host "  SKIP $name (no value found)" -ForegroundColor Yellow
        $skip++
        continue
    }
    
    if ($DryRun) {
        Write-Host "  [DRY-RUN] Would set $name ($($val.Length) chars)" -ForegroundColor Cyan
        $set++
        continue
    }
    
    try {
        Write-Host "  Setting $name... " -NoNewline
        $val | gh secret set $name --repo $REPO 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "OK" -ForegroundColor Green
            $set++
        } else {
            Write-Host "FAILED" -ForegroundColor Red
            $fail++
        }
    } catch {
        Write-Host "ERROR: $_" -ForegroundColor Red
        $fail++
    }
}

Write-Host ""
Write-Host "Results: $set set, $skip skipped, $fail failed" -ForegroundColor $(if ($fail) { "Red" } else { "Green" })
