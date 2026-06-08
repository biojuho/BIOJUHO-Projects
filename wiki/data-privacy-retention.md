---
updated: 2026-06-08T15:49:11+09:00
confidence: medium
source_types:
  - web
  - paper
  - standard
  - book
sources:
  - id: openai_data_controls
    type: web
    title: OpenAI platform data controls
    url: https://platform.openai.com/docs/guides/your-data
    checked: 2026-06-08
  - id: anthropic_api_retention
    type: web
    title: Anthropic API and data retention
    url: https://platform.claude.com/docs/en/build-with-claude/zero-data-retention
    checked: 2026-06-08
  - id: anthropic_privacy_retention
    type: web
    title: Anthropic personal data retention
    url: https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-personal-data
    checked: 2026-06-08
  - id: owasp_llm02
    type: standard
    title: "OWASP LLM02:2025 Sensitive Information Disclosure"
    url: https://genai.owasp.org/llmrisk/llm02-insecure-output-handling/
    checked: 2026-06-08
  - id: nist_privacy_framework
    type: standard
    title: NIST Privacy Framework Version 1.0
    url: https://www.nist.gov/privacy-framework/privacy-framework
    checked: 2026-06-08
  - id: secret_disclosure_code_llms
    type: paper
    title: "Malicious and Unintentional Disclosure Risks in Large Language Models for Code Generation"
    url: https://arxiv.org/abs/2503.22760
    checked: 2026-06-08
  - id: data_privacy_runbook
    type: book
    title: "Data Privacy: A Runbook for Engineers"
    url: https://www.manning.com/books/data-privacy
    checked: 2026-06-08
tags:
  - llm-wiki
  - autoresearch
  - privacy
  - retention
  - pii
  - zdr
---

# Data Privacy Retention

Data privacy retention defines what user, workspace, prompt, response, file, trace, and eval data is sent to providers, stored by the app, retained in logs, and deleted. This note is engineering guidance, not legal advice.

## Retention Contract

```js
const dataHandlingRecord = {
  data_surface: "chat_prompt|model_response|rag_file|trace|eval_row|tool_result|feedback",
  sensitivity: "public|internal|confidential|restricted|regulated|secret",
  contains_pii: true,
  contains_secret: false,
  provider: "openai|anthropic|local|other",
  provider_retention_mode: "default|modified_abuse_monitoring|zero_data_retention|custom_dpa",
  provider_retention_days: 30,
  training_use: "no_by_default|opt_in|unknown|custom",
  app_retention_days: 90,
  deletion_path: "user_delete|admin_delete|scheduled_ttl|legal_hold",
  log_redaction: "none|pii|secret|full_payload_hash_only",
  audit_log_id: "audit_...",
  checked_at: "2026-06-08",
};
```

Provider retention claims are volatile. Any value shown in product UI must carry `checked_at` and should be reverified before customer-facing or compliance use.

## Source Snapshot

| Source | Current takeaway checked 2026-06-08 | JooPark adoption |
| --- | --- | --- |
| OpenAI data controls | API data is not used for model training unless explicitly opted in; abuse-monitoring logs are retained by default for up to 30 days, with eligible ZDR/modified abuse monitoring controls. | Store provider mode per request and warn when ZDR is not active for restricted data. |
| Anthropic API retention | Anthropic documents API and feature-specific retention, including ZDR availability; privacy center states API inputs/outputs are deleted within 30 days unless agreed otherwise. | Treat provider/product channel separately; do not assume Claude web/app policy equals API policy. |
| OWASP LLM02 | Sensitive information disclosure covers PII, confidential business data, credentials, legal documents, and leakage through outputs or application context. | Add prompt/output/tool-result checks for PII, secrets, and access-controlled RAG documents. |
| NIST Privacy Framework | Privacy risk should be handled through enterprise risk management and data processing policies. | Use as the umbrella for minimization, retention, access, deletion, and audit controls. |

## Required Controls

- Data minimization: send only the fields the model/tool needs.
- Surface labeling: classify each prompt, file, trace, eval row, and feedback event before provider dispatch.
- Secret filtering: block credentials and tokens before prompts, traces, eval datasets, and screenshots are stored.
- Retention mode logging: record provider, model, endpoint, retention mode, and checked date.
- RAG access boundaries: retrieved documents must preserve ACL and workspace id in [[rag-evals]] and trace evidence.
- Eval dataset hygiene: incident-derived rows must be scrubbed before entering [[eval-dataset-governance]].
- Output review: any `pii_leak` or `sensitive_disclosure` cluster escalates through [[eval-failure-triage]].
- Deletion path: user/admin deletion must remove or tombstone app state and queued derived artifacts.

## ZDR and Audit Tradeoff

| Choice | Benefit | Risk | Product rule |
| --- | --- | --- | --- |
| Default provider retention | Easier abuse monitoring, debugging, and support evidence. | Prompt/response content may exist in provider logs for the provider-defined window. | Allowed for public/internal data only if policy permits. |
| Modified abuse monitoring | Lower content retention while keeping some safety monitoring. | Requires provider eligibility and customer responsibility for safety monitoring. | Use for confidential data when available. |
| Zero data retention | Strongest provider-side retention reduction. | Some features may be unavailable; app must own abuse monitoring and auditability. | Required for restricted/regulated data unless a custom exception is approved. |
| Local-only processing | Avoids third-party retention. | Model quality, cost, and operational controls may change. | Consider for secrets or high-risk regulated workflows. |

## Eval Hooks

| Eval | Fails when | Linked note |
| --- | --- | --- |
| `pii_output_leak` | Output includes personal data not requested or not authorized. | [[safety]], [[eval-failure-triage]] |
| `secret_prompt_block` | Prompt sends API keys, tokens, private keys, or credentials. | [[deployment-secrets-env]] |
| `rag_acl_boundary` | Retrieved document belongs to another workspace/user. | [[rag-evals]] |
| `trace_payload_redaction` | Trace stores full restricted payload when policy requires redaction. | [[eval-result-lineage]] |
| `retention_mode_mismatch` | Restricted data uses default provider retention. | [[rollout-decision-log]] |

## Product Hook

JooPark should show a privacy-retention badge for each LLM route:

- provider and endpoint;
- provider retention mode and checked date;
- app retention TTL;
- whether prompts/responses/traces/evals are redacted;
- deletion path and audit id;
- last privacy eval status.

The UI must avoid implying legal compliance from a provider mode alone. ZDR is a technical retention control, not a complete privacy program.

## Open Questions

- Which data classes exist in JooPark: workspace notes, uploaded files, code, financial data, health data, or customer support records?
- Should all eval traces redact payloads by default and keep only hashes plus sample ids?
- What user-facing deletion SLA should be supported for derived eval rows and vector indexes?

## Backlinks

- [[index]]
- [[eval-dataset-governance]]
- [[eval-result-lineage]]
- [[eval-failure-triage]]
- [[rag-evals]]
- [[safety]]
- [[agent-tool-permissions]]
- [[deployment-secrets-env]]
- [[source-governance]]

## References

### Web

- OpenAI. "Data controls in the OpenAI platform." https://platform.openai.com/docs/guides/your-data
- Anthropic. "API and data retention." https://platform.claude.com/docs/en/build-with-claude/zero-data-retention
- Anthropic Privacy Center. "How long do you store personal data?" https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-personal-data

### Standard

- OWASP. "LLM02:2025 Sensitive Information Disclosure." https://genai.owasp.org/llmrisk/llm02-insecure-output-handling/
- NIST. "Privacy Framework Version 1.0." https://www.nist.gov/privacy-framework/privacy-framework

### Paper

- Pearce et al. "Malicious and Unintentional Disclosure Risks in Large Language Models for Code Generation." arXiv:2503.22760. https://arxiv.org/abs/2503.22760

### Book

- Bhajaria. "Data Privacy: A Runbook for Engineers." Manning, 2022. ISBN 9781617298998. https://www.manning.com/books/data-privacy
