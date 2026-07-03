# Research Basis

Last refreshed: 2026-06-19.

This file maps external AutoResearch and agent-workflow sources to the local
checks they justify. It is not a claim that every external method is implemented
verbatim. External systems are source-bound hypotheses until local evidence
proves that a change improves this workspace without weakening guardrails.

## Source Catalog

| Source | Type | Local takeaway |
| --- | --- | --- |
| Karpathy AutoResearch | concept / public talk | Keep iteration evidence, evaluator feedback, and durable artifacts before claiming progress. |
| PrefectHQ/fastmcp | GitHub system | Treat MCP transport, service inventory, and docs surfaces as explicit operator contracts. |
| lastmile-ai/mcp-eval | GitHub system | Prefer real agent-to-server smoke evidence, trace metrics, and exportable reports over mock-only tests. |
| evalstate/fast-agent | GitHub system | Declare workflows, provider strategy, MCP server assignment, and usage tracking before wiring runtime orchestration. |
| Veritas-7/autoresearch-skill-system | GitHub system | Bound continuous improvement with same-sample A/B checks, stop-file/watchdog controls, durable status, research basis gates, and fail-closed audits. |
| dsifry/metaswarm | GitHub system | Preserve resumable handoff records that include review queue, local targets, and next action. |
| kodustech/agent-readiness | GitHub system | Keep autonomous-agent readiness visible through JSON/Markdown gates and minimum evidence thresholds. |
| Uninen/devserver-mcp | GitHub system | Keep local service status, browser automation, and process monitoring as operator-visible workflow surfaces. |

## Adoption Boundary

Do not adopt any source as production behavior without local evidence. A source
can influence prompts, candidate selection, documentation, harness design, or
operator tooling only after the local cycle records:

- source identity and URL;
- latest observed source commit when the source is a GitHub repository;
- local review targets;
- same-sample baseline and candidate result when behavior changes;
- validator or focused test result;
- security or secret-safety result when artifacts may contain sensitive data;
- rollback, no-adopt, or follow-up decision;
- completion audit mapping the user objective to artifacts.

If a source needs model fine-tuning, untrusted code execution, remote services,
or large benchmark spend, keep it as research evidence until an isolated sandbox adapter exists.

## Local Evidence Surfaces

- `ops/references/github_modernization_sources.json`
- `ops/scripts/github_modernization_radar.py`
- `ops/scripts/github_modernization_handoff.py`
- `ops/references/agent_workflows.json`
- `.agents/skills/auto-research-karpathy/SKILL.md`
- `.agents/skills/auto-research-karpathy/references/source-backed-patterns.md`
- `.agents/skills/auto-research-karpathy/references/workspace-loop.md`
- `.agents/skills/auto-research-karpathy/scripts/validate_skill.py`
