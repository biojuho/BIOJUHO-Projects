# Canva MCP OpenAPI Interop Contract - 2026-06-04

## Summary

- Tools parsed: 20
- Read-only tools: 9
- Destructive tools: 1
- Tools with OpenAI namespaced metadata: 4
- OpenAI metadata keys: openai/outputTemplate, openai/resultCanProduceWidget, openai/toolInvocation/invoked, openai/toolInvocation/invoking, openai/widgetAccessible
- Paths: /tools, /tools/{toolName}/call
- Generated at: `2026-06-05T00:03:08.797286Z`
- OpenAPI JSON: `docs/reports/2026-06/CANVA_MCP_OPENAPI_CONTRACT_2026-06-04.json`

## Tool Surface

- `upload-asset-from-url` (write-capable); OpenAI metadata: openai/widgetAccessible, openai/toolInvocation/invoking, openai/toolInvocation/invoked
- `search-designs` (read-only); OpenAI metadata: openai/outputTemplate, openai/toolInvocation/invoking, openai/toolInvocation/invoked, openai/widgetAccessible, openai/resultCanProduceWidget
- `get-design` (read-only); OpenAI metadata: none
- `get-design-pages` (read-only); OpenAI metadata: none
- `get-design-content` (read-only); OpenAI metadata: none
- `create-folder` (write-capable); OpenAI metadata: none
- `move-item-to-folder` (write-capable); OpenAI metadata: none
- `list-folder-items` (read-only); OpenAI metadata: none
- `comment-on-design` (write-capable); OpenAI metadata: none
- `list-comments` (read-only); OpenAI metadata: none
- `list-replies` (read-only); OpenAI metadata: none
- `reply-to-comment` (write-capable); OpenAI metadata: none
- `generate-design` (write-capable); OpenAI metadata: openai/outputTemplate, openai/toolInvocation/invoking, openai/toolInvocation/invoked, openai/widgetAccessible, openai/resultCanProduceWidget
- `create-design-from-candidate` (write-capable); OpenAI metadata: none
- `start-editing-transaction` (write-capable); OpenAI metadata: openai/outputTemplate, openai/toolInvocation/invoking, openai/toolInvocation/invoked, openai/widgetAccessible, openai/resultCanProduceWidget
- `perform-editing-operations` (write-capable); OpenAI metadata: none
- `commit-editing-transaction` (destructive); OpenAI metadata: none
- `cancel-editing-transaction` (write-capable); OpenAI metadata: none
- `get-design-thumbnail` (read-only); OpenAI metadata: none
- `get-assets` (read-only); OpenAI metadata: none

## Operating Decision

This is an offline interoperability contract. It records the OpenAPI shape a future MCP-to-OpenAPI proxy must satisfy, but it does not claim that a live HTTP proxy is deployed.
