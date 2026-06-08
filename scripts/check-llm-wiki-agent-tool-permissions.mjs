#!/usr/bin/env node
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const source = readFileSync(join(root, "llm-wiki-view.js"), "utf8");
const context = { window: {} };
vm.runInNewContext(source, context, { filename: "llm-wiki-view.js" });

const wiki = context.window.JooParkLlmWikiView?.data;
if (!wiki) {
  console.error(JSON.stringify({ status: "fail", error: "missing JooParkLlmWikiView data" }, null, 2));
  process.exit(1);
}

const articles = wiki.categories.flatMap((cat) => (cat.articles || []).map((article) => ({ cat, article })));
const byId = new Map(articles.map((entry) => [entry.article.id, entry]));
const checks = [];

function body(id) {
  const entry = byId.get(id);
  return entry ? entry.article.body || "" : "";
}

function articleSources(id) {
  const entry = byId.get(id);
  return entry ? entry.article.sources || [] : [];
}

function check(id, terms, sources = []) {
  const text = body(id);
  const actualSources = articleSources(id);
  const missingTerms = terms.filter((term) => !text.includes(term));
  const missingSources = sources.filter((sourceId) => !actualSources.includes(sourceId));
  checks.push({
    id,
    status: missingTerms.length || missingSources.length ? "fail" : "pass",
    missingTerms,
    missingSources,
  });
}

const agentToolPermissionSources = [
  "openai_agents_human_in_loop",
  "openai_agents_guardrails",
  "openai_agents_tools",
  "openai_tools",
  "anthropic_tool_use",
  "anthropic_handle_tool_calls",
  "mcp_tools",
  "mcp_authorization",
  "mcp_security_best_practices",
  "owasp_llm06_excessive_agency",
];

const agentToolPermissionTerms = [
  "LLM06:2025 Excessive Agency",
  "excessive agency",
  "excessive functionality",
  "excessive permissions",
  "excessive autonomy",
  "permissions matrix",
  "tool_policy_bundle",
  "tool_authority_level",
  "read_only",
  "write_draft",
  "external_side_effect",
  "money_movement",
  "infrastructure_change",
  "needs_approval",
  "approval_required",
  "require_approval",
  "HostedMCPTool",
  "tool_config={\"require_approval\":\"always\"}",
  "on_approval_request",
  "RunResult.interruptions",
  "RunState",
  "state.approve",
  "state.reject",
  "always_approve",
  "always_reject",
  "function tools",
  "Agent.as_tool()",
  "agents-as-tools approvals surface on the outer run",
  "ShellTool",
  "ApplyPatchTool",
  "input guardrails",
  "output guardrails",
  "tripwire",
  "fail closed",
  "tool_result",
  "is_error",
  "tool_choice",
  "tools/list",
  "tools/call",
  "inputSchema",
  "outputSchema",
  "OAuth 2.1",
  "per-client consent",
  "redirect_uri",
  "token passthrough",
  "approval_id",
  "approver_id",
  "approval_status",
  "approval_reason",
  "risk_level",
  "blast_radius",
  "expires_at",
  "decision_id",
  "audit_log",
  "A/B 비교: prompt-only autonomy vs permission matrix",
  "A/B 비교: per-agent approval vs per-tool/per-call policy",
  "A/B 비교: auto-approve trusted tools vs human approval queue",
];

checks.push({
  id: "source_registry",
  status: agentToolPermissionSources.every((id) => wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08") ? "pass" : "fail",
  missingTerms: [],
  missingSources: agentToolPermissionSources.filter((id) => !(wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08")),
});

check("agent-tool-permissions", agentToolPermissionTerms, agentToolPermissionSources);

check("source-governance", [
  "Agent Tool Permission 검증",
  "scripts/check-llm-wiki-agent-tool-permissions.mjs",
  "OpenAI Agents SDK human-in-the-loop",
  "OpenAI Agents SDK guardrails",
  "OpenAI Agents SDK tools",
  "OWASP LLM06:2025 Excessive Agency",
  ...agentToolPermissionTerms,
], agentToolPermissionSources);

const failed = checks.filter((item) => item.status !== "pass");
const payload = {
  status: failed.length ? "fail" : "pass",
  checkedAt: new Date().toISOString(),
  articleCount: articles.length,
  sourceCount: Object.keys(wiki.sources || {}).length,
  checks,
};

console.log(JSON.stringify(payload, null, 2));
if (failed.length) process.exit(1);
