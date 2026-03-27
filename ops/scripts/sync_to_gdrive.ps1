param(
    [string]$SourcePath,
    [string]$DestinationPath = "I:\My Drive\AI-Projects-Backup"
)

$src = if ($SourcePath) {
    (Resolve-Path $SourcePath).Path
} else {
    (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

$dst = $DestinationPath

$excludeDirs = @(
    "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".git", ".agent", ".agents", "artifacts", "cache", "chroma_db",
    "test-results", "output", "data", "ignition", "typechain-types",
    ".hardhat", "coverage"
)
$excludeExts = @(".pyc", ".log", ".db", ".sqlite", ".tmp", ".class", ".o")
$excludeFiles = @(
    ".env", "credentials.json", "token.json", "serviceAccountKey.json",
    "canva_url.txt", "package-lock.json", "*.lock", "yarn.lock"
)

function Copy-Filtered {
    param([string]$CurrentSource, [string]$CurrentDest)

    if (-not (Test-Path $CurrentDest)) {
        New-Item -ItemType Directory -Path $CurrentDest -Force | Out-Null
    }

    foreach ($item in (Get-ChildItem $CurrentSource -ErrorAction SilentlyContinue)) {
        if ($item.PSIsContainer) {
            if ($item.Name -in $excludeDirs) { continue }
            Copy-Filtered -CurrentSource $item.FullName -CurrentDest (Join-Path $CurrentDest $item.Name)
            continue
        }

        if ($item.Name -in $excludeFiles) { continue }
        if ($item.Extension -in $excludeExts) { continue }

        try {
            Copy-Item -Path $item.FullName -Destination (Join-Path $CurrentDest $item.Name) -Force
        } catch {
            Write-Host "  SKIP: $($item.Name) - $_" -ForegroundColor DarkGray
        }
    }
}

Write-Host "===================================" -ForegroundColor Cyan
Write-Host "  AI Projects -> Google Drive sync" -ForegroundColor Cyan
Write-Host "===================================" -ForegroundColor Cyan
Write-Host "Source: $src"
Write-Host "Target: $dst"
Write-Host ""

$startTime = Get-Date
Copy-Filtered -CurrentSource $src -CurrentDest $dst
$elapsed = [math]::Round(((Get-Date) - $startTime).TotalSeconds, 1)

$count = (Get-ChildItem $dst -Recurse -File -ErrorAction SilentlyContinue).Count
$sizeMB = [math]::Round((Get-ChildItem $dst -Recurse -File -ErrorAction SilentlyContinue |
           Measure-Object -Property Length -Sum).Sum / 1MB, 1)

Write-Host ""
Write-Host "===================================" -ForegroundColor Green
Write-Host "  Done" -ForegroundColor Green
Write-Host "  Files : $count" -ForegroundColor White
Write-Host "  Size  : ${sizeMB} MB" -ForegroundColor White
Write-Host "  Elapsed: ${elapsed}s" -ForegroundColor White
Write-Host "===================================" -ForegroundColor Green
