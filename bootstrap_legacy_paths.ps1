param(
    [switch]$Force = $false
)

$workspaceRoot = Split-Path -Parent $PSCommandPath
$python = if (Test-Path (Join-Path $workspaceRoot ".venv\\Scripts\\python.exe")) {
    Join-Path $workspaceRoot ".venv\\Scripts\\python.exe"
} else {
    "python"
}

$argsList = @((Join-Path $workspaceRoot "bootstrap_legacy_paths.py"))
if ($Force) {
    $argsList += "--force"
}

& $python @argsList
exit $LASTEXITCODE
