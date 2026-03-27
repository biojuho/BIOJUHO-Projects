$src = "D:\AI 프로젝트"
$dst = "I:\내 드라이브\AI-Projects-Backup"

$excludeDirs = @("node_modules","__pycache__",".venv","venv","dist","build",
                 ".git",".agent",".agents","artifacts","cache","chroma_db",
                 "test-results","output","data","ignition","typechain-types",
                 ".hardhat","coverage")
$excludeExts = @(".pyc",".log",".db",".sqlite",".tmp",".class",".o")
$excludeFiles = @(".env","credentials.json","token.json","serviceAccountKey.json",
                  "canva_url.txt","package-lock.json","*.lock","yarn.lock")

function Copy-Filtered {
    param([string]$Source, [string]$Dest)

    if (-not (Test-Path $Dest)) {
        New-Item -ItemType Directory -Path $Dest -Force | Out-Null
    }

    $items = Get-ChildItem $Source -ErrorAction SilentlyContinue
    foreach ($item in $items) {
        if ($item.PSIsContainer) {
            if ($item.Name -in $excludeDirs) { continue }
            Copy-Filtered -Source $item.FullName -Dest (Join-Path $Dest $item.Name)
        } else {
            if ($item.Name -in $excludeFiles) { continue }
            if ($item.Extension -in $excludeExts) { continue }
            try {
                Copy-Item -Path $item.FullName -Destination (Join-Path $Dest $item.Name) -Force
            } catch {
                Write-Host "  SKIP: $($item.Name) - $_" -ForegroundColor DarkGray
            }
        }
    }
}

Write-Host "===================================" -ForegroundColor Cyan
Write-Host "  AI 프로젝트 -> Google Drive 동기화" -ForegroundColor Cyan
Write-Host "===================================" -ForegroundColor Cyan
Write-Host "소스: $src"
Write-Host "대상: $dst"
Write-Host ""

$startTime = Get-Date
Copy-Filtered -Source $src -Dest $dst
$elapsed = [math]::Round(((Get-Date) - $startTime).TotalSeconds, 1)

$count = (Get-ChildItem $dst -Recurse -File -ErrorAction SilentlyContinue).Count
$sizeMB = [math]::Round((Get-ChildItem $dst -Recurse -File -ErrorAction SilentlyContinue |
           Measure-Object -Property Length -Sum).Sum / 1MB, 1)

Write-Host ""
Write-Host "===================================" -ForegroundColor Green
Write-Host "  완료!" -ForegroundColor Green
Write-Host "  파일 수  : $count" -ForegroundColor White
Write-Host "  총 크기  : ${sizeMB} MB" -ForegroundColor White
Write-Host "  소요 시간: ${elapsed}초" -ForegroundColor White
Write-Host "===================================" -ForegroundColor Green
