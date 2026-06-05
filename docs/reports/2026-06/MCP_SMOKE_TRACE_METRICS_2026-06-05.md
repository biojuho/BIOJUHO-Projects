# MCP Smoke Trace Metrics

## Source

- Smoke report: `var\workspace-smoke-mcp-canva-tool-inventory-2026-06-05.json`
- Scope: `mcp`
- Source status: `complete`
- Source generated at: `2026-06-05T07:13:25.621676+00:00`

## Summary

- Checks: 6
- Passed: 6
- Failed: 0
- Timing observed: 4 observed, 2 missing
- Total observed seconds: `119.43`
- Slowest check: `DailyNews unit tests` (`117.48`s)
- Max cwd depth: 2
- Max command path depth: 5
- Command path tokens: 14

## Runtime Kinds

| Kind | Count |
| --- | ---: |
| compileall | 2 |
| npm | 1 |
| pytest | 3 |

## Checks

| Check | Kind | OK | CWD | Duration seconds | Command path depth |
| --- | --- | --- | --- | ---: | ---: |
| notebooklm compile | compileall | true | . |  | 5 |
| github-mcp compile | compileall | true | . |  | 5 |
| DailyNews unit tests | pytest | true | automation\DailyNews | 117.48 | 4 |
| canva-mcp build | npm | true | mcp\canva-mcp | 1.17 | 0 |
| desci-research-mcp tests | pytest | true | mcp\desci-research-mcp | 0.38 | 4 |
| telegram-mcp tests | pytest | true | mcp\telegram-mcp | 0.4 | 4 |

## Trace Integrity

- OK: `true`
- Issues: none
