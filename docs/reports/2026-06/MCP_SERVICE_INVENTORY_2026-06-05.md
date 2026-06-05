# MCP Service Inventory - 2026-06-05

## Summary

- Services: 5
- Status counts: active=4, candidate=1
- Languages: external=1, python=3, typescript=1
- Transports: cli=1, http-sse=1, stdio=4
- Auth boundaries: browser-auth=1, canva-oauth=1, environment-credentials=1, github-token=1, public-apis=1
- Generated at: `2026-06-05T18:10:00+09:00`

## Services

### canva-mcp

- Label: Canva MCP
- Project: `canva-mcp`
- Status: `active`
- Language: `typescript`
- Transport modes: `http-sse`, `stdio`
- Auth boundary: `canva-oauth`
- Smoke scope: `mcp`
- Smoke checks: `canva-mcp build`
- Entrypoints:
  - `mcp/canva-mcp/package.json`
  - `mcp/canva-mcp/src/server/server.ts`
  - `mcp/canva-mcp/src/server/tools.ts`
- Evidence:
  - `mcp/canva-mcp/tests/tool-inventory.test.mjs`
  - `docs/reports/2026-06/AUTO_RESEARCH_CANVA_TOOL_INVENTORY_GUARD_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_SMOKE_TRACE_METRICS_2026-06-05.md`

### desci-research-mcp

- Label: DeSci Research MCP
- Project: `desci-research-mcp`
- Status: `active`
- Language: `python`
- Transport modes: `stdio`
- Auth boundary: `public-apis`
- Smoke scope: `mcp`
- Smoke checks: `desci-research-mcp tests`
- Entrypoints:
  - `mcp/desci-research-mcp/pyproject.toml`
  - `mcp/desci-research-mcp/server.py`
- Evidence:
  - `mcp/desci-research-mcp/tests/test_server_helpers.py`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_SMOKE_TRACE_METRICS_2026-06-05.md`

### telegram-mcp

- Label: Telegram MCP
- Project: `telegram-mcp`
- Status: `active`
- Language: `python`
- Transport modes: `stdio`
- Auth boundary: `environment-credentials`
- Smoke scope: `mcp`
- Smoke checks: `telegram-mcp tests`
- Entrypoints:
  - `mcp/telegram-mcp/pyproject.toml`
  - `mcp/telegram-mcp/server.py`
- Evidence:
  - `mcp/telegram-mcp/tests/test_server_helpers.py`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_SMOKE_TRACE_METRICS_2026-06-05.md`

### github-mcp

- Label: GitHub MCP
- Project: `github-mcp`
- Status: `active`
- Language: `external`
- Transport modes: `stdio`
- Auth boundary: `github-token`
- Smoke scope: `mcp`
- Smoke checks: `github-mcp compile`
- Entrypoints:
  - `mcp/github-mcp/README.md`
  - `mcp/github-mcp/package.json`
  - `mcp/github-mcp/scripts/fetch_info.py`
- Evidence:
  - `mcp/github-mcp/tests/test_github_mcp.py`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_SMOKE_TRACE_METRICS_2026-06-05.md`

### notebooklm-mcp

- Label: NotebookLM MCP
- Project: `notebooklm-mcp`
- Status: `candidate`
- Language: `python`
- Transport modes: `cli`
- Auth boundary: `browser-auth`
- Smoke scope: `mcp`
- Smoke checks: `notebooklm compile`
- Entrypoints:
  - `mcp/notebooklm-mcp/pyproject.toml`
  - `mcp/notebooklm-mcp/scripts/list_notebooks.py`
- Evidence:
  - `mcp/notebooklm-mcp/tests/test_local_smoke.py`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_SMOKE_TRACE_METRICS_2026-06-05.md`
