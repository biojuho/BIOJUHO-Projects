# Windows UTF-8 Runbook

Use this runbook when operating the project from PowerShell or Windows Task Scheduler.

## Shell Setup

```powershell
$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"
```

## Local Execution

```powershell
$env:PYTHONPATH="$PWD\src"
python -m antigravity_mcp jobs generate-brief --window manual --max-items 5
```

## Notes

- Repository docs and scripts are now stored in UTF-8.
- `run_server.bat` sets `PYTHONPATH` to `src` before launching the MCP server.
- If mojibake still appears in the terminal, update the console font and verify `chcp 65001`.
