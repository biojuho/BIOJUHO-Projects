# AutoResearch Canva Tool Inventory Guard - 2026-06-05

## Source Signal

- Upstream: `mastra-ai/mastra` commit `57879dd3eea869cec0a6696fc9a8aa6459faf4b3`
- URL: https://github.com/mastra-ai/mastra/commit/57879dd3eea869cec0a6696fc9a8aa6459faf4b3
- Pattern adopted: a tools endpoint must merge or mirror every tool source. The upstream failure mode dropped dynamically created tools when bundler-discovered tools were present.

## A/B Contract

- Baseline: Canva MCP had stdio/OAuth smoke tests, but no direct guard proving `listTools()` matched the exported server registry or that widget-backed tools remained mirrored by resources and resource templates.
- Variant: add a stdio inventory regression that compares runtime MCP output with `dist/server/tools.js`, and checks widget tool templates against `resources/list` and `resources/templates/list`.
- Primary KPI: detect silent tool inventory loss before release.
- Guardrails: keep Canva runtime behavior unchanged and preserve the existing `npm run test:local` path.
- Decision: accepted. The variant adds coverage without changing tool dispatch behavior.

## Changes

- `mcp/canva-mcp/tests/tool-inventory.test.mjs`
  - Verifies stdio `listTools()` exactly mirrors exported `tools`.
  - Keeps auth helper, search, generation, and editor tools visible in one runtime inventory.
  - Verifies widget-backed tools have matching resource and resource-template entries.
- `mcp/canva-mcp/tsconfig.build.json`
  - Adds `ignoreDeprecations: "6.0"` so the Canva server build continues under TypeScript 6 while existing relaxed build options remain unchanged.

## Verification

- `cmd /c npm run build:server`
  - Passed after the TypeScript deprecation option was added.
- `cmd /c node --test tests/tool-inventory.test.mjs`
  - Passed `2/2`.
- `cmd /c npm run test:local`
  - Passed `6/6`.
  - Covered build, helper script syntax checks, existing stdio/OAuth tests, and the new inventory guard.
- `python ops\scripts\run_workspace_smoke.py --scope mcp --json-out var\workspace-smoke-mcp-canva-tool-inventory-2026-06-05.json`
  - Passed `6/6`.
  - JSON status: `complete`.

## Notes

- Live Canva OAuth remains an external approval/configuration boundary; this cycle only verifies local stdio and registry integrity.
- Existing generated Canva asset files were already dirty in the worktree and were not staged for this cycle.
