param(
    [string]$ProjectPath,
    [string]$DriveLetter = "G",
    [string]$BackupFolder = "AI-Projects-Backup"
)

function Resolve-WorkspaceRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

function Find-GoogleDriveRoot {
    param([string]$MountLetter)

    $candidates = @(
        "${MountLetter}:\My Drive",
        "${MountLetter}:\내 드라이브",
        "$env:USERPROFILE\Google Drive\My Drive",
        "$env:USERPROFILE\Google Drive\내 드라이브",
        "$env:USERPROFILE\Google Drive"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    return $null
}

$resolvedProjectPath = if ($ProjectPath) { (Resolve-Path $ProjectPath).Path } else { Resolve-WorkspaceRoot }
$googleDriveRoot = Find-GoogleDriveRoot -MountLetter $DriveLetter

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Google Drive sync setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Workspace: $resolvedProjectPath" -ForegroundColor Green

if (-not $googleDriveRoot) {
    Write-Host "ERROR: Could not find a Google Drive mount." -ForegroundColor Red
    Write-Host "Try a different drive letter or run with -ProjectPath and -DriveLetter." -ForegroundColor Yellow
    exit 1
}

$syncTarget = Join-Path $googleDriveRoot $BackupFolder
if (-not (Test-Path $syncTarget)) {
    New-Item -ItemType Directory -Path $syncTarget -Force | Out-Null
}

Write-Host "Google Drive root: $googleDriveRoot" -ForegroundColor Green
Write-Host "Backup target    : $syncTarget" -ForegroundColor Green
Write-Host ""

$syncScript = Join-Path $PSScriptRoot "sync_to_gdrive.ps1"
& powershell -NoProfile -ExecutionPolicy Bypass -File $syncScript -SourcePath $resolvedProjectPath -DestinationPath $syncTarget

Write-Host ""
Write-Host "Suggested scheduled task command:" -ForegroundColor Yellow
Write-Host "powershell -ExecutionPolicy Bypass -File `"$syncScript`" -SourcePath `"$resolvedProjectPath`" -DestinationPath `"$syncTarget`"" -ForegroundColor Gray
