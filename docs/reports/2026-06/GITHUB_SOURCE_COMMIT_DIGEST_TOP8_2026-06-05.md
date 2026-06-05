# GitHub Source Commit Delta Digest

- Status: `pass`
- Complete: `true`
- Selected repositories: `8`
- Failed repositories: `0`
- Commit limit per repo: `5`
- Token available: `false`
- Source queue: `docs/reports/2026-06/GITHUB_SOURCE_REVIEW_QUEUE_2026-06-05.json`
- Source change summary: `docs/reports/2026-06/GITHUB_SOURCE_CHANGE_SUMMARY_2026-06-05.json`
- Baseline generated at: `2026-06-04T18:54:22.968302+00:00`
- Source change generated at: `2026-06-04T23:01:51.324669+00:00`
- Generated at: `2026-06-05T00:15:09.539792+00:00`

## Digest

| Rank | Repo | Window | Commits | Latest commit subjects | Decision |
| ---: | --- | --- | ---: | --- | --- |
| 1 | `microsoft/agent-framework` | `2026-06-04T18:52:34Z` to `2026-06-04T22:36:03Z` | 4 | Python: Add GitHub Copilot integration tests to CI workflows (#6346)<br>.NET: Bump ModelContextProtocol from 1.1.0 to 1.2.0 (#3956) (#6239)<br>Python: Fix toolbox consent flow in hosted agent (#6249) | review_required_before_local_adoption |
| 2 | `mastra-ai/mastra` | `2026-06-04T18:53:13Z` to `2026-06-04T23:01:11Z` | 5 | fix(client-js): keep client tools for signal continuations (#17593)<br>docs(reference/pubsub): document opt-in subscriber batching (#17586)<br>feat(core/events): opt-in batched delivery for PubSub subscribers (#16482) | review_required_before_local_adoption |
| 3 | `microsoft/playwright-mcp` | `2026-05-28T01:32:25Z` to `2026-06-04T20:56:00Z` | 0 | none returned | no_local_adoption_commit_window_empty |
| 4 | `vercel/ai` | `2026-06-04T18:46:15Z` to `2026-06-04T23:01:19Z` | 5 | Version Packages (canary) (#15836)<br>feat(provider/google-vertex): add Gemini text-to-speech (speech) model support (#15779)<br>fix(openai): round-trip namespace on function_call input items (#15193) | review_required_before_local_adoption |
| 5 | `OpenHands/OpenHands` | `2026-06-04T17:44:55Z` to `2026-06-04T22:58:36Z` | 4 | Bump SDK packages to v1.25.0 (#14653)<br>PLTF-2899: await SaaS get_user_id() in Slack repo-inference log (#14658)<br>PLTF-2899: store GitHub PR timestamps as naive UTC (asyncpg DataError) (#14657) | review_required_before_local_adoption |
| 6 | `pydantic/pydantic-ai` | `2026-06-04T08:54:32Z` to `2026-06-04T22:52:35Z` | 3 | Map base `seed` setting to xAI (#5741)<br>Handle `UploadedFile` consistently with `FileUrl` in UI adapters (#5772)<br>Fix incomplete streamed response when `event_stream_handler` doesn't consume the stream (#5771) | review_required_before_local_adoption |
| 7 | `Significant-Gravitas/AutoGPT` | `2026-06-04T16:34:25Z` to `2026-06-04T21:54:28Z` | 0 | none returned | no_local_adoption_commit_window_empty |
| 8 | `agno-agi/agno` | `2026-06-04T18:49:40Z` to `2026-06-04T22:22:34Z` | 0 | none returned | no_local_adoption_commit_window_empty |

## Repository Details

### microsoft/agent-framework

- Source: https://github.com/microsoft/agent-framework
- Category: `enterprise-agent-framework`
- Priority: `high` score `47`
- Fetch source: `github_api`
- Adoption signal: Compare workflow and orchestration changes against local agent workflow gate evidence.
- Local evidence:
  - `ops/references/agent_workflows.json`
  - `ops/scripts/agent_workflow_gate_runner.py`
  - `tests/test_agent_workflow_gate_runner.py`
  - `ops/references/mcp_service_manifest.json`
  - `ops/scripts/mcp_service_runtime_smoke.py`
- Latest commits:
  - `f3c3efed4301` `2026-06-04T22:06:26Z` Python: Add GitHub Copilot integration tests to CI workflows (#6346) (https://github.com/microsoft/agent-framework/commit/f3c3efed4301905cff795794790bd4b4719742a4)
  - `bbccb7c28c86` `2026-06-04T20:51:15Z` .NET: Bump ModelContextProtocol from 1.1.0 to 1.2.0 (#3956) (#6239) (https://github.com/microsoft/agent-framework/commit/bbccb7c28c86a0c2712d65e367fa8029065294eb)
  - `dbc312a78a75` `2026-06-04T20:28:59Z` Python: Fix toolbox consent flow in hosted agent (#6249) (https://github.com/microsoft/agent-framework/commit/dbc312a78a7579170068910599bfff5ca639c0d6)
  - `bb9ed63a347b` `2026-06-04T20:15:29Z` .NET: Restructure skill script schemas XML and remove resources from body (#6343) (https://github.com/microsoft/agent-framework/commit/bb9ed63a347b3e437106b27ff7547bd388fd5bbe)

### mastra-ai/mastra

- Source: https://github.com/mastra-ai/mastra
- Category: `typescript-agent-application-framework`
- Priority: `high` score `46`
- Fetch source: `github_api`
- Adoption signal: Compare TypeScript agent-app changes against dashboard and Canva operator surfaces.
- Local evidence:
  - `apps/dashboard/src/App.jsx`
  - `apps/dashboard/src/components/QualityPanel.jsx`
  - `mcp/canva-mcp/src/server/server.ts`
  - `mcp/canva-mcp/src/server/tools.ts`
  - `ops/references/dev_server_browser_checks.json`
- Latest commits:
  - `b3e9781a93a1` `2026-06-04T23:00:01Z` fix(client-js): keep client tools for signal continuations (#17593) (https://github.com/mastra-ai/mastra/commit/b3e9781a93a18e8e492849040016ddf239c00d9c)
  - `b756ff19ef26` `2026-06-04T19:46:16Z` docs(reference/pubsub): document opt-in subscriber batching (#17586) (https://github.com/mastra-ai/mastra/commit/b756ff19ef26da52c9a0d5e258343c1f53bc8394)
  - `3b45ea950155` `2026-06-04T19:42:22Z` feat(core/events): opt-in batched delivery for PubSub subscribers (#16482) (https://github.com/mastra-ai/mastra/commit/3b45ea95015557a6cb9d70dc5252af54ab1b78ac)
  - `e9be4e747ec3` `2026-06-04T19:40:56Z` feat(core): add SignalProvider abstraction + @mastra/github-signals package (#17577) (https://github.com/mastra-ai/mastra/commit/e9be4e747ec3d8b65548bff92f9377db06105376)
  - `151f90efa076` `2026-06-04T19:35:23Z` chore(deps): update opentelemetry (#17519) (https://github.com/mastra-ai/mastra/commit/151f90efa07649e3dd1b4632a46a43f67363728c)

### microsoft/playwright-mcp

- Source: https://github.com/microsoft/playwright-mcp
- Category: `mcp-browser-automation`
- Priority: `high` score `46`
- Fetch source: `none`
- Adoption signal: No commit subjects returned for the pushed_at window.
- Local evidence:
  - `ops/references/dev_server_browser_checks.json`
  - `ops/scripts/dev_server_browser_smoke.py`
  - `tests/test_dev_server_browser_smoke.py`
  - `apps/desci-platform/scripts/browser_smoke.py`
  - `tests/test_desci_browser_smoke.py`
- Latest commits: none returned

### vercel/ai

- Source: https://github.com/vercel/ai
- Category: `typescript-ai-app-toolkit`
- Priority: `high` score `46`
- Fetch source: `github_api`
- Adoption signal: Compare TypeScript agent-app changes against dashboard and Canva operator surfaces.
- Local evidence:
  - `apps/dashboard/src/App.jsx`
  - `apps/dashboard/src/components/QualityPanel.jsx`
  - `mcp/canva-mcp/src/server/server.ts`
  - `mcp/canva-mcp/src/server/tools.ts`
  - `ops/scripts/dev_server_browser_smoke.py`
- Latest commits:
  - `43ad34c6a665` `2026-06-04T23:01:09Z` Version Packages (canary) (#15836) (https://github.com/vercel/ai/commit/43ad34c6a665973f9d949e38bf8e34481bd5aef0)
  - `2ce3c65448f3` `2026-06-04T22:48:42Z` feat(provider/google-vertex): add Gemini text-to-speech (speech) model support (#15779) (https://github.com/vercel/ai/commit/2ce3c65448f36eb3629c50095888a64326167d0d)
  - `94eba1b0594e` `2026-06-04T22:22:30Z` fix(openai): round-trip namespace on function_call input items (#15193) (https://github.com/vercel/ai/commit/94eba1b0594ec6e34726cf3436bb953e46000106)
  - `beb6c72357fc` `2026-06-04T20:59:14Z` docs(contributing): document the Experimental_ prefix seam convention (#15833) (https://github.com/vercel/ai/commit/beb6c72357fc970c3985a9b7e5ec346622102f28)
  - `480c2fb3913e` `2026-06-04T19:13:12Z` Version Packages (canary) (#15827) (https://github.com/vercel/ai/commit/480c2fb3913e56808278da8a89bc82665cc403da)

### OpenHands/OpenHands

- Source: https://github.com/OpenHands/OpenHands
- Category: `autonomous-coding-agent-platform`
- Priority: `high` score `44`
- Fetch source: `github_api`
- Adoption signal: Review commit subjects against the mapped local evidence before adoption.
- Local evidence:
  - `.agents/skills/auto-research-karpathy/SKILL.md`
  - `ops/references/agent_workflows.json`
  - `ops/scripts/agent_workflow_gate_runner.py`
  - `tests/test_agent_workflow_gate_runner.py`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_RUNNER_2026-06-05.md`
- Latest commits:
  - `64ae0752086f` `2026-06-04T21:41:11Z` Bump SDK packages to v1.25.0 (#14653) (https://github.com/OpenHands/OpenHands/commit/64ae0752086fd1b2408f42fd4ac36d9e26651aba)
  - `21b3b46ed198` `2026-06-04T20:27:00Z` PLTF-2899: await SaaS get_user_id() in Slack repo-inference log (#14658) (https://github.com/OpenHands/OpenHands/commit/21b3b46ed1986cff8c87f804148b12053fee5ddc)
  - `f2f77a666c92` `2026-06-04T20:21:38Z` PLTF-2899: store GitHub PR timestamps as naive UTC (asyncpg DataError) (#14657) (https://github.com/OpenHands/OpenHands/commit/f2f77a666c9286a9df5b5a7d9597eca1e1ddc2c3)
  - `57b0da3df607` `2026-06-04T20:18:39Z` PLTF-2895: event_callback index ? use plain CREATE INDEX (#14651) (https://github.com/OpenHands/OpenHands/commit/57b0da3df60794ea05e25258ad81a661034293d5)

### pydantic/pydantic-ai

- Source: https://github.com/pydantic/pydantic-ai
- Category: `typed-agent-framework`
- Priority: `high` score `44`
- Fetch source: `github_api`
- Adoption signal: Review commit subjects against the mapped local evidence before adoption.
- Local evidence:
  - `packages/shared/harness/core.py`
  - `packages/shared/harness/adapters/native.py`
  - `packages/shared/harness/token_tracker.py`
  - `packages/shared/harness/tests/test_harness.py`
  - `ops/scripts/run_workspace_smoke.py`
- Latest commits:
  - `70cb782fdc39` `2026-06-04T22:52:34Z` Map base `seed` setting to xAI (#5741) (https://github.com/pydantic/pydantic-ai/commit/70cb782fdc39c26a2b2123a6eb7e338c0d8f0654)
  - `ed31bdd64e11` `2026-06-04T22:02:29Z` Handle `UploadedFile` consistently with `FileUrl` in UI adapters (#5772) (https://github.com/pydantic/pydantic-ai/commit/ed31bdd64e11ce1475916a398ee3312791ed2d38)
  - `49f62a386041` `2026-06-04T21:47:50Z` Fix incomplete streamed response when `event_stream_handler` doesn't consume the stream (#5771) (https://github.com/pydantic/pydantic-ai/commit/49f62a386041abd6e0d960dd629c3b4fe28eac63)

### Significant-Gravitas/AutoGPT

- Source: https://github.com/Significant-Gravitas/AutoGPT
- Category: `continuous-agent-platform`
- Priority: `high` score `44`
- Fetch source: `none`
- Adoption signal: No commit subjects returned for the pushed_at window.
- Local evidence:
  - `.agents/skills/auto-research-karpathy/SKILL.md`
  - `ops/references/autoresearch_completion_contract.json`
  - `ops/scripts/autoresearch_completion_audit.py`
  - `tests/test_autoresearch_completion_audit.py`
  - `ops/references/agent_workflows.json`
- Latest commits: none returned

### agno-agi/agno

- Source: https://github.com/agno-agi/agno
- Category: `full-stack-agent-platform`
- Priority: `high` score `43`
- Fetch source: `none`
- Adoption signal: No commit subjects returned for the pushed_at window.
- Local evidence:
  - `.agents/skills/auto-research-karpathy/SKILL.md`
  - `ops/references/agent_workflows.json`
  - `ops/scripts/agent_workflow_gate_runner.py`
  - `tests/test_agent_workflow_gate_runner.py`
  - `ops/scripts/autoresearch_completion_audit.py`
- Latest commits: none returned
