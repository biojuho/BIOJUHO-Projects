# GitHub Source Commit Delta Digest

- Status: `pass`
- Complete: `true`
- Selected repositories: `12`
- Failed repositories: `0`
- Commit limit per repo: `8`
- Token available: `false`
- Candidate repositories with pushed_at movement: `16`
- Overflow repositories: `4`
- Source queue: `var\github-source-review-queue-continue.json`
- Source change summary: `var\github-source-change-summary-continue.json`
- Baseline generated at: `2026-06-04T18:54:22.968302+00:00`
- Source change generated at: `2026-06-05T04:32:03.154499+00:00`
- Generated at: `2026-06-05T04:32:14.934621+00:00`

## Digest

| Rank | Repo | Window | Commits | Latest commit subjects | Decision |
| ---: | --- | --- | ---: | --- | --- |
| 1 | `microsoft/agent-framework` | `2026-06-04T18:52:34Z` to `2026-06-05T01:16:19Z` | 6 | Python: MCP long-running task support in Python (#6319)<br>Python: bump package versions for 1.8.0 release (#6351)<br>Python: Add GitHub Copilot integration tests to CI workflows (#6346) | review_required_before_local_adoption |
| 2 | `openai/openai-agents-python` | `2026-06-04T07:38:27Z` to `2026-06-05T01:11:08Z` | 2 | docs: translate pages<br>docs: add Latitude to external tracing processors list (#3577) | review_required_before_local_adoption |
| 3 | `mastra-ai/mastra` | `2026-06-04T18:53:13Z` to `2026-06-05T04:03:09Z` | 8 | fix(core): keep part timestamps out of message ordering (#17598)<br>fix(client-js): keep client tools for signal continuations (#17593)<br>docs(reference/pubsub): document opt-in subscriber batching (#17586) | review_required_before_local_adoption |
| 4 | `microsoft/playwright-mcp` | `2026-05-28T01:32:25Z` to `2026-06-04T20:56:00Z` | 0 | none returned | no_local_adoption_commit_window_empty |
| 5 | `vercel/ai` | `2026-06-04T18:46:15Z` to `2026-06-05T04:31:08Z` | 8 | Version Packages (canary) (#15839)<br>feat: Realtime API support for browser<->provider websocket connectio...<br>Version Packages (canary) (#15836) | review_required_before_local_adoption |
| 6 | `agno-agi/agno` | `2026-06-04T18:49:40Z` to `2026-06-05T02:55:20Z` | 0 | none returned | no_local_adoption_commit_window_empty |
| 7 | `crewAIInc/crewAI` | `2026-06-04T18:28:34Z` to `2026-06-05T01:38:54Z` | 2 | feat(flow): type DSL triggers as route-aware decorators (#6042)<br>chat api for convo flows (#6034) | review_required_before_local_adoption |
| 8 | `FlowiseAI/Flowise` | `2026-06-04T13:39:57Z` to `2026-06-05T03:41:08Z` | 1 | Fix Flowise 591 (#6476) | review_required_before_local_adoption |
| 9 | `google/adk-python` | `2026-06-04T18:03:48Z` to `2026-06-04T23:45:20Z` | 8 | fix: Format the files<br>refactor: Separate PR analysis from triage for automation<br>fix(cli): Serialize LiteLlm graph models safely | review_required_before_local_adoption |
| 10 | `OpenHands/OpenHands` | `2026-06-04T17:44:55Z` to `2026-06-04T23:14:37Z` | 4 | Bump SDK packages to v1.25.0 (#14653)<br>PLTF-2899: await SaaS get_user_id() in Slack repo-inference log (#14658)<br>PLTF-2899: store GitHub PR timestamps as naive UTC (asyncpg DataError... | review_required_before_local_adoption |
| 11 | `pydantic/pydantic-ai` | `2026-06-04T08:54:32Z` to `2026-06-05T02:31:14Z` | 5 | fix(messages): from_data_uri crashes on a valid non-base64 data URI (...<br>Add `api_host` and `timeout` to `XaiProvider` (#5742)<br>Map base `seed` setting to xAI (#5741) | review_required_before_local_adoption |
| 12 | `Significant-Gravitas/AutoGPT` | `2026-06-04T16:34:25Z` to `2026-06-05T04:23:52Z` | 0 | none returned | no_local_adoption_commit_window_empty |

## Selection Batch

- Source signal: `mastra-ai/mastra opt-in PubSub subscriber batching`
- Batch size: `12`
- Candidate repositories: `16`
- Selected repositories: `12`
- Overflow repositories: `4`
- Overflow policy: `defer_to_next_digest_without_fetching`

| Rank | Repo | Priority | Score |
| ---: | --- | --- | ---: |
| 13 | `open-telemetry/opentelemetry-collector` | high | 43 |
| 14 | `evalstate/fast-agent` | high | 39 |
| 15 | `strands-agents/harness-sdk` | high | 37 |
| 16 | `Uninen/devserver-mcp` | medium | 27 |

## Repository Details

### microsoft/agent-framework

- Source: https://github.com/microsoft/agent-framework
- Category: `enterprise-agent-framework`
- Priority: `high` score `48`
- Fetch source: `github_atom_feed`
- Adoption signal: Compare workflow and orchestration changes against local agent workflow gate evidence.
- Local evidence:
  - `ops/references/agent_workflows.json`
  - `ops/scripts/agent_workflow_gate_runner.py`
  - `tests/test_agent_workflow_gate_runner.py`
  - `ops/references/mcp_service_manifest.json`
  - `ops/scripts/mcp_service_runtime_smoke.py`
- Latest commits:
  - `bf4ad48cf24c` `2026-06-05T00:04:55Z` Python: MCP long-running task support in Python (#6319) (https://github.com/microsoft/agent-framework/commit/bf4ad48cf24c8eb86c994cc62e3e2848a926887d)
  - `01fc518b2905` `2026-06-04T23:03:24Z` Python: bump package versions for 1.8.0 release (#6351) (https://github.com/microsoft/agent-framework/commit/01fc518b290527ecc89919664c90a5fed8e14d8d)
  - `f3c3efed4301` `2026-06-04T22:06:26Z` Python: Add GitHub Copilot integration tests to CI workflows (#6346) (https://github.com/microsoft/agent-framework/commit/f3c3efed4301905cff795794790bd4b4719742a4)
  - `bbccb7c28c86` `2026-06-04T20:51:15Z` .NET: Bump ModelContextProtocol from 1.1.0 to 1.2.0 (#3956) (#6239) (https://github.com/microsoft/agent-framework/commit/bbccb7c28c86a0c2712d65e367fa8029065294eb)
  - `dbc312a78a75` `2026-06-04T20:28:59Z` Python: Fix toolbox consent flow in hosted agent (#6249) (https://github.com/microsoft/agent-framework/commit/dbc312a78a7579170068910599bfff5ca639c0d6)
  - `bb9ed63a347b` `2026-06-04T20:15:29Z` .NET: Restructure skill script schemas XML and remove resources from ... (https://github.com/microsoft/agent-framework/commit/bb9ed63a347b3e437106b27ff7547bd388fd5bbe)

### openai/openai-agents-python

- Source: https://github.com/openai/openai-agents-python
- Category: `openai-agent-runtime-sdk`
- Priority: `high` score `47`
- Fetch source: `github_atom_feed`
- Adoption signal: Review commit subjects against the mapped local evidence before adoption.
- Local evidence:
  - `.agents/skills/auto-research-karpathy/SKILL.md`
  - `ops/references/agent_workflows.json`
  - `ops/scripts/agent_workflow_manifest.py`
  - `ops/scripts/agent_workflow_gate_runner.py`
  - `ops/scripts/autoresearch_completion_audit.py`
- Latest commits:
  - `5121f302a5d4` `2026-06-05T00:53:07Z` docs: translate pages (https://github.com/openai/openai-agents-python/commit/5121f302a5d43fa20c9f78966e4db6f08f724622)
  - `f4e5d96f9fda` `2026-06-04T23:03:01Z` docs: add Latitude to external tracing processors list (#3577) (https://github.com/openai/openai-agents-python/commit/f4e5d96f9fda158f9541b575d2aa5232107cb939)

### mastra-ai/mastra

- Source: https://github.com/mastra-ai/mastra
- Category: `typescript-agent-application-framework`
- Priority: `high` score `46`
- Fetch source: `github_atom_feed`
- Adoption signal: Compare TypeScript agent-app changes against dashboard and Canva operator surfaces.
- Local evidence:
  - `apps/dashboard/src/App.jsx`
  - `apps/dashboard/src/components/QualityPanel.jsx`
  - `mcp/canva-mcp/src/server/server.ts`
  - `mcp/canva-mcp/src/server/tools.ts`
  - `ops/references/dev_server_browser_checks.json`
- Latest commits:
  - `0c72f032abb1` `2026-06-05T02:37:51Z` fix(core): keep part timestamps out of message ordering (#17598) (https://github.com/mastra-ai/mastra/commit/0c72f032abb13254df5a7856d64be2f207b8006d)
  - `b3e9781a93a1` `2026-06-04T23:00:01Z` fix(client-js): keep client tools for signal continuations (#17593) (https://github.com/mastra-ai/mastra/commit/b3e9781a93a18e8e492849040016ddf239c00d9c)
  - `b756ff19ef26` `2026-06-04T19:46:16Z` docs(reference/pubsub): document opt-in subscriber batching (#17586) (https://github.com/mastra-ai/mastra/commit/b756ff19ef26da52c9a0d5e258343c1f53bc8394)
  - `3b45ea950155` `2026-06-04T19:42:22Z` feat(core/events): opt-in batched delivery for PubSub subscribers (#1... (https://github.com/mastra-ai/mastra/commit/3b45ea95015557a6cb9d70dc5252af54ab1b78ac)
  - `e9be4e747ec3` `2026-06-04T19:40:56Z` feat(core): add SignalProvider abstraction + @mastra/github-signals p... (https://github.com/mastra-ai/mastra/commit/e9be4e747ec3d8b65548bff92f9377db06105376)
  - `151f90efa076` `2026-06-04T19:35:23Z` chore(deps): update opentelemetry (#17519) (https://github.com/mastra-ai/mastra/commit/151f90efa07649e3dd1b4632a46a43f67363728c)
  - `6c6eff0c67b7` `2026-06-04T19:34:44Z` chore(deps): update dependency @blaxel/core to ^0.2.86 (#17384) (https://github.com/mastra-ai/mastra/commit/6c6eff0c67b7329b6c74bed6806a944ce2057d84)
  - `3103d763617b` `2026-06-04T19:34:00Z` chore(deps): update dependency @fastify/swagger-ui to ^5.2.6 (#17552) (https://github.com/mastra-ai/mastra/commit/3103d763617b795c3eb8abd3bf79188908b3855b)

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
- Fetch source: `github_atom_feed`
- Adoption signal: Compare TypeScript agent-app changes against dashboard and Canva operator surfaces.
- Local evidence:
  - `apps/dashboard/src/App.jsx`
  - `apps/dashboard/src/components/QualityPanel.jsx`
  - `mcp/canva-mcp/src/server/server.ts`
  - `mcp/canva-mcp/src/server/tools.ts`
  - `ops/scripts/dev_server_browser_smoke.py`
- Latest commits:
  - `7254ac64a7b9` `2026-06-05T04:31:05Z` Version Packages (canary) (#15839) (https://github.com/vercel/ai/commit/7254ac64a7b91838844f9a05d56c3e37faabec06)
  - `ce769dd2f392` `2026-06-05T04:28:13Z` feat: Realtime API support for browser<->provider websocket connectio... (https://github.com/vercel/ai/commit/ce769dd2f392ec82529f626223630f8222f7b475)
  - `43ad34c6a665` `2026-06-04T23:01:09Z` Version Packages (canary) (#15836) (https://github.com/vercel/ai/commit/43ad34c6a665973f9d949e38bf8e34481bd5aef0)
  - `2ce3c65448f3` `2026-06-04T22:48:42Z` feat(provider/google-vertex): add Gemini text-to-speech (speech) mode... (https://github.com/vercel/ai/commit/2ce3c65448f36eb3629c50095888a64326167d0d)
  - `94eba1b0594e` `2026-06-04T22:22:30Z` fix(openai): round-trip namespace on function_call input items (#15193) (https://github.com/vercel/ai/commit/94eba1b0594ec6e34726cf3436bb953e46000106)
  - `beb6c72357fc` `2026-06-04T20:59:14Z` docs(contributing): document the Experimental_ prefix seam convention... (https://github.com/vercel/ai/commit/beb6c72357fc970c3985a9b7e5ec346622102f28)
  - `480c2fb3913e` `2026-06-04T19:13:12Z` Version Packages (canary) (#15827) (https://github.com/vercel/ai/commit/480c2fb3913e56808278da8a89bc82665cc403da)
  - `9a1b0ea29bf4` `2026-06-04T19:09:33Z` release @ai-sdk/policy-opa (#15832) (https://github.com/vercel/ai/commit/9a1b0ea29bf46745a551801c64cea95cecff4d4d)

### agno-agi/agno

- Source: https://github.com/agno-agi/agno
- Category: `full-stack-agent-platform`
- Priority: `high` score `44`
- Fetch source: `none`
- Adoption signal: No commit subjects returned for the pushed_at window.
- Local evidence:
  - `.agents/skills/auto-research-karpathy/SKILL.md`
  - `ops/references/agent_workflows.json`
  - `ops/scripts/agent_workflow_gate_runner.py`
  - `tests/test_agent_workflow_gate_runner.py`
  - `ops/scripts/autoresearch_completion_audit.py`
- Latest commits: none returned

### crewAIInc/crewAI

- Source: https://github.com/crewAIInc/crewAI
- Category: `multi-agent-flow-control`
- Priority: `high` score `44`
- Fetch source: `github_atom_feed`
- Adoption signal: Review commit subjects against the mapped local evidence before adoption.
- Local evidence:
  - `ops/references/agent_workflows.json`
  - `ops/scripts/agent_workflow_gate_runner.py`
  - `tests/test_agent_workflow_gate_runner.py`
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_MATRIX_SAFE_FIRST_GATES_2026-06-05.json`
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_MATRIX_SAFE_FIRST_GATES_2026-06-05.md`
- Latest commits:
  - `906cd9769d7e` `2026-06-04T21:07:49Z` feat(flow): type DSL triggers as route-aware decorators (#6042) (https://github.com/crewAIInc/crewAI/commit/906cd9769d7e2125485bbc09e8d8ef5cb1c29805)
  - `14ce97d78787` `2026-06-04T20:36:48Z` chat api for convo flows (#6034) (https://github.com/crewAIInc/crewAI/commit/14ce97d787873a2c310d40c508a9d70c0ffd3616)

### FlowiseAI/Flowise

- Source: https://github.com/FlowiseAI/Flowise
- Category: `low-code-agent-workflow-builder`
- Priority: `high` score `44`
- Fetch source: `github_atom_feed`
- Adoption signal: Review commit subjects against the mapped local evidence before adoption.
- Local evidence:
  - `apps/dashboard/src/App.jsx`
  - `apps/dashboard/src/components/QualityPanel.jsx`
  - `ops/references/agent_workflows.json`
  - `ops/scripts/agent_workflow_manifest.py`
  - `ops/scripts/dev_server_control.py`
- Latest commits:
  - `42d593f8ca85` `2026-06-05T03:41:04Z` Fix Flowise 591 (#6476) (https://github.com/FlowiseAI/Flowise/commit/42d593f8ca854471059051a7fdd89bf8d8ab7c12)

### google/adk-python

- Source: https://github.com/google/adk-python
- Category: `code-first-agent-development-kit`
- Priority: `high` score `44`
- Fetch source: `github_atom_feed`
- Adoption signal: Review commit subjects against the mapped local evidence before adoption.
- Local evidence:
  - `ops/references/agent_workflows.json`
  - `ops/scripts/agent_workflow_manifest.py`
  - `ops/scripts/agent_workflow_gate_runner.py`
  - `tests/test_agent_workflow_manifest.py`
  - `tests/test_agent_workflow_gate_runner.py`
- Latest commits:
  - `9670ce2644f4` `2026-06-04T23:45:00Z` fix: Format the files (https://github.com/google/adk-python/commit/9670ce2644f422892997c65940e7330f1a26f799)
  - `10e5f07ab649` `2026-06-04T23:35:46Z` refactor: Separate PR analysis from triage for automation (https://github.com/google/adk-python/commit/10e5f07ab649398c7ed724b0c3b251ade9833375)
  - `c1e852fd2df3` `2026-06-04T23:20:26Z` fix(cli): Serialize LiteLlm graph models safely (https://github.com/google/adk-python/commit/c1e852fd2df3b476d298193a489da27e9271f6ec)
  - `928017d39194` `2026-06-04T22:53:01Z` chore: add automatic adk web updates in release process (https://github.com/google/adk-python/commit/928017d3919401a6225a9a51b3f762a6ceb7836c)
  - `139d851aa449` `2026-06-04T22:29:20Z` chore: 2.2.0 release (https://github.com/google/adk-python/commit/139d851aa449eaf85df526585395e1dc5e28e82b)
  - `cd81f7bde91d` `2026-06-04T21:46:07Z` fix(streaming): Ensure final partial=False frame is always yielded (https://github.com/google/adk-python/commit/cd81f7bde91df78d6cece539a6f98dda2aa8c9c0)
  - `2c52af00752d` `2026-06-04T21:41:36Z` chore: 2.1 tag (https://github.com/google/adk-python/commit/2c52af00752d8c586cf48a9847e5a0d65b6ba157)
  - `e87558cb0e39` `2026-06-04T21:06:58Z` ci: Remove unsupported --remote flag from gh repo fork (https://github.com/google/adk-python/commit/e87558cb0e39e7594b4dc9fa65ecb72c47f33957)

### OpenHands/OpenHands

- Source: https://github.com/OpenHands/OpenHands
- Category: `autonomous-coding-agent-platform`
- Priority: `high` score `44`
- Fetch source: `github_atom_feed`
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
  - `f2f77a666c92` `2026-06-04T20:21:38Z` PLTF-2899: store GitHub PR timestamps as naive UTC (asyncpg DataError... (https://github.com/OpenHands/OpenHands/commit/f2f77a666c9286a9df5b5a7d9597eca1e1ddc2c3)
  - `57b0da3df607` `2026-06-04T20:18:39Z` PLTF-2895: event_callback index ? use plain CREATE INDEX (#14651) (https://github.com/OpenHands/OpenHands/commit/57b0da3df60794ea05e25258ad81a661034293d5)

### pydantic/pydantic-ai

- Source: https://github.com/pydantic/pydantic-ai
- Category: `typed-agent-framework`
- Priority: `high` score `44`
- Fetch source: `github_atom_feed`
- Adoption signal: Review commit subjects against the mapped local evidence before adoption.
- Local evidence:
  - `packages/shared/harness/core.py`
  - `packages/shared/harness/adapters/native.py`
  - `packages/shared/harness/token_tracker.py`
  - `packages/shared/harness/tests/test_harness.py`
  - `ops/scripts/run_workspace_smoke.py`
- Latest commits:
  - `1b42945de65b` `2026-06-05T00:51:26Z` fix(messages): from_data_uri crashes on a valid non-base64 data URI (... (https://github.com/pydantic/pydantic-ai/commit/1b42945de65b2816fed3cffa371671a2ac759241)
  - `78bfaaed27ab` `2026-06-04T23:35:42Z` Add `api_host` and `timeout` to `XaiProvider` (#5742) (https://github.com/pydantic/pydantic-ai/commit/78bfaaed27abffecb761973d841608ba8b1edbf6)
  - `70cb782fdc39` `2026-06-04T22:52:34Z` Map base `seed` setting to xAI (#5741) (https://github.com/pydantic/pydantic-ai/commit/70cb782fdc39c26a2b2123a6eb7e338c0d8f0654)
  - `ed31bdd64e11` `2026-06-04T22:02:29Z` Handle `UploadedFile` consistently with `FileUrl` in UI adapters (#5772) (https://github.com/pydantic/pydantic-ai/commit/ed31bdd64e11ce1475916a398ee3312791ed2d38)
  - `49f62a386041` `2026-06-04T21:47:50Z` Fix incomplete streamed response when `event_stream_handler` doesn't ... (https://github.com/pydantic/pydantic-ai/commit/49f62a386041abd6e0d960dd629c3b4fe28eac63)

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
