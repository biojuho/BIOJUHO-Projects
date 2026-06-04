# Canva MCP OpenAPI Interop Contract - 2026-06-04

## Summary

- Tools parsed: 20
- Read-only tools: 9
- Destructive tools: 1
- Paths: /tools, /tools/{toolName}/call
- Generated at: `2026-06-04T11:32:15.846416Z`
- OpenAPI JSON: `docs/reports/2026-06/CANVA_MCP_OPENAPI_CONTRACT_2026-06-04.json`

## Tool Surface

- `upload-asset-from-url` (write-capable)
- `search-designs` (read-only)
- `get-design` (read-only)
- `get-design-pages` (read-only)
- `get-design-content` (read-only)
- `create-folder` (write-capable)
- `move-item-to-folder` (write-capable)
- `list-folder-items` (read-only)
- `comment-on-design` (write-capable)
- `list-comments` (read-only)
- `list-replies` (read-only)
- `reply-to-comment` (write-capable)
- `generate-design` (write-capable)
- `create-design-from-candidate` (write-capable)
- `start-editing-transaction` (write-capable)
- `perform-editing-operations` (write-capable)
- `commit-editing-transaction` (destructive)
- `cancel-editing-transaction` (write-capable)
- `get-design-thumbnail` (read-only)
- `get-assets` (read-only)

## Operating Decision

This is an offline interoperability contract. It records the OpenAPI shape a future MCP-to-OpenAPI proxy must satisfy, but it does not claim that a live HTTP proxy is deployed.
