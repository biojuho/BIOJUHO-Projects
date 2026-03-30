param()

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$packRoot = Join-Path $projectRoot "review_pack"
$sharedRoot = Join-Path $packRoot "shared"

$files = @(
    "review_pack/PROJECT_BRIEF.md",
    "review_pack/PROMPT_TO_EXTERNAL_LLM.md",
    "review_pack/REDACTION_AND_ATTACHMENTS.md",
    "README.md",
    "pyproject.toml",
    "docs/product/kpis.md",
    "prompts/insight_quality_check.md",
    "config/reasoning_prompts.json",
    "output/SAMPLE-INSIGHT-OUTPUT.md",
    "src/antigravity_mcp/cli.py",
    "src/antigravity_mcp/server.py",
    "src/antigravity_mcp/config.py",
    "src/antigravity_mcp/pipelines/analyze.py",
    "src/antigravity_mcp/integrations/llm_adapter.py",
    "src/antigravity_mcp/integrations/insight_adapter.py",
    "src/antigravity_mcp/state/store.py",
    "tests/test_notion_adapter.py",
    "tests/unit/test_adapters.py"
)

New-Item -ItemType Directory -Force -Path $sharedRoot | Out-Null

$copied = New-Object System.Collections.Generic.List[string]

foreach ($relativePath in $files) {
    $sourcePath = Join-Path $projectRoot $relativePath
    if (-not (Test-Path -LiteralPath $sourcePath)) {
        Write-Warning "Skipped missing file: $relativePath"
        continue
    }

    $normalizedRelativePath = $relativePath -replace "/", "\"
    if ($normalizedRelativePath.StartsWith("review_pack\")) {
        $destinationRelativePath = $normalizedRelativePath.Substring("review_pack\".Length)
    } else {
        $destinationRelativePath = $normalizedRelativePath
    }

    $destinationPath = Join-Path $sharedRoot $destinationRelativePath
    $destinationDir = Split-Path -Parent $destinationPath
    New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null
    Copy-Item -LiteralPath $sourcePath -Destination $destinationPath -Force
    $copied.Add($destinationRelativePath) | Out-Null
}

$manifestPath = Join-Path $sharedRoot "MANIFEST.txt"
$manifestLines = @(
    "DailyNews external review pack",
    "Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")",
    "",
    "Included files:"
) + ($copied | Sort-Object | ForEach-Object { "- $_" })

Set-Content -LiteralPath $manifestPath -Value $manifestLines -Encoding utf8

Write-Host "Created review pack at: $sharedRoot"
