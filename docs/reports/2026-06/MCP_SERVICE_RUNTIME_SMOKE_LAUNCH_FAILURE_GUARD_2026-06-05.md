# MCP Service Runtime Smoke

- Status: `pass`
- Manifest generated at: `2026-06-04T21:03:00+09:00`
- Checked services: `3`
- Skipped services: `1`
- Passed services: `3`
- Failed services: `0`
- Credential-gated checked services: `1`
- Total tools listed: `39`

## Services

### dailynews-antigravity

- Status: `pass`
- Server: `Antigravity Content Engine MCP` / `1.27.2`
- Command: `"D:\AI project_push_8921d77\.venv\Scripts\python.exe" -m antigravity_mcp serve`
- Tools listed: `26`
- Expected minimum tools: `26`
- Missing env for tool calls: `none`
- Capability keys: `experimental, prompts, resources, tools`

### desci-research

- Status: `pass`
- Server: `desci-research` / `1.27.2`
- Command: `"D:\AI project_push_8921d77\.venv\Scripts\python.exe" server.py`
- Tools listed: `6`
- Expected minimum tools: `6`
- Missing env for tool calls: `none`
- Capability keys: `experimental, prompts, resources, tools`

### telegram-bot

- Status: `pass`
- Server: `telegram-bot` / `1.27.2`
- Command: `"D:\AI project_push_8921d77\.venv\Scripts\python.exe" server.py`
- Tools listed: `7`
- Expected minimum tools: `7`
- Missing env for tool calls: `TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID`
- Capability keys: `experimental, prompts, resources, tools`

## Skipped Services

- `canva-local`: `stdio_transport_not_declared`

## Errors

- none
