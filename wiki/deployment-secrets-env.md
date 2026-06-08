---
updated: 2026-06-08T15:55:53+09:00
confidence: medium
source_types:
  - web
  - standard
  - paper
  - book
sources:
  - id: openai_api_authentication
    type: web
    title: OpenAI API authentication
    url: https://developers.openai.com/api/reference/overview
    checked: 2026-06-08
  - id: openai_api_key_safety
    type: web
    title: OpenAI API key safety best practices
    url: https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety
    checked: 2026-06-08
  - id: twelve_factor_config
    type: standard
    title: The Twelve-Factor App config
    url: https://www.12factor.net/config
    checked: 2026-06-08
  - id: owasp_secrets_management
    type: standard
    title: OWASP Secrets Management Cheat Sheet
    url: https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html
    checked: 2026-06-08
  - id: github_actions_secrets
    type: web
    title: GitHub Actions secrets
    url: https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets
    checked: 2026-06-08
  - id: github_actions_oidc
    type: web
    title: GitHub Actions OpenID Connect
    url: https://docs.github.com/en/actions/concepts/security/openid-connect
    checked: 2026-06-08
  - id: github_secret_push_protection
    type: web
    title: GitHub secret scanning push protection
    url: https://docs.github.com/en/code-security/concepts/secret-security/push-protection
    checked: 2026-06-08
  - id: vercel_environment_variables
    type: web
    title: Vercel environment variables
    url: https://vercel.com/docs/environment-variables
    checked: 2026-06-08
  - id: netlify_environment_variables
    type: web
    title: Netlify environment variables
    url: https://docs.netlify.com/build/environment-variables/overview/
    checked: 2026-06-08
  - id: openai_production_best_practices
    type: web
    title: OpenAI production best practices
    url: https://developers.openai.com/api/docs/guides/production-best-practices
    checked: 2026-06-08
  - id: openai_data_controls
    type: web
    title: OpenAI data controls
    url: https://developers.openai.com/api/docs/guides/your-data
    checked: 2026-06-08
  - id: how_bad_can_it_git
    type: paper
    title: "How Bad Can It Git? Characterizing Secret Leakage in Public GitHub Repositories"
    url: https://bradreaves.net/publication/mmr19/
    checked: 2026-06-08
  - id: secretbench
    type: paper
    title: "SecretBench: A Dataset of Software Secrets"
    url: https://arxiv.org/abs/2303.06729
    checked: 2026-06-08
  - id: security_engineering
    type: book
    title: "Security Engineering: A Guide to Building Dependable Distributed Systems"
    url: https://openlibrary.org/books/OL18632587M/Security_engineering
    checked: 2026-06-08
tags:
  - llm-wiki
  - autoresearch
  - secrets
  - env
  - deployment
  - oidc
  - api-keys
---

# Deployment Secrets Env

Deployment secrets and environment variables define how API keys, cloud credentials, OAuth tokens, webhook secrets, and user-provided keys move through local development, CI, deployment, and runtime.

## Secret Contract

```js
const secretRecord = {
  secret_id: "sec-openai-prod-route",
  secret_type: "api_key|oauth_token|webhook_secret|cloud_credential|database_url|user_byok",
  provider: "openai",
  environment: "local|preview|staging|production|ci",
  storage: "env_file|platform_secret|kms|vault|github_secret|oidc_ephemeral",
  exposed_to_client: false,
  rotation_days: 90,
  last_rotated_at: "2026-06-08",
  owner: "platform",
  least_privilege_scope: "project:model-route:read-write",
  leak_detection: ["git_push_protection", "runtime_redaction", "usage_monitor"],
  incident_runbook: "rotate-disable-audit",
};
```

## Secret Matrix Contract

JooPark should keep an explicit `deployment_secret_matrix` instead of relying on tribal knowledge:

```js
const deployment_secret_matrix = {
  secret_inventory: ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DATABASE_URL", "WEBHOOK_SECRET"],
  secret_classification: "provider_api_key|cloud_credential|database_credential|user_byok",
  secret_owner: "platform",
  environment: "development|preview|staging|production",
  injection_mode: "runtime_injection|build_time_injection|public_runtime_config",
  visibility: "server-only",
  storage: "key management service|GitHub Actions secrets|Vercel|Netlify|local_env_file",
  local_file: ".env.local|.env",
  lifecycle: ["creation", "rotation", "revocation", "expiration"],
  leak_response: ["blast_radius", "break-glass", "bypass reason"],
};
```

The safe default is `runtime_injection` into a server-only backend route. `build_time_injection` can freeze secrets into build artifacts, and `public_runtime_config` must never include provider API keys.

## Rules

- Never expose provider API keys in browser, mobile, or static frontend bundles.
- Use one key per owner/team/workload where the provider supports it.
- Store local keys in ignored env files or the OS secret store, not in source code.
- Route public client requests through a backend or token broker.
- Enable secret scanning and push protection for repositories.
- Prefer OIDC short-lived cloud credentials over long-lived CI deployment secrets.
- Rotate immediately on suspected exposure; deleting a committed key from the latest commit is not enough.
- Redact secrets from prompts, traces, logs, screenshots, eval datasets, and error messages.

OpenAI API authentication treats API keys as bearer credentials and OpenAI key-safety guidance says provider keys should not be exposed in `client-side environments`, browsers or apps; use environment variables and a key management service for production. Twelve-Factor Config frames config as `environment variables` that differ per deploy and are not committed to code. OWASP Secrets Management adds lifecycle controls: `creation`, `rotation`, `revocation`, and `expiration`. GitHub push protection blocks pushes with detected secrets and records a `bypass reason` if a contributor bypasses the block. GitHub Actions OIDC lets workflows request a `short-lived access token` with `id-token: write`, avoiding `no long-lived cloud secrets` in CI.

## Environment Matrix

| Environment | Allowed storage | Disallowed |
| --- | --- | --- |
| `development` | `.env.local` or `.env` ignored by git, OS keychain, 1Password/Vault, shell env, `vercel env pull` for Development values. | Shared hardcoded key, committed env file, public browser bundle. |
| `preview` | Vercel Preview, Netlify Deploy Previews, branch-scoped values, staging-only provider key. | Production key reused in preview. |
| `staging` | Staging-only provider key and staging data stores. | User production BYOK or production database URL. |
| `production` | KMS/Vault/platform secret with owner, rotation, revocation, expiration, and audit. | Manual key copied into frontend build. |
| `ci` | GitHub Actions secrets for low-risk static values; OIDC with short-lived access token for cloud deploy. | Long-lived cloud admin key. |

Platform-specific handling:

- **Vercel**: distinguish Production, Preview, and Development environment variables. Pull local values with `vercel env pull`; never expose server-only provider keys through a public runtime variable.
- **Netlify**: distinguish Local development, Deploy Previews, Branch deploys, and production deploy context values. Mark sensitive variables with `Contains secret values` so Netlify's Secrets Controller applies stronger handling and team audit log visibility.
- **GitHub Actions secrets**: set scoped values with `gh secret set`, including `--env ENV_NAME`, `--org ORG_NAME`, and `--repos` when appropriate. Access values through the `secrets context`; if a derived value appears in logs, mask it with `::add-mask::VALUE`.

## LLM-Specific Hazards

| Hazard | Why it matters | Control |
| --- | --- | --- |
| Prompt leakage | Secrets in system prompts can be revealed or logged. | Never put secrets in prompts; use server-side tools. |
| Trace leakage | Full payload traces may include env values or tokens. | [[data-privacy-retention]] redaction and payload hashes. |
| Eval leakage | Failed examples can copy real secrets into datasets. | Scrub before [[eval-dataset-governance]]. |
| BYOK misuse | User keys entered in UI can be stolen if handled client-side. | Token broker, encrypted storage, explicit deletion path. |
| Tool result exposure | Tool returns secret and model repeats it. | Tool schema redaction and [[safety]] evals. |

## Source A/B Findings

| Comparison | A | B | JooPark decision |
| --- | --- | --- | --- |
| Config location | Twelve-Factor Config says env vars are per-deploy and not committed. | OpenAI key safety adds no browsers or apps, no public repo, and key management service for production. | Store provider keys only in server-only env/KMS paths. |
| CI cloud credentials | GitHub Actions secrets are straightforward and scoped by repo/environment/org. | OpenID Connect (OIDC) with `id-token: write` exchanges a signed claim for a short-lived access token. | Prefer OIDC for cloud deploy; use secrets for provider keys that do not support federation. |
| Leak prevention | GitHub secret scanning and push protection can block pushes and record bypasses. | OWASP lifecycle requires revocation, rotation, expiration, and audit after exposure. | Treat push protection as prevention, not incident closure. |

## A/B 비교: build-time injection vs runtime server proxy

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. Build-time injection | static build에서 설정을 쉽게 참조한다. | secret이 bundle, sourcemap, cache artifact로 굳을 수 있다. | public_runtime_config와 non-secret feature flag만. |
| B. Runtime server proxy | provider key가 server-only 경계에 남고 rotation이 쉽다. | backend route와 auth/rate-limit 운영이 필요하다. | OPENAI_API_KEY, ANTHROPIC_API_KEY 기본값. |

## A/B 비교: static GitHub secret vs OIDC short-lived token

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. Static GitHub secret | 설정이 쉽고 많은 provider가 지원한다. | 장기 credential이 저장되고 rotation/revocation 부담이 커진다. | provider API key처럼 federation 불가한 값. |
| B. OpenID Connect (OIDC) | cloud provider가 job마다 short-lived access token을 발급하고 no long-lived cloud secrets 상태를 만든다. | cloud trust policy와 `sub`, `aud`, `environment`, `repo_property_*` claim 설계가 필요하다. | cloud deploy credential 기본값. |

## A/B 비교: one shared provider key vs per-environment key

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. One shared provider key | 빠르게 시작하고 secret count가 적다. | blast_radius가 커지고 preview/staging 사고가 production에 영향을 준다. | local prototype까지만. |
| B. Per-environment key | development, preview, staging, production별 사용량·rotation·revocation이 분리된다. | secret_inventory와 owner 관리가 필요하다. | production 운영 기본값. |

## Leak Response

1. Disable or rotate the exposed secret immediately.
2. Identify `blast_radius`: provider, project, environment, usage, and logs.
3. Review billing/usage and access logs.
4. Remove secret from current source and historical artifacts where possible.
5. Add detector or push-protection rule if the format was missed.
6. Record push protection bypass reason, secret scanning alert id, and break-glass approver if applicable.
7. Create [[postmortem-action-ledger]] item for prevention and closure evidence.
8. Rerun safety/privacy evals if the secret appeared in prompts, traces, or datasets.

## Product Hook

JooPark should show deployment secret posture without revealing values:

- route id and secret owner;
- environment and storage type;
- last rotation and next rotation due;
- whether client exposure is blocked;
- secret scanning/push protection state;
- OIDC availability for deploy;
- last leak-response drill.

## Open Questions

- Does JooPark need a BYOK flow, or should all model calls use platform-managed project keys?
- Which deployment platform stores production secrets today?
- Should preview deployments be blocked if they reference production model keys?

## Backlinks

- [[index]]
- [[data-privacy-retention]]
- [[safety]]
- [[agent-tool-permissions]]
- [[runtime-reliability]]
- [[rollout-decision-log]]
- [[postmortem-action-ledger]]
- [[source-governance]]

## References

### Web

- OpenAI. "API authentication." https://developers.openai.com/api/reference/overview
- OpenAI Help Center. "Best Practices for API Key Safety." https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety
- OpenAI. "Production best practices." https://developers.openai.com/api/docs/guides/production-best-practices
- OpenAI. "Data controls." https://developers.openai.com/api/docs/guides/your-data
- GitHub Docs. "Using secrets in GitHub Actions." https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets
- GitHub Docs. "OpenID Connect." https://docs.github.com/en/actions/concepts/security/openid-connect
- GitHub Docs. "Push protection." https://docs.github.com/en/code-security/concepts/secret-security/push-protection
- Vercel. "Environment variables." https://vercel.com/docs/environment-variables
- Netlify. "Environment variables overview." https://docs.netlify.com/build/environment-variables/overview/

### Standard

- Twelve-Factor App. "Config." https://www.12factor.net/config
- OWASP. "Secrets Management Cheat Sheet." https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html

### Paper

- Meli, McNiece, and Reaves. "How Bad Can It Git? Characterizing Secret Leakage in Public GitHub Repositories." NDSS 2019. https://bradreaves.net/publication/mmr19/
- Basak et al. "SecretBench: A Dataset of Software Secrets." arXiv:2303.06729. https://arxiv.org/abs/2303.06729

### Book

- Anderson. "Security Engineering: A Guide to Building Dependable Distributed Systems." Wiley, 2008. ISBN 9780470068526. https://openlibrary.org/books/OL18632587M/Security_engineering
