# MCP Smoke Trace Metrics

## Source

- Smoke report: `docs\reports\2026-06\WORKSPACE_SMOKE_USAGE_SIDECAR_2026-06-05.json`
- Scope: `mcp`
- Source status: `complete`
- Source generated at: `2026-06-05T08:43:44.031405+00:00`

## Summary

- Checks: 1
- Passed: 1
- Failed: 0
- Timing observed: 0 observed, 1 missing
- Total observed seconds: `None`
- Slowest check: `None` (`None`s)
- Usage observed: 1 observed, 0 missing
- Total tokens: `155`
- Cost USD: `0.0042`
- Costliest check: `usage sidecar probe` (`0.0042` USD)
- Max cwd depth: 0
- Max command path depth: 0
- Command path tokens: 0

## Runtime Kinds

| Kind | Count |
| --- | ---: |
| other | 1 |

## Checks

| Check | Kind | OK | CWD | Duration seconds | Total tokens | Cost USD | Command path depth |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| usage sidecar probe | other | true | . |  | 155 | 0.0042 | 0 |

## Span Tree

- Root span: `mcp:root`
- Child spans: 1
- Max depth: 1

| Span | Parent | Previous | Check | Status |
| --- | --- | --- | --- | --- |
| mcp:check:1 | mcp:root |  | usage sidecar probe | ok |

## Trace Integrity

- OK: `true`
- Issues: none
