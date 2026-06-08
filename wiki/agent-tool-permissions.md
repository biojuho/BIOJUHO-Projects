---
updated: 2026-06-08T15:50:21+09:00
confidence: medium
source_types:
  - web
  - paper
  - standard
  - book
sources:
  - id: openai_agents_hitl
    type: web
    title: OpenAI Agents SDK human-in-the-loop
    url: https://openai.github.io/openai-agents-python/human_in_the_loop/
    checked: 2026-06-08
  - id: openai_agents_tools
    type: web
    title: OpenAI Agents SDK tools
    url: https://openai.github.io/openai-agents-js/guides/tools
    checked: 2026-06-08
  - id: mcp_authorization
    type: standard
    title: Model Context Protocol authorization specification
    url: https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization
    checked: 2026-06-08
  - id: owasp_llm_top10_2025
    type: standard
    title: OWASP Top 10 for LLM Applications 2025
    url: https://owasp.org/www-project-top-10-for-large-language-model-applications/assets/PDF/OWASP-Top-10-for-LLMs-v2025.pdf
    checked: 2026-06-08
  - id: toolemu
    type: paper
    title: "Identifying the Risks of LM Agents with an LM-Emulated Sandbox"
    url: https://arxiv.org/abs/2309.15817
    checked: 2026-06-08
  - id: mcp_security_analysis
    type: paper
    title: "Breaking the Protocol: Security Analysis of the Model Context Protocol Specification and Prompt Injection Vulnerabilities in Tool-Integrated LLM Agents"
    url: https://arxiv.org/abs/2601.17549
    checked: 2026-06-08
  - id: secure_reliable_systems
    type: book
    title: "Building Secure and Reliable Systems"
    url: https://openlibrary.org/works/OL24764469W/Building_Secure_and_Reliable_Systems
    checked: 2026-06-08
tags:
  - llm-wiki
  - autoresearch
  - agents
  - tools
  - permissions
  - hitl
  - mcp
---

# Agent Tool Permissions

Agent tool permissions define which tools an LLM agent can see, when it can call them, whether a human must approve the call, and how side effects are audited.

## Permission Contract

```js
const toolPermission = {
  tool_id: "workspace.file.delete",
  tool_provider: "local-mcp",
  permission_tier: "read_only|external_read|reversible_write|destructive_write|financial_or_legal",
  default_enabled: false,
  user_scope_required: "workspace:file:delete",
  auth_subject: "user_123",
  auth_resource: "workspace_456",
  needs_approval: true,
  approval_policy: "always|first_time|risk_based|never",
  approval_prompt_fields: ["tool", "resource", "parameters", "diff", "rollback"],
  max_call_count_per_run: 1,
  timeout_ms: 30000,
  audit_log_required: true,
  rollback_available: true,
  sensitive_data_allowed: false,
};
```

This contract is separate from transport authorization. MCP authorization can establish who may access a protected server or resource; the app still needs runtime policy for what the agent may do in this specific task.

## Permission Tiers

| Tier | Examples | Approval rule | Eval gate |
| --- | --- | --- | --- |
| `read_only` | Search docs, inspect calendar metadata, list files. | Usually no approval after user grants scope. | Tool selection accuracy and data-boundary checks. |
| `external_read` | Fetch web URL, call remote API, retrieve private drive doc. | Approval when crossing workspace/account boundary. | Prompt-injection and source trust checks in [[safety]]. |
| `reversible_write` | Draft email, create ticket, update staging note. | Approval before write or before send/publish. | Diff review and rollback evidence. |
| `destructive_write` | Delete file, modify production config, revoke access. | Always approve with explicit resource and rollback plan. | [[eval-failure-triage]] excessive-agency tests. |
| `financial_or_legal` | Payment, contract, legal notice, HR action. | Human owner performs final action; agent can draft only. | Policy review plus audit log. |

## Controls

- Least privilege: expose only tools relevant to the current task.
- Conditional availability: disable tools when user scope, environment, or task intent is missing.
- Human-in-the-loop: require approval for high-impact calls and nested agent tools.
- Parameter review: approval UI must show exact resource, parameters, diff, and side effect.
- Call budgets: cap tool call count, recursion, runtime, and spend per run.
- Output-boundary check: tool results from external content must be treated as untrusted prompt input.
- Auditability: log approval subject, tool call id, normalized args, result summary, and rollback state.
- Breakglass: emergency tools need stronger logging, short TTL, and postmortem review.

OpenAI Agents SDK supports approval-based interruptions and `needsApproval` for tools. MCP's authorization spec defines transport-level OAuth-based authorization patterns. OWASP LLM06 frames excessive agency as over-broad autonomy, permissions, or functionality; the agent permission model should directly test that risk.

## Tool Risk Examples

| Failure | Cause | Mitigation |
| --- | --- | --- |
| Agent sends an email instead of drafting it. | `send_email` exposed without approval. | Split `draft_email` and `send_email`; approval required for send. |
| Agent deletes the wrong workspace file. | Resource id not displayed in approval prompt. | Require diff/resource preview and exact path confirmation. |
| Agent follows malicious instructions from a web page. | External read content treated as trusted system context. | Label tool output as untrusted and run prompt-injection evals. |
| Agent calls tool repeatedly until budget is exhausted. | No max call count or spend cap. | Per-run budgets and failure escalation. |
| Agent uses a private MCP server with broad token scope. | Transport authorization over-grants resources. | Resource-scoped OAuth and app-level policy checks. |

## JooPark Product Hook

JooPark should maintain a tool permission registry:

- tool id, provider, permission tier, owner, and default state;
- required user scope and resource boundary;
- approval policy and prompt fields;
- audit log retention and redaction mode;
- last safety eval and last excessive-agency failure cluster;
- rollback capability.

The UI should keep approval prompts compact but concrete. A button labeled "approve" is insufficient without showing exactly what will happen.

## Open Questions

- Which JooPark tools are allowed in autonomous mode versus draft-only mode?
- Should MCP server registration require a signed manifest and owner review?
- How should nested agents inherit or narrow permissions from the parent run?

## Backlinks

- [[index]]
- [[safety]]
- [[eval-failure-triage]]
- [[eval-result-lineage]]
- [[data-privacy-retention]]
- [[runtime-reliability]]
- [[deployment-secrets-env]]
- [[postmortem-action-ledger]]
- [[source-governance]]

## References

### Web

- OpenAI Agents SDK. "Human-in-the-loop." https://openai.github.io/openai-agents-python/human_in_the_loop/
- OpenAI Agents SDK. "Tools." https://openai.github.io/openai-agents-js/guides/tools

### Standard

- Model Context Protocol. "Authorization." https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization
- OWASP. "Top 10 for Large Language Model Applications 2025." https://owasp.org/www-project-top-10-for-large-language-model-applications/assets/PDF/OWASP-Top-10-for-LLMs-v2025.pdf

### Paper

- Ruan et al. "Identifying the Risks of LM Agents with an LM-Emulated Sandbox." arXiv:2309.15817. https://arxiv.org/abs/2309.15817
- Hou et al. "Breaking the Protocol: Security Analysis of the Model Context Protocol Specification and Prompt Injection Vulnerabilities in Tool-Integrated LLM Agents." arXiv:2601.17549. https://arxiv.org/abs/2601.17549

### Book

- Adkins et al. "Building Secure and Reliable Systems." O'Reilly, 2020. ISBN 9781492083122. https://openlibrary.org/works/OL24764469W/Building_Secure_and_Reliable_Systems
