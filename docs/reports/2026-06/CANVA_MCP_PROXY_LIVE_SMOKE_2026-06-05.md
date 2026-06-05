# Canva MCP Proxy Live Smoke

## Summary

- Service: `canva-mcp`
- OK: `true`
- Host: `127.0.0.1`
- Port: `59219`
- Checks: 5/5 passed
- OpenAPI path count: 22
- Auth header: `Authorization: Bearer <redacted>`
- Generated at: `2026-06-05T08:10:14.221269+00:00`

## Commands

- Build cwd: `mcp/canva-mcp`
- Build: `npm run build:server`
- Proxy cwd: `mcp/canva-mcp`
- Proxy: `uvx mcpo --host 127.0.0.1 --port 59219 --api-key <redacted> --strict-auth -- node dist/server/stdio.js`

## Checks

| Check | OK | Detail |
| --- | --- | --- |
| build | true | npm run build:server |
| authenticated-openapi | true | http://127.0.0.1:59219/openapi.json returned JSON |
| authenticated-docs | true | http://127.0.0.1:59219/docs returned 200 |
| unauthenticated-openapi-rejected | true | http://127.0.0.1:59219/openapi.json returned 401 without auth |
| required-openapi-paths | true | required paths present |
