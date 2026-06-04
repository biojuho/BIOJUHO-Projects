# MCP Service Manifest

- Generated at: `2026-06-04T12:05:12.843643+00:00`
- Manifest generated at: `2026-06-04T21:03:00+09:00`
- Total services: `4`
- FastMCP services: `3`
- Languages: `{"python": 3, "typescript": 1}`
- Frameworks: `{"FastMCP": 3, "MCP SDK": 1}`
- Transports: `{"http-metadata": 1, "sse": 1, "stdio": 3}`

## Services

### dailynews-antigravity

- Name: Antigravity Content Engine MCP
- Project: `DailyNews`
- Language/framework: `python` / `FastMCP`
- Transports: `stdio`
- Detected tools: `26`
- Required env count: `0`
- Smoke checks: `DailyNews unit tests`

### desci-research

- Name: DeSci Research MCP
- Project: `desci`
- Language/framework: `python` / `FastMCP`
- Transports: `stdio`
- Detected tools: `6`
- Required env count: `0`
- Smoke checks: `desci-research-mcp helper tests`

### telegram-bot

- Name: Telegram Bot MCP
- Project: `notifications`
- Language/framework: `python` / `FastMCP`
- Transports: `stdio`
- Detected tools: `7`
- Required env count: `2`
- Smoke checks: `telegram-mcp helper tests`

### canva-local

- Name: Canva MCP
- Project: `canva-mcp`
- Language/framework: `typescript` / `MCP SDK`
- Transports: `sse, http-metadata`
- Detected tools: `20`
- Required env count: `2`
- Smoke checks: `canva mcp typecheck, canva mcp server build`
