---
updated: 2026-06-08T16:06:25+09:00
confidence: medium
source_types:
  - web
  - paper
  - standard
  - book
sources:
  - id: w3c_prov_dm
    type: standard
    title: W3C PROV-DM
    url: https://www.w3.org/TR/prov-dm/
    checked: 2026-06-08
  - id: nist_ssdf
    type: standard
    title: NIST SP 800-218 Secure Software Development Framework
    url: https://csrc.nist.gov/pubs/sp/800/218/final
    checked: 2026-06-08
  - id: w3c_vc_data_integrity
    type: standard
    title: W3C Verifiable Credential Data Integrity 1.0
    url: https://www.w3.org/TR/vc-data-integrity/
    checked: 2026-06-08
  - id: dcat_design
    type: paper
    title: "The W3C Data Catalog Vocabulary, Version 2: Rationale, Design Principles, and Uptake"
    url: https://arxiv.org/abs/2303.08883
    checked: 2026-06-08
  - id: craft_of_research
    type: book
    title: "The Craft of Research"
    url: https://openlibrary.org/books/OL3556930M/The_craft_of_research
    checked: 2026-06-08
tags:
  - llm-wiki
  - autoresearch
  - sources
  - governance
  - provenance
  - freshness
---

# Source Governance

Source governance defines how JooPark wiki notes choose sources, record provenance, refresh volatile claims, and mark uncertainty. It is the operating policy for all notes in this AutoResearch queue.

## Source Record Contract

```js
const sourceRecord = {
  source_id: "openai_models_20260608",
  type: "official_doc|standard|paper|book|project_file|news|community",
  title: "OpenAI models",
  url: "https://developers.openai.com/api/docs/models/compare",
  publisher: "OpenAI",
  checked_at: "2026-06-08",
  claim_scope: ["model_id", "context_window", "tool_support", "pricing"],
  volatility: "low|medium|high",
  stale_after_days: 14,
  used_in_notes: ["model-landscape", "model-optimization-routing"],
  confidence: "high|medium|low",
  caveat: "pricing and model lifecycle can change without code changes"
};
```

## Source Hierarchy

| Source type | Use for | Caveat |
| --- | --- | --- |
| Official docs | API behavior, model lists, pricing, retention, product limits. | Can change quickly; always store `checked_at`. |
| Standards | Governance, provenance, security, incident, privacy concepts. | Often abstract; translate into product contracts. |
| Papers | Evaluation method, benchmark limits, failure taxonomies, research evidence. | May not be production-ready; do not overclaim. |
| Books | Stable concepts, engineering framing, research practice. | Do not use for current API behavior. |
| Project files | JooPark-specific implementation and verifier context. | Must be re-read after code changes. |
| News/community | Early signal only. | Never use alone for production decisions. |

W3C PROV-DM gives a language for entities, activities, and agents in provenance. NIST SSDF frames secure development and release evidence. W3C Data Integrity and Verifiable Credentials are relevant when source assertions must be signed or machine-verifiable. The Craft of Research provides stable source evaluation practices.

## LLM Wiki Source Governance Contract

The embedded LLM wiki uses `WIKI_SOURCES` in `llm-wiki-view.js` as the canonical official-source registry. Runtime metadata exposes `sourcePolicy.status = "source-governance/v1"` and every article with source IDs should render the `검증 출처` panel with `공식 출처 링크` anchors. README 운영 절차 documents the minimum recheck commands and release audit markers, so the markdown note, embedded UI, and release gate stay aligned.

```js
const sourcePolicy = {
  status: "source-governance/v1",
  registry: "WIKI_SOURCES",
  required_ui: ["검증 출처", "공식 출처 링크", "source panel"],
  required_note_fields: ["source_id", "source_url", "checked_at", "claim_scope", "freshness_sla", "stale_after_days"],
  uncertainty_markers: ["불확실", "#검증필요"],
  release_audit: "llm_wiki_source_governance"
};
```

Operational rules:

- `WIKI_SOURCES` owns source title, URL, type, checked date, and note; wiki articles reference it by stable source ID.
- Obsidian notes keep `checked_at`, `stale_after_days`, `source_url`, `claim_scope`, and `confidence` so source refresh work is visible outside the UI bundle.
- If an official source cannot confirm a model, price, retention rule, or API parameter, mark the claim `불확실` and add `#검증필요`.
- The UI must keep a `source panel` for all source-backed articles; the smoke test checks `검증 출처` and counts external links.
- README 운영 절차 is part of governance: changes that affect source-backed articles must keep the checker list and release audit text current.

## Freshness SLA

| Claim | Stale threshold | Examples |
| --- | ---: | --- |
| Pricing, model list, deprecation, quota, retention mode | 7-14 days | [[model-landscape]], [[cost-observability]], [[data-privacy-retention]] |
| API parameters, tool schemas, SDK behavior | 14-30 days | [[api-examples]], [[agent-tool-permissions]] |
| Security/safety guidance | 30-60 days | [[safety]], [[deployment-secrets-env]] |
| Benchmarks and papers | 90-180 days | [[rag-evals]], [[evaluator-calibration]] |
| Books and stable standards | 180-365 days | [[postmortem-action-ledger]], [[source-governance]] |
| Project files | On every local code/doc change | [[index]] and all implementation-linked notes |

## Governance Rules

- Every note needs frontmatter with `updated`, `confidence`, `source_types`, and `sources`.
- Volatile claims need `checked_at` and a stale threshold.
- If sources conflict, keep the claim out of product UI and mark `#검증필요`.
- Use official docs for API behavior even when papers or posts explain the idea better.
- Use papers to explain measurement and limitations, not provider feature availability.
- Use books only for stable concepts, not current platform facts.
- Preserve backlinks so downstream notes can be found during refresh.
- When a note affects release decisions, link it to [[rollout-decision-log]] or [[eval-result-lineage]].

## Provenance Mapping

| PROV idea | JooPark wiki mapping |
| --- | --- |
| Entity | Source page, paper, book, project file, eval row, trace, note. |
| Activity | Research cycle, eval run, source refresh, release decision. |
| Agent | Human reviewer, Codex run, provider, standards body, author. |
| WasDerivedFrom | Wiki claim derived from a source record. |
| WasGeneratedBy | Note created by an AutoResearch cycle. |
| WasAttributedTo | Claim tied to source publisher/author and reviewer. |

## Stale-Claim Workflow

1. Detect stale source by `checked_at` or provider changelog.
2. Refresh official docs first.
3. Diff claim fields, not just page text.
4. Update affected notes and `CHANGELOG.md`.
5. Rerun any affected eval or release gate.
6. If the claim cannot be verified, mark `#검증필요` and remove it from product-facing copy.

## A/B Comparison

### A/B 비교: official docs vs third-party summaries

| Choice | Strength | Weakness | Decision |
| --- | --- | --- | --- |
| A. Official docs and standards first | Highest authority for API shape, model IDs, retention, security, and platform limits. | May omit context, rationale, or benchmark caveats. | Default for product and release claims. |
| B. Third-party summaries first | Faster to scan and often compares providers in one place. | Can drift, misquote pricing, or mix tiers without checked dates. | Use only as discovery; do not ship unsupported claims. |

### A/B 비교: embedded source registry vs scattered links

| Choice | Strength | Weakness | Decision |
| --- | --- | --- | --- |
| A. Embedded `WIKI_SOURCES` registry | One canonical `source_id` map feeds article source panels, browser smoke, and release audit. | Editing diffs are longer and require runtime syntax checks. | Keep for this no-build static SPA. |
| B. Scattered markdown links | Easier ad hoc note editing. | Harder to verify source parity, stale claims, and UI source coverage. | Avoid for source-backed LLM/API facts. |

### A/B 비교: stale silence vs explicit `#검증필요`

| Choice | Strength | Weakness | Decision |
| --- | --- | --- | --- |
| A. Leave stale claims unmarked | Cleaner prose and less operator friction. | Readers cannot tell current facts from expired facts. | Reject for volatile provider/API claims. |
| B. Mark `불확실` and `#검증필요` | Makes uncertainty searchable and blocks accidental release use. | Requires follow-up refresh work. | Default when source freshness or provider conflict is unresolved. |

## Recheck Commands

These commands are the README 운영 절차 baseline for source-backed LLM wiki updates:

```sh
node --check llm-wiki-view.js
node scripts/check-llm-wiki-api-examples.mjs
node scripts/check-llm-wiki-rag-eval.mjs
node scripts/check-llm-wiki-eval-dataset-governance.mjs
node scripts/check-llm-wiki-eval-result-lineage.mjs
node scripts/check-llm-wiki-eval-failure-triage.mjs
node scripts/check-llm-wiki-evaluator-calibration.mjs
node scripts/check-llm-wiki-postmortem-action-ledger.mjs
node scripts/check-llm-wiki-rollout-decision-log.mjs
node scripts/check-llm-wiki-multimodal-files.mjs
node scripts/check-llm-wiki-model-optimization-routing.mjs
node scripts/check-llm-wiki-data-privacy-retention.mjs
node scripts/check-llm-wiki-runtime-reliability.mjs
node scripts/check-llm-wiki-prompt-release-management.mjs
node scripts/check-llm-wiki-agent-tool-permissions.mjs
node scripts/check-llm-wiki-deployment-secrets-env.mjs
node scripts/check-llm-wiki-safety-ops.mjs
node scripts/check-llm-wiki-cost-observability.mjs
node --check scripts/smoke-llm-wiki.mjs
BASE_URL=http://127.0.0.1:5178 node scripts/smoke-llm-wiki.mjs
node scripts/audit-release-readiness.mjs --format=summary
```

## Product Hook

JooPark should expose a source governance dashboard:

- stale notes by claim category;
- sources used by more than one note;
- volatile claims without checked date;
- unresolved `#검증필요`;
- release decisions depending on stale sources;
- project files changed since last source refresh.

This turns the wiki from static documentation into an operational evidence layer.

## Open Questions

- Should JooPark sign high-impact source records or keep plain markdown provenance?
- What stale threshold should block a release automatically?
- Should external source refreshes be part of CI or a separate operator workflow?

## Backlinks

- [[index]]
- [[eval-result-lineage]]
- [[rollout-decision-log]]
- [[model-landscape]]
- [[data-privacy-retention]]
- [[cost-observability]]
- [[api-examples]]

## References

### Standard

- W3C. "PROV-DM: The PROV Data Model." https://www.w3.org/TR/prov-dm/
- NIST. "SP 800-218 Secure Software Development Framework Version 1.1." https://csrc.nist.gov/pubs/sp/800/218/final
- W3C. "Verifiable Credential Data Integrity 1.0." https://www.w3.org/TR/vc-data-integrity/

### Paper

- Albertoni et al. "The W3C Data Catalog Vocabulary, Version 2: Rationale, Design Principles, and Uptake." arXiv:2303.08883. https://arxiv.org/abs/2303.08883

### Book

- Booth, Colomb, and Williams. "The Craft of Research." University of Chicago Press, 2003. ISBN 9780226065687. https://openlibrary.org/books/OL3556930M/The_craft_of_research
