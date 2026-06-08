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

const deploymentSecretSources = [
  "openai_api_authentication",
  "openai_api_key_safety",
  "twelve_factor_config",
  "owasp_secrets_management",
  "github_actions_secrets",
  "github_actions_oidc",
  "github_secret_push_protection",
  "vercel_environment_variables",
  "netlify_environment_variables",
  "openai_production_best_practices",
  "openai_data_controls",
];

const deploymentSecretTerms = [
  "deployment_secret_matrix",
  "secret_inventory",
  "secret_classification",
  "secret_owner",
  "runtime_injection",
  "build_time_injection",
  "public_runtime_config",
  "server-only",
  "OPENAI_API_KEY",
  "ANTHROPIC_API_KEY",
  "key management service",
  "client-side environments",
  "browsers or apps",
  "do not commit",
  "do not share",
  "Twelve-Factor Config",
  "environment variables",
  "development",
  "preview",
  "staging",
  "production",
  "Vercel",
  "Production",
  "Preview",
  "Development",
  "vercel env pull",
  ".env.local",
  ".env",
  "Netlify",
  "Deploy Previews",
  "Branch deploys",
  "Local development",
  "Contains secret values",
  "Secrets Controller",
  "team audit log",
  "GitHub Actions secrets",
  "gh secret set",
  "--env ENV_NAME",
  "--org ORG_NAME",
  "--repos",
  "secrets",
  "secrets context",
  "::add-mask::VALUE",
  "OpenID Connect (OIDC)",
  "id-token: write",
  "short-lived access token",
  "no long-lived cloud secrets",
  "sub",
  "aud",
  "environment",
  "repo_property_*",
  "push protection",
  "secret scanning",
  "blocks pushes",
  "bypass reason",
  "creation",
  "rotation",
  "revocation",
  "expiration",
  "blast_radius",
  "break-glass",
  "A/B 비교: build-time injection vs runtime server proxy",
  "A/B 비교: static GitHub secret vs OIDC short-lived token",
  "A/B 비교: one shared provider key vs per-environment key",
];

checks.push({
  id: "source_registry",
  status: deploymentSecretSources.every((id) => wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08") ? "pass" : "fail",
  missingTerms: [],
  missingSources: deploymentSecretSources.filter((id) => !(wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08")),
});

check("deployment-secrets-env", deploymentSecretTerms, deploymentSecretSources);

check("source-governance", [
  "Deployment Secrets/Env 검증",
  "scripts/check-llm-wiki-deployment-secrets-env.mjs",
  "OpenAI API authentication",
  "OpenAI API key safety",
  "The Twelve-Factor App config",
  "OWASP Secrets Management Cheat Sheet",
  "GitHub Actions secrets",
  "GitHub Actions OpenID Connect",
  "GitHub secret scanning push protection",
  "Vercel environment variables",
  "Netlify environment variables",
  ...deploymentSecretTerms,
], deploymentSecretSources);

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
