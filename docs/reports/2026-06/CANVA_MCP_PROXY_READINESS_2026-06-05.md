# Canva MCP Proxy Readiness

## Summary

- Service: `canva-mcp`
- Ready: `true`
- Tool count: 22
- OpenAPI path count: 22
- Generated at: `2026-06-05T07:58:16.121652+00:00`

## Commands

- Build cwd: `mcp/canva-mcp`
- Build: `npm run build:server`
- Proxy cwd: `mcp/canva-mcp`
- Proxy: `uvx mcpo --port 8000 --api-key <CANVA_MCP_PROXY_API_KEY> -- node dist/server/stdio.js`
- Docs: `http://localhost:8000/docs`
- OpenAPI: `http://localhost:8000/openapi.json`

## Checks

| Check | OK | Detail |
| --- | --- | --- |
| tools-source | true | mcp\canva-mcp\src\server\tools.ts |
| stdio-source | true | mcp\canva-mcp\src\server\stdio.ts |
| dist-stdio | true | mcp\canva-mcp\dist\server\stdio.js |
| openapi-contract | true | docs\reports\2026-06\CANVA_MCP_OPENAPI_CONTRACT_2026-06-05.json |
| api-key-env | true | CANVA_MCP_PROXY_API_KEY is configured |
| contract-api-key-security | true | OpenAPI contract defines X-API-Key security |
| contract-tool-sync | true | OpenAPI paths match tools.ts |
