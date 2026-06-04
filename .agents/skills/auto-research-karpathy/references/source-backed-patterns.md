# Source-Backed Patterns

Use this reference when a cycle needs current external grounding before choosing
an implementation direction.

## Karpathy-Style Software 3.0

Primary source:

- Andrej Karpathy, "Software Is Changing (Again)", YC AI Startup School:
  <https://www.youtube.com/watch?v=LCEmiRjPEtQ>

Operational interpretation for this workspace:

- Treat prompts and natural-language specs as programs that need versioning,
  tests, and observable behavior.
- Treat the agent as a director of partially autonomous systems, not as a reason
  to skip review.
- Build with short feedback loops: specify intent, generate or edit, inspect,
  run, click, measure, and refine.
- Preserve human-readable traces so later agents can understand why a variant
  was accepted or rejected.

## MCP Production Composition

Primary source:

- PrefectHQ/fastmcp: <https://github.com/PrefectHQ/fastmcp>

Useful pattern:

- A production MCP system needs a clear server/client composition, transport
  choices, docs, tests, and security policy. FastMCP positions MCP as the
  connection layer between LLMs and tools/data, and exposes a path from
  prototype to production.

Local mapping:

- `mcp/canva-mcp/src/server/server.ts`
- `mcp/canva-mcp/src/server/stdio.ts`
- `mcp/canva-mcp/tests`
- `docs/MCP_HEALTH_CHECK.md`

## Real Agent-to-Tool Evaluation

Primary source:

- lastmile-ai/mcp-eval: <https://github.com/lastmile-ai/mcp-eval>

Useful pattern:

- Prefer real environment testing over mocks for agent tool paths.
- Capture traces, metrics, JSON/HTML evidence, and CI-friendly assertions.
- Test the agent, MCP server, and tool-use path together when the risk is in
  integration behavior.

Local mapping:

- `ops/scripts/run_workspace_smoke.py`
- `ops/scripts/workspace_smoke_report.py`
- `apps/desci-platform/scripts/product_smoke.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `docs/QUALITY_GATE.md`

## Declarative Agent Workflows

Primary source:

- evalstate/fast-agent: <https://github.com/evalstate/fast-agent>

Useful pattern:

- Keep agent workflows declarative and version-controlled.
- Use evaluator-optimizer, router, parallel, and orchestrator-worker patterns
  when the task naturally decomposes.
- Keep skills, MCP server configs, and agent prompts in files that can be
  inspected and tested.

Local mapping:

- `packages/shared/harness/core.py`
- `packages/shared/harness/adapters/native.py`
- `packages/shared/harness/token_tracker.py`
- `packages/shared/tests/test_workflow_trace.py`

## Dev Server and Browser Automation

Primary source:

- Uninen/devserver-mcp: <https://github.com/Uninen/devserver-mcp>

Useful pattern:

- Manage multiple dev servers with status and logs.
- Use Playwright or browser automation as a first-class validation path for
  web apps.
- Combine process status, logs, screenshots, and route-level checks before
  calling a product surface launch-ready.

Local mapping:

- `apps/desci-platform/scripts/browser_smoke.py`
- `apps/dashboard/src/components/QualityPanel.jsx`
- `ops/scripts/workspace_smoke_report.py`
- `docs/QUALITY_GATE.md`

## Adoption Heuristic

Promote an external pattern only when it satisfies all checks:

1. The source is primary or official.
2. The pattern solves a real local gap.
3. A local evidence path already exists or can be added safely.
4. The pattern can be verified offline after adoption.
5. The change does not expand credential, deployment, or data risk without an
   explicit release decision.
