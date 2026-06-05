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
- Usage observed: 0 observed, 6 missing
- Total tokens: `None`
- Cost USD: `None`
- Costliest check: `None` (`None` USD)
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

| Check | Kind | OK | CWD | Duration seconds | Total tokens | Cost USD | Command path depth |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| notebooklm compile | compileall | true | . |  |  |  | 5 |
| github-mcp compile | compileall | true | . |  |  |  | 5 |
| DailyNews unit tests | pytest | true | automation\DailyNews | 117.48 |  |  | 4 |
| canva-mcp build | npm | true | mcp\canva-mcp | 1.17 |  |  | 0 |
| desci-research-mcp tests | pytest | true | mcp\desci-research-mcp | 0.38 |  |  | 4 |
| telegram-mcp tests | pytest | true | mcp\telegram-mcp | 0.4 |  |  | 4 |

## Span Tree

- Root span: `mcp:root`
- Child spans: 6
- Max depth: 1

| Span | Parent | Previous | Check | Status |
| --- | --- | --- | --- | --- |
| mcp:check:1 | mcp:root |  | notebooklm compile | ok |
| mcp:check:2 | mcp:root | mcp:check:1 | github-mcp compile | ok |
| mcp:check:3 | mcp:root | mcp:check:2 | DailyNews unit tests | ok |
| mcp:check:4 | mcp:root | mcp:check:3 | canva-mcp build | ok |
| mcp:check:5 | mcp:root | mcp:check:4 | desci-research-mcp tests | ok |
| mcp:check:6 | mcp:root | mcp:check:5 | telegram-mcp tests | ok |

## Trace Integrity

- OK: `true`
- Issues: none
