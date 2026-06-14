# DSCI QC Log

## 2026-06-13 (Per-Route Document Meta for SPA Routes)

### Scope
- Follow-up to the index.html hardening: the SPA had no per-route `document.title`/meta, so every route (`/pricing`, `/explore`, `/investors`, 404) showed the home title in the browser tab, bookmarks, and deep-link social shares. Only `ProposalView` had any title handling.
- Owned paths: `frontend/src/hooks/useDocumentMeta.js` (+ test), `frontend/src/components/{LandingPage,PricingPage,Investors,ResearchFeed,NotFound}.jsx`, this log.

### A/B Decision
- A (baseline): single static title from index.html for all routes.
- B (variant): a dependency-free `useDocumentMeta` hook that sets title + meta description + OG/Twitter title/description + canonical per route, locale-aware (ko-KR/en-US via existing `useLocale`), and restores the index.html baseline on unmount. Wired into the 5 public routes.
- Rejected react-helmet (would add a dependency; CLAUDE.md forbids unapproved deps). The hook is ~110 lines, no new dep, no bundle change.
- Selected B: distinct titles improve tab/bookmark UX, crawler per-page understanding, and deep-link share cards.

### Verification
- `npx vitest run src/hooks/useDocumentMeta.test.jsx` -> 4 passed (set+propagate, canonical-from-path, restore-on-unmount, create-missing-tag). Found+fixed a test-fixture ordering bug (innerHTML assignment wiped the jsdom `<title>`); hook itself unchanged.
- `npx vitest run` page tests for LandingPage/PricingPage/Investors/ResearchFeed/NotFound -> 27 passed total, no regressions.
- `npm run lint` -> clean. `npm run build` -> built in 1.61s.

### Result
- Public routes now carry correct, locale-aware titles and meta. Additive, revertible.
- Next cycle: PricingPage `Product`/`Offer` JSON-LD injected client-side, and an axe-core a11y smoke over the landing+pricing flow.

## 2026-06-13 (Launch SEO/a11y Meta Hardening — index.html)

### Scope
- Baseline audit of `frontend/index.html` for launch readiness surfaced concrete defects: `<html lang="en">` on Korean-primary content (screen-reader mispronunciation + wrong search-engine language detection), no `og:image` (broken social-share preview), no Twitter Card, no `canonical`, no JSON-LD structured data, no `<noscript>` fallback.
- Owned paths: `frontend/index.html`, `frontend/public/og-image.png`, `frontend/scripts/generate_og_image.py`, this log.

### External Checks
- 2026 SaaS SEO guidance confirms the direction: Organization JSON-LD on home + SoftwareApplication (with offers) on product/pricing, canonical on every page, Open Graph + Twitter Card on every page, meta description treated as conversion copy.
  - https://withsentari.com/saas-seo-best-practices-2026/
  - https://netstager.ae/blog/json-ld-for-modern-seo/
  - https://www.desisle.com/resources/saas-meta-tags-cheat-sheet

### A/B Decision
- A (baseline): existing minimal head — `lang="en"`, partial OG (no image), no Twitter/canonical/JSON-LD.
- B (variant): `lang="ko"`, full OG (image 1200×630 + locale + alt), Twitter `summary_large_image`, `canonical`, `robots`, `author`, Organization + SoftwareApplication JSON-LD (`@graph`) with the real pricing offers (Starter $0 / Pro $29 / Enterprise $199), and a bilingual `<noscript>` fallback.
- Primary KPI: launch meta completeness + language correctness. Secondary: build, JS bundle, no broken asset reference.
- Selected B: strictly dominates A. og:image points at a real generated PNG (no broken reference); JSON-LD parses; no JS bundle change (image is a static public asset).

### Verification
- `python scripts/generate_og_image.py` -> wrote `public/og-image.png` (42889 bytes, 1200x630, brand bg #040811 / accent #20BB8A). Visually confirmed: wordmark + Korean tagline + feature chips + domain, no text overlap.
- JSON-LD parsed with `json.loads`: `@graph` = [Organization, SoftwareApplication]; offers = [Starter:0, Pro:29, Enterprise:199]; `<html lang>` = `ko`.
- `npm run build` -> built in 2.33s; `dist/og-image.png` present (42889 bytes); `dist/index.html` carries all new meta (twitter:card, ld+json, lang="ko", og:image).
- `npm run lint` -> clean. `npm run check:bundle` -> OK (max chunk <= 500KB, entry <= 260KB) — unchanged.

### Result
- Launch landing now has correct language, valid structured data, and working social-share previews. Pure additive/correctness change, cleanly revertible.
- Next cycle: per-route canonical + dynamic meta for SPA routes (PricingPage Product schema), and a Playwright a11y smoke (axe-core) on the landing flow.

## 2026-06-07 (AI Lab Key Finding Action Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_KEY_FINDING_ACTION_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated Key Findings scoring and found that `key_finding_fields` accepted broad Action meaning lines such as `add source freshness to the first-pass opportunity discovery workflow`.
- Expanded generic phrase rejection so broad Key Finding action meanings must be replaced with artifact, owner, decision gate, checklist, or review workflow context.
- Added a regression for broad Key Finding action meanings.
- Updated the shared prompt contract to reject broad Key Finding action wording.

### Verification
- Direct false-positive probe -> `needs_revision score=0.975 failed_check_ids=['key_finding_fields']`.
- Focused Key Finding action regression set -> `3 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `165 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-key-finding-action-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `195 passed`.
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_KEY_FINDING_ACTION_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Evidence Map Follow-Up Anchor Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EVIDENCE_MAP_FOLLOWUP_ANCHOR_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated Evidence Map follow-up scoring and found that `evidence_map_confidence_followup` accepted broad follow-up wording such as `check sponsor deadlines and eligibility`.
- Added follow-up anchor markers so verification actions need proof anchors such as retrieval dates, source URLs, evidence snippets, prior-award abstracts, live-provider packet, credential recovery, strict scoring, or blocker validation.
- Added a regression for broad Evidence Map follow-up verification wording.
- Updated the shared prompt contract to reject broad Evidence Map follow-up wording.

### Verification
- Direct false-positive probe -> `needs_revision score=0.975 failed_check_ids=['evidence_map_confidence_followup']`.
- Focused Evidence Map follow-up regression set -> `3 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `164 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-evidence-map-followup-anchor-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `194 passed`.
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EVIDENCE_MAP_FOLLOWUP_ANCHOR_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Red Flag Escalation Action Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_RED_FLAG_ESCALATION_ACTION_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated Reviewer Red Flags scoring and found that `reviewer_red_flags_actionability` accepted escalation wording with role and timing but no resolution action.
- Added escalation action markers so red flags need an owner, timing, and resolve/verify/validate/correct/recover action before reuse.
- Added a regression for broad red-flag escalation wording.
- Updated the shared prompt contract to reject broad red-flag escalation wording.
- Hardened the AI Lab browser-smoke fixture so copied review packets pass the stricter red-flag escalation contract.

### Verification
- Direct false-positive probe -> `needs_revision score=0.975 failed_check_ids=['reviewer_red_flags_actionability']`.
- Focused red-flag escalation regression set -> `3 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `163 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Initial dev-auth browser smoke exposed a fixture gap in `reviewer_red_flags_actionability`; after fixture hardening it passed `1/1` in `var/desci-ai-lab-red-flag-escalation-action-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `193 passed`.
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_RED_FLAG_ESCALATION_ACTION_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Assumptions Validation Anchor Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ASSUMPTIONS_VALIDATION_ANCHOR_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated Assumptions & Boundaries scoring and found that `assumptions_boundaries` accepted broad validation wording such as `review source freshness before final pursuit`.
- Added validation-specific anchor checks so Validation must include concrete anchors such as every sponsor page, retrieval dates, compliance constraints, memo review, PI approval, proposal drafting, source snapshot, or launch review.
- Added a regression for broad Assumptions validation wording.
- Updated the shared prompt contract to reject broad Assumptions validation wording.
- Hardened the AI Lab browser-smoke fixture so the copied review packet passes the stricter Assumptions validation contract.

### Verification
- Direct false-positive probe -> `needs_revision score=0.975 failed_check_ids=['assumptions_boundaries']`.
- Focused Assumptions validation-anchor regression set -> `3 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `162 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Initial dev-auth browser smoke exposed a fixture gap in `assumptions_boundaries`; after fixture hardening it passed `1/1` in `var/desci-ai-lab-assumptions-validation-anchor-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `192 passed`.
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ASSUMPTIONS_VALIDATION_ANCHOR_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Reference Query Topic Anchor Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REFERENCE_QUERY_TOPIC_ANCHOR_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated References & Search Queries scoring and found that broad query terms could pass when they contained source-verification markers but no concrete topic/source anchor.
- Added a topic-anchor requirement for reference queries, preserving concrete NASA acceptance-criteria queries while rejecting broad terms such as `sponsor eligibility prior award RFP review`.
- Added a regression for broad reference-query terms without topic anchors.
- Updated the shared prompt contract to reject broad reference-query wording.

### Verification
- Direct false-positive probe -> `needs_revision score=0.95 failed_check_ids=['references_search_queries', 'references_verification_search_plan']`.
- Focused reference-query regression set -> `4 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `161 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-reference-query-topic-anchor-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `191 passed`.
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REFERENCE_QUERY_TOPIC_ANCHOR_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Risk Field Anchor Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_RISK_FIELD_ANCHOR_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated Risks & Open Questions scoring and found that `risks_open_questions_owner_verification` accepted broad verification, review, and follow-up fields when the surrounding risk text was specific.
- Added field-specific anchors so verification/status/follow-up details need reusable artifacts or review moments such as retrieval dates, sponsor pages, prior-award abstracts, source snapshot, Day 2 review, PI decision slot, affected sponsor rows, sponsor confirmation, launch review, or production reuse.
- Added a regression for broad risk verification/status/follow-up wording.
- Updated the shared prompt contract to reject broad risk-field wording.
- Hardened the AI Lab browser-smoke fixture so the copied review packet passes the stricter risk-field contract.

### Verification
- Direct false-positive probe -> `needs_revision score=0.975 failed_check_ids=['risks_open_questions_owner_verification']`.
- Focused Risk/Open Question field-anchor regression set -> `3 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `160 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Initial dev-auth browser smoke exposed a fixture gap in `risks_open_questions_owner_verification`; after fixture hardening it passed `1/1` in `var/desci-ai-lab-risk-field-anchor-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `190 passed`.
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_RISK_FIELD_ANCHOR_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Action Plan Dependency Anchor Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_PLAN_DEPENDENCY_ANCHOR_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated Action Plan dependency scoring and found that `action_plan_dependency_order` accepted broad source-freshness and eligibility dependency wording.
- Required dependency details to include an operational anchor such as source URLs, prior-award abstracts, memo scoring, proposal drafting, budget conflict, live provider, or credential recovery.
- Expanded generic phrase rejection so `source freshness and eligibility must be available before work` is rejected as a dependency substitute.
- Added a regression for broad Action Plan dependency marker stuffing.
- Updated the shared prompt contract to reject broad dependency wording.

### Verification
- Direct false-positive probe -> `needs_revision score=0.975 failed_check_ids=['action_plan_dependency_order']`.
- Focused Action Plan dependency-anchor regression set -> `3 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `159 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-action-plan-dependency-anchor-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `189 passed`.
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_PLAN_DEPENDENCY_ANCHOR_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Alternative Comparison Tradeoff Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ALTERNATIVE_COMPARISON_TRADEOFF_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated Alternative Comparison scoring and found that `competitive_alternative_comparison` accepted broad tradeoff wording when baseline and tradeoff markers were present.
- Expanded generic phrase rejection so `manual spreadsheet scouting is cheaper but less connected to source freshness` and `generic grant platforms cover more programs but rarely support proposal planning` are rejected.
- Required a concrete differentiator such as owner handoff, eligibility evidence, lab-specific go/no-go gates, repeatable source evidence, or scorer-ready packet detail.
- Added a regression for broad Alternative Comparison tradeoff wording.
- Updated the shared prompt contract to reject broad Alternative Comparison tradeoff wording.

### Verification
- Direct false-positive probe -> `needs_revision score=0.975 failed_check_ids=['competitive_alternative_comparison']`.
- Focused Alternative Comparison tradeoff regression set -> `3 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `158 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-alternative-comparison-tradeoff-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `188 passed`.
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ALTERNATIVE_COMPARISON_TRADEOFF_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Quality Criteria Destination Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_QUALITY_CRITERIA_DESTINATION_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated Quality Criteria scoring and found that `quality_criteria_actionable_acceptance` accepted a broad Reuse destination when it contained proposal-planning and review-packet markers.
- Expanded generic phrase rejection so `proposal planning handoff and review packet` is rejected unless the destination names concrete paste artifacts such as the weekly meeting note and two-page pursuit memo.
- Added a regression for vague Quality Criteria reuse-destination wording.
- Updated the shared prompt contract to reject broad reuse-destination wording in Quality Criteria.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- Focused accepted-packet probe -> `decision pass 1.0 []`, `grounded pass 1.0 []`.
- Focused Quality Criteria destination regression set -> `3 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `157 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-quality-criteria-destination-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `187 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_QUALITY_CRITERIA_DESTINATION_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Reusable Handoff Destination Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REUSABLE_HANDOFF_DESTINATION_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated copy-ready Reusable Handoff scoring and found that `reusable_handoff` accepted broad destination wording when role, meeting-note, and source-check markers were still present.
- Expanded generic phrase rejection so `approve the owner and review slot` and `paste this into the meeting note and reuse the source-check checklist` are rejected.
- Added a regression for vague copy-ready handoff destination wording.
- Updated the shared prompt contract to reject broad copy-ready handoff destination wording.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- Focused accepted-packet probe -> `decision pass 1.0 []`, `grounded pass 1.0 []`.
- Focused Reusable Handoff destination regression set -> `3 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `156 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-reusable-handoff-destination-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `186 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REUSABLE_HANDOFF_DESTINATION_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Artifact-Ready Evidence Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ARTIFACT_READY_EVIDENCE_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated Artifact-ready Handoff scoring and found that `artifact_ready_handoff_format` accepted a broad Evidence attachment field when it contained source, eligibility, evidence, and quality-report markers.
- Expanded generic phrase rejection so `source-backed evidence, eligibility notes, and quality report` is rejected as a substitute for source URLs and prior-award abstracts.
- Added a regression for vague Artifact-ready Evidence attachment wording.
- Updated the shared prompt contract to reject broad Evidence attachment wording.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- Focused accepted-packet probe -> `decision pass 1.0 []`, `grounded pass 1.0 []`.
- Focused Artifact-ready Evidence regression set -> `3 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `155 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-artifact-ready-evidence-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `185 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ARTIFACT_READY_EVIDENCE_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Quality Criteria Ready Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_QUALITY_CRITERIA_READY_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated Quality Criteria scoring and found that `quality_criteria_actionable_acceptance` accepted broad Ready to use wording when it named source-backed evidence, uncertainty, owner, and next action but omitted the actual recommendation/decision.
- Expanded generic phrase rejection so `source-backed evidence, uncertainty, owner, and next action are present` is rejected.
- Added a regression for vague Quality Criteria ready-condition wording.
- Updated the shared prompt contract to reject broad ready-condition wording in Quality Criteria.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- Focused accepted-packet probe -> `decision pass 1.0 []`, `grounded pass 1.0 []`.
- Focused Quality Criteria ready-condition regression set -> `3 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `154 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-quality-criteria-ready-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `184 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_QUALITY_CRITERIA_READY_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Reference Source Freshness Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REFERENCE_SOURCE_FRESHNESS_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated References source freshness scoring and found that `references_source_freshness` and `references_each_source_freshness` accepted broad freshness wording when it contained retrieved/accessed markers.
- Expanded generic source freshness rejection so `record retrieved/accessed date before final decision` is rejected unless freshness is tied to each source, sponsor page, or evidence record.
- Added a regression for broad Reference source freshness wording.
- Updated the shared prompt contract to reject broad source freshness placeholders.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- Focused accepted-packet probe -> `decision pass 1.0 []`, `grounded pass 1.0 []`.
- Focused References freshness regression set -> `4 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `153 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-reference-source-freshness-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `183 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REFERENCE_SOURCE_FRESHNESS_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Reference Query Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REFERENCE_QUERY_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated References/Search Queries scoring and found that `references_search_queries` and `references_verification_search_plan` accepted broad sponsor-eligibility query wording when source-scope and topic markers were present.
- Expanded generic reference-query rejection so `grant translational oncology sponsor eligibility`, `digital health sponsor eligibility`, and `prior award translational oncology sponsor eligibility` are rejected.
- Added a regression for broad sponsor-eligibility reference queries.
- Updated the shared prompt contract to reject broad sponsor-eligibility query substitutes.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- Focused accepted-packet probe -> `decision pass 1.0 []`, `grounded pass 1.0 []`.
- Focused References query regression set -> `3 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `152 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-reference-query-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `182 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REFERENCE_QUERY_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Reference Source Lead Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REFERENCE_SOURCE_LEAD_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated References/Search Queries scoring and found that `references_search_queries` accepted broad Source lead context when one concrete source-family marker was present.
- Added generic Source lead identity rejection so `prior award context`, `eligibility materials`, `evidence lists`, `sponsor source pages`, and broad `source pages` are rejected.
- Added a regression for vague Source lead material/context wording.
- Updated the shared prompt contract to reject vague Source lead source-family substitutes.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- Focused accepted-packet probe -> `decision pass 1.0 []`, `grounded pass 1.0 []`.
- Focused References Source lead regression set -> `4 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `151 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-reference-source-lead-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `181 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REFERENCE_SOURCE_LEAD_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Quality Criteria Evidence Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_QUALITY_CRITERIA_EVIDENCE_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated Quality Criteria scoring and found that `quality_criteria_actionable_acceptance` accepted broad Evidence required wording when it named only source-backed evidence, cited evidence, and the strict quality report.
- Expanded generic phrase rejection so `source-backed evidence, cited evidence, and the strict quality report` is rejected as a substitute for source URLs, retrieval dates, eligibility notes, and prior-award abstracts.
- Added a regression for vague Quality Criteria evidence requirements.
- Updated the shared prompt contract to reject broad evidence-required wording in Quality Criteria.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- Focused accepted-packet probe -> `decision pass 1.0 []`, `grounded pass 1.0 []`.
- Focused Quality Criteria regression set -> `3 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `150 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-quality-criteria-evidence-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `180 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_QUALITY_CRITERIA_EVIDENCE_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Red Flag Source Context High Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_RED_FLAG_SOURCE_CONTEXT_HIGH_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated Reviewer Red Flags scoring and found that `reviewer_red_flags_actionability` accepted vague source-context red flags when the item still had all labels, role markers, and proposal-planning text.
- Expanded generic phrase rejection so `source freshness and eligibility look weak`, `eligibility status conflicts with source context`, and `unsupported claim or missing source line` are rejected.
- Added a regression for vague Reviewer Red Flags source context.
- Updated the shared prompt contract to reject generic red-flag source-context substitutes.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- Focused accepted-packet probe -> `decision pass 1.0 []`, `grounded pass 1.0 []`.
- Focused Reviewer Red Flags regression set -> `3 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `149 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-red-flag-source-context-high-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `179 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_RED_FLAG_SOURCE_CONTEXT_HIGH_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Risk Context High Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_RISK_CONTEXT_HIGH_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated Risks & Open Questions scoring and found that `risks_open_questions_owner_verification` accepted vague risk details when the section still had enough source freshness, eligibility, sponsor, shortlist, or Day 1 markers.
- Expanded generic phrase rejection so `source freshness issues could affect fit scoring`, `sponsor pages and eligibility context may change the shortlist`, `sponsor pages and eligibility context`, and `check source material before the Day 1 memo` are rejected.
- Added regressions for vague risk source-fit scoring and vague risk sponsor/eligibility context.
- Updated the shared prompt contract to reject generic risk-context substitutes.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- Focused accepted-packet probe -> `decision pass 1.0 []`, `grounded pass 1.0 []`.
- Focused Risks & Open Questions regression set -> `4 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `148 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-risk-context-high-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `178 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_RISK_CONTEXT_HIGH_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Assumptions/Boundaries Context High Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ASSUMPTION_BOUNDARY_CONTEXT_HIGH_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated Assumptions & Boundaries scoring and found that `assumptions_boundaries` accepted vague context substitutes when they contained sponsor, prior award, source freshness, eligibility, or first-pass ranking markers.
- Expanded generic phrase rejection so `public sponsor context`, `prior award context`, `source freshness and eligibility context`, `private sponsor context`, `sponsor context`, and `source context` are rejected.
- Added regressions for vague assumption source context and vague assumption boundary context.
- Updated the shared prompt contract to reject generic context substitutes in Assumptions & Boundaries.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- Focused accepted-packet probe -> `decision pass 1.0 []`, `grounded pass 1.0 []`.
- Focused Assumptions & Boundaries regression set -> `4 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `146 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-assumption-boundary-context-high-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `176 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ASSUMPTION_BOUNDARY_CONTEXT_HIGH_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Action Plan Input/Gate High Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_PLAN_INPUT_GATE_HIGH_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated Action Plan scoring and found that `action_plan_handoff_fields` accepted vague Inputs and Decision gate wording when the work items still had dated structure.
- Expanded generic phrase rejection so `source materials`, `eligibility context`, `prior examples`, `go/no-go review when ready`, and `when ready` are rejected in Action Plan handoff fields.
- Added regressions for vague Action Plan input context and vague Action Plan decision-gate context.
- Updated the shared prompt contract to require high-specificity source and decision context in Action Plan Inputs and Decision gate fields.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- Focused accepted-packet probe -> `decision pass 1.0 []`, `grounded pass 1.0 []`.
- Focused Action Plan regression set -> `4 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `144 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-action-plan-input-gate-high-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `174 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_PLAN_INPUT_GATE_HIGH_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Artifact-Ready Handoff High Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ARTIFACT_READY_HANDOFF_HIGH_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated artifact-ready handoff scoring and found that `artifact_ready_handoff_format` accepted vague labeled fields with broad workflow or meeting-note markers.
- Expanded generic phrase rejection for artifact-ready fields so `useful workflow`, `useful context`, `approve the useful next step`, and `when ready` are rejected.
- Added a regression for vague artifact-ready handoff fields.
- Updated the shared prompt contract to reject generic artifact-ready handoff wording.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `142 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-artifact-ready-handoff-high-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `172 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ARTIFACT_READY_HANDOFF_HIGH_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Reusable Handoff Stakeholder High Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REUSABLE_HANDOFF_STAKEHOLDER_HIGH_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated Reusable Handoff scoring and found that `reusable_handoff` accepted vague stakeholder asks when artifact-ready fields remained concrete.
- Expanded generic phrase rejection for copy-ready handoff entries so `approve the useful next step` and `when ready` are rejected.
- Added a regression for vague reusable-handoff stakeholder asks.
- Updated the shared prompt contract to reject generic stakeholder ask wording in Reusable Handoff.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `141 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-reusable-handoff-stakeholder-high-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `171 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REUSABLE_HANDOFF_STAKEHOLDER_HIGH_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Confidence Basis High Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_CONFIDENCE_BASIS_HIGH_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated Confidence Calibration and found that `confidence_calibration` accepted generic `source quality` and `evidence strength` basis wording when raise/lower triggers were concrete.
- Tightened confidence basis so it requires high-specificity evidence context such as source freshness, eligibility evidence, prior-award evidence, private sponsor preferences, copied Markdown, evidence source snippets, strict local scoring, live provider packet, or unsupported claims.
- Added generic phrase rejection for vague confidence-basis wording.
- Added a regression for generic Confidence Calibration basis context.
- Updated the shared prompt contract to reject generic confidence-basis wording.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `140 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-confidence-basis-high-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `170 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_CONFIDENCE_BASIS_HIGH_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Audience High Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_AUDIENCE_HIGH_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated Audience & Use Case scoring and found that `audience_use_case_specificity` accepted vague marker-complete context.
- Tightened Audience, Use case, Decision context, and Destination details so they require high-specificity context such as sponsor shortlist, proposal-planning pursuit memo, weekly go/no-go, draft development, two-page pursuit memo, scorer-ready review packet, launch-review handoff, strict quality report, or live-packet artifact.
- Added generic phrase rejection for vague audience, workflow, decision, and reuse wording.
- Added a regression for vague Audience & Use Case context.
- Updated the shared prompt contract to reject generic Audience & Use Case wording.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `139 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-audience-high-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `169 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_AUDIENCE_HIGH_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Reference Query High Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REFERENCE_QUERY_HIGH_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated References search queries and found that `references_search_queries` and `references_verification_search_plan` accepted vague query wording.
- Tightened verification queries so they require high-specificity topic or source-intent terms such as translational oncology, clinical trial recruitment, digital health trial recruitment, sponsor eligibility, prior award, RFP, NASA acceptance criteria, UNDP risk recording, strict scorer, or live-provider packet.
- Added generic phrase rejection for vague query source and evidence wording.
- Added a regression for vague verification search queries.
- Updated the shared prompt contract to reject generic verification query wording.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `138 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-reference-query-high-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `168 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REFERENCE_QUERY_HIGH_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Decision Field High Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_DECISION_FIELD_HIGH_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated Recommendation / Decision scoring and found that `decision_recommendation_fields` accepted vague `useful workflow` and `available source materials` wording.
- Tightened Recommendation and Rationale fields so they require high-specificity decision context such as ranked-pilot workflow, scorer-ready packet workflow, retrieved eligibility, prior-award evidence, sponsor shortlist, copied review-packet workflow, source evidence quality scoring, or live-provider reuse.
- Added generic phrase rejection for vague decision source and workflow wording.
- Added a regression for vague Decision source context.
- Updated the shared prompt contract to reject generic Recommendation and Rationale wording.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `137 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-decision-field-high-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `167 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_DECISION_FIELD_HIGH_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Key Findings High Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_KEY_FINDINGS_HIGH_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated Key Findings scoring and found that `key_finding_fields` accepted a vague first finding when the rest of the section remained strong.
- Tightened Claim, Evidence, Uncertainty, and Action meaning fields so they require high-specificity source, workflow, constraint, owner, deadline, eligibility, prior-award, packet, scoring, provider, risk-treatment, or proposal-planning context.
- Added generic phrase rejection for vague source and workflow wording.
- Added a regression for vague Key Finding source context.
- Updated the shared prompt contract to reject generic Key Finding source and workflow wording.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `136 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-key-findings-high-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `166 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_KEY_FINDINGS_HIGH_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Executive Summary High Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EXECUTIVE_SUMMARY_HIGH_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated Executive Summary scoring and found that `executive_summary_decision_snapshot` accepted vague `source materials`, `background evidence`, `source details`, and `useful memo` prose.
- Tightened summary snapshots so they require high-specificity source or artifact details such as sponsor eligibility pages, prior-award abstracts, source URLs, copied review packet, evidence snippets, strict quality report, or release meeting handoff.
- Added generic phrase rejection for vague summary source and artifact wording.
- Added a regression for vague Executive Summary source context.
- Updated the shared prompt contract to reject generic summary source and artifact wording.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `135 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-executive-summary-high-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `165 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EXECUTIVE_SUMMARY_HIGH_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Deep Dive High Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_DEEP_DIVE_HIGH_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated Deep Dive dimensions and found that `deep_dive_dimension_specificity` accepted vague `should be considered/reviewed` operating prose.
- Tightened dimensions so they require high-specificity source, retrieval, eligibility, clinical, regulatory, owner, timing, budget, packet, risk, proposal, or pursuit-priority detail.
- Added generic phrase rejection for non-actionable dimension wording.
- Added a regression for vague Deep Dive dimension context.
- Updated the shared prompt contract to reject generic Deep Dive wording.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `134 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-deep-dive-high-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `164 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_DEEP_DIVE_HIGH_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Quality Criteria High Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_QUALITY_CRITERIA_HIGH_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated Quality Criteria and found that `quality_criteria_actionable_acceptance` accepted vague acceptance context.
- Tightened Ready, reject/hold, evidence, verifier, and reuse-destination lines so they require high-specificity evidence, uncertainty, action, eligibility, retrieval, prior-award, strict report, provider, blocker, packet, launch, memo, or proposal context.
- Added generic phrase rejection for vague acceptance wording.
- Added a regression for vague Quality Criteria acceptance context.
- Updated the shared prompt contract to reject generic Quality Criteria wording.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `133 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-quality-criteria-high-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `163 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_QUALITY_CRITERIA_HIGH_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Reference Source Lead Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REFERENCE_SOURCE_LEAD_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated References and found that `references_search_queries` accepted vague `Source lead:` wording when parenthetical metadata was concrete.
- Tightened source lead identity so `Source lead:` details must name concrete source families such as sponsor program pages, prior award lists, eligibility PDFs, NIH opportunity pages, NIH RePORTER, NASA acceptance criteria, or UNDP risk guidance.
- Added a regression for vague reference source lead identity.
- Updated the shared prompt contract to reject vague source lead wording.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `132 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-reference-source-lead-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `162 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REFERENCE_SOURCE_LEAD_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Evidence Map High Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EVIDENCE_MAP_HIGH_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated Evidence Map details and found that `evidence_map` accepted vague source/evidence context.
- Tightened Strong, Weak, Missing, and Follow-up verification details so they require high-specificity sponsor, eligibility, deliverable, funding, prior-award, reviewer, institutional, scoring, packet, provider, or credential context.
- Added generic phrase rejection for vague Evidence Map source context.
- Added a regression for vague Evidence Map source context.
- Updated the shared prompt contract to reject generic Evidence Map wording.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `131 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-evidence-map-high-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `161 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EVIDENCE_MAP_HIGH_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Decision Change Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_DECISION_CHANGE_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated decision change conditions and found that `decision_change_condition_verifiable` accepted generic `source evidence changes` wording.
- Tightened change conditions so they require concrete triggers such as source freshness, eligibility, stale source, applicant eligibility, deadline, deliverable, compliance, provider credential, copied source packet parsing, browser smoke, or launch review.
- Added a regression for generic decision change conditions.
- Updated the shared prompt contract to reject generic `source evidence changes` wording.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `130 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-decision-change-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `160 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_DECISION_CHANGE_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Safety Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_SAFETY_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated safety sections and found that `assumptions_boundaries` accepted generic source/sponsor context.
- Re-evaluated risks and found that `risks_open_questions` accepted generic source-change risk prose when labels were present.
- Tightened Assumptions & Boundaries so each field needs high-specificity sponsor page, prior award, eligibility, source freshness, private sponsor, credential, PI approval, compliance, live-provider, or production-reuse context.
- Tightened Risks & Open Questions so risk/question, verification, and follow-up fields reject generic source-change boilerplate.
- Added regressions for generic source/sponsor assumptions and generic source-change risks/open questions.
- Updated the shared prompt contract to reject generic safety-section wording.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `129 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-safety-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `159 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_SAFETY_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Red Flag Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_RED_FLAG_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated reviewer red flags and found that `reviewer_red_flags_actionability` accepted generic source/claim-only red-flag prose.
- Tightened red-flag details so they require high-specificity blockers such as eligibility, deadline, deliverable, source freshness, unverifiable quotes, uncited source lines, live-provider launch blockers, risk treatment, time plan, status, or proposal-planning resolution.
- Added generic phrase rejection for weak source/claim wording.
- Added a regression for generic source/claim reviewer red flags.
- Updated the shared prompt contract to reject generic red-flag actionability.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `127 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-red-flag-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `157 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_RED_FLAG_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Action Success and Alternative Comparison Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_SUCCESS_ALT_COMPARISON_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated Action Plan metrics and found that `action_plan_measurable_success_criteria` accepted generic metrics like `all tasks pass the score` and `one item has complete status`.
- Re-evaluated Deep Dive comparisons and found that `competitive_alternative_comparison` accepted generic marker-stuffed comparison prose.
- Tightened success metrics so each metric must include concrete source, retrieval, eligibility, draft, review, packet, failure, risk, blocker, sponsor, or artifact context.
- Tightened alternative comparisons so comparison clauses require a concrete baseline and at least two concrete tradeoff details.
- Added regressions for generic Action Plan success metrics and generic alternative-comparison marker stuffing.
- Updated the shared prompt contract to reject generic success metric and alternative-comparison wording.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `126 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-action-success-alt-comparison-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `156 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_SUCCESS_ALT_COMPARISON_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Reuse Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REUSE_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated reuse claims and found that `reusable_handoff` accepted generic copy-ready prose when labels and length were present.
- Re-evaluated competitive value and found that `competitive_reuse_value` accepted marker-stuffed prose without a concrete baseline, audience, and reusable artifact.
- Tightened both checks so reuse claims must name concrete source, sponsor, eligibility, packet, review, owner, artifact, scoring, audience, or baseline context.
- Added regressions for generic copy-ready handoff detail and generic competitive reuse marker stuffing.
- Updated the shared prompt contract to reject generic reuse and competitive-value wording.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `124 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-reuse-specificity-browser-smoke-2026-06-07.json`.
- Combined regression -> `154 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REUSE_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Confidence Calibration Bidirectional)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_CONFIDENCE_CALIBRATION_BIDIRECTIONAL_2026-06-07.md`

### Changes
- Re-evaluated confidence calibration and found that `confidence_calibration` accepted broad confidence-change markers without requiring both raise and lower conditions.
- Tightened the check so the `Confidence calibration:` clause must include confidence level, evidence basis, uncertainty, and both raise-confidence and lower-confidence conditions.
- Added a regression where the calibration says confidence would change but does not name both directions.
- Updated the shared prompt contract to require both raise and lower confidence conditions.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `85 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `115 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-confidence-calibration-bidirectional-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_CONFIDENCE_CALIBRATION_BIDIRECTIONAL_2026-06-07.md`.

## 2026-06-07 (AI Lab Competitive Reuse Value Clause)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_COMPETITIVE_REUSE_VALUE_CLAUSE_2026-06-07.md`

### Changes
- Re-evaluated competitive reuse value and found that `competitive_reuse_value` accepted broad markers scattered across Deep Dive.
- Tightened the check so a `Competitive reuse value:` clause must include baseline, differentiator, reuse-value, and user-value signals.
- Added a regression where the reuse-value clause keeps broad reuse and alternative wording but omits concrete differentiator/artifact value.
- Updated the browser fixture to name platform operators and launch reviewers as beneficiary roles.
- Updated the shared prompt contract to request reusable artifact, beneficiary, and advantage over the baseline.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `84 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `114 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-competitive-reuse-value-clause-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_COMPETITIVE_REUSE_VALUE_CLAUSE_2026-06-07.md`.

## 2026-06-07 (AI Lab Competitive Comparison Tradeoff)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_COMPETITIVE_COMPARISON_TRADEOFF_2026-06-07.md`

### Changes
- Re-evaluated competitive positioning and found that `competitive_alternative_comparison` accepted broad comparison/product markers without requiring a real tradeoff.
- Tightened the check so `Alternative comparison:` or `Competitive comparison:` must include baseline alternative, tradeoff, and differentiator detail.
- Added a regression where alternative/product keywords remain but tradeoff and differentiator detail are missing.
- Updated the shared prompt contract to request baseline alternative, concrete tradeoff, and differentiator.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `83 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `113 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-competitive-comparison-tradeoff-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_COMPETITIVE_COMPARISON_TRADEOFF_2026-06-07.md`.

## 2026-06-07 (AI Lab Assumptions Labeled Fields)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ASSUMPTIONS_LABELED_FIELDS_2026-06-07.md`

### Changes
- Re-evaluated Assumptions & Boundaries readiness and found that `assumptions_boundaries` checked labels at the section level without verifying useful field detail.
- Tightened the check so `Assumption:`, `Boundary:`, `Constraint:`, and `Validation:` labels must each include useful detail.
- Added a regression where the `Validation:` label is present but empty.
- Updated the shared prompt contract to request labeled, nonblank Assumptions & Boundaries fields.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `82 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `112 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-assumptions-labeled-fields-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ASSUMPTIONS_LABELED_FIELDS_2026-06-07.md`.

## 2026-06-07 (AI Lab References Distinct Query Plan)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REFERENCES_DISTINCT_QUERY_PLAN_2026-06-07.md`

### Changes
- Re-evaluated References readiness and found that `references_verification_search_plan` counted useful query lines without checking uniqueness.
- Tightened the check so the References section must include at least three useful and distinct normalized verification queries.
- Added a regression where the same useful query is repeated three times.
- Updated the shared prompt contract to require distinct verification search queries.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `81 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `111 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-references-distinct-query-plan-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REFERENCES_DISTINCT_QUERY_PLAN_2026-06-07.md`.

## 2026-06-07 (AI Lab Handoff Nonempty Fields)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_HANDOFF_NONEMPTY_FIELDS_2026-06-07.md`

### Changes
- Re-evaluated reusable handoff readiness and found that `artifact_ready_handoff_format` counted labels without checking field detail.
- Tightened the check so Decision log, Stakeholder ask, Owner next step, and Evidence attachment labels must include useful copy-ready content.
- Added a regression where the `Evidence attachment:` row is present but empty.
- Updated the shared prompt contract to state that artifact-ready handoff labels must not be blank.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `80 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `110 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-handoff-nonempty-fields-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_HANDOFF_NONEMPTY_FIELDS_2026-06-07.md`.

## 2026-06-07 (AI Lab Quality Criteria Labeled Lines)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_QUALITY_CRITERIA_LABELED_LINES_2026-06-07.md`

### Changes
- Re-evaluated Quality Criteria readiness and found that `quality_criteria_actionable_acceptance` could pass a single paragraph containing the right marker phrases.
- Tightened the check so ready, reject/hold, evidence-required, verifier/owner, and reuse-destination criteria must also appear as labeled lines.
- Added a regression where all marker words remain present but the labeled criteria rows are missing.
- Updated the shared prompt contract to request labeled `Ready to use:`, `Do not use:`, `Evidence required:`, `Verifier/owner:`, and `Reuse destination:` lines.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `79 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `109 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-quality-criteria-labeled-lines-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_QUALITY_CRITERIA_LABELED_LINES_2026-06-07.md`.

## 2026-06-07 (AI Lab Reviewer Red Flags Each Item Actionability)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REVIEWER_RED_FLAGS_EACH_ITEM_ACTIONABILITY_2026-06-07.md`

### Changes
- Re-evaluated Reviewer Red Flags readiness and found that `reviewer_red_flags_actionability` checked owner and timing at the section level.
- Added a Reviewer Red Flags item parser and tightened the check so every `Red flag:` item must include stop/reject language, evidence-blocker language, resolution owner, and resolution timing.
- Added a regression where one red-flag item omits its own escalation owner and timing while the section-level red-flags check still passes.
- Updated the shared prompt contract to request per-item `Red flag`, `Stop condition`, `Evidence blocker`, and `Escalation` fields.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `78 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `108 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-reviewer-red-flags-each-item-actionability-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REVIEWER_RED_FLAGS_EACH_ITEM_ACTIONABILITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Risks Each Item Verification)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_RISKS_EACH_ITEM_VERIFICATION_2026-06-07.md`

### Changes
- Re-evaluated Risks & Open Questions readiness and found that `risks_open_questions_owner_verification` checked owner, verification, status/review timing, and follow-up at the section level.
- Added a Risks & Open Questions item parser and tightened the check so every Risk or Open question item must include owner, verification, status/review timing, and follow-up/mitigation context.
- Added a regression where one risk item changes `Verification:` to a weaker `Context:` label.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `77 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `107 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-risks-each-item-verification-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_RISKS_EACH_ITEM_VERIFICATION_2026-06-07.md`.

## 2026-06-07 (AI Lab Evidence Map Each Item Confidence Followup)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EVIDENCE_MAP_EACH_ITEM_CONFIDENCE_FOLLOWUP_2026-06-07.md`

### Changes
- Re-evaluated Evidence Map readiness and found that `evidence_map_confidence_followup` checked confidence and follow-up signals at the section level.
- Added an Evidence Map item parser and tightened the check so every Strong, Weak, or Missing item must include confidence and follow-up verification context.
- Removed `owner` as a standalone follow-up marker to avoid passing without explicit verification/check/follow-up language.
- Added a regression where one Evidence Map item changes `Follow-up verification:` to a neutral `Next note:`.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `76 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `106 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-evidence-map-each-item-confidence-followup-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EVIDENCE_MAP_EACH_ITEM_CONFIDENCE_FOLLOWUP_2026-06-07.md`.

## 2026-06-07 (AI Lab Key Findings Each Item Fields)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_KEY_FINDINGS_EACH_ITEM_FIELDS_2026-06-07.md`

### Changes
- Re-evaluated Key Findings readiness and found that `key_finding_fields` checked Claim, Evidence, Uncertainty, and Action meaning at the whole-output level.
- Tightened the check to parse Key Finding items and require every detected item to include all four labels.
- Added a regression where one Key Finding changes `Uncertainty:` to a weaker `Caveat:` label.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `75 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `105 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-key-findings-each-item-fields-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_KEY_FINDINGS_EACH_ITEM_FIELDS_2026-06-07.md`.

## 2026-06-07 (AI Lab Action Plan Each Item Timeline Success)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_PLAN_EACH_ITEM_TIMELINE_SUCCESS_2026-06-07.md`

### Changes
- Re-evaluated Action Plan timing and success readiness and found that `action_plan_timeline_success_metric` checked those signals at the section level.
- Tightened the check to parse Action Plan work items and require every detected item to include timing or priority plus a success metric, done condition, acceptance, or completion marker.
- Added a regression where the second Action Plan item keeps output detail but changes `Success metric:` to a neutral progress note.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `74 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `104 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-action-plan-each-item-timeline-success-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_PLAN_EACH_ITEM_TIMELINE_SUCCESS_2026-06-07.md`.

## 2026-06-07 (AI Lab Action Plan Each Item Dependency)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `var/desci-ai-lab-review-packet-sample-2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_PLAN_EACH_ITEM_DEPENDENCY_2026-06-07.md`

### Changes
- Re-evaluated Action Plan dependency readiness and found that `action_plan_dependency_order` checked dependency and blocker signals at the section level.
- Tightened the check to parse Action Plan work items and require every detected item to include sequence, dependency, and blocked-by context.
- Added a regression where the second Action Plan item omits its `Dependencies/blocked by` line while the rest of the plan remains strong.
- Updated the static sample review packet so the Day 6-7 compliance item has its own dependency and blocker condition.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `73 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `103 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-action-plan-each-item-dependency-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_PLAN_EACH_ITEM_DEPENDENCY_2026-06-07.md`.

## 2026-06-07 (AI Lab Action Plan Each Item Handoff)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_PLAN_EACH_ITEM_HANDOFF_2026-06-07.md`

### Changes
- Re-evaluated Action Plan execution readiness and found that `action_plan_handoff_fields` checked Owner, Inputs, Artifact, and Decision gate at the section level.
- Tightened the check to parse Action Plan work items and require every detected item to include `Owner:`, `Inputs:`, `Artifact:`, and `Decision gate:`.
- Added a regression where the second Action Plan item omits `Artifact:` while the rest of the plan remains strong.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `72 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `102 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-action-plan-each-item-handoff-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_PLAN_EACH_ITEM_HANDOFF_2026-06-07.md`.

## 2026-06-07 (AI Lab Action Plan All Metrics)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `var/desci-ai-lab-review-packet-sample-2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_PLAN_ALL_METRICS_2026-06-07.md`

### Changes
- Re-evaluated Action Plan readiness and found that `action_plan_measurable_success_criteria` could pass with `metrics=3 measurable=2`.
- Tightened the existing check so every declared `Success metric` or `Done condition` must be measurable.
- Added a regression where only one Action Plan item has a vague success metric and the output is rejected.
- Updated the static sample review packet so the Day 6-7 compliance item has a complete, measurable success condition.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `71 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `101 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-action-plan-all-metrics-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_PLAN_ALL_METRICS_2026-06-07.md`.

## 2026-06-07 (AI Lab Safety Sections Quoted Evidence)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `var/desci-ai-lab-review-packet-sample-2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_SAFETY_SECTIONS_QUOTED_EVIDENCE_2026-06-07.md`

### Changes
- Re-evaluated strict quoted-evidence mode and found that Assumptions & Boundaries, Reviewer Red Flags, and Risks & Open Questions could cite source IDs without source-matching quotes.
- Added `assumptions_boundaries_quoted_evidence_matches_sources`, `reviewer_red_flags_quoted_evidence_matches_sources`, and `risks_open_questions_quoted_evidence_matches_sources`.
- Added regressions where every other strict quote check still passes but one safety-section quote support line is removed.
- Updated the strict scorer fixture, browser fixture, static sample review packet, and BioLinker prompt guidance.
- Kept each new quoted phrase on a citation-scoped line so the global quote matcher evaluates it only against the matching source.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `70 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `100 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=74 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-safety-sections-quoted-evidence-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_SAFETY_SECTIONS_QUOTED_EVIDENCE_2026-06-07.md`.

## 2026-06-07 (AI Lab Deep Dive Quoted Evidence)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `var/desci-ai-lab-review-packet-sample-2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_DEEP_DIVE_QUOTED_EVIDENCE_2026-06-07.md`

### Changes
- Re-evaluated strict quoted-evidence mode and found that Deep Dive could cite source IDs without a source-matching quote.
- Added `deep_dive_quoted_evidence_matches_sources` to require quoted evidence in technical, operational, comparison, or reuse-value details when `--require-quoted-evidence` is enabled.
- Added a regression where Summary, Key Findings, Decision, Evidence Map, Action Plan, Reusable Handoff, and Quality Criteria quote checks still pass but Deep Dive quote support is removed.
- Updated the strict scorer fixture, browser fixture, static sample review packet, and BioLinker prompt guidance.
- Split the static sample Deep Dive into separate citation-scoped lines so an S1 quote is not evaluated against a later S2 citation on the same line.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `67 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `97 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=71 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-deep-dive-quoted-evidence-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_DEEP_DIVE_QUOTED_EVIDENCE_2026-06-07.md`.

## 2026-06-07 (AI Lab Quality Criteria Quoted Evidence)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `var/desci-ai-lab-review-packet-sample-2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_QUALITY_CRITERIA_QUOTED_EVIDENCE_2026-06-07.md`

### Changes
- Re-evaluated strict quoted-evidence mode and found that Quality Criteria could cite source IDs without a source-matching quote.
- Added `quality_criteria_quoted_evidence_matches_sources` to require quoted evidence in ready/reject/evidence/verifier criteria when `--require-quoted-evidence` is enabled.
- Added a regression where Summary, Key Findings, Decision, Evidence Map, Action Plan, and Reusable Handoff quote checks still pass but Quality Criteria quote support is removed.
- Updated the strict scorer fixture, browser fixture, static sample review packet, and BioLinker prompt guidance.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `66 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `96 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=70 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-quality-criteria-quoted-evidence-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_QUALITY_CRITERIA_QUOTED_EVIDENCE_2026-06-07.md`.

## 2026-06-07 (AI Lab Reusable Handoff Quoted Evidence)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `var/desci-ai-lab-review-packet-sample-2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REUSABLE_HANDOFF_QUOTED_EVIDENCE_2026-06-07.md`

### Changes
- Re-evaluated strict quoted-evidence mode and found that Reusable Handoff could cite source IDs without a source-matching quote.
- Added `reusable_handoff_quoted_evidence_matches_sources` to require quoted evidence in pasted handoff text when `--require-quoted-evidence` is enabled.
- Added a regression where Summary, Key Findings, Decision, Evidence Map, and Action Plan quote checks still pass but Reusable Handoff quote support is removed.
- Updated the strict scorer fixture, browser fixture, static sample review packet, and BioLinker prompt guidance.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `65 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `95 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=69 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-reusable-handoff-quoted-evidence-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REUSABLE_HANDOFF_QUOTED_EVIDENCE_2026-06-07.md`.

## 2026-06-07 (AI Lab Action Plan Quoted Evidence)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `var/desci-ai-lab-review-packet-sample-2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_PLAN_QUOTED_EVIDENCE_2026-06-07.md`

### Changes
- Re-evaluated strict quoted-evidence mode and found that Action Plan inputs, gates, and blockers could cite source IDs without a source-matching quote.
- Added `action_plan_quoted_evidence_matches_sources` to require quoted evidence in the Action Plan when `--require-quoted-evidence` is enabled.
- Added a regression where Summary, Key Findings, Decision, and Evidence Map quote checks still pass but Action Plan quote support is removed.
- Updated the strict scorer fixture, browser fixture, static sample review packet, and BioLinker prompt guidance.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `64 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `94 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=68 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-action-plan-quoted-evidence-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_PLAN_QUOTED_EVIDENCE_2026-06-07.md`.

## 2026-06-07 (AI Lab Executive Summary Quoted Evidence)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `var/desci-ai-lab-review-packet-sample-2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EXECUTIVE_SUMMARY_QUOTED_EVIDENCE_2026-06-07.md`

### Changes
- Re-evaluated strict quoted-evidence mode and found that the Executive Summary could cite source IDs without including a quoted phrase copied from a cited source.
- Added `executive_summary_quoted_evidence_matches_sources` to require source-matching quoted evidence in the first summary block when `--require-quoted-evidence` is enabled.
- Added a regression where later quote checks still pass but the Executive Summary quote is removed.
- Updated the strict scorer fixture, browser fixture, static sample review packet, and BioLinker prompt guidance.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `63 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `93 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=67 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-executive-summary-quoted-evidence-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EXECUTIVE_SUMMARY_QUOTED_EVIDENCE_2026-06-07.md`.

## 2026-06-07 (AI Lab Audience Use Case Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_AUDIENCE_USE_CASE_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated Audience & Use Case and found that generic audience, use-case, decision-context, and destination wording could pass the structural section check.
- Added `audience_use_case_specificity` to require named roles, a concrete workflow, decision moment, destination artifact, and reuse action.
- Added a regression where `audience_use_case` still passes but generic placeholder wording fails the new specificity gate.
- Updated BioLinker prompt guidance to avoid generic audiences and require a role-specific reuse workflow.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `62 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `92 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=66 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-audience-use-case-specificity-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_AUDIENCE_USE_CASE_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Executive Summary Citations)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EXECUTIVE_SUMMARY_CITATIONS_2026-06-07.md`

### Changes
- Re-evaluated the first-read Executive Summary and found that recommendation, evidence basis, uncertainty, and next action text could omit source citations even when later sections cited the evidence bundle.
- Added `executive_summary_cite_sources` to require the Executive Summary to cite provided evidence sources.
- Added a regression where later source citations remain valid but Executive Summary citations are removed.
- Updated BioLinker prompt guidance and the browser fixture's first summary evidence line.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `61 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `91 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=65 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-executive-summary-citations-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EXECUTIVE_SUMMARY_CITATIONS_2026-06-07.md`.

## 2026-06-07 (AI Lab Deep Dive Citations)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_DEEP_DIVE_CITATIONS_2026-06-07.md`

### Changes
- Re-evaluated Deep Dive and found that detailed technical, operational, comparison, and reuse-value claims could omit source citations even when evidence sources were provided.
- Added `deep_dive_cite_sources` to require Deep Dive to cite provided evidence sources.
- Added a regression where other source citations remain valid but Deep Dive citations are removed.
- Updated grounded scorer fixtures, browser fixture Deep Dive, sample packet, and BioLinker prompt guidance.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `60 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `90 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=64 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-deep-dive-citations-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_DEEP_DIVE_CITATIONS_2026-06-07.md`.

## 2026-06-07 (AI Lab Quality Criteria Citations)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_QUALITY_CRITERIA_CITATIONS_2026-06-07.md`

### Changes
- Re-evaluated Quality Criteria and found that ready-to-use, reject/hold, evidence-required, verifier, and reuse-destination conditions could omit source citations even when evidence sources were provided.
- Added `quality_criteria_cite_sources` to require Quality Criteria to cite provided evidence sources.
- Added a regression where other source citations remain valid but quality-criteria citations are removed.
- Updated grounded scorer fixtures, browser fixture Quality Criteria, sample packet, and BioLinker prompt guidance.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `59 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `89 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=63 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-quality-criteria-citations-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_QUALITY_CRITERIA_CITATIONS_2026-06-07.md`.

## 2026-06-07 (AI Lab Reusable Handoff Citations)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REUSABLE_HANDOFF_CITATIONS_2026-06-07.md`

### Changes
- Re-evaluated Reusable Handoff and found that copy-ready decision logs, asks, and evidence attachments could omit source citations even when evidence sources were provided.
- Added `reusable_handoff_cite_sources` to require Reusable Handoff to cite provided evidence sources.
- Added a regression where other source citations remain valid but reusable-handoff citations are removed.
- Updated grounded scorer fixtures, browser fixture Reusable Handoff, sample packet, and BioLinker prompt guidance.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `58 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `88 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=62 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-reusable-handoff-citations-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REUSABLE_HANDOFF_CITATIONS_2026-06-07.md`.

## 2026-06-07 (AI Lab Assumptions Boundaries Citations)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ASSUMPTIONS_BOUNDARIES_CITATIONS_2026-06-07.md`

### Changes
- Re-evaluated Assumptions & Boundaries and found that evidence assumptions, constraints, and validation steps could omit source citations even when evidence sources were provided.
- Added `assumptions_boundaries_cite_sources` to require Assumptions & Boundaries to cite provided evidence sources.
- Added a regression where other source citations remain valid but assumptions/boundaries citations are removed.
- Updated grounded scorer fixtures, browser fixture Assumptions & Boundaries, sample packet, and BioLinker prompt guidance.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `57 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `87 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=61 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-assumptions-boundaries-citations-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ASSUMPTIONS_BOUNDARIES_CITATIONS_2026-06-07.md`.

## 2026-06-07 (AI Lab Action Plan Citations)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_PLAN_CITATIONS_2026-06-07.md`

### Changes
- Re-evaluated the Action Plan and found that evidence-dependent inputs, gates, and blockers could omit source citations even when evidence sources were provided.
- Added `action_plan_cite_sources` to require the Action Plan to cite provided evidence sources.
- Added a regression where other source citations remain valid but Action Plan citations are removed.
- Updated grounded scorer fixtures, browser fixture Action Plan, sample packet, and BioLinker prompt guidance.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `56 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `86 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=60 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-action-plan-citations-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_PLAN_CITATIONS_2026-06-07.md`.

## 2026-06-07 (AI Lab Risks Open Questions Citations)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_RISKS_OPEN_QUESTIONS_CITATIONS_2026-06-07.md`

### Changes
- Re-evaluated Risks & Open Questions and found that operational risks and validation criteria could omit source citations even when evidence sources were provided.
- Added `risks_open_questions_cite_sources` to require Risks & Open Questions to cite provided evidence sources.
- Added a regression where other source citations remain valid but risk-section citations are removed.
- Updated grounded scorer fixtures, browser fixture risks, sample packet, and BioLinker prompt guidance.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `55 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `85 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=59 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-risks-open-questions-citations-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_RISKS_OPEN_QUESTIONS_CITATIONS_2026-06-07.md`.

## 2026-06-07 (AI Lab Reviewer Red Flags Citations)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REVIEWER_RED_FLAGS_CITATIONS_2026-06-07.md`

### Changes
- Re-evaluated Reviewer Red Flags and found that stop/hold criteria could omit source citations even when evidence sources were provided.
- Added `reviewer_red_flags_cite_sources` to require Reviewer Red Flags to cite provided evidence sources.
- Added a regression where Recommendation citations remain valid but Reviewer Red Flags lose their own citations.
- Updated grounded scorer fixtures, browser fixture red flags, sample packet, and BioLinker prompt guidance.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `54 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `84 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=58 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-reviewer-red-flags-citations-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REVIEWER_RED_FLAGS_CITATIONS_2026-06-07.md`.

## 2026-06-07 (AI Lab Evidence Map Quoted Evidence)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EVIDENCE_MAP_QUOTED_EVIDENCE_2026-06-07.md`

### Changes
- Re-evaluated strict quoted-evidence mode and found that Strong/Weak Evidence Map rows could cite sources without their own direct quote.
- Added `evidence_map_quoted_evidence_matches_sources` to require every Strong/Weak Evidence Map item to include a source-matching quoted evidence phrase when strict quote mode is enabled.
- Added a regression where global quote matching, decision quotes, and Key Finding quotes pass, but one Evidence Map row loses its own quote.
- Updated browser fixture Evidence Map rows and BioLinker prompt guidance.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `53 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `83 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=57 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-evidence-map-quoted-evidence-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EVIDENCE_MAP_QUOTED_EVIDENCE_2026-06-07.md`.

## 2026-06-07 (AI Lab Decision Quoted Evidence)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_DECISION_QUOTED_EVIDENCE_2026-06-07.md`

### Changes
- Re-evaluated strict quoted-evidence mode and found that Recommendation / Decision could cite sources without a direct quoted phrase.
- Added `decision_recommendation_quoted_evidence_matches_sources` to require a source-matching quote in the decision section when strict quote mode is enabled.
- Added a regression where global quote matching and Key Findings quote support pass, but the decision section loses its own quote.
- Updated strict scorer fixtures, browser fixture, sample packet, and BioLinker prompt guidance.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `52 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `82 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=56 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-decision-quoted-evidence-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_DECISION_QUOTED_EVIDENCE_2026-06-07.md`.

## 2026-06-07 (AI Lab Key Findings Quoted Evidence)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_KEY_FINDINGS_QUOTED_EVIDENCE_2026-06-07.md`

### Changes
- Re-evaluated strict quoted-evidence mode and found that Key Findings could still rely on term overlap while quotes appeared elsewhere in the packet.
- Added `key_findings_quoted_evidence_matches_sources` to require every Key Finding item to include a source-matching quoted evidence phrase when strict quote mode is enabled.
- Added a regression where overall quoted evidence still passes but one Key Finding loses its own quote.
- Updated strict scorer fixtures, sample packet Key Findings, and BioLinker prompt guidance.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `51 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `81 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=55 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-key-findings-quoted-evidence-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_KEY_FINDINGS_QUOTED_EVIDENCE_2026-06-07.md`.

## 2026-06-07 (AI Lab References Source Type Context)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REFERENCES_SOURCE_TYPE_CONTEXT_2026-06-07.md`

### Changes
- Re-evaluated visible References and found that copied JSON source records could include `source_type` while the reviewer-facing reference line omitted it.
- Added `references_include_evidence_source_types` to require source ID, exact URL, and source type/category in the matching References line.
- Added a regression where JSON source type remains present but the visible reference drops it.
- Updated scorer fixtures, browser fixture References, sample packet References, and BioLinker prompt guidance.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `50 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `80 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=54 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-references-source-type-context-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REFERENCES_SOURCE_TYPE_CONTEXT_2026-06-07.md`.

## 2026-06-07 (AI Lab Evidence Source Type Metadata)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EVIDENCE_SOURCE_TYPE_METADATA_2026-06-07.md`

### Changes
- Re-evaluated copied source records and found that they preserved IDs, URLs, freshness, and reference mirroring but not the evidence category.
- Preserved `source_type`, `source_category`, `category`, `kind`, `evidence_type`, or `type` during normalization.
- Added `evidence_sources_type_metadata` to reject empty or generic source type/category metadata.
- Updated scorer fixtures, browser fixture source records, sample packet JSON, and BioLinker prompt guidance.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `49 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `79 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=53 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-evidence-source-type-metadata-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EVIDENCE_SOURCE_TYPE_METADATA_2026-06-07.md`.

## 2026-06-07 (AI Lab References Mirror Evidence Sources)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REFERENCES_MIRROR_EVIDENCE_SOURCES_2026-06-07.md`

### Changes
- Re-evaluated copied source traceability and found that Evidence Sources JSON could remain complete while visible References omitted one provided source.
- Added `references_mirror_evidence_sources` to require every evidence source ID and exact URL to appear in References.
- Added a regression where `S2` remains cited and present in the source bundle but is missing from References.
- Strengthened BioLinker prompt guidance to mirror every evidence source ID in References with its URL and freshness note.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `48 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `78 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=52 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-references-mirror-evidence-sources-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REFERENCES_MIRROR_EVIDENCE_SOURCES_2026-06-07.md`.

## 2026-06-07 (AI Lab Evidence Source Freshness Metadata)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EVIDENCE_SOURCE_FRESHNESS_METADATA_2026-06-07.md`

### Changes
- Re-evaluated copied review-packet reuse and found that Evidence Sources JSON dropped per-source freshness metadata.
- Preserved `freshness`, `source_freshness`, `checked`, `checked_at`, `retrieved`, `retrieved_at`, `accessed`, and `accessed_at` fields during normalization.
- Added `evidence_sources_freshness_metadata` to require freshness metadata for every evidence source record.
- Updated source fixtures, browser fixture, sample packet JSON, and BioLinker prompt guidance.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `47 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `77 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=51 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-evidence-source-freshness-metadata-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EVIDENCE_SOURCE_FRESHNESS_METADATA_2026-06-07.md`.

## 2026-06-07 (AI Lab No Placeholder Sources)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_NO_PLACEHOLDER_SOURCES_2026-06-07.md`

### Changes
- Re-evaluated source usability and found that a passing packet could still contain `example.org` placeholder source URLs.
- Added `references_no_placeholder_sources` for visible References/Search Queries output.
- Added `evidence_sources_non_placeholder` for Evidence Sources JSON metadata.
- Replaced AI Lab fixture source URLs with inspectable NIH, NIH RePORTER, NASA SWE-034, and UNDP URLs.
- Strengthened the BioLinker prompt to prohibit placeholder/test-only source domains.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `46 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `76 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=50 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-no-placeholder-sources-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_NO_PLACEHOLDER_SOURCES_2026-06-07.md`.

## 2026-06-07 (AI Lab Decision Change Condition Verifiable)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_DECISION_CHANGE_CONDITION_VERIFIABLE_2026-06-07.md`

### Changes
- Re-evaluated Recommendation / Decision scoring and found that Change condition wording could pass while remaining subjective.
- Added `decision_change_condition_verifiable` to require source/evidence criteria, a decision effect, and review timing.
- Hardened wrapped-line parsing for change conditions so time-bound continuation text is scored.
- Strengthened the BioLinker prompt with verifiable change-condition guidance.
- Added regression coverage where the old decision-field check passes but the new verifiability gate fails.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `44 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `74 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=48 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-decision-change-condition-verifiable-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_DECISION_CHANGE_CONDITION_VERIFIABLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Reviewer Red Flags Actionability)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REVIEWER_RED_FLAGS_ACTIONABILITY_2026-06-07.md`

### Changes
- Re-evaluated Reviewer Red Flags scoring and found that escalation wording could pass without a responsible owner or review timing.
- Added `reviewer_red_flags_actionability` to require stop/reject conditions, evidence blockers, responsible owner/reviewer, and review or resolution timing.
- Strengthened the BioLinker prompt with red-flag owner/timing guidance.
- Added regression coverage where the old red-flag check passes but the new actionability gate fails.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `43 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `73 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=47 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-reviewer-red-flags-actionability-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REVIEWER_RED_FLAGS_ACTIONABILITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Deep Dive Dimension Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_DEEP_DIVE_DIMENSION_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated Deep Dive scoring and found that dimension labels could pass without concrete operating detail.
- Added `deep_dive_dimension_specificity` to require at least three dimension clauses with concrete workflow, evidence, constraint, owner, metric, or artifact detail.
- Strengthened the BioLinker prompt with per-dimension specificity guidance.
- Added regression coverage for label-only Deep Dive dimensions and browser-smoke rendered-fragment checks for concrete dimension details.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `42 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `72 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=46 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-deep-dive-dimension-specificity-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_DEEP_DIVE_DIMENSION_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Key Findings Item Citations)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_KEY_FINDINGS_ITEM_CITATIONS_2026-06-07.md`

### Changes
- Re-evaluated source-grounded Key Findings scoring and found that global citation checks could hide an uncited individual finding.
- Added `key_findings_items_cite_sources` to require each Key Finding item to cite a valid provided source ID.
- Strengthened the BioLinker prompt with per-finding Evidence-field citation guidance.
- Added regression coverage for an uncited Key Finding and browser-smoke rendered-fragment checks for cited Key Findings rows.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `41 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `71 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=45 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-key-findings-item-citations-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_KEY_FINDINGS_ITEM_CITATIONS_2026-06-07.md`.

## 2026-06-07 (AI Lab Evidence Map Item Citations)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EVIDENCE_MAP_ITEM_CITATIONS_2026-06-07.md`

### Changes
- Re-evaluated source-grounded Evidence Map scoring and found that section-level citations could hide uncited Strong/Weak evidence items.
- Added `evidence_map_items_cite_sources` to require each Strong or Weak Evidence Map item to cite a valid provided source ID.
- Strengthened the BioLinker prompt with item-level Evidence Map citation guidance.
- Added regression coverage for an uncited Weak Evidence Map item and browser-smoke rendered-fragment checks for cited Strong/Weak rows.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `40 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `70 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=44 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-evidence-map-item-citations-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EVIDENCE_MAP_ITEM_CITATIONS_2026-06-07.md`.

## 2026-06-07 (AI Lab Action Plan Measurable Success)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `var/desci-ai-lab-review-packet-sample-2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_PLAN_MEASURABLE_SUCCESS_2026-06-07.md`

### Changes
- Re-evaluated Action Plan success metrics and found that the scorer accepted subjective success labels.
- Added `action_plan_measurable_success_criteria` to require measurable numeric, zero/no-failure, or explicit completion criteria.
- Strengthened the BioLinker prompt with measurable Success metric / Done condition guidance.
- Added regression coverage for action plans with unmeasurable success metrics.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `39 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `69 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=43 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-action-plan-measurable-success-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_PLAN_MEASURABLE_SUCCESS_2026-06-07.md`.

## 2026-06-07 (AI Lab References Search Plan)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `var/desci-ai-lab-review-packet-sample-2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REFERENCES_SEARCH_PLAN_2026-06-07.md`

### Changes
- Re-evaluated `References & Search Queries` and found that the scorer accepted a single shallow query.
- Added `references_verification_search_plan` to require at least three concrete verification search queries.
- Updated scorer fixtures, browser fixtures, the review-packet sample, and the BioLinker prompt with a reusable follow-up search plan.
- Added regression coverage for a present but under-complete References search plan.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `38 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `68 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=42 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-references-search-plan-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REFERENCES_SEARCH_PLAN_2026-06-07.md`.

## 2026-06-07 (AI Lab Risks Owner Verification)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `var/desci-ai-lab-review-packet-sample-2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_RISKS_OWNER_VERIFICATION_2026-06-07.md`

### Changes
- Re-evaluated `Risks & Open Questions` and found that the scorer only required some risk text and some question text.
- Added `risks_open_questions_owner_verification` to require owner, verification, status/review timing, and follow-up or mitigation fields.
- Updated scorer fixtures, browser fixtures, the review-packet sample, and the BioLinker prompt with operational risk/open-question bullets.
- Added regression coverage for a present but generic Risks & Open Questions section.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `37 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `67 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=41 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-risks-owner-verification-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_RISKS_OWNER_VERIFICATION_2026-06-07.md`.

## 2026-06-07 (AI Lab Quality Criteria Acceptance)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `var/desci-ai-lab-review-packet-sample-2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_QUALITY_CRITERIA_ACCEPTANCE_2026-06-07.md`

### Changes
- Re-evaluated Quality Criteria usefulness and found that the scorer only required section presence.
- Added `quality_criteria_actionable_acceptance` to require ready-to-use, reject/hold, evidence-required, verifier/owner, and reuse-destination conditions.
- Updated scorer fixtures, browser fixtures, the review-packet sample, and the BioLinker prompt with actionable acceptance criteria.
- Added regression coverage for a present but generic Quality Criteria section.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `36 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `66 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=40 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-quality-criteria-acceptance-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_QUALITY_CRITERIA_ACCEPTANCE_2026-06-07.md`.

## 2026-06-07 (AI Lab Executive Summary Snapshot)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `var/desci-ai-lab-review-packet-sample-2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EXECUTIVE_SUMMARY_SNAPSHOT_2026-06-07.md`

### Changes
- Re-evaluated first-screen usefulness and found that the scorer only required Executive Summary presence.
- Added `executive_summary_decision_snapshot` to require recommendation/decision, evidence basis, uncertainty/confidence, and next action/artifact in the summary.
- Updated scorer fixtures, browser fixtures, the review-packet sample, and the BioLinker prompt with decision-ready summary snapshots.
- Added regression coverage for a present but generic Executive Summary.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `35 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `29 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `65 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=39 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-executive-summary-snapshot-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EXECUTIVE_SUMMARY_SNAPSHOT_2026-06-07.md`.

## 2026-06-07 (AI Lab Key Findings Count)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `var/desci-ai-lab-review-packet-sample-2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_KEY_FINDINGS_COUNT_2026-06-07.md`

### Changes
- Re-evaluated Key Findings completeness and found that the prompt requested 3-5 findings while the scorer accepted a two-finding packet.
- Added `key_findings_count` to require 3-5 usable Key Findings items.
- Added a third source-backed finding to scorer fixtures, browser fixtures, and the review-packet sample.
- Strengthened the BioLinker research prompt and regression coverage for the former two-finding output.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `34 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `29 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `64 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=38 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-key-findings-count-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_KEY_FINDINGS_COUNT_2026-06-07.md`.

## 2026-06-07 (AI Lab Artifact-Ready Handoff)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `var/desci-ai-lab-review-packet-sample-2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ARTIFACT_READY_HANDOFF_2026-06-07.md`

### Changes
- Re-evaluated handoff usefulness after confidence calibration and found that a brief could be copy-ready in prose while still lacking stable labeled fields for memo or ticket reuse.
- Added `artifact_ready_handoff_format` to require an artifact-ready field block with decision log, stakeholder ask, owner next step, and evidence attachment labels.
- Strengthened the BioLinker research prompt to request labeled artifact-ready handoff fields.
- Updated scorer fixtures, browser fixtures, the review-packet sample, and regression coverage for copy-ready prose without structured artifact fields.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `33 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `29 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `63 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=37 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-artifact-ready-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ARTIFACT_READY_HANDOFF_2026-06-07.md`.

## 2026-06-07 (AI Lab Confidence Calibration)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `var/desci-ai-lab-review-packet-sample-2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_CONFIDENCE_CALIBRATION_2026-06-07.md`

### Changes
- Re-evaluated confidence handling after competitive-reuse scoring and found that a brief could say `Confidence: medium` without saying why confidence is medium or what would change it.
- Added `confidence_calibration` to require a confidence level, evidence basis, uncertainty, and explicit raise/lower confidence condition in Recommendation / Decision.
- Strengthened the BioLinker research prompt to request confidence calibration.
- Updated scorer fixtures, browser fixtures, browser evidence metadata, the review-packet sample, and regression coverage for uncalibrated confidence wording.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `32 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `29 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `62 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=36 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-confidence-calibration-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_CONFIDENCE_CALIBRATION_2026-06-07.md`.

## 2026-06-07 (AI Lab Competitive Reuse Value)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `var/desci-ai-lab-review-packet-sample-2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_COMPETITIVE_REUSE_2026-06-07.md`

### Changes
- Re-evaluated output usefulness after specificity scoring and found that a brief could compare alternatives without saying why the generated packet is reusable and valuable for the actual operator workflow.
- Added `competitive_reuse_value` to require a baseline alternative, differentiator, reusable artifact value, and user benefit inside the Deep Dive.
- Strengthened the BioLinker research prompt to request competitive reuse value versus generic or commercial alternatives.
- Updated scorer fixtures, browser fixtures, the review-packet sample, and regression coverage for comparison language that omits reusable user value.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `31 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `29 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `61 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=35 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-competitive-reuse-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_COMPETITIVE_REUSE_2026-06-07.md`.

## 2026-06-07 (AI Lab Specificity)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `var/desci-ai-lab-review-packet-sample-2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_SPECIFICITY_2026-06-07.md`

### Changes
- Re-evaluated output usefulness after action-plan dependency scoring and found that a structured brief could still read like a generic template if concrete source/material details were stripped.
- Added `specific_output_details` to require concrete source/material, numeric/deadline, named operator/artifact, and context-constraint signals.
- Strengthened the BioLinker research prompt to request source/material details, numbers or deadlines, named roles/artifacts, and context-specific constraints.
- Updated browser fixtures with visible source IDs, source URLs, and source snippets, and added a regression for generic structured output.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `30 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `29 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `60 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=34 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-specificity-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_SPECIFICITY_2026-06-07.md`.

## 2026-06-07 (AI Lab Action Plan Dependencies)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `var/desci-ai-lab-review-packet-sample-2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_PLAN_DEPENDENCIES_2026-06-07.md`

### Changes
- Re-evaluated execution readiness after reviewer red-flags scoring and found that Action Plan items could have owners, timing, and success metrics without dependency order or blocked-by conditions.
- Added `action_plan_dependency_order` to require sequencing, dependency/prerequisite, and blocked-by signals in the Action Plan.
- Strengthened the BioLinker research prompt to request dependencies, blocked-by conditions, prerequisites, and sequencing.
- Updated browser/sample fixtures and added a regression for action plans without dependency-order language.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `29 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `29 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `59 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=33 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-action-plan-dependencies-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_PLAN_DEPENDENCIES_2026-06-07.md`.

## 2026-06-07 (AI Lab Reviewer Red Flags)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `var/desci-ai-lab-review-packet-sample-2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REVIEWER_RED_FLAGS_2026-06-07.md`

### Changes
- Re-evaluated review safety after audience/use-case scoring and found that outputs could be polished but still omit explicit do-not-use or escalation conditions.
- Added `reviewer_red_flags` to require red-flag, stop-condition, evidence-blocker, and escalation signals.
- Strengthened the BioLinker research prompt to request do-not-use, stop, hold, reject, or escalation conditions.
- Updated browser/sample fixtures and added a regression for outputs without reviewer red flags.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `28 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `29 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `58 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=32 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-reviewer-red-flags-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REVIEWER_RED_FLAGS_2026-06-07.md`.

## 2026-06-07 (AI Lab Audience and Use Case)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `var/desci-ai-lab-review-packet-sample-2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_AUDIENCE_USE_CASE_2026-06-07.md`

### Changes
- Re-evaluated product fit after assumptions/boundaries scoring and found that outputs could be rigorous but still fail to name the intended reader, decision workflow, or destination artifact.
- Added `audience_use_case` to require audience, use-case/job-to-be-done, decision-context, and destination/artifact signals.
- Strengthened the BioLinker research prompt to request the intended audience, concrete use case, decision context, and destination artifact.
- Updated browser/sample fixtures and added a regression for outputs without audience and use-case content.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `27 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `29 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `57 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=31 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-audience-use-case-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_AUDIENCE_USE_CASE_2026-06-07.md`.

## 2026-06-07 (AI Lab Assumptions and Boundaries)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `var/desci-ai-lab-review-packet-sample-2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ASSUMPTIONS_BOUNDARIES_2026-06-07.md`

### Changes
- Re-evaluated accuracy and safe reuse after reusable handoff scoring and found that outputs could be pasted into a decision log without stating assumptions, boundaries, constraints, or validation needs.
- Added `assumptions_boundaries` to require assumption, boundary/out-of-scope, constraint/dependency, and validation signals.
- Strengthened the BioLinker research prompt to request assumptions, scope boundaries, constraints, and validation steps before final use.
- Updated browser/sample fixtures and added a regression for outputs without assumptions and boundaries.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `26 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `29 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `56 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=30 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-assumptions-boundaries-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ASSUMPTIONS_BOUNDARIES_2026-06-07.md`.

## 2026-06-07 (AI Lab Reusable Handoff)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `var/desci-ai-lab-review-packet-sample-2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REUSABLE_HANDOFF_2026-06-07.md`

### Changes
- Re-evaluated reuse quality and found that a decision-ready answer could still require rewriting before a reviewer could paste it into a meeting note, decision log, or stakeholder ask.
- Added `reusable_handoff` to require decision-log, stakeholder, copy-ready, and owner/next-step signals.
- Strengthened the BioLinker research prompt to request a copy-ready decision log, stakeholder ask, owner/next step, and paste-ready meeting or memo text.
- Updated browser/sample fixtures and added a regression for outputs without reusable handoff content.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `25 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `29 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `55 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=29 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-reusable-handoff-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REUSABLE_HANDOFF_2026-06-07.md`.

## 2026-06-07 (AI Lab Per-Source Freshness)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_PER_SOURCE_FRESHNESS_2026-06-07.md`

### Changes
- Re-evaluated the source freshness check and found that section-level freshness could pass while an individual source reference line remained stale or unchecked.
- Added `references_each_source_freshness` to require freshness context on each source-bearing reference line.
- Excluded search-query lines from per-source freshness enforcement.
- Strengthened the stale-reference regression so it proves both section-level and per-source freshness failures.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `24 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `29 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `54 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=28 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-per-source-freshness-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_PER_SOURCE_FRESHNESS_2026-06-07.md`.

## 2026-06-07 (AI Lab Decision Field Group)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `var/desci-ai-lab-review-packet-sample-2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_DECISION_FIELD_GROUP_2026-06-07.md`

### Changes
- Re-evaluated the Recommendation / Decision contract and found that action plus rationale could pass without a field group for reviewer confidence and change conditions.
- Added `decision_recommendation_fields` to require recommendation, rationale, confidence, and change-condition signals.
- Strengthened the BioLinker research prompt to request explicit `Recommendation`, `Rationale`, `Confidence`, and `Change condition` fields.
- Updated browser/sample fixtures and added a regression for decision sections without confidence or change condition.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `24 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `29 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `54 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=27 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-decision-field-group-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_DECISION_FIELD_GROUP_2026-06-07.md`.

## 2026-06-07 (AI Lab Source Freshness Context)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `var/desci-ai-lab-review-packet-sample-2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_SOURCE_FRESHNESS_CONTEXT_2026-06-07.md`

### Changes
- Re-evaluated the References contract and found that concrete URLs/search queries could pass without any checked/retrieved/accessed date or freshness note.
- Added `references_source_freshness` to require source freshness context in `References & Search Queries`.
- Strengthened the BioLinker research prompt to ask for checked/retrieved/accessed dates or source freshness notes.
- Updated scorer/browser/sample fixtures and added a regression for stale reference lists.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `23 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `29 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `53 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=26 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-source-freshness-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_SOURCE_FRESHNESS_CONTEXT_2026-06-07.md`.

## 2026-06-07 (AI Lab Evidence Confidence and Follow-up)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EVIDENCE_CONFIDENCE_FOLLOWUP_2026-06-07.md`

### Changes
- Re-evaluated the Evidence Map contract and found that Strong/Weak/Missing categories could pass without explicit confidence or follow-up verification.
- Added `evidence_map_confidence_followup` to require confidence levels and follow-up verification actions.
- Strengthened the BioLinker research prompt to require Confidence and Follow-up verification in the Evidence Map.
- Updated scorer/browser/sample fixtures and added a regression for categorized but unverifiable Evidence Maps.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `22 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `29 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `52 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=25 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-evidence-confidence-followup-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EVIDENCE_CONFIDENCE_FOLLOWUP_2026-06-07.md`.

## 2026-06-07 (AI Lab Action Plan Timeline and Success Metric)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_PLAN_TIMELINE_SUCCESS_METRIC_2026-06-07.md`

### Changes
- Re-evaluated the Action Plan contract and found that owner/input/artifact/decision-gate fields could still pass without timing, sequence, priority, or measurable completion criteria.
- Added `action_plan_timeline_success_metric` to require timing or priority language plus success metrics or done conditions.
- Strengthened the BioLinker research prompt to require Timing/Priority and Success metric or Done condition for each Action Plan item.
- Updated scorer/browser/sample fixtures and added a regression for Action Plans that retain handoff fields but omit timeline and success metrics.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `21 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `29 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `51 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=24 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-action-plan-timeline-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_PLAN_TIMELINE_SUCCESS_METRIC_2026-06-07.md`.

## 2026-06-07 (AI Lab Source-Backed Decision Recommendation)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_SOURCE_BACKED_DECISION_RECOMMENDATION_2026-06-07.md`

### Changes
- Re-evaluated the new Recommendation / Decision requirement and found it could still pass source-grounded scoring without citing the evidence bundle.
- Added `decision_recommendation_cites_sources` to require a known source ID in the Recommendation / Decision section when evidence sources are provided.
- Strengthened the BioLinker research prompt to cite source IDs in that section when available.
- Updated scorer/browser/sample fixtures and added a regression for uncited recommendations under evidence scoring.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `20 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `29 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `50 passed`.
- Updated source-backed review-packet sample -> `pass score=1.000 passed=23 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-source-backed-decision-recommendation-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_SOURCE_BACKED_DECISION_RECOMMENDATION_2026-06-07.md`.

## 2026-06-07 (AI Lab Decision Recommendation Scorer)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_DECISION_RECOMMENDATION_SCORER_2026-06-07.md`

### Changes
- Re-evaluated the output contract and found that a source-grounded, actionable, context-fit brief could still pass without an explicit recommendation or decision.
- Added `decision_recommendation` to the AI Lab output scorer.
- Strengthened the BioLinker research prompt to require a `Recommendation / Decision` section with recommendation, rationale, confidence, and change conditions.
- Updated scorer/browser/sample fixtures and added a regression that rejects output missing the decision recommendation.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `19 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `29 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `49 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=22 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-decision-recommendation-review-packet-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_DECISION_RECOMMENDATION_SCORER_2026-06-07.md`.

## 2026-06-07 (AI Lab Contextual Review Packet)

### Scope
- `apps/desci-platform/frontend/src/hooks/useAgentTools.js`
- `apps/desci-platform/frontend/src/__tests__/components/AILab.test.jsx`
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_CONTEXTUAL_REVIEW_PACKET_2026-06-07.md`

### Changes
- Re-evaluated the review packet against context-fit requirements and found that it did not preserve the user's original topic.
- Added `## User Request Context` with Tool, Topic, and Deep research mode to copied review packets.
- Added scorer support for parsing packet topic context and checking `topic_context_fit`.
- Updated browser smoke to assert the copied packet includes the original topic and scores the packet with that topic.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `48 passed`.
- AILab Vitest -> `7 passed`.
- Targeted AILab ESLint -> pass.
- Updated review-packet sample -> `pass score=1.000 passed=21 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-contextual-review-packet-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_CONTEXTUAL_REVIEW_PACKET_2026-06-07.md`.

## 2026-06-07 (AI Lab Competitive Comparison Scorer)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_COMPETITIVE_COMPARISON_SCORER_2026-06-07.md`

### Changes
- Re-evaluated the output contract against the commercial-competitiveness requirement and found that Deep Dive could pass without an alternative or competitor comparison.
- Added `competitive_alternative_comparison` to the scorer.
- Strengthened the BioLinker research prompt to require at least one competing solution or alternative approach comparison with tradeoffs.
- Updated scorer and browser fixtures to include concrete alternative-comparison language.

### Verification
- Existing actionable packet sample initially failed under the new check: `needs_revision`, `19/20`, failed `competitive_alternative_comparison`.
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `46 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=20 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-competitive-review-packet-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_COMPETITIVE_COMPARISON_SCORER_2026-06-07.md`.

## 2026-06-07 (AI Lab Actionable Handoff Scorer)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTIONABLE_HANDOFF_SCORER_2026-06-07.md`

### Changes
- Re-evaluated the strict scorer and found that a seven-day Action Plan could still pass without explicit owner, required inputs, expected artifact, or decision gate.
- Added `action_plan_handoff_fields` to make Action Plans directly executable.
- Strengthened the BioLinker research prompt to require Owner, Inputs, Artifact, and Decision gate per Action Plan item.
- Updated scorer and browser fixtures to pass the stricter actionability bar.

### Verification
- Existing review-packet sample initially failed under the new check: `needs_revision`, `18/19`, failed `action_plan_handoff_fields`.
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `45 passed`.
- Updated review-packet sample -> `pass score=1.000 passed=19 failed=0`.
- Dev-auth browser smoke `ai-lab-result-copy-failure` -> `1/1 PASS` in `var/desci-ai-lab-actionable-review-packet-browser-smoke-2026-06-07.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTIONABLE_HANDOFF_SCORER_2026-06-07.md`.

## 2026-06-07 (AI Lab Review Packet Browser Scorer Ready)

### Scope
- `apps/desci-platform/scripts/browser_smoke.py`
- `apps/desci-platform/backend/tests/test_browser_smoke.py`
- `var/desci-ai-lab-review-packet-scorer-ready-browser-smoke-2026-06-07.json`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REVIEW_PACKET_BROWSER_SCORER_READY_2026-06-07.md`

### Changes
- Re-evaluated the AI Lab browser smoke and found it confirmed the review-packet button, but not that the copied packet could pass the strict scorer.
- Updated the browser fixture with quoted evidence phrases that match the fixture source snippets.
- Captured the copied review-packet payload in the browser smoke, parsed it with `parse_review_packet`, and scored it with strict source-grounded plus quoted-evidence checks.
- Kept the result-copy denial path covered in the same smoke.

### Verification
- `python -m py_compile apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `21 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `36 passed`.
- `python apps/desci-platform/scripts/browser_smoke.py --frontend http://127.0.0.1:5204 --expect-dev-auth --only-check ai-lab-result-copy-failure --timeout 45 --json-out var/desci-ai-lab-review-packet-scorer-ready-browser-smoke-2026-06-07.json` -> `1/1 PASS`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REVIEW_PACKET_BROWSER_SCORER_READY_2026-06-07.md`.

## 2026-06-07 (AI Lab Review Packet Direct Scoring)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `docs/reports/2026-06/DESCI_AI_LAB_REVIEW_PACKET_QUALITY_SAMPLE_2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REVIEW_PACKET_DIRECT_SCORING_2026-06-07.md`

### Changes
- Re-evaluated the copied review-packet handoff and found that reviewers still had to split the packet into separate output and evidence files before scoring.
- Added direct `--review-packet` parsing for the generated result section and embedded evidence JSON.
- Preserved strict source-grounded and quoted-evidence scoring on the parsed packet.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py apps/desci-platform/backend/services/agent_service.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `35 passed`.
- Review-packet CLI sample -> `pass score=1.000 passed=18 failed=0`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REVIEW_PACKET_DIRECT_SCORING_2026-06-07.md`.

## 2026-06-07 (AI Lab Review Packet Copy)

### Scope
- `apps/desci-platform/frontend/src/hooks/useAgentTools.js`
- `apps/desci-platform/frontend/src/components/AILab.jsx`
- `apps/desci-platform/frontend/src/i18n/messages.js`
- `apps/desci-platform/frontend/src/__tests__/components/AILab.test.jsx`
- `apps/desci-platform/scripts/browser_smoke.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REVIEW_PACKET_COPY_2026-06-07.md`

### Changes
- Re-evaluated evidence-source UI and found that reviewers still had to manually combine result Markdown, evidence JSON, strict scorer command, and review notes.
- Added a one-click review packet that includes the generated result, evidence JSON, strict scorer command, and review focus notes.
- Added a `Copy review packet` UI action and browser-smoke visibility coverage.

### Verification
- `npx vitest run --pool=threads --maxWorkers=1 --isolate src/__tests__/components/AILab.test.jsx` from `apps/desci-platform/frontend` -> `7 passed`.
- `npx eslint src/components/AILab.jsx src/hooks/useAgentTools.js src/__tests__/components/AILab.test.jsx src/i18n/messages.js` from `apps/desci-platform/frontend` -> pass.
- `python -m py_compile apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `20 passed`.
- `python apps/desci-platform/scripts/browser_smoke.py --frontend http://127.0.0.1:5204 --expect-dev-auth --only-check ai-lab-result-copy-failure --timeout 45 --json-out var/desci-ai-lab-review-packet-browser-smoke-2026-06-07.json` -> `1/1 PASS`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REVIEW_PACKET_COPY_2026-06-07.md`.

## 2026-06-07 (AI Lab Claim Review Export)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `docs/reports/2026-06/DESCI_AI_LAB_QUOTED_EVIDENCE_OUTPUT_QUALITY_SAMPLE_2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_CLAIM_REVIEW_EXPORT_2026-06-07.md`

### Changes
- Re-evaluated scorer output and found that PASS/FAIL checks did not give reviewers a concrete claim-by-claim review table.
- Added `claim_review.items` to JSON reports and `## Cited Claim Review` to Markdown reports.
- Added support statuses for unknown source, unsupported, term overlap, and quoted support.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `13 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `34 passed`.
- Strict quoted-evidence CLI sample -> `pass score=1.000 passed=18 failed=0`.
- Claim review table verified in `docs/reports/2026-06/DESCI_AI_LAB_QUOTED_EVIDENCE_OUTPUT_QUALITY_SAMPLE_2026-06-07.md`.
- `python apps/desci-platform/scripts/browser_smoke.py --frontend http://127.0.0.1:5204 --expect-dev-auth --only-check ai-lab-result-copy-failure --timeout 45 --json-out var/desci-ai-lab-claim-review-browser-smoke-2026-06-07.json` -> `1/1 PASS`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_CLAIM_REVIEW_EXPORT_2026-06-07.md`.

## 2026-06-07 (AI Lab Output Quality Completion Audit)

### Scope
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_OUTPUT_QUALITY_COMPLETION_AUDIT_2026-06-07.md`
- `var/desci-ai-lab-quoted-evidence-output-quality-sample-2026-06-07.json`
- `var/desci-ai-lab-quoted-evidence-browser-smoke-2026-06-07.json`
- `next-actions.md`

### Changes
- Audited the active output-quality objective against concrete artifacts and verification evidence.
- Mapped requirements for immediate usability, completeness, specificity, context fit, commercial competitiveness, reusability, external criteria, repeated re-evaluation, and live-output verification.
- Recorded that the local pipeline is materially improved but the active goal is not complete because live provider output remains externally blocked and the user asked for continued iteration until stopped.

### Verification
- Report existence verified for recovery packet, output contract, output quality scorer, source-grounded scorer, evidence sources UI, claim-support scorer, and quoted-evidence scorer.
- Strict sample evidence `var/desci-ai-lab-quoted-evidence-output-quality-sample-2026-06-07.json` -> `18/18 PASS`.
- Browser evidence `var/desci-ai-lab-quoted-evidence-browser-smoke-2026-06-07.json` -> `1/1 PASS`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_OUTPUT_QUALITY_COMPLETION_AUDIT_2026-06-07.md`.

## 2026-06-07 (AI Lab Quoted-Evidence Scorer)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `docs/reports/2026-06/DESCI_AI_LAB_QUOTED_EVIDENCE_OUTPUT_QUALITY_SAMPLE_2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_QUOTED_EVIDENCE_SCORER_2026-06-07.md`

### Changes
- Re-evaluated claim-support scoring and found that reviewers still had to inspect source snippets manually to find the exact supporting phrase.
- Added optional strict quoted-evidence mode requiring quoted phrases to appear in cited source snippets.
- Updated the BioLinker research prompt and regression coverage to request short quoted evidence phrases when source summaries are available.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `21 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `34 passed`.
- Strict quoted-evidence CLI sample -> `pass score=1.000 passed=18 failed=0`.
- `python apps/desci-platform/scripts/browser_smoke.py --frontend http://127.0.0.1:5204 --expect-dev-auth --only-check ai-lab-result-copy-failure --timeout 45 --json-out var/desci-ai-lab-quoted-evidence-browser-smoke-2026-06-07.json` -> `1/1 PASS`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_QUOTED_EVIDENCE_SCORER_2026-06-07.md`.

## 2026-06-07 (AI Lab Claim-Support Scorer)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `docs/reports/2026-06/DESCI_AI_LAB_SOURCE_GROUNDED_OUTPUT_QUALITY_SAMPLE_2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_CLAIM_SUPPORT_SCORER_2026-06-07.md`

### Changes
- Re-evaluated source-grounded scoring and found that known citations could still be decorative if the cited line and source snippet were unrelated.
- Added deterministic cited-line/source-snippet support overlap checks.
- Added regression coverage for unrelated cited claims and updated the passing source-grounded/browser fixtures to carry real support overlap.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py apps/desci-platform/backend/services/agent_service.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `9 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `30 passed`.
- `npx vitest run --pool=threads --maxWorkers=1 --isolate src/__tests__/components/AILab.test.jsx` from `apps/desci-platform/frontend` -> `7 passed`.
- `npx eslint src/components/AILab.jsx src/hooks/useAgentTools.js src/__tests__/components/AILab.test.jsx src/i18n/messages.js` from `apps/desci-platform/frontend` -> pass.
- Source-grounded CLI sample -> `pass score=1.000 passed=17 failed=0`.
- `python apps/desci-platform/scripts/browser_smoke.py --frontend http://127.0.0.1:5204 --expect-dev-auth --only-check ai-lab-result-copy-failure --timeout 45 --json-out var/desci-ai-lab-claim-support-browser-smoke-2026-06-07.json` -> `1/1 PASS`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_CLAIM_SUPPORT_SCORER_2026-06-07.md`.

## 2026-06-07 (AI Lab Evidence Sources UI)

### Scope
- `apps/desci-platform/backend/services/agent_service.py`
- `apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py`
- `apps/desci-platform/frontend/src/hooks/useAgentTools.js`
- `apps/desci-platform/frontend/src/components/AILab.jsx`
- `apps/desci-platform/frontend/src/i18n/messages.js`
- `apps/desci-platform/frontend/src/__tests__/components/AILab.test.jsx`
- `apps/desci-platform/scripts/browser_smoke.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EVIDENCE_SOURCES_UI_2026-06-07.md`

### Changes
- Re-evaluated source-grounded scoring and found that normal AI Lab results still did not expose a structured evidence bundle to users.
- Added backend `evidence_sources` with source ID, title, URL, and snippet while preserving the legacy URL-only `sources` list.
- Added an AI Lab result evidence section and copyable `{ "sources": [...] }` JSON payload for scorer/review reuse.
- Updated browser smoke to verify the evidence panel in the successful result path.

### Verification
- `python -m py_compile apps/desci-platform/backend/services/agent_service.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_agent_service_evidence_sources.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `29 passed`.
- `npx vitest run --pool=threads --maxWorkers=1 --isolate src/__tests__/components/AILab.test.jsx` from `apps/desci-platform/frontend` -> `7 passed`.
- `npx eslint src/components/AILab.jsx src/hooks/useAgentTools.js src/__tests__/components/AILab.test.jsx src/i18n/messages.js` from `apps/desci-platform/frontend` -> pass.
- `python apps/desci-platform/scripts/browser_smoke.py --frontend http://127.0.0.1:5204 --expect-dev-auth --only-check ai-lab-result-copy-failure --timeout 45 --json-out var/desci-ai-lab-evidence-sources-browser-smoke-2026-06-07.json` -> `1/1 PASS`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EVIDENCE_SOURCES_UI_2026-06-07.md`.

## 2026-06-07 (AI Lab Source-Grounded Scorer)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `docs/reports/2026-06/DESCI_AI_LAB_SOURCE_GROUNDED_OUTPUT_QUALITY_SAMPLE_2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_SOURCE_GROUNDED_SCORER_2026-06-07.md`

### Changes
- Re-evaluated the scorer against commercial-quality AI research expectations and found it still lacked source traceability.
- Added optional source-grounded scoring with evidence JSON, known-source citation checks, Evidence Map citation checks, and required-evidence failure mode.
- Made evidence JSON loading BOM-safe for Windows PowerShell generated files.
- Updated the BioLinker research prompt so numbered search results should be cited in Key Findings, Evidence Map, and References.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `16 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `28 passed`.
- Source-grounded CLI sample with BOM-prefixed evidence JSON -> `pass score=1.000 passed=16 failed=0`.
- `python apps/desci-platform/scripts/browser_smoke.py --frontend http://127.0.0.1:5204 --expect-dev-auth --only-check ai-lab-result-copy-failure --timeout 45 --json-out var/desci-ai-lab-source-grounded-scorer-browser-smoke-2026-06-07.json` -> `1/1 PASS`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_SOURCE_GROUNDED_SCORER_2026-06-07.md`.

## 2026-06-07 (AI Lab Scorer False-Positive Hardening)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `docs/reports/2026-06/DESCI_AI_LAB_OUTPUT_QUALITY_SCORER_SAMPLE_2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_SCORER_FALSE_POSITIVE_HARDENING_2026-06-07.md`

### Changes
- Re-evaluated the new AI Lab scorer and reproduced a false-positive where padded heading-only output passed `1.0`.
- Added section-body checks so evidence map, risks/open questions, and references/search queries must contain usable content rather than only headings.
- Added regression coverage for the heading-only placeholder case and regenerated scorer sample evidence under the stricter criteria.

### Verification
- False-positive baseline before hardening: `pass 1.0 []`.
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `4 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `24 passed`.
- Regenerated sample CLI evidence -> `pass score=1.000 passed=12 failed=0`.
- `python apps/desci-platform/scripts/browser_smoke.py --frontend http://127.0.0.1:5204 --expect-dev-auth --only-check ai-lab-result-copy-failure --timeout 45 --json-out var/desci-ai-lab-output-quality-scorer-content-browser-smoke-2026-06-07.json` -> `1/1 PASS`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_SCORER_FALSE_POSITIVE_HARDENING_2026-06-07.md`.

## 2026-06-07 (AI Lab Output Quality Scorer)

### Scope
- `apps/desci-platform/scripts/ai_lab_output_quality.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `apps/desci-platform/backend/tests/test_ai_lab_output_quality.py`
- `docs/reports/2026-06/DESCI_AI_LAB_OUTPUT_QUALITY_SCORER_SAMPLE_2026-06-07.md`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_OUTPUT_QUALITY_SCORER_2026-06-07.md`

### Changes
- Re-evaluated the AI Lab output contract and found that real generated Markdown still had no standalone offline quality scorer.
- Added a standard-library scorer that checks the decision-ready research brief structure and writes JSON/Markdown evidence.
- Connected the AI Lab browser-smoke success fixture to the same scorer so prompt, fixture, and offline evidence share one contract.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `3 passed`.
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `23 passed`.
- Sample CLI evidence -> `pass score=1.000 passed=12 failed=0`.
- `python apps/desci-platform/scripts/browser_smoke.py --frontend http://127.0.0.1:5204 --expect-dev-auth --only-check ai-lab-result-copy-failure --timeout 45 --json-out var/desci-ai-lab-output-quality-scorer-browser-smoke-2026-06-07.json` -> `1/1 PASS`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_OUTPUT_QUALITY_SCORER_2026-06-07.md`.

## 2026-06-07 (AI Lab Output Contract)

### Scope
- `packages/shared/prompts/templates/biolinker_research.yaml`
- `packages/shared/tests/test_prompt_notifier_metrics.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_OUTPUT_CONTRACT_2026-06-07.md`

### Changes
- Re-evaluated the AI Lab success path and found that the browser fixture could still pass with arbitrary Markdown.
- Tightened the BioLinker research prompt into a decision-ready research brief contract with executive summary, key findings, evidence map, action plan, risks, references, and quality criteria.
- Added prompt regression coverage so future edits preserve the required output contract.
- Updated the AI Lab browser-smoke success fixture to render and verify structured output sections before checking copy-error handling.

### Verification
- `python -m py_compile apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- `python apps/desci-platform/scripts/browser_smoke.py --frontend http://127.0.0.1:5204 --expect-dev-auth --only-check ai-lab-result-copy-failure --timeout 45 --json-out var/desci-ai-lab-success-output-quality-browser-smoke-2026-06-07.json` -> `1/1 PASS`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_OUTPUT_CONTRACT_2026-06-07.md`.

## 2026-06-07 (AI Lab Recovery Packet)

### Scope
- `apps/desci-platform/frontend/src/hooks/useAgentTools.js`
- `apps/desci-platform/frontend/src/components/AILab.jsx`
- `apps/desci-platform/frontend/src/i18n/messages.js`
- `apps/desci-platform/frontend/src/__tests__/components/AILab.test.jsx`
- `apps/desci-platform/scripts/browser_smoke.py`

### Changes
- Re-evaluated the real `/ai-lab` provider-failure output: the app showed a support ID and retry action, but no usable task artifact.
- Added a copy-ready execution packet for failed AI Lab runs that preserves the user's input, tool type, output contract, and quality criteria without fabricating generated content.
- Localized the known provider-unavailable message and kept support IDs visible.
- Extended browser smoke so the provider-unavailable path verifies packet visibility and copied payload content.

### Verification
- `python -m py_compile apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `node scripts/run-vitest-split.mjs src/__tests__/components/AILab.test.jsx` from `apps/desci-platform/frontend` -> `6 passed`.
- `npx vitest run --pool=threads --maxWorkers=1 --isolate src/__tests__/components/AILab.test.jsx` from `apps/desci-platform/frontend` -> `6 passed`.
- `npx eslint src/components/AILab.jsx src/hooks/useAgentTools.js src/__tests__/components/AILab.test.jsx src/i18n/messages.js` from `apps/desci-platform/frontend` -> pass.
- `python apps/desci-platform/scripts/browser_smoke.py --frontend http://127.0.0.1:5204 --expect-dev-auth --only-check ai-lab-agent-error-visible --timeout 45 --json-out var/desci-ai-lab-recovery-packet-browser-smoke-2026-06-07.json` -> `1/1 PASS`.
- Manual Playwright check on the real 503 path confirmed the packet includes the Korean oncology trial recruitment topic, `## 출력 형식`, `## 품질 기준`, and `Action Plan`; screenshot `desci-ai-lab-recovery-packet-2026-06-07.png`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_RECOVERY_PACKET_2026-06-07.md`.

## 2026-06-06 (MyLab Mint Success Receipt)

### Scope
- `apps/desci-platform/frontend/src/components/ui/SuccessModal.jsx`
- `apps/desci-platform/frontend/src/__tests__/components/SuccessModal.test.jsx`
- `apps/desci-platform/scripts/browser_smoke.py`
- `apps/desci-platform/backend/tests/test_browser_smoke.py`

### Changes
- Reproduced the MyLab mint-success UX gap: the transaction hash receipt displayed an external-link icon, but the hash was not actually clickable.
- Updated `SuccessModal` so transaction hashes link to Polygon Amoy Polygonscan.
- Added component coverage for the transaction explorer link.
- Added browser smoke `mylab-mint-success` to seed a mintable paper, restore a wallet through `eth_accounts`, submit `/nft/mint`, verify the payload, and assert the success receipt link.

### Verification
- `python -m py_compile apps/desci-platform/scripts/browser_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `15 passed`.
- `cmd /c npx vitest run src/__tests__/components/SuccessModal.test.jsx --config vite.config.js` -> `1 passed`.
- `cmd /c npx eslint src/components/ui/SuccessModal.jsx src/__tests__/components/SuccessModal.test.jsx` -> pass.
- Live Playwright probe restored wallet `0x1234567890123456789012345678901234567890`, posted `token_uri: ipfs://browser-smoke-mint-paper`, received mint status `200`, rendered the success modal, linked the tx hash to Amoy Polygonscan, and recorded console/page errors `0`; screenshot `var/desci-mylab-mint-success-2026-06-06.png`.
- `python apps/desci-platform/scripts/browser_smoke.py --frontend http://127.0.0.1:5211 --timeout 30 --expect-dev-auth --json-out apps/desci-platform/var/desci-mylab-mint-success-browser-smoke-2026-06-06.json` -> `49/49 PASS`.
- Runtime release gate with `--runtime-browser-expect-dev-auth` -> `2/2 PASS`: `var/desci-mylab-mint-success-release-gate-2026-06-06.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_MYLAB_MINT_SUCCESS_2026-06-06.md`.

## 2026-06-06 (AI Lab Agent Failure Handling)

### Scope
- `apps/desci-platform/backend/routers/agent.py`
- `apps/desci-platform/backend/main.py`
- `apps/desci-platform/backend/services/vc_repository.py`
- `apps/desci-platform/backend/tests/test_router_edge_cases.py`
- `apps/desci-platform/backend/tests/test_vc_repository.py`
- `apps/desci-platform/frontend/src/hooks/useAgentTools.js`
- `apps/desci-platform/frontend/src/__tests__/components/AILab.test.jsx`
- `apps/desci-platform/scripts/browser_smoke.py`
- `apps/desci-platform/backend/tests/test_browser_smoke.py`

### Changes
- Reproduced the real `/ai-lab` Content Writer failure with Playwright: the configured Gemini key returned provider `403`, the backend raised an unhandled 500, and the browser showed `Failed to fetch` because the failure did not complete as structured CORS-safe JSON.
- Added route-level agent error boundaries that convert provider exceptions into sanitized `503` responses without exposing provider credential messages to the user.
- Exposed `X-Request-ID` and `X-Response-Time-Ms` through CORS so frontend error panels can show support IDs.
- Updated AI Lab agent calls to suppress expected API-error console logging once the error is handled in the UI.
- Added browser smoke `ai-lab-agent-error-visible` to verify the AI Lab provider-unavailable panel, support ID, retry action, and request payload.
- Fixed a release-gate blocker found during full smoke: VC repository now falls back to the curated memory seed when a configured Postgres/Supabase backend fails at query time.

### Verification
- `python -m py_compile apps/desci-platform/backend/main.py apps/desci-platform/backend/routers/agent.py apps/desci-platform/backend/services/vc_repository.py apps/desci-platform/scripts/browser_smoke.py apps/desci-platform/backend/tests/test_router_edge_cases.py apps/desci-platform/backend/tests/test_vc_repository.py apps/desci-platform/backend/tests/test_browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_vc_repository.py apps/desci-platform/backend/tests/test_vcs_router.py apps/desci-platform/backend/tests/test_router_edge_cases.py apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `67 passed`.
- `cmd /c npx vitest run src/__tests__/components/AILab.test.jsx --config vite.config.js` -> `5 passed`.
- `cmd /c npx eslint src/hooks/useAgentTools.js src/__tests__/components/AILab.test.jsx` -> pass.
- Direct API probe for `POST /api/agent/write` on the invalid-provider runtime returned `503` with CORS allowed for `http://127.0.0.1:5210`.
- Direct `/vcs?limit=3` probe returned `200` after the Postgres runtime fallback.
- Live Playwright probe on `/ai-lab` saw `write_status: 503`, structured error visible, support ID visible, retry visible, unexpected console errors `0`, page errors `0`, and network failures `0`; screenshot `var/desci-ai-lab-agent-error-2026-06-06.png`.
- `python apps/desci-platform/scripts/browser_smoke.py --frontend http://127.0.0.1:5210 --timeout 30 --expect-dev-auth --json-out apps/desci-platform/var/desci-ai-lab-agent-error-browser-smoke-2026-06-06.json` -> `48/48 PASS`.
- Runtime release gate with `--runtime-browser-expect-dev-auth` -> `2/2 PASS`: `var/desci-ai-lab-agent-error-release-gate-2026-06-06.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_AGENT_FAILURE_HANDLING_2026-06-06.md`.

## 2026-06-06 (Wallet Restore Across Direct Routes)

### Scope
- `apps/desci-platform/frontend/src/contexts/AuthContext.jsx`
- `apps/desci-platform/frontend/src/__tests__/contexts/AuthContext.test.jsx`
- `apps/desci-platform/scripts/browser_smoke.py`
- `apps/desci-platform/backend/tests/test_browser_smoke.py`

### Changes
- Reproduced the reload/deep-link gap: a previously connected wallet was held only in React state, so a direct `/governance` load lost wallet readiness even when the EIP-1193 provider could return an authorized account.
- Added passive wallet restore on `AuthProvider` mount via `eth_accounts` without prompting the wallet or switching chains.
- Subscribed to provider `accountsChanged` and `disconnect` events so wallet state updates when the active account changes or the wallet disconnects.
- Added AuthContext regression coverage for initial `eth_accounts` restore, account-change updates, account clearing, and disconnect clearing.
- Added browser smoke `wallet-restore-direct-governance` to load `/governance` directly with a mocked authorized provider, assert the wallet-required panel is gone, create a proposal, and verify the POST proposer uses the restored address.

### Verification
- `cmd /c npx vitest run src/__tests__/contexts/AuthContext.test.jsx src/__tests__/lib/walletConnection.test.js src/__tests__/components/Wallet.test.jsx --config vite.config.js` -> `3 passed`, `8 passed`.
- `cmd /c npx eslint src/contexts/AuthContext.jsx src/__tests__/contexts/AuthContext.test.jsx src/__tests__/lib/walletConnection.test.js src/__tests__/components/Wallet.test.jsx` -> pass.
- `python -m py_compile apps/desci-platform/scripts/browser_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `15 passed`.
- Live Playwright probe loaded `/governance` directly with `eth_accounts` returning `0x5555555555555555555555555555555555555555`, confirmed the wallet-required panel was hidden, submit was enabled, `POST /governance/proposals` -> `200`, posted proposer matched the restored address, and recorded console/page errors `0`; screenshot `var/desci-wallet-restore-governance-2026-06-06.png`.
- `python apps/desci-platform/scripts/browser_smoke.py --frontend http://127.0.0.1:5209 --timeout 30 --expect-dev-auth --json-out apps/desci-platform/var/desci-wallet-restore-browser-smoke-2026-06-06.json` -> `47/47 PASS`.
- Runtime release gate with `--runtime-browser-expect-dev-auth` -> `2/2 PASS`: `var/desci-wallet-restore-release-gate-2026-06-06.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_WALLET_RESTORE_2026-06-06.md`.

## 2026-06-06 (Governance Fallback Persistence)

### Scope
- `apps/desci-platform/backend/routers/governance.py`
- `apps/desci-platform/backend/routers/web3.py`
- `apps/desci-platform/backend/tests/test_router_edge_cases.py`
- `apps/desci-platform/backend/tests/test_smoke_pipeline.py`
- `apps/desci-platform/scripts/browser_smoke.py`
- `apps/desci-platform/backend/tests/test_browser_smoke.py`

### Changes
- Reproduced the Firestore-disabled fallback gap: `create_proposal()` returned a proposal ID, but the next `list_proposals()` call did not include it.
- Added an in-process fallback governance store so local/dev/smoke runtimes preserve created proposals and vote totals when Firestore is unavailable.
- Added fallback vote handling that rejects unknown proposal IDs instead of returning false success.
- Added `GET /transactions/{address}` with Firestore-backed reads and a `200 []` local fallback to remove the connected Wallet page's missing-route console error.
- Added backend regression coverage for fallback proposal listing, fallback vote total updates, unknown proposal votes, and wallet transaction fallback.
- Added browser smoke `governance-connected-create-vote` to connect a mocked wallet, create a proposal, vote For, and verify the visible `For: 100` total.

### Verification
- `python -m py_compile apps/desci-platform/backend/routers/governance.py apps/desci-platform/backend/routers/web3.py apps/desci-platform/scripts/browser_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_router_edge_cases.py apps/desci-platform/backend/tests/test_smoke_pipeline.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_router_edge_cases.py apps/desci-platform/backend/tests/test_smoke_pipeline.py -q -p no:cacheprovider` -> `53 passed`.
- `cmd /c npx vitest run src/__tests__/components/Governance.test.jsx --config vite.config.js` -> `4 passed`.
- `cmd /c npx eslint src/__tests__/components/Governance.test.jsx src/components/Governance.jsx` -> pass.
- Live Playwright probe connected a mocked Polygon Amoy wallet, created `Runtime Fallback Governance Probe 2026-06-06`, observed `POST /governance/proposals` -> `200`, voted For with `POST /governance/proposals/{id}/vote` -> `200`, saw `For: 100`, and recorded console/page errors `0`; screenshot `var/desci-governance-fallback-vote-2026-06-06.png`.
- `python apps/desci-platform/scripts/browser_smoke.py --frontend http://127.0.0.1:5208 --timeout 30 --expect-dev-auth --json-out apps/desci-platform/var/desci-governance-fallback-browser-smoke-2026-06-06.json` -> `46/46 PASS`.
- Runtime release gate with `--runtime-browser-expect-dev-auth` -> `2/2 PASS`: `var/desci-governance-fallback-release-gate-2026-06-06.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_GOVERNANCE_FALLBACK_PERSISTENCE_2026-06-06.md`.

## 2026-06-06 (VC Portal Deal-Flow Matches)

### Scope
- `apps/desci-platform/backend/models.py`
- `apps/desci-platform/backend/routers/vcs.py`
- `apps/desci-platform/backend/tests/test_vcs_router.py`
- `apps/desci-platform/frontend/src/hooks/useVCDashboard.js`
- `apps/desci-platform/frontend/src/hooks/useVCDashboard.test.jsx`
- `apps/desci-platform/frontend/src/components/VCDashboard.jsx`
- `apps/desci-platform/frontend/src/components/vc/DealFlowPanel.jsx`
- `apps/desci-platform/frontend/src/components/vc/VCSelectorCard.jsx`
- `apps/desci-platform/frontend/src/__tests__/components/VCDashboard.test.jsx`
- `apps/desci-platform/frontend/src/i18n/messages.js`
- `apps/desci-platform/scripts/browser_smoke.py`

### Changes
- Reproduced the real `/vc-portal` selection path and confirmed baseline selection rendered the VC profile while deal flow stayed empty and no `/vcs/{vc_id}/matches` request was made.
- Added `GET /vcs/{vc_id}/matches` backed by the existing smart matcher and a response model for ranked VC deal-flow assets.
- Updated `useVCDashboard` to fetch ranked matches on VC selection, expose match-loading/error state, and keep the selected profile visible.
- Added deal-flow results/error test IDs and an accessible `label`/`select` association for the VC selector.
- Added component coverage proving selected VC matches render as cards.
- Expanded browser smoke `vc-portal-select` to verify the match request and populated deal-flow grid with deterministic route data.

### Verification
- `python -m py_compile apps/desci-platform/backend/models.py apps/desci-platform/backend/routers/vcs.py apps/desci-platform/backend/tests/test_vcs_router.py apps/desci-platform/scripts/browser_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_vcs_router.py -q -p no:cacheprovider` -> `11 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `15 passed`.
- `cmd /c npx vitest run src/hooks/useVCDashboard.test.jsx src/__tests__/components/VCDashboard.test.jsx --config vite.config.js` -> `2 passed`.
- `cmd /c npx eslint src/hooks/useVCDashboard.js src/hooks/useVCDashboard.test.jsx src/components/VCDashboard.jsx src/components/vc/DealFlowPanel.jsx src/components/vc/VCSelectorCard.jsx src/__tests__/components/VCDashboard.test.jsx` -> pass.
- Live Playwright probe selected `vc-kip-001`, observed `GET /vcs/vc-kip-001/matches?limit=10` -> `200`, rendered `2` deal-flow results, and recorded console/page errors `0`; screenshot `var/desci-vc-deal-flow-matches-2026-06-06.png`.
- `python apps/desci-platform/scripts/browser_smoke.py --frontend http://127.0.0.1:5207 --timeout 30 --expect-dev-auth --json-out apps/desci-platform/var/desci-vc-deal-flow-browser-smoke-2026-06-06.json` -> `45/45 PASS`.
- Runtime release gate with `--runtime-browser-expect-dev-auth` -> `2/2 PASS`: `var/desci-vc-deal-flow-release-gate-2026-06-06.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_VC_DEAL_FLOW_MATCHES_2026-06-06.md`.

## 2026-06-06 (Asset Upload Receipt)

### Scope
- `apps/desci-platform/backend/services/asset_manager.py`
- `apps/desci-platform/backend/tests/test_asset_manager.py`
- `apps/desci-platform/frontend/src/components/AssetManager.jsx`
- `apps/desci-platform/frontend/src/i18n/messages.js`
- `apps/desci-platform/frontend/src/__tests__/components/AssetManager.test.jsx`
- `apps/desci-platform/frontend/src/__tests__/mocks/locale-messages.js`
- `apps/desci-platform/scripts/browser_smoke.py`

### Changes
- Reproduced the real `/assets` upload flow with Playwright MCP and confirmed uploaded assets were identifiable only by UUID saved filenames in the tracked list.
- Added generic asset manifests that preserve original filename, saved filename, selected type, size, indexed state, analysis, and upload timestamp.
- Updated `/assets` listing to merge manifest-backed assets with legacy files and sort newest first.
- Added a durable Asset Library upload receipt with original filename, type, size, indexing state, and next actions to `/vc-portal` and `/biolinker`.
- Updated tracked asset cards to show original filename first and `Saved as ...` storage metadata second.
- Expanded browser smoke `asset-upload-readiness` to verify receipt, original filename preservation, next-action links, and saved filename metadata.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_asset_manager.py -q -p no:cacheprovider` -> `3 passed`.
- `cmd /c npx vitest run src/__tests__/components/AssetManager.test.jsx --config vite.config.js` -> `4 passed`.
- `cmd /c npx eslint src/components/AssetManager.jsx src/__tests__/components/AssetManager.test.jsx` -> pass.
- `python -m py_compile apps/desci-platform/scripts/browser_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/services/asset_manager.py apps/desci-platform/backend/tests/test_asset_manager.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `15 passed`.
- Manual Playwright MCP confirmed baseline UUID-only list, then variant receipt/list with original filename, `Indexed`, `/vc-portal`, `/biolinker`, network 200s, and console errors `0`; screenshot `var/desci-asset-upload-receipt-2026-06-06.png`.
- `python apps/desci-platform/scripts/browser_smoke.py --frontend http://127.0.0.1:5206 --timeout 30 --expect-dev-auth --json-out apps/desci-platform/var/desci-asset-upload-receipt-browser-smoke-2026-06-06.json` -> `45/45 PASS`.
- Runtime release gate with `--runtime-browser-expect-dev-auth` -> `2/2 PASS` on retry: `var/desci-asset-upload-receipt-release-gate-2026-06-06.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_ASSET_UPLOAD_RECEIPT_2026-06-06.md`.

## 2026-06-06 (Peer Review Wallet-Required Submission)

### Scope
- `apps/desci-platform/frontend/src/components/PeerReview.jsx`
- `apps/desci-platform/frontend/src/hooks/usePeerReview.js`
- `apps/desci-platform/frontend/src/i18n/messages.js`
- `apps/desci-platform/frontend/src/__tests__/components/PeerReview.test.jsx`
- `apps/desci-platform/scripts/browser_smoke.py`

### Changes
- Reproduced the real `/peer-review` no-wallet path with Playwright MCP: critique entry enabled submit, submit posted to `/reward/review`, and backend returned `422`.
- Made wallet connection an explicit rewarded-review requirement in the checklist.
- Kept critique readiness visible while keeping overall submit blocked until a wallet address exists.
- Added a wallet-required status panel with `Open Wallet` -> `/wallet`.
- Hardened `usePeerReview` so direct no-wallet submission is blocked before the backend call and successful submissions always include `user_address`.
- Added focused Peer Review regression coverage and updated authenticated browser smoke for the new no-wallet contract.

### Verification
- `cmd /c npx vitest run src/__tests__/components/PeerReview.test.jsx --config vite.config.js` -> `2 passed`.
- `cmd /c npx eslint src/components/PeerReview.jsx src/hooks/usePeerReview.js src/__tests__/components/PeerReview.test.jsx` -> pass.
- `python -m py_compile apps/desci-platform/scripts/browser_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `15 passed`.
- Manual Playwright MCP confirmed critique ready, wallet missing, `Open Wallet` href `/wallet`, disabled submit, no `/reward/review` POST, and console errors `0`; screenshot `var/desci-peer-review-wallet-required-2026-06-06.png`.
- `python apps/desci-platform/scripts/browser_smoke.py --frontend http://127.0.0.1:5205 --timeout 30 --expect-dev-auth --json-out apps/desci-platform/var/desci-peer-review-wallet-required-browser-smoke-2026-06-06.json` -> `45/45 PASS`.
- Runtime release gate with `--runtime-browser-expect-dev-auth` -> `2/2 PASS`: `var/desci-peer-review-wallet-required-release-gate-2026-06-06.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_PEER_REVIEW_WALLET_REQUIRED_2026-06-06.md`.

## 2026-06-06 (BioLinker Empty Match Actions)

### Scope
- `apps/desci-platform/frontend/src/components/MatchingResults.jsx`
- `apps/desci-platform/frontend/src/components/BioLinker.jsx`
- `apps/desci-platform/frontend/src/i18n/messages.js`
- `apps/desci-platform/frontend/src/__tests__/components/BioLinker.test.jsx`
- `apps/desci-platform/scripts/browser_smoke.py`
- `apps/desci-platform/backend/tests/test_browser_smoke.py`

### Changes
- Reproduced the real upload -> durable receipt -> Match Studio path with Playwright MCP and confirmed the valid paper handoff could end in a no-match dead end.
- Replaced the one-sentence no-match state with a structured empty state: title, explanatory body, `Open Funding Radar` link, and `Analyze an RFP` tab-switch action.
- Kept the RFP action inside the same paper-scoped Match Studio URL so the uploaded paper context is not lost.
- Added icon-bearing empty-state actions in `MatchingResults.jsx` and left populated match cards unchanged.
- Added English fallback message keys and focused BioLinker coverage for zero-match next actions.
- Added `biolinker-empty-match-next-actions` to authenticated browser smoke.
- Hardened browser smoke for locale-sensitive route titles and dashboard upload render proof.

### Verification
- `cmd /c npx vitest run src/__tests__/components/BioLinker.test.jsx --config vite.config.js` -> `6 passed`.
- `python -m py_compile apps/desci-platform/scripts/browser_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `15 passed`.
- Manual Playwright MCP upload -> receipt -> Match Studio -> empty match actions -> RFP Analysis CTA; console errors `0`; screenshot `var/desci-biolinker-empty-match-actions-2026-06-06.png`.
- `python apps/desci-platform/scripts/browser_smoke.py --frontend http://127.0.0.1:5204 --timeout 30 --expect-dev-auth --json-out apps/desci-platform/var/desci-biolinker-empty-match-browser-smoke-2026-06-06.json` -> `45/45 PASS`.
- Runtime release gate with `--runtime-browser-expect-dev-auth` -> `2/2 PASS`: `var/desci-biolinker-empty-match-release-gate-2026-06-06.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_BIOLINKER_EMPTY_MATCH_ACTIONS_2026-06-06.md`.

## 2026-06-06 (BioLinker Paper Context Handoff)

### Scope
- `apps/desci-platform/frontend/src/components/BioLinker.jsx`
- `apps/desci-platform/frontend/src/i18n/messages.js`
- `apps/desci-platform/frontend/src/__tests__/components/BioLinker.test.jsx`
- `apps/desci-platform/frontend/src/__tests__/mocks/locale-messages.js`
- `apps/desci-platform/scripts/browser_smoke.py`
- `apps/desci-platform/backend/tests/test_browser_smoke.py`

### Changes
- Reproduced the real receipt -> Match Studio path with Playwright MCP after uploading a PDF through `/upload`.
- Confirmed the baseline handoff reached `/biolinker?paper_id=...&paper_title=...`, but posted `/jobs/match/paper` twice for the same paper under the dev browser path.
- Added a same-`paper_id` guard in `BioLinker.jsx` so receipt deep links create one private match job.
- Replaced the short paper banner with a durable paper-context status panel that exposes paper title, paper ID, loading/completed/failed copy, and `role="status"`/`aria-atomic="true"`.
- Removed redundant `decodeURIComponent` around `paper_title` because URL search params already provide decoded values.
- Added `biolinker-paper-context-handoff` to authenticated browser smoke to verify one match POST, no EventSource, visible context, and rendered match results.
- Refreshed live AutoResearch source evidence with Veritas `HEAD` `82b369b4e3566ec0d78842bad1cf8dac2624e437`.

### Verification
- `cmd /c npx vitest run src/__tests__/components/BioLinker.test.jsx --config vite.config.js` -> `5 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `15 passed`.
- Manual Playwright MCP upload -> receipt -> Match Studio -> one `/jobs/match/paper 200`, console errors `0`, paper context panel visible with CID.
- `python apps/desci-platform/scripts/browser_smoke.py --frontend http://127.0.0.1:5203 --timeout 30 --expect-dev-auth --json-out var/desci-biolinker-paper-context-browser-smoke-2026-06-06.json` -> `44/44 PASS`.
- Runtime release gate with `--runtime-browser-expect-dev-auth` -> `2/2 PASS`: `var/desci-biolinker-paper-context-release-gate-2026-06-06.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_BIOLINKER_PAPER_CONTEXT_HANDOFF_2026-06-06.md`.

## 2026-06-06 (Upload Durable Receipt)

### Scope
- `apps/desci-platform/frontend/src/components/UploadPaper.jsx`
- `apps/desci-platform/frontend/src/components/Dashboard.jsx`
- `apps/desci-platform/frontend/src/i18n/messages.js`
- `apps/desci-platform/frontend/src/__tests__/components/UploadPaper.test.jsx`
- `apps/desci-platform/frontend/src/__tests__/mocks/locale-messages.js`
- `apps/desci-platform/scripts/browser_smoke.py`
- `apps/desci-platform/backend/tests/test_browser_smoke.py`

### Changes
- Reproduced the live `/upload` submit workflow with Playwright MCP and confirmed the previous success evidence disappeared after the transient reset window.
- Replaced the transient-only upload success state with a durable receipt panel that keeps title, authors, CID, IPFS, Research Vault, and Match Studio handoff links visible after the form resets.
- Marked the receipt as `role="status"` with `aria-atomic="true"` so the completed submission is announced without stealing focus.
- Added explicit English receipt message keys and test mocks.
- Added a stable dashboard quick-action test id to remove a role/name locator flake in runtime release-gate browser smoke.
- Added `upload-submit-receipt` to authenticated browser smoke, including upload/indexing mocks, authenticated job polling, no unexpected EventSource, and a 6-second persistence check.
- Refreshed live AutoResearch source evidence with Veritas `HEAD` `7caad9a4de258ba8d0c55f71edd89bdd4bb6208b`.

### Verification
- `cmd /c npx vitest run src/__tests__/components/UploadPaper.test.jsx src/__tests__/components/Dashboard.test.jsx --config vite.config.js` -> `20 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `15 passed`.
- Manual Playwright MCP upload after fix -> durable receipt visible after `7s`; console errors `0`; network: `/upload 200`, `/jobs/papers/index 200`, `/jobs/<id> 200`; no `/events`.
- `python apps/desci-platform/scripts/browser_smoke.py --frontend http://127.0.0.1:5202 --timeout 30 --expect-dev-auth --json-out var/desci-upload-receipt-browser-smoke-2026-06-06.json` -> `43/43 PASS`.
- Runtime release gate with `--runtime-browser-expect-dev-auth` -> `2/2 PASS`: `var/desci-upload-receipt-release-gate-2026-06-06.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_UPLOAD_DURABLE_RECEIPT_2026-06-06.md`.

## 2026-06-06 (Upload Submit Private Job Polling)

### Scope
- `apps/desci-platform/frontend/src/hooks/useJobProgress.js`
- `apps/desci-platform/frontend/src/components/UploadPaper.jsx`
- `apps/desci-platform/frontend/src/components/BioLinker.jsx`
- `apps/desci-platform/frontend/src/components/ResearchFeed.jsx`
- `apps/desci-platform/scripts/browser_smoke.py`

### Changes
- Reproduced the actual `/upload` submit path with Playwright MCP file chooser, metadata entry, terms check, and submit click.
- Confirmed the baseline uploaded and indexed successfully but still emitted unauthenticated `GET /jobs/<id>/events` 401 console errors before fallback polling recovered.
- Added `useJobProgress({ preferPolling: true })` and used it for private UploadPaper and BioLinker jobs, keeping SSE as the default for public jobs.
- Normalized `/papers/public` records in `ResearchFeed.jsx` so uploaded records using `keywords`, `cid`, and array `authors` render safely.
- Updated browser smoke `/explore` expectation to verify stable workflow signals instead of a fixed mock paper title.
- Refreshed live AutoResearch source evidence with Veritas `HEAD` `588df8d2c6b87dfccaa6864849ed5e6123e4494b`.

### Verification
- `cmd /c npx vitest run src/hooks/useJobProgress.test.jsx src/__tests__/components/UploadPaper.test.jsx src/__tests__/components/ResearchFeed.test.jsx --config vite.config.js` -> `15 passed`.
- Manual Playwright MCP upload after fix -> console errors `0`; network: `/upload 200`, `/jobs/papers/index 200`, `/jobs/<id> 200`; no `/events` 401.
- Manual Playwright MCP `/explore` -> uploaded paper card rendered with IPFS and AI analysis links; console errors `0`.
- `python apps/desci-platform/scripts/browser_smoke.py --frontend http://127.0.0.1:5201 --timeout 20 --expect-dev-auth --json-out var/desci-upload-submit-browser-smoke-2026-06-06.json` -> `42/42 PASS`.
- Runtime release gate with `--runtime-browser-expect-dev-auth` -> `2/2 PASS`: `var/desci-upload-submit-release-gate-2026-06-06.json`.
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_browser_smoke.py` -> `71 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_UPLOAD_SUBMIT_WORKFLOW_2026-06-06.md`.

## 2026-06-06 (Browser No-Networkidle Runtime Gate)

### Scope
- `apps/desci-platform/scripts/browser_smoke.py`
- `apps/desci-platform/backend/tests/test_browser_smoke.py`
- `apps/desci-platform/scripts/release_gate.py`
- `apps/desci-platform/backend/tests/test_release_gate.py`

### Changes
- Removed remaining browser-smoke `networkidle` and `wait_for_load_state` usage.
- Added fresh-page isolation for each browser smoke check so route mocks, console listeners, and late API failures do not leak between checks.
- Updated dashboard readiness refresh smoke to wait for rendered progress/summary text instead of sampling the initial panel state.
- Added `release_gate.py --runtime-browser-expect-dev-auth` so runtime release-gate browser evidence can validate local dev-auth frontends explicitly.
- Refreshed live AutoResearch source evidence with Veritas `HEAD` `588df8d2c6b87dfccaa6864849ed5e6123e4494b`.

### Verification
- `python -m py_compile apps\desci-platform\scripts\browser_smoke.py apps\desci-platform\backend\tests\test_browser_smoke.py` -> PASS.
- `python -m pytest apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `15 passed`.
- `python -m py_compile apps\desci-platform\scripts\release_gate.py apps\desci-platform\scripts\browser_smoke.py apps\desci-platform\backend\tests\test_release_gate.py apps\desci-platform\backend\tests\test_browser_smoke.py` -> PASS.
- `python -m pytest apps\desci-platform\backend\tests\test_release_gate.py apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `71 passed`.
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5199 --expect-dev-auth --timeout 8 --json-out var\desci-browser-smoke-no-networkidle-final-2026-06-06.json` -> `42/42 PASS`.
- Manual Playwright MCP clicked `/dashboard` Quick Actions `Submit new research` -> `/upload`; console errors `0`, filtered API requests `200`.
- Runtime release gate with `--runtime-browser-expect-dev-auth` -> `2/2 PASS`: `var\desci-release-gate-runtime-no-networkidle-dev-auth-2026-06-06.json`.
- Workspace DeSci smoke attempt timed out with partial evidence in `var\workspace-smoke-desci-no-networkidle-2026-06-06.json`; runtime release gate is the accepted evidence for this cycle.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_BROWSER_NO_NETWORKIDLE_2026-06-06.md`.

## 2026-06-06 (Workspace Smoke Resume Filters)

### Scope
- `ops/scripts/run_workspace_smoke.py`
- `tests/test_workspace_smoke.py`

### Changes
- Added `--only-check` to run exact smoke checks without replaying an entire scope.
- Added `--start-after` to resume a scoped smoke run after a named check, preserving default check order.
- Added fail-closed selection tests so missing check names print available checks instead of silently skipping validation.
- Refreshed live AutoResearch source evidence with Veritas `HEAD` `20b8328fd7d94e814d56422c8de02a7f2c12c006`.

### Verification
- Existing DeSci full smoke artifact finished after the earlier shell timeout and now reports `8/8 passed`: `var/workspace-smoke-desci-browser-readiness-wait-2026-06-06.json`.
- Resume proof: `python ops/scripts/run_workspace_smoke.py --scope desci --start-after "desci backend smoke" --json-out var/workspace-smoke-desci-resume-release-readiness-2026-06-06.json` -> `1/1 passed`.
- `python -m py_compile ops/scripts/run_workspace_smoke.py tests/test_workspace_smoke.py` -> PASS.
- Focused resume-filter tests -> `2 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_WORKSPACE_SMOKE_RESUME_2026-06-06.md`.

## 2026-06-06 (Browser Readiness Wait)

### Scope
- `apps/desci-platform/scripts/browser_smoke.py`
- `apps/desci-platform/backend/tests/test_browser_smoke.py`

### Changes
- Replaced the core route-smoke readiness wait with `domcontentloaded` plus screen-render evidence instead of relying on Playwright `networkidle`.
- Updated dashboard quick-upload smoke to wait for the upload route and visible upload UI, not idle network state.
- Updated the Funding Radar -> BioLinker bridge smoke to wait for the imported notice panel and exact textarea payload before asserting the handoff.
- Added a regression assertion that generic route checks now navigate with `domcontentloaded`.
- Refreshed live AutoResearch source evidence with Veritas `HEAD` `ffcaf1caa8089b155289e00a8875012d3e7c904f`.

### Verification
- Baseline strict browser smoke with system Python failed `38/42`: `var/desci-browser-smoke-networkidle-baseline-system-2026-06-06.json`.
- Direct timing probe showed `/login` rendered expected user text in `1631.2ms` and `/dashboard` in `924.9ms`, while `networkidle` still timed out near 9 seconds.
- Variant strict browser smoke passed `42/42`: `var/desci-browser-smoke-readiness-wait-variant-2026-06-06.json`.
- Direct clicked Funding Radar -> BioLinker proof saved `var/desci-notices-biolinker-bridge-readiness-wait-2026-06-06.png` with imported panel visible and textarea payload present.
- `python -m py_compile apps/desci-platform/scripts/browser_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py` -> PASS.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `13 passed`.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `19 passed`.
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-browser-readiness-wait-2026-06-06.json` initially exceeded the shell wait, but the underlying run completed and now reports `8/8 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_BROWSER_READINESS_WAIT_2026-06-06.md`.

## 2026-06-06 (RabbitMQ Fast Fallback)

### Scope
- `apps/desci-platform/backend/services/rabbitmq_bus.py`
- `apps/desci-platform/backend/tests/test_rabbitmq_bus.py`

### Changes
- Added local RabbitMQ URL detection and fast failure defaults for absent local brokers: one connection attempt, zero retry delay, `socket_timeout=0.35`, and `stack_timeout=0.8`.
- Added a reconnect cooldown so repeated `is_connected` checks do not re-open the slow connection path on every health/readiness request.
- Preserved the previous `blocked_connection_timeout=300` default unless explicitly overridden by `RABBITMQ_BLOCKED_CONNECTION_TIMEOUT_SECONDS`.
- Added focused regressions for local timeout defaults and no immediate retry after failed connection.
- Refreshed live AutoResearch source evidence with Veritas `HEAD` `d7f4f676c4ed90190460db31913d3d34f0a71242`.

### Verification
- Baseline local probes before the variant showed `/ready` at `12728ms` and `/health` at `12783ms` with RabbitMQ unavailable.
- RabbitMQ focused tests -> `2 passed`.
- Python compile check for `rabbitmq_bus.py` and `test_rabbitmq_bus.py` -> PASS.
- Standalone RabbitMQ init after the variant -> `742.8ms`, `connected=False`, and retained `blocked_timeout_default=300.0`.
- Product smoke after the variant -> `5/5 passed`: `var/desci-rabbitmq-fast-fallback-product-smoke-2026-06-06.json`.
- Product smoke on a freshly restarted backend from the current files -> `5/5 passed`: `var/desci-rabbitmq-fast-fallback-product-smoke-current-2026-06-06.json`.
- Authenticated browser smoke with the default 20s route timeout -> `42/42 passed`: `var/desci-rabbitmq-fast-fallback-browser-smoke-default-2026-06-06.json`.
- Strict 8s browser probe still failed `3/42` on `networkidle` waits for `/login` and `/dashboard`; this is recorded as the next performance target, not a RabbitMQ regression blocker.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_RABBITMQ_FAST_FALLBACK_2026-06-06.md`.

## 2026-06-06 (Operational Headers And AI Lab Copy)

### Scope
- `apps/desci-platform/backend/main.py`
- `apps/desci-platform/backend/tests/test_api_endpoints.py`
- `apps/desci-platform/frontend/src/hooks/useAgentTools.js`
- `apps/desci-platform/frontend/src/__tests__/components/AILab.test.jsx`
- `apps/desci-platform/frontend/src/i18n/messages.js`

### Changes
- Added FastAPI operational headers so launch-critical API responses preserve or create `X-Request-ID` and always include `X-Content-Type-Options=nosniff`.
- Fixed `AI Lab` result-copy feedback so clipboard permission denial no longer shows a false success toast.
- Added backend coverage for product-smoke API header expectations and frontend coverage for successful and rejected clipboard writes.
- Refreshed live AutoResearch source evidence with Veritas `HEAD` `8e431b6abe550c64c76d94d4d125e23cab1c1518`.

### Verification
- Baseline product smoke failed on missing headers: `var/desci-ailab-copy-baseline-product-2026-06-06.json`.
- Product smoke after variant -> `5/5 passed`: `var/desci-operational-headers-ailab-copy-product-smoke-2026-06-06.json`.
- Backend focused test -> `1 passed`.
- `AILab` focused tests -> `4 passed`.
- Focused ESLint for changed frontend files -> PASS.
- Direct Playwright click evidence: baseline false success screenshot `var/desci-ailab-copy-baseline-click-2026-06-06.png`; variant failure-feedback screenshot `var/desci-ailab-copy-variant-click-2026-06-06.png`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_OPERATIONAL_HEADERS_AILAB_COPY_2026-06-06.md`.

## 2026-06-06 (Recommendation Backend Fallback)

### Scope
- `apps/desci-platform/frontend/src/components/dashboard/RecommendationList.jsx`
- `apps/desci-platform/frontend/src/i18n/messages.js`
- `apps/desci-platform/frontend/src/__tests__/components/DashboardLists.test.jsx`

### Changes
- Added a recommendation-card error state so `/notices` transport failures render an actionable localized backend-unavailable fallback instead of the normal empty recommendations state.
- Preserved successful notice-card rendering, true empty-array rendering, and server-response `detail` plus `request_id` support ids.
- Added focused regressions for successful recommendations, no-response backend failure, and server-error support ids.
- Refreshed source evidence with Veritas live `HEAD` `7ef8678b2e821653992b4e093158724ae3e046b0`.

### Verification
- `cmd /c "npx vitest run src/__tests__/components/DashboardLists.test.jsx --pool=forks --maxWorkers=1 --isolate"` -> `6 passed`.
- `cmd /c "npx eslint src/components/dashboard/RecommendationList.jsx src/__tests__/components/DashboardLists.test.jsx"` -> PASS.
- Direct Playwright browser evidence -> `var\desci-recommendation-fallback-browser-2026-06-06.json` with `recommendation_fallback_visible=true`, `recommendation_empty_absent=true`, `raw_failed_fetch_absent=true`, `vc_fallback_visible=true`.
- DeSci release-readiness contracts -> `142 passed`.
- DeSci canonical smoke -> `8/8 PASS` via `var\workspace-smoke-desci-recommendation-fallback-2026-06-06.json`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_RECOMMENDATION_FALLBACK_2026-06-06.md`.

## 2026-06-06 (VC Match Backend Fallback)

### Scope
- `apps/desci-platform/frontend/src/components/dashboard/VCMatchList.jsx`
- `apps/desci-platform/frontend/src/__tests__/components/DashboardLists.test.jsx`

### Changes
- Added a `VCMatchList` no-response error adapter so backend-unavailable states show the localized VC matching fallback instead of raw `Failed to fetch`.
- Kept server-response errors on the existing support formatter path, preserving backend detail and support ids.
- Added focused regressions for both the backend-unavailable fallback and API response support-id branch.
- Refreshed source evidence with Veritas live `HEAD` `73a27e2b5d3eb9ac8fad2d5b245947114ec3feb1`.

### Verification
- `cmd /c "npx vitest run src/__tests__/components/DashboardLists.test.jsx --pool=forks --maxWorkers=1 --isolate"` -> `4 passed`.
- `cmd /c "npx eslint src/components/dashboard/VCMatchList.jsx src/__tests__/components/DashboardLists.test.jsx"` -> PASS.
- Direct Playwright MCP `/dashboard` QA with a closed API base -> localized VC fallback visible and page body `Failed to fetch` check false.
- DeSci canonical smoke -> `8/8 PASS` via `var\workspace-smoke-desci-vcmatch-fallback-2026-06-06.json`.
- DeSci launch secret scan -> `status=valid findings=0 missing=0 scanned=13` via `var\desci-launch-secret-scan-vcmatch-fallback-2026-06-06.json`.
- Real handoff wrapper -> `ok=true`, `live_source_status=current`, `recorded_latest_observed_commit=73a27e2b5d3eb9ac8fad2d5b245947114ec3feb1`, `secret_scan.state=valid`, `secret_scan.scanned=14`, and `unexpected_failed_checks=[]`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_VCMATCH_FALLBACK_2026-06-06.md`.

## 2026-06-06 (Handoff Refresh Status Gate)

### Scope
- `ops/scripts/auto_research_status.py`
- `ops/scripts/desci_launch_handoff_refresh.py`
- `tests/test_auto_research_status.py`
- `tests/test_desci_launch_handoff_refresh.py`

### Changes
- Added AutoResearch status gates for the DeSci handoff-refresh bundle: `desci_launch_handoff_refresh_ready` and `desci_launch_handoff_refresh_source_fields_ready`.
- Validated the bundle's topic, live-source state, secret-scan state, expected bootstrap self-check handling, source commit, nested radar metadata, radar JSON commit, radar paths, and auto-refresh flags.
- Made the wrapper converge one final status pass after the final bundle write so status JSON and bundle evidence settle on `status=ok`.
- Made DeSci launch secret-scan selection prefer the handoff-refresh scan when present, because it is the bundle-covering 14-target launch scan.
- Refreshed source evidence with Veritas live `HEAD` `f4028bd484f9b24d4720fe465802b3a259ac5c0b`.

### Verification
- `python -m py_compile ops\scripts\auto_research_status.py ops\scripts\desci_launch_handoff_refresh.py tests\test_auto_research_status.py tests\test_desci_launch_handoff_refresh.py` -> PASS.
- DeSci-focused status/wrapper tests -> `17 passed`.
- Radar/status/scanner/wrapper regression -> `83 passed`.
- Workspace smoke -> `8/8 PASS` via `var\workspace-smoke-workspace-2026-06-06-desci-handoff-refresh-status-gate.json`.
- Real wrapper: `var\desci-launch-handoff-refresh-2026-06-06.json` -> `ok=true`, `status=ok`, `topic=DeSci`, `live_source_status=current`, `radar_auto_refreshed=false`, `secret_scan=valid`, `findings=0`, `missing=0`, `scanned=14`.
- Real status gates -> `PASS desci_launch_handoff_secret_scan_ready`, `PASS desci_launch_handoff_refresh_ready`, and `PASS desci_launch_handoff_refresh_source_fields_ready`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_HANDOFF_REFRESH_STATUS_GATE_2026-06-06.md`.

## 2026-06-06 (Handoff Report Path And Readiness Fallback)

### Scope
- `ops/scripts/desci_launch_handoff_refresh.py`
- `tests/test_desci_launch_handoff_refresh.py`
- `apps/desci-platform/frontend/src/components/ProductReadinessPanel.jsx`
- `apps/desci-platform/frontend/src/__tests__/components/ProductReadinessPanel.test.jsx`

### Changes
- Added `bundle_json_path` to the DeSci handoff bundle and `bundle=...` to CLI output, adapting the Veritas v8.621 active report-path visibility pattern.
- Kept global support-error formatting unchanged, but made ProductReadiness prefer its operator fallback when `/ready` fails before any API response is available.
- Removed the ProductReadiness support formatter mock so the focused component test covers the real network-error path.
- Refreshed source evidence with Veritas live `HEAD` `f6eedec8988f017544bcb0bad54667b512bab677`.

### Verification
- `python -m py_compile ops\scripts\desci_launch_handoff_refresh.py tests\test_desci_launch_handoff_refresh.py` -> PASS.
- Wrapper tests -> `7 passed`.
- DeSci-focused status/scanner/wrapper tests -> `15 passed, 54 deselected`.
- Radar/status/scanner/wrapper regression -> `75 passed`.
- ProductReadiness focused tests -> `5 passed`.
- ProductReadiness focused ESLint -> PASS.
- Direct Playwright MCP `/dashboard` QA clicked `새로고침` and confirmed the ProductReadiness fallback note stayed actionable instead of raw `Failed to fetch`.
- DeSci canonical smoke -> `8/8 PASS` via `var\workspace-smoke-desci-handoff-report-path-2026-06-06.json`.
- Workspace smoke -> `8/8 PASS` via `var\workspace-smoke-workspace-2026-06-06-handoff-report-path.json`.
- DeSci launch secret scan -> `status=valid findings=0 missing=0 scanned=13` via `var\desci-launch-secret-scan-handoff-report-path-2026-06-06.json`.
- Real wrapper: `var\desci-launch-handoff-refresh-2026-06-06.json` -> `ok=true`, `bundle_json_path=var/desci-launch-handoff-refresh-2026-06-06.json`, `recorded_latest_observed_commit=f6eedec8988f017544bcb0bad54667b512bab677`, `radar_auto_refreshed=True`, `secret_scan=valid`, `findings=0`, `missing=0`, `scanned=14`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_HANDOFF_REPORT_PATH_READINESS_FALLBACK_2026-06-06.md`.

## 2026-06-06 (Launch Handoff Refresh)

### Scope
- `ops/scripts/desci_launch_handoff_refresh.py`
- `tests/test_desci_launch_handoff_refresh.py`

### Changes
- Added a one-command DeSci handoff refresh wrapper that converges radar, status, and no-value secret-scan evidence.
- The wrapper requires live Veritas source freshness by default, auto-refreshes missing/stale DeSci radar evidence, pre-scans before status, scans generated outputs, then writes a final bundle.
- The bundle fails closed on wrong topic, stale live source, unexpected status failures, missing scan targets, and secret findings.
- Refreshed source evidence with Veritas live `HEAD` `26f0cb9c4a57c03a7f50f41317da8510d581417a` and agent-readiness `HEAD` `aedf9bbebfce162aadbf9c2f5647c15a3fafd657`.

### Verification
- `python -m py_compile ops\scripts\desci_launch_handoff_refresh.py tests\test_desci_launch_handoff_refresh.py` -> PASS.
- Wrapper tests -> `7 passed`.
- DeSci-focused status/scanner/wrapper tests -> `15 passed`.
- Radar/status/scanner/wrapper regression -> `75 passed`.
- Workspace smoke -> `8/8 PASS` via `var\workspace-smoke-workspace-2026-06-06-desci-handoff-refresh.json`.
- Real wrapper: `var\desci-launch-handoff-refresh-2026-06-06.json` -> `ok=true`, `status=ok`, `topic=DeSci`, `live_source_status=current`, `secret_scan=valid`, `findings=0`, `missing=0`, `scanned=14`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_HANDOFF_REFRESH_2026-06-06.md`.

## 2026-06-06 (Secret Scan Status Gate)

### Scope
- `ops/scripts/auto_research_status.py`
- `tests/test_auto_research_status.py`

### Changes
- Added DeSci topic operator-status gate `desci_launch_handoff_secret_scan_ready`.
- Added `## DeSci Launch Evidence` to DeSci operator-status Markdown.
- The gate requires the latest `var/desci-launch-secret-scan*.json` to be `status=valid`, `ok=true`, have no findings, have no missing paths, and scan at least 13 targets.
- Loaded scan findings are sanitized to pattern/path metadata so malformed scan JSON cannot echo a raw secret value through status output.
- Refreshed source evidence with Veritas live `HEAD` `a8a7d1f1fac16c7224e665c604caed0bfa33857a` and agent-readiness `HEAD` `aedf9bbebfce162aadbf9c2f5647c15a3fafd657`.

### Verification
- `python -m py_compile ops\scripts\auto_research_status.py tests\test_auto_research_status.py` -> PASS.
- DeSci-focused status tests -> `5 passed`.
- Full AutoResearch status tests -> `58 passed`.
- Radar/status/scanner regression -> `67 passed`.
- Final workspace smoke: `var\workspace-smoke-workspace-2026-06-06-desci-secret-scan-status-gate-final.json` -> `8/8 PASS`.
- Real status gate: `PASS desci_launch_handoff_secret_scan_ready`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_SECRET_SCAN_STATUS_GATE_2026-06-06.md`.

## 2026-06-06 (Launch Secret Scan)

### Scope
- `ops/scripts/desci_launch_secret_scan.py`
- `tests/test_desci_launch_secret_scan.py`

### Changes
- Added a DeSci-specific launch handoff secret scan that covers current report, operator status, radar, browser smoke, workspace smoke, deploy-readiness, QC log, devlog, next-actions, and handoff artifacts.
- The scanner records only pattern names and paths, never matched values.
- Covered DeSci launch secret shapes for Stripe keys, webhook secrets, EVM deployer private keys, Firebase private key blocks, provider RPC project URLs, Railway/Vercel tokens, and shared provider/token/database patterns.
- Refreshed source evidence with Veritas live `HEAD` `2e5e8f49c59bb9a9bcd1c036cf3cac01a3a4c5d2` and agent-readiness `HEAD` `aedf9bbebfce162aadbf9c2f5647c15a3fafd657`.

### Verification
- `python -m py_compile ops\scripts\desci_launch_secret_scan.py tests\test_desci_launch_secret_scan.py` -> PASS.
- Focused scanner tests -> `3 passed`.
- Radar/status/scanner regression -> `63 passed`.
- Real DeSci launch scan: `var\desci-launch-secret-scan-2026-06-06.json` -> `status=valid findings=0 missing=0 scanned=13`.
- Final workspace smoke: `var\workspace-smoke-workspace-2026-06-06-desci-launch-secret-scan-final.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-launch-secret-scan-2026-06-06.json` -> 8 adopted sources; `var\auto-research-status-desci-launch-secret-scan-2026-06-06.json` -> `status=ok`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_LAUNCH_SECRET_SCAN_2026-06-06.md`.

## 2026-06-06 (Launch Action Copy Failure Browser Proof)

### Scope
- `scripts/browser_smoke.py`
- `backend/tests/test_browser_smoke.py`
- `ops/references/github_modernization_sources.json`

### Changes
- Added `dashboard-readiness-copy-failure` to dev-auth browser smoke.
- The new route browser-proves that Stripe action copy denial shows `role=alert` feedback.
- The same route browser-proves that `Copy all` denial shows full-queue failure feedback.
- Preserved the existing successful clipboard payload route as a separate proof path.
- Refreshed source evidence with Veritas live `HEAD` `8a10b58460fd1de40e79480ab4bc6cfd95c349ec` and agent-readiness `HEAD` `aedf9bbebfce162aadbf9c2f5647c15a3fafd657`.

### Verification
- `python -m py_compile apps\desci-platform\scripts\browser_smoke.py` -> PASS.
- Browser-smoke contracts -> `12 passed`.
- Dev-auth browser proof: `var\desci-browser-smoke-launch-action-copy-failure-2026-06-06.json` -> `42/42 PASS`.
- DeSci canonical smoke: `var\workspace-smoke-desci-2026-06-06-launch-action-copy-failure-browser.json` -> `8/8 PASS`.
- Final workspace smoke: `var\workspace-smoke-workspace-2026-06-06-launch-action-copy-failure-browser-final.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-launch-action-copy-failure-browser-2026-06-06.json` -> 8 adopted sources; `var\auto-research-status-desci-launch-action-copy-failure-browser-2026-06-06.json` -> `status=ok`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_LAUNCH_ACTION_COPY_FAILURE_BROWSER_2026-06-06.md`.

## 2026-06-06 (Launch Action Copy Feedback)

### Scope
- `frontend/src/components/ProductReadinessPanel.jsx`
- `frontend/src/__tests__/components/ProductReadinessPanel.test.jsx`
- `scripts/browser_smoke.py`
- `ops/references/github_modernization_sources.json`

### Changes
- Added visible and assistive-technology-friendly copy feedback to the ProductReadiness launch action queue.
- Successful single-action and `Copy all` flows now announce what was copied.
- Clipboard write failures now show an actionable alert instead of silently clearing state.
- Added timeout cleanup for copy feedback state.
- Refreshed source evidence with Veritas live `HEAD` `d24f6f0ec19320b7a9489745dd5eb5663a686f6a` and agent-readiness `HEAD` `aedf9bbebfce162aadbf9c2f5647c15a3fafd657`.

### Verification
- `python -m py_compile apps\desci-platform\scripts\browser_smoke.py` -> PASS.
- Browser-smoke contracts -> `12 passed`.
- ProductReadinessPanel focused tests -> `5 passed`.
- Frontend lint/build -> PASS.
- Dev-auth browser proof: `var\desci-browser-smoke-launch-action-copy-feedback-2026-06-06.json` -> `41/41 PASS`.
- DeSci canonical smoke: `var\workspace-smoke-desci-2026-06-06-launch-action-copy-feedback.json` -> `8/8 PASS`.
- Final workspace smoke: `var\workspace-smoke-workspace-2026-06-06-launch-action-copy-feedback-final.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-launch-action-copy-feedback-2026-06-06.json` -> 8 adopted sources; `var\auto-research-status-desci-launch-action-copy-feedback-2026-06-06.json` -> `status=ok`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_LAUNCH_ACTION_COPY_FEEDBACK_2026-06-06.md`.

## 2026-06-06 (Launch Action Accessibility)

### Scope
- `frontend/src/components/ProductReadinessPanel.jsx`
- `frontend/src/__tests__/components/ProductReadinessPanel.test.jsx`
- `scripts/browser_smoke.py`
- `ops/references/github_modernization_sources.json`

### Changes
- Added distinct accessible names to each ProductReadiness launch action copy button.
- Added a distinct accessible name to the queue-level `Copy all` button with the current action count.
- Focused component tests now assert the action-specific button names.
- Dev-auth browser smoke now queries the copy controls by role/name to prove the accessibility tree exposes unambiguous labels.
- Refreshed source evidence with Veritas live `HEAD` `d814262c82e0d6e9ca3827ebf2fa0b4796f55db6` and agent-readiness `HEAD` `aedf9bbebfce162aadbf9c2f5647c15a3fafd657`.

### Verification
- `python -m py_compile apps\desci-platform\scripts\browser_smoke.py` -> PASS.
- Browser-smoke contracts -> `12 passed`.
- ProductReadinessPanel focused tests -> `4 passed`.
- Frontend lint/build -> PASS.
- Dev-auth browser proof: `var\desci-browser-smoke-launch-action-a11y-2026-06-06.json` -> `41/41 PASS`.
- DeSci canonical smoke: `var\workspace-smoke-desci-2026-06-06-launch-action-a11y.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-launch-action-a11y-2026-06-06.json` -> 8 adopted sources; `var\auto-research-status-desci-launch-action-a11y-2026-06-06.json` -> `status=ok`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_LAUNCH_ACTION_A11Y_2026-06-06.md`.

## 2026-06-06 (Launch Action Copy All)

### Scope
- `frontend/src/components/ProductReadinessPanel.jsx`
- `frontend/src/__tests__/components/ProductReadinessPanel.test.jsx`
- `scripts/browser_smoke.py`
- `ops/references/github_modernization_sources.json`

### Changes
- Added a `Copy all` button to the ProductReadiness launch action queue.
- The combined payload includes every failed or warning launch action with label, priority, status, remediation, and required env names.
- Added focused component coverage for combined Stripe billing, Stripe return URL, Stripe portal configuration, and Web3 payload content.
- Extended dev-auth browser smoke to click `Copy all`, read the clipboard, and reject Stripe secret-shaped values.
- Refreshed source evidence with Veritas live `HEAD` `1e54418e21a42bfa452c7cd8f46c403cdf2a3fff` and agent-readiness `HEAD` `aedf9bbebfce162aadbf9c2f5647c15a3fafd657`.

### Verification
- `python -m py_compile apps\desci-platform\scripts\browser_smoke.py` -> PASS.
- Browser-smoke contracts -> `12 passed`.
- ProductReadinessPanel focused tests -> `4 passed`.
- Frontend lint/build -> PASS.
- Dev-auth browser proof: `var\desci-browser-smoke-launch-action-copy-all-2026-06-06.json` -> `41/41 PASS`.
- DeSci canonical smoke: `var\workspace-smoke-desci-2026-06-06-launch-action-copy-all.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-launch-action-copy-all-2026-06-06.json` -> 8 adopted sources; `var\auto-research-status-desci-launch-action-copy-all-2026-06-06.json` -> `status=ok`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_LAUNCH_ACTION_COPY_ALL_2026-06-06.md`.

## 2026-06-06 (Stripe Portal Configuration)

### Scope
- `backend/routers/subscription.py`
- `backend/main.py`
- `backend/tests/test_router_edge_cases.py`
- `backend/tests/test_api_endpoints.py`
- `frontend/src/components/ProductReadinessPanel.jsx`
- `frontend/src/__tests__/components/ProductReadinessPanel.test.jsx`
- `scripts/browser_smoke.py`
- `ops/references/github_modernization_sources.json`

### Changes
- Billing Portal session creation now passes `configuration` when `STRIPE_PORTAL_CONFIGURATION_ID` is set.
- Production `/ready` now emits optional `stripe_portal` warning/remediation when an explicit Billing Portal configuration ID is not set.
- ProductReadiness labels the warning as `Stripe portal configuration`.
- Browser smoke proves the dashboard launch action queue renders `STRIPE_PORTAL_CONFIGURATION_ID` and default-portal guidance.
- Refreshed source evidence with Veritas live `HEAD` `d814262c82e0d6e9ca3827ebf2fa0b4796f55db6`.

### Verification
- `python -m py_compile apps\desci-platform\backend\main.py apps\desci-platform\backend\routers\subscription.py apps\desci-platform\scripts\browser_smoke.py` -> PASS.
- Router edge tests -> `26 passed`; API endpoint tests -> `40 passed`; browser/API contracts -> `52 passed`.
- ProductReadinessPanel focused tests -> `4 passed`.
- Frontend lint/build -> PASS.
- Dev-auth browser proof: `var\desci-browser-smoke-stripe-portal-configuration-2026-06-06.json` -> `41/41 PASS`.
- DeSci canonical smoke: `var\workspace-smoke-desci-2026-06-06-stripe-portal-configuration.json` -> `8/8 PASS`.
- Workspace smoke: `var\workspace-smoke-workspace-2026-06-06-stripe-portal-configuration.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-stripe-portal-configuration-2026-06-06.json` -> 8 adopted sources; `var\auto-research-status-desci-stripe-portal-configuration-2026-06-06.json` -> `status=ok`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_STRIPE_PORTAL_CONFIGURATION_2026-06-06.md`.

## 2026-06-06 (Launch Action Copy)

### Scope
- `frontend/src/components/ProductReadinessPanel.jsx`
- `frontend/src/__tests__/components/ProductReadinessPanel.test.jsx`
- `scripts/browser_smoke.py`
- `ops/references/github_modernization_sources.json`

### Changes
- Added copy buttons to ProductReadiness launch action queue items.
- The copied payload includes readiness label, priority, status, remediation, and required env names.
- Added focused component coverage proving the Stripe copied payload includes launch env names/remediation and no Stripe secret-shaped value.
- Extended dev-auth browser smoke to grant clipboard permissions, click the Stripe copy button, and validate the clipboard payload in Chromium.
- Refreshed source evidence with Veritas live `HEAD` `c0de5896d1d911f677f7c2c64f0442f02d658fe1` and agent-readiness `HEAD` `aedf9bbebfce162aadbf9c2f5647c15a3fafd657`.

### Verification
- `python -m py_compile apps\desci-platform\scripts\browser_smoke.py` -> PASS.
- Browser-smoke contracts -> `12 passed`.
- ProductReadinessPanel focused tests -> `4 passed`.
- Frontend lint/build -> PASS.
- Dev-auth browser proof: `var\desci-browser-smoke-launch-action-copy-2026-06-06.json` -> `41/41 PASS`.
- DeSci canonical smoke: `var\workspace-smoke-desci-2026-06-06-launch-action-copy.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-launch-action-copy-2026-06-06.json` -> 8 adopted sources; `var\auto-research-status-desci-launch-action-copy-2026-06-06.json` -> `status=ok`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_LAUNCH_ACTION_COPY_2026-06-06.md`.

## 2026-06-06 (Stripe Return URL Product Readiness)

### Scope
- `backend/main.py`
- `backend/tests/test_api_endpoints.py`
- `frontend/src/components/ProductReadinessPanel.jsx`
- `frontend/src/__tests__/components/ProductReadinessPanel.test.jsx`
- `scripts/browser_smoke.py`
- `ops/references/github_modernization_sources.json`

### Changes
- Added a required `/ready` check named `stripe_return_url` so ProductReadiness blocks paid launch when production `DESCI_FRONTEND_URL` is missing or unsafe.
- The check reuses the same public HTTPS origin rules as the preflight/runtime Stripe return URL guards.
- Added frontend label/test coverage so the launch action queue renders the `DESCI_FRONTEND_URL` remediation.
- Extended dev-auth browser smoke to prove the dashboard readiness refresh renders the Stripe return URL action in Chromium.
- Refreshed source evidence with Veritas live `HEAD` `c0de5896d1d911f677f7c2c64f0442f02d658fe1`.

### Verification
- `python -m py_compile apps\desci-platform\backend\main.py apps\desci-platform\scripts\browser_smoke.py` -> PASS.
- API endpoint tests -> `38 passed`; browser/API contracts -> `50 passed`; release/product/docs contracts -> `69 passed`.
- ProductReadinessPanel focused tests -> `4 passed`.
- Frontend lint/build -> PASS.
- Dev-auth browser proof: `var\desci-browser-smoke-stripe-return-url-product-readiness-2026-06-06.json` -> `41/41 PASS`.
- DeSci canonical smoke: `var\workspace-smoke-desci-2026-06-06-stripe-return-url-product-readiness.json` -> `8/8 PASS`.
- Workspace smoke: `var\workspace-smoke-workspace-2026-06-06-stripe-return-url-product-readiness.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-stripe-return-url-product-readiness-2026-06-06.json` -> 8 adopted sources; `var\auto-research-status-desci-stripe-return-url-product-readiness-2026-06-06.json` -> `status=ok`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_STRIPE_RETURN_URL_PRODUCT_READINESS_2026-06-06.md`.

## 2026-06-06 (Launch Action Queue)

### Scope
- `frontend/src/components/ProductReadinessPanel.jsx`
- `frontend/src/__tests__/components/ProductReadinessPanel.test.jsx`
- `scripts/browser_smoke.py`
- `ops/references/github_modernization_sources.json`

### Changes
- Added a dashboard launch action queue derived from failed or warning `/ready` checks.
- The queue renders required/optional badges, readiness labels, remediation, and required env names so operators do not have to scan every readiness card.
- Added ProductReadinessPanel regression coverage for failed Stripe and warning Web3 actions.
- Extended dev-auth browser smoke to prove the dashboard renders the Stripe action queue with `STRIPE_WEBHOOK_SECRET` and Pro Price ID guidance.
- Refreshed source evidence with Veritas live `HEAD` `34d3ccd680c6989e4b586d67761ebd1974db33f6` and agent-readiness `HEAD` `aedf9bbebfce162aadbf9c2f5647c15a3fafd657`.

### Verification
- `python -m py_compile apps\desci-platform\scripts\browser_smoke.py` -> PASS.
- Browser-smoke contracts -> `12 passed`.
- ProductReadinessPanel focused tests -> `4 passed`.
- Frontend lint/build -> PASS.
- Dev-auth browser proof: `var\desci-browser-smoke-launch-action-queue-2026-06-06.json` -> `41/41 PASS`.
- DeSci canonical smoke: `var\workspace-smoke-desci-2026-06-06-launch-action-queue.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-launch-action-queue-2026-06-06.json` -> 8 adopted sources; `var\auto-research-status-desci-launch-action-queue-2026-06-06.json` -> `status=ok`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_LAUNCH_ACTION_QUEUE_2026-06-06.md`.

## 2026-06-06 (Stripe Return URL Runtime Guard)

### Scope
- `backend/routers/subscription.py`
- `backend/tests/test_router_edge_cases.py`
- `ops/references/github_modernization_sources.json`

### Changes
- Added a production-only runtime guard for Stripe return origins.
- Checkout and Billing Portal session creation now reject unsafe production `DESCI_FRONTEND_URL` values before customer lookup or Stripe session creation.
- Unsafe production origins include localhost, reserved documentation/example domains, non-HTTPS URLs, and path-bearing frontend URLs.
- Local/development smoke keeps the existing localhost fallback behavior.
- Refreshed source evidence with Veritas live `HEAD` `d57446610c7a48260dcd2d01dd0ae5e4edb8fc9a`.

### Verification
- `python -m py_compile apps\desci-platform\backend\routers\subscription.py` -> PASS.
- Router edge tests -> `25 passed`.
- Broader backend launch slice -> `115 passed`.
- DeSci canonical smoke: `var\workspace-smoke-desci-2026-06-06-stripe-return-url-runtime-guard.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-stripe-return-url-runtime-guard-2026-06-06.json` -> 8 adopted sources; `var\auto-research-status-desci-stripe-return-url-runtime-guard-2026-06-06.json` -> `status=ok`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_STRIPE_RETURN_URL_RUNTIME_GUARD_2026-06-06.md`.

## 2026-06-06 (Stripe Return URL Readiness)

### Scope
- `scripts/env_doctor.py`
- `scripts/deploy_readiness.py`
- `backend/tests/test_env_doctor.py`
- `backend/tests/test_deploy_readiness.py`
- `backend/tests/test_deployment_docs.py`
- `README.md`
- `DEPLOYMENT_GUIDE.md`
- `OPERATIONS_RUNBOOK.md`
- `ops/references/github_modernization_sources.json`

### Changes
- Added production `frontend_return_url` env-doctor coverage for `DESCI_FRONTEND_URL`.
- Added Railway `railway_frontend_return_url` deploy-readiness coverage for the same value.
- `DESCI_FRONTEND_URL` must now be a public `https://` frontend origin without paths, queries, fragments, localhost, or example domains.
- Updated docs so operators know the value drives Stripe Checkout success/cancel URLs and Billing Portal return URLs.
- Refreshed source evidence with Veritas live `HEAD` `d57446610c7a48260dcd2d01dd0ae5e4edb8fc9a`.

### Verification
- `python -m py_compile apps\desci-platform\scripts\env_doctor.py apps\desci-platform\scripts\deploy_readiness.py` -> PASS.
- Env/deploy/docs focused tests -> `50 passed`.
- Production example env doctor evidence: `var\desci-env-doctor-production-example-stripe-return-url-readiness-2026-06-06.json` -> expected fail includes `frontend_return_url`.
- Production example Railway readiness evidence: `var\desci-deploy-readiness-railway-production-example-stripe-return-url-readiness-2026-06-06.json` -> expected fail includes `railway_frontend_return_url`.
- Release-gate/product-smoke contracts -> `63 passed`.
- DeSci canonical smoke: `var\workspace-smoke-desci-2026-06-06-stripe-return-url-readiness.json` -> `8/8 PASS`.
- Workspace smoke: `var\workspace-smoke-workspace-2026-06-06-stripe-return-url-readiness.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-stripe-return-url-readiness-2026-06-06.json` -> 8 adopted sources; `var\auto-research-status-desci-stripe-return-url-readiness-2026-06-06.json` -> `status=ok`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_STRIPE_RETURN_URL_READINESS_2026-06-06.md`.

## 2026-06-06 (Stripe Webhook Signed Event)

### Scope
- `backend/tests/test_router_edge_cases.py`
- `ops/references/github_modernization_sources.json`

### Changes
- Added production signed-webhook regression coverage proving `stripe.Webhook.construct_event` is the trusted event source.
- The signed-event test sends untrusted raw metadata and verifies tier/customer updates use only the verified event returned by Stripe.
- Added invalid-signature coverage that returns `400` and leaves subscription state untouched.
- Refreshed source evidence with Veritas live `HEAD` `88405accfd3d1ad6f6e07ff7ad2afb8d743856d3` and agent-readiness `HEAD` `aedf9bbebfce162aadbf9c2f5647c15a3fafd657`.

### Verification
- `python -m py_compile apps\desci-platform\backend\routers\subscription.py` -> PASS.
- `python -m pytest apps\desci-platform\backend\tests\test_router_edge_cases.py -q -p no:cacheprovider` -> `21 passed`.
- `python -m pytest apps\desci-platform\backend\tests\test_router_edge_cases.py apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `33 passed`.
- `python -m pytest apps\desci-platform\backend\tests\test_api_endpoints.py apps\desci-platform\backend\tests\test_deploy_readiness.py apps\desci-platform\backend\tests\test_env_doctor.py apps\desci-platform\backend\tests\test_router_edge_cases.py apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `109 passed`.
- Dev-auth browser proof: `var\desci-browser-smoke-stripe-webhook-signed-event-2026-06-06.json` -> `41/41 PASS`.
- Canonical DeSci smoke: `var\workspace-smoke-desci-2026-06-06-stripe-webhook-signed-event.json` -> `8/8 PASS`.
- Workspace smoke: `var\workspace-smoke-workspace-2026-06-06-stripe-webhook-signed-event-final.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-stripe-webhook-signed-event-2026-06-06.json` -> 8 adopted sources; `var\auto-research-status-desci-stripe-webhook-signed-event-2026-06-06.json` -> `status=ok`.
- Handoff/radar/status contracts: `38 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_STRIPE_WEBHOOK_SIGNED_EVENT_2026-06-06.md`.

## 2026-06-06 (Pricing Billing Portal Error Browser Proof)

### Scope
- `frontend/src/__tests__/components/PricingPage.test.jsx`
- `frontend/src/components/Notices.jsx`
- `scripts/browser_smoke.py`
- `backend/tests/test_browser_smoke.py`
- `ops/scripts/auto_research_status.py`
- `ops/references/github_modernization_sources.json`

### Changes
- Added `pricing-billing-portal-error-visible` to authenticated browser smoke.
- The check fixtures a paid `pro` user, forces `/subscription/portal` to return `503`, clicks `Manage billing`, verifies API detail in `pricing-checkout-error`, stays on `/pricing`, and rejects success/cancel UI.
- Added PricingPage unit coverage for Billing Portal API failure feedback.
- Added stable notice-card `data-testid` selectors and updated `notices-biolinker-bridge` to click the exact fixture card instead of the last visible Analyze Fit button.
- Made AutoResearch status JSON reads BOM-aware so UTF-16 JSON artifacts from Windows/PowerShell do not block status generation.
- Refreshed source evidence with Veritas live `HEAD` `ee19365b24457f7c9965c010075b40a86783abce` and agent-readiness `HEAD` `aedf9bbebfce162aadbf9c2f5647c15a3fafd657`.

### Verification
- `python -m py_compile apps\desci-platform\scripts\browser_smoke.py` -> PASS.
- `python -m pytest apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `12 passed`.
- `cmd /c npm run test -- src/__tests__/components/PricingPage.test.jsx src/__tests__/components/Notices.test.jsx` -> `12 passed`.
- Dev-auth browser proof: `var\desci-browser-smoke-pricing-billing-portal-error-2026-06-06-pass.json` -> `41/41 PASS`.
- `cmd /c npm run lint` -> PASS.
- `cmd /c npm run build` -> PASS.
- DeSci canonical smoke: `var\workspace-smoke-desci-2026-06-06-pricing-billing-portal-error.json` -> `8/8 PASS`.
- Workspace smoke: `var\workspace-smoke-workspace-2026-06-06-pricing-billing-portal-error-final.json` -> `8/8 PASS`.
- `python -m py_compile ops\scripts\auto_research_status.py` -> PASS.
- `python -m pytest tests\test_auto_research_status.py -q -p no:cacheprovider` -> `30 passed`.
- Radar/status: `var\github-modernization-radar-desci-pricing-billing-portal-error-2026-06-06.json` -> 8 adopted sources; `var\auto-research-status-desci-pricing-billing-portal-error-2026-06-06.json` -> `status=ok`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_PRICING_BILLING_PORTAL_ERROR_BROWSER_2026-06-06.md`.

## 2026-06-06 (Stripe Webhook Fail-Closed)

### Scope
- `backend/routers/subscription.py`
- `backend/tests/test_router_edge_cases.py`
- `ops/references/github_modernization_sources.json`

### Changes
- Added a production environment guard to Stripe webhook handling.
- Production webhooks now return `503` when Stripe is not configured.
- Production webhooks now return `503` when `STRIPE_WEBHOOK_SECRET` is missing, instead of accepting unsigned JSON.
- Preserved the unsigned JSON webhook fallback for local development smoke and edge-case tests.
- Refreshed source evidence with Veritas live `HEAD` `0c454579d36bb91d96ededc88f3f6fb17d933efe` and agent-readiness `HEAD` `aedf9bbebfce162aadbf9c2f5647c15a3fafd657`.

### Verification
- `python -m py_compile apps\desci-platform\backend\routers\subscription.py` -> PASS.
- `python -m pytest apps\desci-platform\backend\tests\test_router_edge_cases.py -q -p no:cacheprovider` -> `19 passed`.
- `python -m pytest apps\desci-platform\backend\tests\test_router_edge_cases.py apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `31 passed`.
- `python -m pytest apps\desci-platform\backend\tests\test_api_endpoints.py apps\desci-platform\backend\tests\test_deploy_readiness.py apps\desci-platform\backend\tests\test_env_doctor.py apps\desci-platform\backend\tests\test_router_edge_cases.py apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `107 passed`.
- Dev-auth browser proof: `var\desci-browser-smoke-stripe-webhook-fail-closed-2026-06-06.json` -> `41/41 PASS`.
- Canonical DeSci smoke: `var\workspace-smoke-desci-2026-06-06-stripe-webhook-fail-closed.json` -> `8/8 PASS`.
- Workspace smoke: `var\workspace-smoke-workspace-2026-06-06-stripe-webhook-fail-closed.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-stripe-webhook-fail-closed-2026-06-06.json` -> 8 adopted sources; `var\auto-research-status-desci-stripe-webhook-fail-closed-2026-06-06.json` -> `status=ok`.
- Handoff/radar/status contracts: `35 passed`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_STRIPE_WEBHOOK_FAIL_CLOSED_2026-06-06.md`.

## 2026-06-06 (Pricing Enterprise Contact Browser Proof)

### Scope
- `scripts/browser_smoke.py`
- `backend/tests/test_browser_smoke.py`
- `frontend/src/__tests__/components/PricingPage.test.jsx`
- `ops/references/github_modernization_sources.json`

### Changes
- Added `pricing-enterprise-contact-intent` to public browser smoke.
- The check records `window.open`, clicks the Enterprise CTA, verifies the sales `mailto:` target, stays on `/pricing`, and asserts zero `/subscription/checkout` POSTs.
- Added `/subscription/tier` fixture coverage to `landing-cta-intent` so clicking Pricing from the landing page does not depend on live backend tier fetches during public CTA smoke.
- Added PricingPage unit coverage that Enterprise opens sales contact and does not post checkout.
- Refreshed source evidence with Veritas live `HEAD` `0f159f337a92684be1839c1fc006d629601c63f6`.

### Verification
- `python -m py_compile apps\desci-platform\scripts\browser_smoke.py` -> PASS.
- `python -m pytest apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `12 passed`.
- `cmd /c npm run test -- src/__tests__/components/PricingPage.test.jsx` -> `1 file / 8 tests passed`.
- Dev-auth browser proof: `var\desci-browser-smoke-pricing-enterprise-contact-2026-06-06.json` -> `40/40 PASS`.
- no-dev-auth browser proof: `var\desci-browser-smoke-pricing-enterprise-contact-anonymous-2026-06-06.json` -> `13/13 PASS`.
- `cmd /c npm run lint` -> PASS.
- `cmd /c npm run build` -> PASS.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-06-pricing-enterprise-contact.json` -> `8/8 PASS`.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-06-06-pricing-enterprise-contact.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-pricing-enterprise-contact-2026-06-06.json` -> 8 adopted sources; `var\auto-research-status-desci-pricing-enterprise-contact-2026-06-06.json` -> `status=ok`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_PRICING_ENTERPRISE_CONTACT_BROWSER_2026-06-06.md`.

## 2026-06-06 (Billing Portal Browser Proof)

### Scope
- `backend/routers/subscription.py`
- `backend/services/user_tier.py`
- `backend/tests/test_router_edge_cases.py`
- `frontend/src/components/PricingPage.jsx`
- `frontend/src/__tests__/components/PricingPage.test.jsx`
- `scripts/browser_smoke.py`
- `backend/tests/test_browser_smoke.py`
- `docs/QUALITY_GATE.md`
- `ops/references/github_modernization_sources.json`

### Changes
- Persisted Stripe customer IDs from `checkout.session.completed` webhook payloads.
- Reused linked Stripe customers during checkout session creation instead of creating duplicate customer records.
- Added protected `/subscription/portal` to create Stripe billing portal sessions for linked customers.
- Added a paid-account `Manage billing` action on Pricing.
- Added `pricing-billing-portal` to authenticated browser smoke, proving the visible billing action posts to `/subscription/portal` and follows the mocked portal URL.
- Synced `docs/QUALITY_GATE.md` with the concurrent `getdaytrends provider auth recovery packet` default smoke check so workspace smoke inventory stays current.
- Refreshed source evidence with Veritas live `HEAD` `0a7fbd2f66944d41dcb02e95ce2521660c3abf37`.

### Verification
- `python -m py_compile apps\desci-platform\backend\routers\subscription.py apps\desci-platform\backend\services\user_tier.py apps\desci-platform\scripts\browser_smoke.py` -> PASS.
- `python -m pytest apps\desci-platform\backend\tests\test_router_edge_cases.py apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `29 passed`.
- `cmd /c npm run test -- src/__tests__/components/PricingPage.test.jsx` -> `1 file / 7 tests passed`.
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5175 --expect-dev-auth --timeout 25 --json-out var\desci-browser-smoke-billing-portal-2026-06-06.json` -> `39/39 PASS`.
- `cmd /c npm run lint` -> PASS.
- `cmd /c npm run build` -> PASS.
- `python -m pytest tests\test_workspace_regressions.py tests\test_workspace_smoke.py tests\test_auto_research_status.py -q -p no:cacheprovider` -> `64 passed`.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-06-billing-portal.json` -> `8/8 PASS`.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-06-06-billing-portal.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-billing-portal-2026-06-06.json` -> 8 adopted sources; `var\auto-research-status-desci-billing-portal-2026-06-06.json` -> `status=ok`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_BILLING_PORTAL_2026-06-06.md`.

## 2026-06-06 (Pricing Anonymous Paid Redirect Browser Proof)

### Scope
- `scripts/browser_smoke.py`
- `backend/tests/test_browser_smoke.py`
- `ops/references/github_modernization_sources.json`

### Changes
- Added `ANONYMOUS_ACTION_CHECKS` to keep no-dev-auth browser proof separate from the authenticated checkout smoke suite.
- Added `pricing-anonymous-paid-redirect`, which clicks the Pro pricing CTA as an anonymous user, verifies `/login?next=/pricing&plan=pro`, and asserts that no checkout POST occurs before login.
- Kept the dev-auth checkout smoke at `38/38 PASS` by not mixing anonymous state checks into the dev-auth run.
- Refreshed source evidence with Veritas live `HEAD` `9aeeb1e114a41971de76bd3f801097b849433761`.

### Verification
- `python -m py_compile apps\desci-platform\scripts\browser_smoke.py` -> PASS.
- `python -m pytest apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `12 passed`.
- `cmd /c npm run test -- src/__tests__/components/PricingPage.test.jsx` -> `1 file / 6 tests passed`.
- Dev-auth browser regression: `var\desci-browser-smoke-pricing-anonymous-paid-redirect-dev-auth-regression-2026-06-06.json` -> `38/38 PASS`.
- no-dev-auth anonymous proof: `var\desci-browser-smoke-pricing-anonymous-paid-redirect-2026-06-06.json` -> `12/12 PASS`.
- `cmd /c npm run lint` -> PASS.
- `cmd /c npm run build` -> PASS.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-06-pricing-anonymous-paid-redirect.json` -> `8/8 PASS`.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-06-06-pricing-anonymous-paid-redirect.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-pricing-anonymous-paid-redirect-2026-06-06.json` -> 8 adopted sources; `var\auto-research-status-desci-pricing-anonymous-paid-redirect-2026-06-06.json` -> `status=ok`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_PRICING_ANONYMOUS_PAID_REDIRECT_BROWSER_2026-06-06.md`.

## 2026-06-06 (Stripe Subscription Metadata)

### Scope
- `backend/routers/subscription.py`
- `backend/tests/test_router_edge_cases.py`
- `ops/references/github_modernization_sources.json`

### Changes
- Added a shared checkout metadata payload for `uid`, `target_tier`, and `billing`.
- Passed the same metadata to Stripe Checkout Session `metadata` and `subscription_data.metadata`.
- Added `client_reference_id=uid` to make checkout sessions traceable in Stripe.
- Extended router edge-case coverage so subscription lifecycle metadata cannot regress.
- Refreshed the moving Veritas AutoResearch GitHub source commit in the modernization radar to `dddd2c1d33a11d9e0ca68922794015bc7d083553`.

### Verification
- `python -m py_compile apps\desci-platform\backend\routers\subscription.py apps\desci-platform\scripts\browser_smoke.py` -> PASS.
- `python -m pytest apps\desci-platform\backend\tests\test_router_edge_cases.py apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `25 passed`.
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5175 --expect-dev-auth --json-out var\desci-browser-smoke-stripe-subscription-metadata-2026-06-06.json` -> PASS with checkout success/yearly/cancel/error flows.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-06-stripe-subscription-metadata.json` -> `8/8 PASS`.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-06-06-stripe-subscription-metadata.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-stripe-subscription-metadata-2026-06-06.json` -> 8 adopted sources; `var\auto-research-status-desci-stripe-subscription-metadata-2026-06-06.json` -> `status=ok`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_STRIPE_SUBSCRIPTION_METADATA_2026-06-06.md`.

## 2026-06-06 (Pricing Yearly Checkout Browser Proof)

### Scope
- `frontend/src/components/PricingPage.jsx`
- `scripts/browser_smoke.py`
- `backend/tests/test_browser_smoke.py`

### Changes
- Added stable `pricing-billing-monthly` and `pricing-billing-yearly` selectors to the pricing billing toggle.
- Added `pricing-checkout-yearly` to authenticated browser smoke.
- The yearly smoke selects yearly billing, clicks the Pro CTA, verifies a single checkout POST with `tier=pro` and `billing=yearly`, and confirms success with session `browser-smoke-yearly`.
- Refreshed source evidence with Veritas live `HEAD` `924dffd6e3278c50e4fd79199dee5c0d84d4e202`.

### Verification
- `python -m py_compile apps\desci-platform\scripts\browser_smoke.py` -> PASS.
- `python -m pytest apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `11 passed`.
- `cmd /c npm run test -- src/__tests__/components/PricingPage.test.jsx` -> `1 file / 6 tests passed`.
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5175 --expect-dev-auth --timeout 25 --json-out var\desci-browser-smoke-pricing-yearly-checkout-2026-06-06.json` -> `38/38 PASS`.
- `cmd /c npm run lint` -> PASS.
- `cmd /c npm run build` -> PASS.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-06-pricing-yearly-checkout.json` -> `8/8 PASS`.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-06-06-pricing-yearly-checkout.json` -> `8/8 PASS`.
- Radar: `var\github-modernization-radar-desci-pricing-yearly-checkout-2026-06-06.json` -> 8 adopted sources.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_PRICING_YEARLY_CHECKOUT_BROWSER_2026-06-06.md`.

## 2026-06-06 (Stripe Preflight Alignment)

### Scope
- `scripts/env_doctor.py`
- `scripts/deploy_readiness.py`
- `backend/tests/test_env_doctor.py`
- `backend/tests/test_deploy_readiness.py`
- `README.md`
- `ops/references/github_modernization_sources.json`

### Changes
- Aligned production env doctor and deployment readiness with the runtime `/ready` Stripe launch blocker.
- Added shared Stripe launch key coverage for `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_PRO_MONTHLY`, and `STRIPE_PRICE_PRO_YEARLY`.
- Made production env doctor fail missing Stripe launch config instead of treating it as optional.
- Added required Railway deploy-readiness check `railway_stripe`.
- Moved Stripe paid-checkout keys into the README required production checklist.
- Refreshed the moving Veritas AutoResearch GitHub source commit in the modernization radar to `3c3c079f07a3aa50801e4185168f88de5dde2f4f`.

### Verification
- `python -m py_compile apps\desci-platform\scripts\env_doctor.py apps\desci-platform\scripts\deploy_readiness.py` -> PASS.
- `python -m pytest apps\desci-platform\backend\tests\test_deploy_readiness.py apps\desci-platform\backend\tests\test_env_doctor.py apps\desci-platform\backend\tests\test_deployment_docs.py -q -p no:cacheprovider` -> `48 passed`.
- `python apps\desci-platform\scripts\env_doctor.py --profile production --env-file apps\desci-platform\.env.production.example --ignore-process-env --json-out var\desci-env-doctor-stripe-preflight-example-2026-06-06.json` -> expected fail with required Stripe billing incomplete.
- `python apps\desci-platform\scripts\deploy_readiness.py --target all --env-file apps\desci-platform\.env.production.example --ignore-process-env --json-out var\desci-deploy-readiness-stripe-preflight-example-2026-06-06.json` -> expected fail with required `railway_stripe`.
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5175 --expect-dev-auth --json-out var\desci-browser-smoke-stripe-preflight-alignment-2026-06-06.json` -> `37/37 PASS`.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-06-stripe-preflight-alignment.json` -> `8/8 PASS`.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-06-06-stripe-preflight-alignment.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-stripe-preflight-alignment-2026-06-06.json` -> 8 adopted sources; `var\auto-research-status-desci-stripe-preflight-alignment-2026-06-06.json` -> `status=ok`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_STRIPE_PREFLIGHT_ALIGNMENT_2026-06-06.md`.

## 2026-06-06 (Pricing Checkout Error Browser Proof)

### Scope
- `scripts/browser_smoke.py`
- `backend/tests/test_browser_smoke.py`

### Changes
- Added `pricing-checkout-error-visible` to authenticated browser smoke.
- Mocked `/subscription/checkout` with a `503` response, clicked the Pro CTA, and required the visible `pricing-checkout-error` API detail.
- Asserted the checkout POST remains Pro monthly, the browser stays on `/pricing`, and neither success nor cancellation UI is rendered after the failed API call.
- Filtered only the expected Chromium resource console line generated by the mocked `503` inside this one check.
- Refreshed source evidence with Veritas live `HEAD` `15f8a99ce513d018ff83608412939bfdbeb7eec8`.

### Verification
- `python -m py_compile apps\desci-platform\scripts\browser_smoke.py` -> PASS.
- `python -m pytest apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `11 passed`.
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5175 --expect-dev-auth --timeout 25 --json-out var\desci-browser-smoke-pricing-checkout-error-2026-06-06-rerun.json` -> `37/37 PASS`.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-06-pricing-checkout-error.json` -> `8/8 PASS`.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-06-06-pricing-checkout-error.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-pricing-checkout-error-2026-06-06.json` -> 8 adopted sources; `var\auto-research-status-desci-pricing-checkout-error-2026-06-06.json` -> `status=ok`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_PRICING_CHECKOUT_ERROR_BROWSER_2026-06-06.md`.

## 2026-06-06 (Stripe Readiness Browser Action)

### Scope
- `backend/main.py`
- `backend/tests/conftest.py`
- `backend/tests/test_api_endpoints.py`
- `frontend/src/components/ProductReadinessPanel.jsx`
- `frontend/src/__tests__/components/ProductReadinessPanel.test.jsx`
- `frontend/src/i18n/messages.js`
- `scripts/browser_smoke.py`
- `ops/references/github_modernization_sources.json`

### Changes
- Added required `stripe` launch-readiness coverage for `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_PRO_MONTHLY`, and `STRIPE_PRICE_PRO_YEARLY`.
- Added API coverage proving missing Stripe config blocks `/ready` and appears in `launch_blockers`.
- Added ProductReadiness UI fallback/i18n labels for Stripe billing.
- Updated dashboard-readiness-refresh browser fixtures to verify the Stripe row and required summary.
- Refreshed the moving Veritas AutoResearch GitHub source commit in the modernization radar to `77644f60e75e9fe46db836d9659f8ecc4177613d`.

### Verification
- Manual Playwright check: dashboard `/ready` returned `status=blocked`, blockers `stripe,cors`, visible `Stripe 결제` row, and console warnings/errors `0`.
- `python -m py_compile apps\desci-platform\backend\main.py apps\desci-platform\scripts\browser_smoke.py` -> PASS.
- `python -m pytest apps\desci-platform\backend\tests\test_api_endpoints.py::test_ready_returns_product_readiness_checks apps\desci-platform\backend\tests\test_api_endpoints.py::test_ready_blocks_paid_launch_without_stripe_config apps\desci-platform\backend\tests\test_api_endpoints.py::test_launch_control_returns_operator_decision -q -p no:cacheprovider` -> `3 passed`.
- `python -m pytest apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `11 passed`.
- `cmd /c npm run test -- src/__tests__/components/ProductReadinessPanel.test.jsx src/__tests__/components/Dashboard.test.jsx` -> `2 files / 14 tests passed`.
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5175 --expect-dev-auth --json-out var\desci-browser-smoke-stripe-readiness-2026-06-06.json` -> `36/36 PASS`.
- `cmd /c npm run lint` -> passed with no warnings.
- `cmd /c npm run test` -> `29 files / 118 tests passed`.
- `cmd /c npm run build` -> passed.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-06-06-stripe-readiness.json` -> `8/8 PASS`.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-06-stripe-readiness.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-stripe-readiness-2026-06-06.json` -> 8 adopted sources; `var\auto-research-status-desci-stripe-readiness-2026-06-06.json` -> `status=ok`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_STRIPE_READINESS_BROWSER_2026-06-06.md`.

## 2026-06-06 (Pricing Cancel Retry Browser Follow-up)

### Scope
- `frontend/src/components/PricingPage.jsx`
- `frontend/src/__tests__/components/PricingPage.test.jsx`
- `scripts/browser_smoke.py`
- `ops/references/github_modernization_sources.json`

### Changes
- Sanitized the canceled checkout `plan` and `billing` query params before retrying checkout.
- Initialized pricing billing state from the cancellation return URL so retry preserves the canceled billing cycle.
- Added a `pricing-checkout-cancelled-retry` button to the visible cancel notice.
- Extended `pricing-checkout-cancelled` browser smoke to click retry, require a second checkout POST with the same Pro monthly body, and verify retry success at `/subscription/success?session_id=browser-smoke-retry`.
- Refreshed the moving Veritas AutoResearch GitHub source commit in the modernization radar to `3452d54bf855c3e95f54dd29a7e972241cd35c1f`.

### Verification
- `python -m py_compile apps\desci-platform\scripts\browser_smoke.py` -> PASS.
- `python -m pytest apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `11 passed`.
- `cmd /c npm run test -- src/__tests__/components/PricingPage.test.jsx` -> `1 file / 6 tests passed`.
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5175 --expect-dev-auth --timeout 25 --json-out var\desci-browser-smoke-pricing-cancel-retry-2026-06-06.json` -> `36/36 PASS`.
- `cmd /c npm run lint` -> passed with no warnings.
- `cmd /c npm run test` -> `29 files / 118 tests passed`.
- `cmd /c npm run build` -> passed.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-06-pricing-cancel-retry.json` -> `8/8 PASS`.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-06-06-pricing-cancel-retry.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-pricing-cancel-retry-2026-06-06.json` -> 8 adopted sources; `var\auto-research-status-desci-pricing-cancel-retry-2026-06-06.json` -> `status=ok`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_PRICING_CANCEL_RETRY_BROWSER_2026-06-06.md`.

## 2026-06-06 (Pricing Cancel Confirmation Browser Action)

### Scope
- `backend/routers/subscription.py`
- `backend/tests/test_router_edge_cases.py`
- `frontend/src/components/PricingPage.jsx`
- `frontend/src/__tests__/components/PricingPage.test.jsx`
- `scripts/browser_smoke.py`
- `backend/tests/test_browser_smoke.py`
- `ops/references/github_modernization_sources.json`

### Changes
- Changed Stripe checkout cancellation returns from plain `/pricing` to `/pricing?checkout=cancelled&plan=<tier>&billing=<billing>`.
- Added a visible pricing cancellation notice that preserves plan and billing context.
- Added a retry action on the cancellation notice that reopens checkout with the selected plan and billing cycle.
- Added router, component, and browser smoke coverage for cancellation return plus retry success.
- Refreshed the Veritas AutoResearch GitHub source commit in the modernization radar to `7581c6f3a6eeaa79b08f781d9d599ce26b8b19b2`.

### Verification
- Manual Playwright check: `/pricing?checkout=cancelled&plan=pro&billing=yearly` rendered `Checkout canceled. Pro yearly...`, `Retry Pro`, and no success panel; console warnings/errors `0`.
- `python -m py_compile apps\desci-platform\scripts\browser_smoke.py apps\desci-platform\backend\routers\subscription.py` -> PASS.
- `python -m pytest apps\desci-platform\backend\tests\test_browser_smoke.py apps\desci-platform\backend\tests\test_router_edge_cases.py -q -p no:cacheprovider` -> `25 passed`.
- `cmd /c npm run test -- src/__tests__/components/PricingPage.test.jsx` -> `1 file / 6 tests passed`.
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5175 --expect-dev-auth --json-out var\desci-browser-smoke-pricing-cancel-confirmation-2026-06-06.json` -> `36/36 PASS`.
- `cmd /c npm run lint` -> passed with no warnings.
- `cmd /c npm run test` -> `29 files / 118 tests passed`.
- `cmd /c npm run build` -> passed.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-06-06-pricing-cancel-confirmation.json` -> `8/8 PASS`.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-06-pricing-cancel-confirmation.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-pricing-cancel-confirmation-2026-06-06.json` -> 8 adopted sources; `var\auto-research-status-desci-pricing-cancel-confirmation-2026-06-06.json` -> `status=ok`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_PRICING_CANCEL_CONFIRMATION_BROWSER_2026-06-06.md`.

## 2026-06-06 (Pricing Success Confirmation Browser Action)

### Scope
- `frontend/src/components/PricingPage.jsx`
- `frontend/src/__tests__/components/PricingPage.test.jsx`
- `scripts/browser_smoke.py`
- `backend/tests/test_browser_smoke.py`
- `ops/references/github_modernization_sources.json`

### Changes
- Added a dedicated `/subscription/success` checkout confirmation state instead of reusing the pricing plan picker.
- Added stable success selectors for the panel, Stripe session id, dashboard link, and upload link.
- Added PricingPage coverage proving the success route does not render the `Upgrade to Pro` plan picker.
- Strengthened `pricing-checkout-mocked` browser smoke to require the success panel, mocked session id, and next-action links after checkout redirect.
- Refreshed the Veritas AutoResearch GitHub source commit in the modernization radar to `032e2374deee207bc3def35cd9ffde0fb27bda1a`.

### Verification
- Manual Playwright baseline: `/subscription/success?session_id=baseline` rendered the normal pricing plan picker and no success confirmation; console warnings/errors `0`.
- Manual Playwright after fix: `/subscription/success?session_id=after-fix` rendered checkout-complete copy, session `after-fix`, and `/dashboard` plus `/upload` next actions; console warnings/errors `0`.
- `python -m py_compile apps\desci-platform\scripts\browser_smoke.py` -> PASS.
- `python -m pytest apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `11 passed`.
- `cmd /c npm run test -- src/__tests__/components/PricingPage.test.jsx` -> `1 file / 5 tests passed`.
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5175 --expect-dev-auth --json-out var\desci-browser-smoke-pricing-success-confirmation-2026-06-06.json` -> `35/35 PASS`.
- `cmd /c npm run lint` -> passed with no warnings.
- `cmd /c npm run test` -> `29 files / 117 tests passed`.
- `cmd /c npm run build` -> passed.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-06-06-pricing-success-confirmation.json` -> `8/8 PASS`.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-06-pricing-success-confirmation.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-pricing-success-confirmation-2026-06-06.json` -> 8 adopted sources; `var\auto-research-status-desci-pricing-success-confirmation-2026-06-06.json` -> `status=ok`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_PRICING_SUCCESS_CONFIRMATION_BROWSER_2026-06-06.md`.

## 2026-06-06 (Dashboard Readiness Refresh Browser Action)

### Scope
- `frontend/src/components/ProductReadinessPanel.jsx`
- `frontend/src/__tests__/components/ProductReadinessPanel.test.jsx`
- `scripts/browser_smoke.py`
- `backend/tests/test_browser_smoke.py`
- `ops/references/github_modernization_sources.json`

### Changes
- Added stable launch-readiness panel selectors for status, refresh, progress, ready summary, required summary, and individual readiness check rows.
- Strengthened ProductReadinessPanel refresh coverage to prove degraded-to-ready UI updates after a second `/ready` fetch.
- Added `dashboard-readiness-refresh` authenticated browser smoke to fixture `/ready`, verify dashboard readiness summaries and rows, click Refresh, and require another `/ready` GET.
- Refreshed the Veritas AutoResearch GitHub source commit in the modernization radar to `2a6e508bbcd9c05b438f832b39fc6cbd51ba6580`.

### Verification
- Manual Playwright baseline: `/dashboard` under dev auth showed `출시 준비도`, `새로고침`, `전체 준비도`, and `필수 4/5개 준비`; `/ready` returned `200`; console warnings/errors `0`.
- `python -m py_compile apps\desci-platform\scripts\browser_smoke.py` -> PASS.
- `python -m pytest apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `11 passed`.
- `cmd /c npm run test -- src/__tests__/components/ProductReadinessPanel.test.jsx src/__tests__/components/Dashboard.test.jsx` -> `2 files / 14 tests passed`.
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5192 --expect-dev-auth --timeout 25 --json-out var\desci-browser-smoke-dashboard-readiness-refresh-2026-06-06-rerun.json` -> `35/35 PASS`.
- `cmd /c npm run lint` -> passed with no warnings.
- `cmd /c npm run test` -> `29 files / 116 tests passed`.
- `cmd /c npm run build` -> passed.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-06-06-dashboard-readiness-refresh-rerun.json` -> `8/8 PASS`.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-06-dashboard-readiness-refresh-rerun.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-dashboard-readiness-refresh-2026-06-06.json` -> 7 adopted sources; `var\auto-research-status-desci-dashboard-readiness-refresh-2026-06-06.json` -> `status=ok`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_DASHBOARD_READINESS_REFRESH_BROWSER_2026-06-06.md`.

## 2026-06-06 (Landing CTA Intent Browser Action)

### Scope
- `frontend/src/components/LandingPage.jsx`
- `frontend/src/__tests__/components/LandingPage.test.jsx`
- `scripts/browser_smoke.py`
- `backend/tests/test_browser_smoke.py`

### Changes
- Routed primary landing signup CTAs to destination-aware login URLs.
- Added stable landing CTA test ids for header, hero, final CTA, explore, pricing, and sign-in links.
- Added `landing-cta-intent` public browser smoke to verify href contracts and real click-through to `/explore`, `/pricing`, and researcher onboarding.
- Refreshed the Veritas AutoResearch GitHub source commit in the modernization radar to `80a0605c17c61e9be5d117462f6aa9ca407bcfb2`.

### Verification
- `python -m py_compile apps\desci-platform\scripts\browser_smoke.py` -> PASS.
- `python -m pytest apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `11 passed`.
- `cmd /c npm run test -- src/__tests__/components/LandingPage.test.jsx` -> `7 passed`.
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5192 --expect-dev-auth --timeout 25 --json-out var\desci-browser-smoke-landing-cta-2026-06-06.json` -> `34/34 PASS`.
- `cmd /c npm run test` -> `29 files / 116 tests passed`.
- `cmd /c npm run lint` -> passed with no warnings.
- `cmd /c npm run build` -> passed.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-06-landing-cta.json` -> `8/8 PASS`.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-06-06-landing-cta.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-landing-cta-2026-06-06.json` -> 7 adopted sources; `var\auto-research-status-desci-landing-cta-2026-06-06.json` -> `status=ok`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_LANDING_CTA_BROWSER_2026-06-06.md`.

## 2026-06-06 (Investors Filter Browser Action)

### Scope
- `frontend/src/components/Investors.jsx`
- `frontend/src/__tests__/components/Investors.test.jsx`
- `scripts/browser_smoke.py`
- `backend/tests/test_browser_smoke.py`
- `ops/scripts/auto_research_status.py`
- `tests/test_auto_research_status.py`
- `ops/references/github_modernization_sources.json`

### Changes
- Added stable Investors filter, result-count, card, website, and email test ids for reusable public browser smoke.
- Changed `/vcs` loading to mount-only with `tRef` for localized load-failure copy, preventing filter interactions from refetching and showing skeletons.
- Added `investors-filter-directory` public browser smoke to fixture `/vcs`, search `oncology`, filter `US` plus `Series A`, verify one RA Capital card, and check website/mailto links.
- Scoped AutoResearch status next-action/report selection for DeSci radar artifacts so a newer DailyNews top action does not replace the DeSci latest report.
- Refreshed the Veritas AutoResearch GitHub source commit in the modernization radar to `621891ba40e02b37701db6cebf843f6e2acce3a8`.

### Verification
- Manual Playwright baseline: `/investors` search `oncology` plus country `US` showed `RA Capital Management` only, with website and mailto links present and no console errors.
- `python -m py_compile apps\desci-platform\scripts\browser_smoke.py` -> PASS.
- `python -m pytest apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `11 passed`.
- `cmd /c npm run test -- src/__tests__/components/Investors.test.jsx` -> `9 passed`.
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5175 --expect-dev-auth --json-out var\desci-browser-smoke-investors-filter-2026-06-06.json` -> `33/33 PASS`.
- `cmd /c npm run lint` -> passed with no warnings.
- `cmd /c npm run test` -> `29 files / 114 tests passed`.
- `cmd /c npm run build` -> passed.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-06-investors-filter.json` -> `8/8 PASS`.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-06-06-investors-filter.json` -> `8/8 PASS`.
- `python -m pytest tests\test_auto_research_status.py -q -p no:cacheprovider` -> `14 passed`.
- Radar/status: `var\github-modernization-radar-desci-investors-filter-2026-06-06.json` -> 7 adopted sources; `var\auto-research-status-desci-investors-filter-2026-06-06.json` -> `status=ok`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_INVESTORS_FILTER_BROWSER_2026-06-06.md`.

## 2026-06-06 (Explore Analyze Intent Browser Action)

### Scope
- `frontend/src/components/ResearchFeed.jsx`
- `frontend/src/components/Login.jsx`
- `frontend/src/components/ProtectedRoute.jsx`
- `frontend/src/App.jsx`
- `frontend/src/lib/redirect.js`
- `frontend/src/__tests__/components/ResearchFeed.test.jsx`
- `frontend/src/__tests__/components/Login.test.jsx`
- `frontend/src/lib/redirect.test.js`
- `scripts/browser_smoke.py`
- `backend/tests/test_browser_smoke.py`
- `ops/references/github_modernization_sources.json`

### Changes
- Routed public research-feed `Analyze` clicks through login with `next=/biolinker`, `paper_id`, `paper_title`, and `intent=analyze`.
- Added safe login redirect helpers that allow only known internal app paths and preserve limited product context parameters.
- Updated login success, dev-auth login redirect, and anonymous protected-route redirects to use the safe redirect helper.
- Added `explore-analyze-intent` browser smoke with deterministic `/papers/public` and paper-match job fixtures.
- Refreshed the Veritas AutoResearch GitHub source commit in the modernization radar to `77b226b8aab287070895ba7b2056d54126a441e5`.

### Verification
- `python -m py_compile apps\desci-platform\scripts\browser_smoke.py` -> PASS.
- `python -m pytest apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `11 passed`.
- `cmd /c npm run test -- src/__tests__/components/ResearchFeed.test.jsx src/__tests__/components/Login.test.jsx src/lib/redirect.test.js` -> `9 passed`.
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5192 --expect-dev-auth --timeout 25 --json-out var\desci-browser-smoke-explore-intent-2026-06-06-rerun.json` -> `33/33 PASS`.
- `cmd /c npm run test` -> `29 files / 113 tests passed`.
- `cmd /c npm run lint` -> passed with no warnings.
- `cmd /c npm run build` -> passed.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-06-06-explore-intent-rerun.json` -> `8/8 PASS`.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-06-explore-intent-rerun.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-explore-intent-2026-06-06.json` -> 7 adopted sources; `var\auto-research-status-desci-explore-intent-2026-06-06.json` -> `status=ok`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_EXPLORE_INTENT_BROWSER_2026-06-06.md`.

## 2026-06-06 (MyLab Mint Wallet Guard Browser Action)

### Scope
- `scripts/browser_smoke.py`
- `backend/tests/test_browser_smoke.py`
- `frontend/src/hooks/useMyLab.test.jsx`
- `ops/references/github_modernization_sources.json`

### Changes
- Added `mylab-mint-wallet-required` browser smoke to seed `/papers/me`, click the real MyLab `IP-NFT` mint action, and prove no `/nft/mint` POST escapes without a connected wallet.
- Added hook coverage proving `mintNFT` returns before `client.post` and shows wallet-required feedback when `walletAddress` is absent.
- Corrected dev-auth browser-smoke expectations so `/login` is checked as an authenticated redirect to `/dashboard`.
- Refreshed the Veritas AutoResearch GitHub source commit in the modernization radar to `09946d4067e9b966d6adf86282a031513999c8ae`.

### Verification
- Baseline Playwright probe: `/mylab` no-wallet mint click showed wallet-required feedback and sent no `/nft/mint` POST, but had no durable action smoke.
- `python -m py_compile apps\desci-platform\scripts\browser_smoke.py` -> PASS.
- `python -m pytest apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `10 passed`.
- `cmd /c npm run test -- src/hooks/useMyLab.test.jsx` -> `2 passed`.
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5175 --expect-dev-auth --json-out var\desci-browser-smoke-mylab-mint-wallet-2026-06-06.json` -> `31/31 PASS`.
- `cmd /c npm run lint` -> passed with no warnings.
- `cmd /c npm run test` -> `27 files / 106 tests passed`.
- `cmd /c npm run build` -> passed.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-06-mylab-mint-wallet.json` -> `8/8 PASS`.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-06-06-mylab-mint-wallet.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-mylab-mint-wallet-2026-06-06.json` -> 7 adopted sources; `var\auto-research-status-desci-mylab-mint-wallet-2026-06-06.json` -> `status=ok`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_MYLAB_MINT_WALLET_BROWSER_2026-06-06.md`.

## 2026-06-06 (Asset Upload Readiness Browser Action)

### Scope
- `frontend/src/components/AssetManager.jsx`
- `frontend/src/i18n/messages.js`
- `frontend/src/__tests__/components/AssetManager.test.jsx`
- `frontend/src/__tests__/mocks/locale-messages.js`
- `scripts/browser_smoke.py`
- `backend/tests/test_browser_smoke.py`

### Changes
- Replaced auto-upload-on-file-selection with an explicit Asset Library upload action.
- Added a persistent upload-readiness checklist for asset type and allowed PDF/TXT file selection.
- Blocked unsupported file extensions before upload and kept the backend `/assets/upload` API unchanged.
- Added `asset-upload-readiness` browser smoke to prove no POST occurs during file selection and one explicit upload POST carries the selected asset type.
- Refreshed the Veritas AutoResearch GitHub source commit in the modernization radar to `5e4b31b0c2b1763f45b2eea4ba7e740dd8209360`.

### Verification
- `python -m py_compile apps\desci-platform\scripts\browser_smoke.py` -> PASS.
- `python -m pytest apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `10 passed`.
- `cmd /c npm run test -- src/__tests__/components/AssetManager.test.jsx` -> `3 passed`.
- `cmd /c npm run test -- src/__tests__/components/UploadPaper.test.jsx` -> `8 passed`.
- `cmd /c npm run lint` -> passed with no warnings.
- `cmd /c npm run build` -> passed.
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5192 --expect-dev-auth --timeout 25 --json-out var\desci-browser-smoke-asset-readiness-2026-06-06-rerun.json` -> `30/30 PASS`.
- `cmd /c npm run test` -> `27 files / 105 tests passed`.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-06-06-asset-readiness.json` -> `8/8 PASS`.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-06-asset-readiness.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-asset-readiness-2026-06-06.json` -> 7 adopted sources; `var\auto-research-status-desci-asset-readiness-2026-06-06.json` -> `status=action_required` because the shared DailyNews first-run launch check remains externally blocked by `runtime_preflight_blocked`; DeSci/source/workspace checks passed.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_ASSET_READINESS_BROWSER_2026-06-06.md`.

## 2026-06-06 (Pricing Checkout Browser Action)

### Scope
- `frontend/src/components/PricingPage.jsx`
- `frontend/src/services/api.js`
- `frontend/src/__tests__/components/PricingPage.test.jsx`
- `scripts/browser_smoke.py`
- `backend/tests/test_browser_smoke.py`

### Changes
- Added visible checkout failure feedback on the public pricing page.
- Routed anonymous paid-plan clicks to `/login?next=/pricing&plan=<tier>` instead of posting checkout.
- Suppressed duplicate API client console logging only when the caller renders the error itself.
- Added `pricing-checkout-mocked` browser smoke to prove Pro monthly checkout payload and success redirect without relying on live Stripe.
- Refreshed the Veritas AutoResearch GitHub source commit in the modernization radar to `c7f8c14bef65f0ad6c1e499eb1963b26637fed92`.

### Verification
- Baseline Playwright probe: `/pricing` Pro click posted checkout, got Stripe-unconfigured `503`, showed no visible feedback, and emitted console errors.
- Variant Playwright probe: same local Stripe-unconfigured response now renders visible alert text.
- `python -m py_compile apps\desci-platform\scripts\browser_smoke.py` -> PASS.
- `python -m pytest apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `10 passed`.
- `cmd /c npm run test -- src/__tests__/components/PricingPage.test.jsx` -> `4 passed`.
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5175 --expect-dev-auth --json-out var\desci-browser-smoke-pricing-checkout-2026-06-06.json` -> `29/29 PASS`.
- `cmd /c npm run lint` -> passed with no warnings.
- `cmd /c npm run test` -> `26 files / 102 tests passed`.
- `cmd /c npm run build` -> passed.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-06-pricing-checkout.json` -> `8/8 PASS`.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-06-06-pricing-checkout.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-pricing-checkout-2026-06-06.json` -> 7 adopted sources; `var\auto-research-status-desci-pricing-checkout-2026-06-06.json` -> `status=ok`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_PRICING_CHECKOUT_BROWSER_2026-06-06.md`.

## 2026-06-06 (AI Lab Readiness Browser Action)

### Scope
- `frontend/src/components/AILab.jsx`
- `frontend/src/i18n/messages.js`
- `frontend/src/__tests__/components/AILab.test.jsx`
- `frontend/src/__tests__/mocks/locale-messages.js`
- `scripts/browser_smoke.py`
- `backend/tests/test_browser_smoke.py`

### Changes
- Added persistent per-tool AI Workbench run-readiness status for Deep Research, Content Writer, and YouTube Intelligence.
- Kept Run disabled until each active tool's required inputs are complete.
- Localized the readiness checklist in Korean and English.
- Added `ai-lab-readiness` browser smoke to prove empty, partial, and ready states without sending `/api/agent/*` POSTs.
- Refreshed the Veritas AutoResearch GitHub source commit in the modernization radar to `3b70b50a41ee10f1b5221550f5cdc30243a75a9f`.

### Verification
- Baseline Playwright probe: empty `/ai-lab` research Run button was enabled, with no `/api/agent/*` POST after click.
- `python -m py_compile apps\desci-platform\scripts\browser_smoke.py` -> PASS.
- `python -m pytest apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `10 passed`.
- `cmd /c npm run test -- src/__tests__/components/AILab.test.jsx` -> `2 passed`.
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5192 --expect-dev-auth --timeout 25 --json-out var\desci-browser-smoke-ai-lab-readiness-2026-06-06-final.json` -> `28/28 PASS`.
- `cmd /c npm run lint` -> passed with no warnings.
- `cmd /c npm run test` -> `26 files / 100 tests passed`.
- `cmd /c npm run build` -> passed.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-06-ai-lab-readiness.json` -> `8/8 PASS`.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-06-06-ai-lab-readiness.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-ai-lab-readiness-2026-06-06.json` -> 7 adopted sources; `var\auto-research-status-desci-ai-lab-readiness-2026-06-06.json` -> `status=ok`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_READINESS_BROWSER_2026-06-06.md`.

## 2026-06-06 (Funding Radar to BioLinker Bridge Browser Action)

### Scope
- `frontend/src/components/Notices.jsx`
- `frontend/src/components/BioLinker.jsx`
- `frontend/src/i18n/messages.js`
- `frontend/src/__tests__/components/BioLinker.test.jsx`
- `scripts/browser_smoke.py`
- `backend/tests/test_browser_smoke.py`

### Changes
- Added durable imported-notice context in BioLinker when a Funding Radar notice is opened through `Analyze fit`.
- Preserved the imported notice title, source, and body across the `/notices -> /biolinker` route state.
- Kept BioLinker Analyze disabled until organization/team name is supplied even when the imported RFP body is already ready.
- Added `notices-biolinker-bridge` browser smoke with a deterministic `/notices` fixture and no `/analyze` POST.
- Refreshed the Veritas AutoResearch GitHub source commit in the modernization radar to `c17fb54b9cea36dbb4ef43b229cf8b93e82ef2fd`.

### Verification
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5175 --expect-dev-auth --json-out var\desci-browser-smoke-2026-06-06-notices-biolinker-bridge.json` -> `26/26 PASS`.
- `cmd /c npm run test -- src/__tests__/components/BioLinker.test.jsx` -> `3 passed`.
- `cmd /c npm run test` -> `25 files / 97 tests passed`.
- `cmd /c npm run lint` -> passed with no warnings.
- `cmd /c npm run build` -> passed.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `10 passed`.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-06-notices-biolinker-bridge-full.json` -> `8/8 PASS`.
- Radar/status: `var\github-modernization-radar-desci-notices-biolinker-bridge-2026-06-06.json` -> 7 adopted sources; `var\auto-research-status-desci-notices-biolinker-bridge-2026-06-06.json` -> `status=ok`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_NOTICES_BIOLINKER_BRIDGE_BROWSER_2026-06-06.md`.

## 2026-06-05 (Dev-Auth Protected Browser QA)

### Scope
- `frontend/src/lib/devAuth.js`
- `frontend/src/contexts/AuthContext.jsx`
- `frontend/src/services/api.js`
- `frontend/src/components/Dashboard.jsx`
- `frontend/src/components/dashboard/VCMatchList.jsx`
- `frontend/src/components/dashboard/RecommendationList.jsx`
- `scripts/browser_smoke.py`
- `backend/tests/test_browser_smoke.py`
- `frontend/src/__tests__/contexts/devAuth.test.jsx`
- `frontend/src/__tests__/components/Dashboard.test.jsx`
- `frontend/src/__tests__/components/DashboardLists.test.jsx`

### Changes
- Added an explicit dev-only auth bypass so protected DeSci routes can be browser-smoked locally without a real Firebase session.
- Extended browser smoke with `--expect-dev-auth` to verify `/dashboard`, `/upload`, `/notices`, and a real dashboard quick-action click to `/upload`.
- Preserved the default anonymous smoke contract: `/dashboard` and `/upload` still redirect to `/login` unless the dev-auth env is explicitly enabled.
- Fixed dashboard API drift surfaced by protected smoke: vector KPI now reads `/health`, investor cards read `/vcs`, and recommendation cards read `/notices`.
- Refreshed the Veritas AutoResearch GitHub source commit in the modernization radar to `4f9cea073868d0cbdda027cb37f5867847c69369`.

### Verification
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5175 --expect-dev-auth --json-out var\desci-browser-smoke-2026-06-05-dev-auth-protected-click-final2.json` -> `10/10 OK`.
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5175 --json-out var\desci-browser-smoke-2026-06-05-default-after-dev-auth.json` -> `9/9 OK`.
- `cmd /c npm run test` -> `20 files / 79 tests passed`.
- `cmd /c npm run lint` -> passed with no warnings.
- `cmd /c npm run build` -> passed.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `9 passed`.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-05-dev-auth-browser-sequential.json` -> `8/8 PASS`.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-06-05-desci-dev-auth-browser-final.json` -> `8/8 PASS`.
- Managed DeSci dev stack stopped after verification: `var/dev-server-control-desci-stop-after-dev-auth-browser-2026-06-05.json` -> `stopped=2/2`; `var/dev-server-status-desci-after-dev-auth-browser-stop-2026-06-05.json` -> `0/2 ready`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_DEV_AUTH_BROWSER_QA_2026-06-05.md`.

## 2026-06-05 (Investors Korean Chrome Browser Interaction)

### Scope
- `frontend/src/components/Investors.jsx`
- `frontend/src/i18n/messages.js`
- `frontend/src/__tests__/components/Investors.test.jsx`
- `frontend/src/__tests__/contexts/LocaleContext.test.jsx`
- `scripts/browser_smoke.py`
- `backend/tests/test_browser_smoke.py`
- AutoResearch radar evidence

### Changes
- Localized the public `/investors` page chrome through `LocaleContext` so the default Korean app no longer shows English-only route labels, filters, result count, empty state, or load error copy.
- Preserved investor thesis/contact data as source material while translating the operator-facing page controls.
- Promoted `/investors` into default browser smoke coverage; browser smoke now checks 9 flows including investor directory and login validation.
- Refreshed the Veritas AutoResearch GitHub source commit in the modernization radar to `2778ac57843cc680f8c890824bc2fbba70f640cc`.

### Verification
- Playwright opened `http://127.0.0.1:5175/investors` and confirmed `투자자 디렉터리`, `Bio VC 생태계`, Korean filter labels, `54곳 중 54곳 표시 중`, search `oncology` -> `54곳 중 6곳 표시 중`, country `US` -> `54곳 중 1곳 표시 중`, with `0` console warnings/errors.
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5175 --json-out var\desci-browser-smoke-2026-06-05-investors-i18n.json` -> `9/9 OK`.
- `cmd /c npm run test` -> `18 files / 74 tests passed`.
- `cmd /c npm run lint` -> passed.
- `cmd /c npm run build` -> passed.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `8 passed`.
- `python -m pytest tests\test_github_modernization_radar.py -q -p no:cacheprovider` -> `5 passed`.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-05-investors-i18n.json` -> `8/8 PASS`.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-06-05-desci-investors-i18n-radar-refresh-final.json` -> `8/8 PASS`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_INVESTORS_I18N_BROWSER_2026-06-05.md`.

## 2026-06-05 (Login Validation Browser Interaction)

### Scope
- `frontend/src/components/Login.jsx`
- `frontend/src/i18n/messages.js`
- `frontend/src/__tests__/components/Login.test.jsx`
- `scripts/browser_smoke.py`
- `backend/tests/test_browser_smoke.py`
- Runtime smoke docs and AutoResearch radar evidence

### Changes
- Fixed the live login short-password path so the app renders a visible inline `role="alert"` and toast instead of letting native browser validation swallow the React submit flow.
- Added custom invalid-email validation and trimmed email values before sign-in/sign-up calls.
- Promoted the login validation interaction into `browser_smoke.py`; browser-smoke JSON now records `skip_login_validation` and includes the `login-validation` check by default.
- Refreshed the Veritas AutoResearch GitHub source commit in the modernization radar to `0446e942ecdfd98ae2310d1560e130af3190bbe4`.

### Verification
- Playwright click path on `http://127.0.0.1:5175/login` showed inline alert `비밀번호는 6자 이상이어야 합니다.` plus toast, with `0` console warnings/errors.
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5175 --json-out var\desci-browser-smoke-2026-06-05-login-validation.json` -> `8/8 OK`.
- `cmd /c npm run test` -> `18 files / 72 tests passed`.
- `cmd /c npm run lint` -> passed.
- `cmd /c npm run build` -> passed.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_deployment_docs.py tests/test_github_modernization_radar.py -q -p no:cacheprovider` -> `18 passed`.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-05-login-validation-final.json` -> `8/8 PASS`.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-06-05-desci-login-validation-radar-refresh.json` -> `8/8 PASS`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_LOGIN_VALIDATION_BROWSER_2026-06-05.md`.

## 2026-06-05 (Research Feed Action Layout and Build Warning Cleanup)

### Scope
- `frontend/src/components/ResearchFeed.jsx`
- `frontend/vite.config.js`
- AutoResearch report and handoff docs

### Changes
- Fixed the public research feed action-column layout so Korean IPFS action labels no longer clip in research cards.
- Migrated DeSci frontend vendor chunk configuration from deprecated `advancedChunks` to `rolldownOptions.output.codeSplitting`.
- Corrected stale June 5 modernization-radar counts in completion/handoff records from `6/6` to `7/7`.

### Verification
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5175 --json-out var\desci-browser-smoke-2026-06-05-action-layout-fix.json` -> `7/7 OK`.
- `var/desci-click-flow-2026-06-05.md` -> Korean IPFS action buttons had `overflowsText=false`, `spillsPastCard=false`; search/filter/Analyze/pricing click path had `0` console warnings/errors, `0` page errors, and `0` request failures.
- `cmd /c npm run test` -> `17 files / 70 tests passed`.
- `cmd /c npm run lint` -> passed.
- `cmd /c npm run build` -> passed without the prior `advancedChunks` deprecation warning.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_deployment_docs.py tests/test_github_modernization_radar.py -q -p no:cacheprovider` -> `18 passed`.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-05-research-feed-action-layout.json` -> `8/8 PASS`.

## 2026-05-28 (Release Approval Evidence Contract)

### Scope
- `ops/scripts/release_approval_check.py`
- `tests/test_release_approval_check.py`
- Canonical workspace smoke release approval coverage

### Changes
- Added a schema v1 release approval evidence validator so release approval cannot be inferred from deterministic QC alone.
- Canonical workspace smoke now includes `release approval contract tests`.
- The release approval contract requires deterministic-gate evidence, worktree review state, compatibility/deprecation warning review, source-of-truth confirmation, and manual/external-step evidence.
- `release_approval_check.py --init-template` writes a non-approval template and refuses to overwrite existing files without `--force`.
- CLI validation resolves `deterministic_gate.evidence_path` and requires it to be an existing, valid, complete, all-pass smoke JSON report.
- CLI validation now requires schema v1 smoke result scopes to match `affected_scope`; legacy bare-array smoke evidence is rejected for release approval because it does not carry scope evidence.
- CLI validation now requires `deterministic_gate.command` to run `ops/scripts/run_workspace_smoke.py`, include `--scope` matching `affected_scope`, and include `--json-out` matching `deterministic_gate.evidence_path`.
- Worktree approval evidence now requires `changed_paths` for reviewed in-progress diffs, and `clean` status is checked with live `git status --porcelain` during CLI validation.
- `changed_paths` entries now must exist in live `git status --porcelain`; directory prefixes can cover nested changes.
- `changed_paths` must be specific repo-relative paths; root, absolute, parent-escape, and `.git` internal paths are rejected before git-status matching.
- Added `docs/reports/2026-05/RELEASE_APPROVAL_WORKSPACE_2026-05-28.json` as a real machine-validated workspace release approval artifact for the current reviewed-in-progress product-readiness diff set.

### Verification
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-05-28-release-approval-artifact.json` -> `8/8 PASS`
- `python ops\scripts\release_approval_check.py docs\reports\2026-05\RELEASE_APPROVAL_WORKSPACE_2026-05-28.json` -> `release approval evidence is valid`
- `python -m pytest tests/test_release_approval_check.py -q -p no:cacheprovider` -> `31 passed`
- `python -m pytest tests/test_workspace_smoke.py tests/test_release_approval_check.py -q -p no:cacheprovider` -> `59 passed`
- `python ops\scripts\release_approval_check.py --init-template var\release-approval-template-2026-05-28-changed-path-policy.json --force` -> template written; immediate validation fails as intended until timestamp, known affected scope, canonical smoke command, deterministic-gate ok, real smoke evidence path, and actual changed paths replace placeholders
- `python -m pytest tests/test_workspace_smoke.py tests/test_security_gate_contracts.py tests/test_ops_scripts_reports.py tests/test_dashboard_api.py tests/test_release_approval_check.py apps/desci-platform/backend/tests/test_ab_test_matching.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `293 passed`
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-05-28-release-approval-changed-path-policy.json` -> `8/8 PASS`
- `python ops\scripts\session_bootstrap.py --json-out var\session-bootstrap-2026-05-28-release-approval-changed-path-policy.json` -> latest smoke `8/8 PASS`
- FastAPI TestClient `/api/quality_overview` -> `workspace_smoke.status=valid`, `passed=8`, `total=8`, evidence path `var/workspace-smoke-workspace-2026-05-28-release-approval-changed-path-policy.json`

Earlier incremental release-approval verification retained for audit:

- `python -m pytest tests/test_release_approval_check.py -q -p no:cacheprovider` -> `27 passed`
- `python -m pytest tests/test_workspace_smoke.py tests/test_release_approval_check.py -q -p no:cacheprovider` -> `55 passed`
- `python ops\scripts\release_approval_check.py --init-template var\release-approval-template-2026-05-28-changed-paths.json --force` -> template written; immediate validation fails as intended until timestamp, known affected scope, canonical smoke command, deterministic-gate ok, real smoke evidence path, and actual changed paths replace placeholders
- `python -m pytest tests/test_workspace_smoke.py tests/test_security_gate_contracts.py tests/test_ops_scripts_reports.py tests/test_dashboard_api.py tests/test_release_approval_check.py apps/desci-platform/backend/tests/test_ab_test_matching.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `289 passed`
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-05-28-release-approval-changed-paths.json` -> `8/8 PASS`
- `python ops\scripts\session_bootstrap.py --json-out var\session-bootstrap-2026-05-28-release-approval-changed-paths.json` -> latest smoke `8/8 PASS`
- FastAPI TestClient `/api/quality_overview` -> `workspace_smoke.status=valid`, `passed=8`, `total=8`, evidence path `var/workspace-smoke-workspace-2026-05-28-release-approval-changed-paths.json`
- `python -m pytest tests/test_release_approval_check.py -q -p no:cacheprovider` -> `25 passed`
- `python -m pytest tests/test_workspace_smoke.py tests/test_release_approval_check.py -q -p no:cacheprovider` -> `53 passed`
- `python ops\scripts\release_approval_check.py --init-template var\release-approval-template-2026-05-28-worktree.json --force` -> template written; immediate validation fails as intended until timestamp, known affected scope, canonical smoke command, deterministic-gate ok, and real smoke evidence path replace placeholders
- `python -m pytest tests/test_workspace_smoke.py tests/test_security_gate_contracts.py tests/test_ops_scripts_reports.py tests/test_dashboard_api.py tests/test_release_approval_check.py apps/desci-platform/backend/tests/test_ab_test_matching.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `287 passed`
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-05-28-release-approval-worktree.json` -> `8/8 PASS`
- `python ops\scripts\session_bootstrap.py --json-out var\session-bootstrap-2026-05-28-release-approval-worktree.json` -> latest smoke `8/8 PASS`
- FastAPI TestClient `/api/quality_overview` -> `workspace_smoke.status=valid`, `passed=8`, `total=8`, evidence path `var/workspace-smoke-workspace-2026-05-28-release-approval-worktree.json`
- `python -m pytest tests/test_release_approval_check.py -q -p no:cacheprovider` -> `22 passed`
- `python -m pytest tests/test_workspace_smoke.py tests/test_release_approval_check.py -q -p no:cacheprovider` -> `50 passed`
- `python ops\scripts\release_approval_check.py --init-template var\release-approval-template-2026-05-28-command.json --force` -> template written; immediate validation fails as intended until timestamp, known affected scope, canonical smoke command, deterministic-gate ok, and real smoke evidence path replace placeholders
- `python -m pytest tests/test_workspace_smoke.py tests/test_security_gate_contracts.py tests/test_ops_scripts_reports.py tests/test_dashboard_api.py tests/test_release_approval_check.py apps/desci-platform/backend/tests/test_ab_test_matching.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `284 passed`
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-05-28-release-approval-command-match.json` -> `8/8 PASS`
- `python ops\scripts\session_bootstrap.py --json-out var\session-bootstrap-2026-05-28-release-approval-command-match.json` -> latest smoke `8/8 PASS`
- FastAPI TestClient `/api/quality_overview` -> `workspace_smoke.status=valid`, `passed=8`, `total=8`, evidence path `var/workspace-smoke-workspace-2026-05-28-release-approval-command-match.json`
- `python -m pytest tests/test_release_approval_check.py -q -p no:cacheprovider` -> `18 passed`
- `python -m pytest tests/test_workspace_smoke.py tests/test_release_approval_check.py -q -p no:cacheprovider` -> `46 passed`
- `python ops\scripts\release_approval_check.py --init-template var\release-approval-template-2026-05-28-scope.json --force` -> template written; immediate validation fails as intended until timestamp, known affected scope, deterministic-gate ok, and real smoke evidence path replace placeholders
- `python -m pytest tests/test_workspace_smoke.py tests/test_security_gate_contracts.py tests/test_ops_scripts_reports.py tests/test_dashboard_api.py tests/test_release_approval_check.py apps/desci-platform/backend/tests/test_ab_test_matching.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `280 passed`
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-05-28-release-approval-scope-match.json` -> `8/8 PASS`
- `python ops\scripts\session_bootstrap.py --json-out var\session-bootstrap-2026-05-28-release-approval-scope-match.json` -> latest smoke `8/8 PASS`
- FastAPI TestClient `/api/quality_overview` -> `workspace_smoke.status=valid`, `passed=8`, `total=8`, evidence path `var/workspace-smoke-workspace-2026-05-28-release-approval-scope-match.json`
- `python -m pytest tests/test_release_approval_check.py -q -p no:cacheprovider` -> `14 passed`
- `python -m pytest tests/test_workspace_smoke.py tests/test_release_approval_check.py -q -p no:cacheprovider` -> `42 passed`
- `python ops\scripts\release_approval_check.py --init-template var\release-approval-template-2026-05-28-evidence-path.json --force` -> template written; immediate validation fails as intended until timestamp, deterministic-gate ok, and real smoke evidence path replace placeholders
- `python -m pytest tests/test_workspace_smoke.py tests/test_security_gate_contracts.py tests/test_ops_scripts_reports.py tests/test_dashboard_api.py tests/test_release_approval_check.py apps/desci-platform/backend/tests/test_ab_test_matching.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `276 passed`
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-05-28-release-approval-evidence-path.json` -> `8/8 PASS`
- `python ops\scripts\session_bootstrap.py --json-out var\session-bootstrap-2026-05-28-release-approval-evidence-path.json` -> latest smoke `8/8 PASS`
- FastAPI TestClient `/api/quality_overview` -> `workspace_smoke.status=valid`, `passed=8`, `total=8`, evidence path `var/workspace-smoke-workspace-2026-05-28-release-approval-evidence-path.json`
- `python -m pytest tests/test_release_approval_check.py -q -p no:cacheprovider` -> `9 passed`
- `python -m pytest tests/test_workspace_smoke.py tests/test_release_approval_check.py -q -p no:cacheprovider` -> `37 passed`
- `python ops\scripts\release_approval_check.py --init-template var\release-approval-template-2026-05-28.json --force` -> template written; immediate validation fails as intended until real evidence replaces placeholders
- `python -m pytest tests/test_workspace_smoke.py tests/test_security_gate_contracts.py tests/test_ops_scripts_reports.py tests/test_dashboard_api.py tests/test_release_approval_check.py apps/desci-platform/backend/tests/test_ab_test_matching.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `271 passed`
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-05-28-release-approval-template.json` -> `8/8 PASS`
- `python ops\scripts\session_bootstrap.py --json-out var\session-bootstrap-2026-05-28-release-approval-template.json` -> latest smoke `8/8 PASS`
- FastAPI TestClient `/api/quality_overview` -> `workspace_smoke.status=valid`, `passed=8`, `total=8`, evidence path `var/workspace-smoke-workspace-2026-05-28-release-approval-template.json`
- `python -m py_compile ops\scripts\release_approval_check.py ops\scripts\run_workspace_smoke.py` -> passed
- `python -m pytest tests/test_release_approval_check.py tests/test_workspace_smoke.py::test_quality_gate_documents_incremental_json_evidence -q -p no:cacheprovider` -> `7 passed`
- `python -m pytest tests/test_workspace_smoke.py tests/test_release_approval_check.py -q -p no:cacheprovider` -> `34 passed`
- `python -m pytest tests/test_workspace_smoke.py tests/test_security_gate_contracts.py tests/test_ops_scripts_reports.py tests/test_dashboard_api.py tests/test_release_approval_check.py apps/desci-platform/backend/tests/test_ab_test_matching.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `268 passed`
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-05-28-release-approval-contract.json` -> `8/8 PASS`
- `python ops\scripts\session_bootstrap.py --json-out var\session-bootstrap-2026-05-28-release-approval-contract.json` -> latest smoke `8/8 PASS`
- FastAPI TestClient `/api/quality_overview` -> `workspace_smoke.status=valid`, `passed=8`, `total=8`, evidence path `var/workspace-smoke-workspace-2026-05-28-release-approval-contract.json`

### Result
- The deterministic quality gate remains a development-health signal, while release approval now requires explicit machine-checked evidence.

## 2026-05-28 (Dashboard Smoke Evidence Visibility)

### Scope
- `apps/dashboard/routers/gdt.py`
- `apps/dashboard/src/components/QualityPanel.jsx`
- Dashboard API and React contracts

### Changes
- Added `workspace_smoke` to `/api/quality_overview`, using the shared workspace smoke reader instead of duplicating report parsing.
- The API now reports valid, corrupt, missing, and unavailable smoke states with display text, path/name, counts, and report status.
- `QualityPanel` now renders the current workspace smoke status and evidence path for operator visibility.
- `scripts/build.mjs` now captures Vite output, fails CSS compiler `Unknown at rule` warnings, and no longer treats non-zero Vite exits as success just because `dist/` exists.
- Workspace smoke tests now assert dashboard CSS remains plain CSS without Sass-style `@extend`, and use fake Vite runs to prove the build script keeps the warning fail-fast guard and stale-dist false-green protection.

### Verification
- `python -m pytest tests/test_dashboard_api.py -q -p no:cacheprovider` -> `60 passed`
- `npm.cmd test` from `apps/dashboard` -> `3 passed`
- `npm.cmd run lint` from `apps/dashboard` -> passed
- `npm.cmd run build` from `apps/dashboard` -> passed without Lightning CSS `@extend` warnings; CSS compiler warnings and non-zero Vite exits are fail-fast
- `npm.cmd run check:bundle` from `apps/dashboard` -> passed
- `python -m pytest tests/test_workspace_smoke.py tests/test_dashboard_api.py -q -p no:cacheprovider` -> `88 passed`
- `python -m pytest tests/test_workspace_smoke.py tests/test_security_gate_contracts.py tests/test_ops_scripts_reports.py tests/test_dashboard_api.py apps/desci-platform/backend/tests/test_ab_test_matching.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `262 passed`
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-05-28-dashboard-build-failfast.json` -> `7/7 PASS`
- `python ops\scripts\session_bootstrap.py --json-out var\session-bootstrap-2026-05-28-dashboard-build-failfast.json` -> latest smoke `7/7 PASS`
- FastAPI TestClient `/api/quality_overview` -> `workspace_smoke.status=valid`, `passed=7`, `total=7`, evidence path `var/workspace-smoke-workspace-2026-05-28-dashboard-build-failfast.json`

### Result
- The latest workspace smoke evidence is now visible in the live operations dashboard, not just in session/bootstrap files.

## 2026-05-28 (Strict Workspace Smoke Report Consumers)

### Scope
- `ops/scripts/workspace_smoke_report.py`
- Startup/context smoke evidence selection
- Root quality-gate documentation

### Changes
- Legacy array smoke reports remain supported only when every entry is an object with boolean `ok` and at least one result; malformed or empty legacy arrays are skipped like corrupt reports.
- Schema v1 smoke reports with unsupported or boolean `schema_version`, unparseable or timezone-naive `generated_at`, missing/empty/non-string status values, status/progress contradictions, or inconsistent summary counts are now rejected by consumers.
- Schema v1 reports with zero `summary.total` or zero `summary.completed` are rejected so `0/0 PASS` evidence cannot be selected as latest smoke.
- Schema v1 smoke reports must include both the top-level `summary` object and top-level `results` array; summary-only or results-only object evidence is rejected.
- Result-count mismatches, missing required `results[]` fields, non-object `results[]` entries, non-boolean `results[].ok`, `results[].ok`/`returncode` contradictions, and `results[].ok` pass/fail-count drift are rejected when a schema v1 report includes `results`.
- Empty schema v1 result trace fields (`scope`, `name`, `cwd`, `command`) are rejected so every accepted result stays attributable to a check and command.
- Unknown schema v1 result scopes are rejected so accepted results remain within the canonical smoke scope set.
- Newer invalid reports are skipped so `session_bootstrap.py` and `generate_context_snapshot.py` continue to report the newest valid smoke evidence.
- Newest-valid selection is sorted by file modification time inside `latest_valid_smoke_report()`, so it no longer depends on filesystem glob order or caller-provided candidate order.
- Current and legacy smoke report candidate collection is centralized in the shared reader, which ignores matching directories and non-file candidates.
- Canonical `ops/scripts` and legacy `scripts` startup/context entrypoints resolve the workspace root from `workspace-map.json` instead of fixed parent depth.
- All-corrupt smoke candidate states now include the newest corrupt candidate filename in both startup and context snapshots.
- `session_bootstrap.py` keeps the backward-compatible `latest_smoke` display string and adds structured `latest_smoke_evidence` metadata for valid, corrupt, and missing smoke states.

### Verification
- `python -m pytest tests/test_ops_scripts_reports.py -q -p no:cacheprovider` -> `44 passed`
- `python -m pytest tests/test_workspace_smoke.py tests/test_ops_scripts_reports.py -q -p no:cacheprovider` -> `69 passed`
- `python -m pytest tests/test_workspace_smoke.py tests/test_ops_scripts_reports.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `75 passed`
- `python -m pytest tests/test_workspace_smoke.py tests/test_security_gate_contracts.py tests/test_ops_scripts_reports.py apps/desci-platform/backend/tests/test_ab_test_matching.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `199 passed`
- `python ops\scripts\session_bootstrap.py --json-out var\session-bootstrap-2026-05-28-structured-smoke-evidence.json` -> latest smoke `8/8 PASS`; `latest_smoke_evidence.status=valid`, `passed=8`, `total=8`, `report_status=complete`
- `python ops\scripts\generate_context_snapshot.py --dry-run` -> latest smoke `8/8 PASS`
- `python scripts\session_bootstrap.py --json-out var\session-bootstrap-2026-05-28-legacy-root-smoke.json` -> latest smoke `8/8 PASS`
- `python scripts\generate_context_snapshot.py --dry-run` -> latest smoke `8/8 PASS`

### Result
- Startup and context snapshots no longer trust internally contradictory smoke evidence or caller-order-sensitive candidate lists.

## 2026-05-28 (Workspace Smoke Schema Docs Cleanup)

### Scope
- Removed stale root quality-gate wording that described workspace smoke JSON as a bare array.
- Documented schema v1 object fields and nested `results` entry fields.
- Added workspace-smoke assertions to prevent the old wording from returning.

### Verification
- `python -m pytest tests/test_workspace_smoke.py::test_quality_gate_documents_incremental_json_evidence tests/test_workspace_smoke.py::test_quality_gate_documents_desci_release_readiness_coverage apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `8 passed`
- `python -m pytest tests/test_workspace_smoke.py tests/test_ops_scripts_reports.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `48 passed`
- `python -m pytest tests/test_workspace_smoke.py tests/test_security_gate_contracts.py tests/test_ops_scripts_reports.py apps/desci-platform/backend/tests/test_ab_test_matching.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `172 passed`

### Result
- Root smoke evidence documentation now matches the schema v1 writer and consumer contract.

## 2026-05-28 (Quality Gate Operator JSON Contract)

### Scope
- Locked root `docs/QUALITY_GATE.md` wording so canonical DeSci release readiness explicitly covers operator JSON evidence contracts.
- Added workspace-smoke assertions for atomic `--json-out` writer coverage and dry-run artifact validation skip semantics.
- Confirmed the DeSci release-readiness command still runs `test_deployment_docs.py`, which enforces the concrete writer contract.

### Verification
- `python -m pytest tests/test_workspace_smoke.py::test_quality_gate_documents_desci_release_readiness_coverage tests/test_workspace_smoke.py::test_quality_gate_documents_incremental_json_evidence apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `8 passed`
- `python -m pytest tests/test_workspace_smoke.py tests/test_security_gate_contracts.py tests/test_ops_scripts_reports.py apps/desci-platform/backend/tests/test_ab_test_matching.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `172 passed`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-28-quality-gate-operator-json-contract.json` -> `8/8 PASS`

### Result
- Canonical DeSci release readiness now visibly includes the operator evidence contract in the root quality gate.

## 2026-05-28 (Operator JSON Writer Contract)

### Scope
- DeSci operator scripts that expose `--json-out`.
- Release-readiness docs tests.

### Changes
- Added a docs/contract test requiring all operator JSON output scripts to use the shared `write_json_atomic` helper.
- Covered `scripts/env_doctor.py`, `scripts/deploy_readiness.py`, `scripts/product_smoke.py`, `scripts/browser_smoke.py`, `scripts/release_gate.py`, and `backend/scripts/ab_test_matching.py`.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_ab_test_matching.py -q -p no:cacheprovider` -> `11 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_ab_test_matching.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py tests/test_security_gate_contracts.py -q -p no:cacheprovider` -> `130 passed`
- `python ops\scripts\run_workspace_smoke.py --scope cie --json-out var\workspace-smoke-cie-2026-05-28-post-desci-contract-check.json` -> `2/2 PASS`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-28-operator-json-contract.json` -> `8/8 PASS`

### Result
- Atomic evidence writes are now a tested DeSci operator-script invariant, not just a current implementation detail.

## 2026-05-28 (Atomic A/B Matching Evidence)

### Scope
- `backend/scripts/ab_test_matching.py --json-out` evaluation evidence.

### Changes
- Added schema v1 metadata (`schema_version`, `generated_at`, `ok`) to the A/B matching JSON summary.
- Reused the shared atomic evidence writer for JSON output.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_ab_test_matching.py -q -p no:cacheprovider` -> `5 passed`
- `python backend\scripts\ab_test_matching.py --top-k 3 --json-out ..\..\var\desci-ab-test-matching-2026-05-28-atomic-cli.json` -> schema v1, ok=true, no `.tmp`
- `python -m pytest apps/desci-platform/backend/tests/test_ab_test_matching.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py tests/test_security_gate_contracts.py -q -p no:cacheprovider` -> `129 passed`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-28-ab-test-evidence-atomic.json` -> `8/8 PASS`

### Result
- Experiment/evaluation evidence now follows the same machine-readable and interrupted-write guarantees as release evidence.

## 2026-05-28 (Release-Gate Dry-Run Artifact Skip)

### Scope
- `scripts/release_gate.py --dry-run --json-out` artifact reporting.
- Release handoff docs for dry-run semantics.

### Changes
- Dry-run results now use `dry_run_artifact_reports()` so expected child artifact paths are listed without reading existing files from disk.
- Dry-run artifact reports include `validation_skipped: true` and `validation_skip_reason: dry_run`.
- Added regression coverage proving stale invalid artifacts are not parsed during dry-run JSON report generation.
- Updated README, deployment guide, and operations runbook to document the behavior.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `60 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py tests/test_security_gate_contracts.py -q -p no:cacheprovider` -> `124 passed`
- `python scripts\release_gate.py --dry-run --skip-compose --skip-backend --skip-frontend --skip-contracts --env-evidence-dir ..\..\var --json-out ..\..\var\desci-release-gate-2026-05-28-dry-run-artifact-skip.json` -> schema v1, ok=true, `validation_skipped=1`, no validation failures
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-28-dry-run-artifact-skip.json` -> `8/8 PASS`

### Result
- Dry-run handoff reports now describe planned evidence paths without being contaminated by stale child files.

## 2026-05-28 (Atomic Child Evidence Reports)

### Scope
- DeSci JSON evidence writers for env doctor, deploy readiness, product smoke, browser smoke, and release gate.
- Release handoff documentation and security fixture hygiene.

### Changes
- Added `scripts/evidence_io.py` for shared same-directory temp-file JSON writes followed by atomic replacement.
- Updated all DeSci `--json-out` evidence writers to use the shared atomic writer.
- Updated README, deployment guide, and operations runbook to describe parent and child reports as atomically replaced.
- Replaced a PEM-shaped deploy-readiness test fixture with `not-a-real-test-private-key`.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py tests/test_security_gate_contracts.py -q -p no:cacheprovider` -> `123 passed`
- `python -m py_compile apps\desci-platform\scripts\evidence_io.py apps\desci-platform\scripts\env_doctor.py apps\desci-platform\scripts\deploy_readiness.py apps\desci-platform\scripts\product_smoke.py apps\desci-platform\scripts\browser_smoke.py apps\desci-platform\scripts\release_gate.py` -> passed
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-28-atomic-child-evidence.json` -> `8/8 PASS`
- Direct CLI JSON writes:
  - `python scripts\env_doctor.py --profile local --ignore-process-env --json-out ..\..\var\desci-env-doctor-2026-05-28-atomic-cli.json` -> schema v1, ok=true, no `.tmp`
  - `python scripts\deploy_readiness.py --target github --ignore-process-env --json-out ..\..\var\desci-deploy-readiness-2026-05-28-atomic-cli.json` -> schema v1, ok=false, no `.tmp`
  - `python scripts\product_smoke.py --api http://127.0.0.1:1 --skip-frontend --retries 0 --timeout 0.2 --json-out ..\..\var\desci-product-smoke-2026-05-28-atomic-cli-failure.json` -> schema v1, ok=false, no `.tmp`
  - `python scripts\browser_smoke.py --frontend http://127.0.0.1:1 --timeout 0.2 --skip-protected --json-out ..\..\var\desci-browser-smoke-2026-05-28-atomic-cli-failure.json` -> schema v1, ok=false, no `.tmp`
  - `python scripts\release_gate.py --dry-run --skip-compose --skip-backend --skip-frontend --skip-contracts --env-evidence-dir ..\..\var --json-out ..\..\var\desci-release-gate-2026-05-28-atomic-cli-chain-dry-run.json` -> schema v1, ok=true, no `.tmp`

### Result
- The full DeSci release handoff evidence chain now has interrupted-write protection, not just the parent report.

## 2026-05-28 (Atomic Release-Gate Parent Report)

### Scope
- `scripts/release_gate.py --json-out` parent handoff report.
- README, deployment guide, and operations runbook release-evidence documentation.

### Changes
- `write_json_report()` now writes to a same-directory temporary file before atomically replacing the parent release-gate JSON report.
- Added regression coverage that verifies existing report replacement and temporary-file cleanup.
- Documented the atomic parent-report behavior in release handoff docs.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `59 passed`
- `python -m pytest tests/test_workspace_smoke.py tests/test_security_gate_contracts.py tests/test_ops_scripts_reports.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `125 passed`
- `python scripts\release_gate.py --dry-run --skip-compose --skip-backend --skip-frontend --skip-contracts --json-out ..\..\var\desci-release-gate-2026-05-28-atomic-parent-dry-run.json` -> parent JSON written; `.tmp` absent
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-28-release-gate-atomic-parent.json` -> `8/8 PASS`

### Result
- Release handoff evidence now has the same interrupted-write protection as workspace smoke evidence.

## 2026-05-28 (Resilient Workspace Smoke Report Consumers)

### Scope
- Startup/context smoke evidence readers.
- Quality gate contract for unreadable smoke candidates.

### Changes
- Added `latest_valid_smoke_report()` so smoke consumers skip unreadable candidates and use the newest valid report.
- Updated `session_bootstrap.py` and `generate_context_snapshot.py` to use the shared valid-report selector.
- Documented the corrupt-candidate fallback behavior in `docs/QUALITY_GATE.md`.

### Verification
- `python -m pytest tests/test_workspace_smoke.py tests/test_ops_scripts_reports.py -q -p no:cacheprovider` -> `34 passed`
- `python ops\scripts\session_bootstrap.py --json-out var\session-bootstrap-2026-05-28-smoke-consumer-corrupt-skip.json` -> latest smoke reported as `2/2 PASS`
- `python ops\scripts\generate_context_snapshot.py --dry-run` -> latest smoke reported as `2/2 PASS`

### Result
- A single malformed smoke artifact no longer hides the latest valid product-readiness evidence.

## 2026-05-28 (Workspace Smoke Report Consumers)

### Scope
- Startup and context snapshot scripts that read workspace smoke evidence.
- Backward compatibility for legacy smoke JSON reports.

### Changes
- Added a shared smoke report summarizer for both legacy array payloads and `schema_version: 1` object payloads.
- Updated `session_bootstrap.py` and `generate_context_snapshot.py` to scan `var/workspace-smoke*.json` plus legacy `var/smoke/*.json`.
- Added regression coverage for partial schema v1 summaries and legacy payload summaries.

### Verification
- `python -m pytest tests/test_ops_scripts_reports.py -q -p no:cacheprovider` -> `9 passed`
- `python -m pytest tests/test_workspace_smoke.py tests/test_security_gate_contracts.py tests/test_ops_scripts_reports.py apps/desci-platform/backend/tests/test_env_doctor.py -q -p no:cacheprovider` -> `65 passed`
- `python ops\scripts\run_workspace_smoke.py --scope cie --json-out var\workspace-smoke-cie-2026-05-28-json-schema-v1-consumer-safe.json` -> `2/2 PASS`
- `python ops\scripts\session_bootstrap.py --json-out var\session-bootstrap-2026-05-28-smoke-schema-v1-consumer-safe-rerun.json` -> latest smoke reported as `2/2 PASS`
- `python ops\scripts\generate_context_snapshot.py --dry-run` -> latest smoke reported as `2/2 PASS`

### Result
- Existing workspace startup/context summaries now remain accurate after the smoke JSON schema migration.

## 2026-05-28 (Workspace Smoke JSON Schema v1)

### Scope
- Workspace smoke runner JSON report payload.
- Quality-gate documentation for machine-readable smoke evidence.

### Changes
- Replaced bare array smoke JSON with `schema_version: 1` object payloads.
- Added `generated_at`, `status`, `summary`, and `results` fields to each smoke JSON report.
- Updated workspace smoke tests and `docs/QUALITY_GATE.md` to enforce the schema and partial/complete status semantics.

### Verification
- `python -m pytest tests/test_workspace_smoke.py tests/test_security_gate_contracts.py apps/desci-platform/backend/tests/test_env_doctor.py -q -p no:cacheprovider` -> `56 passed`
- `python -m pytest tests/test_workspace_smoke.py::test_main_writes_json_report_for_selected_scope tests/test_workspace_smoke.py::test_main_updates_json_report_after_each_completed_check tests/test_workspace_smoke.py::test_write_json_report_replaces_existing_report_atomically -q -p no:cacheprovider` -> `3 passed`
- `python ops\scripts\run_workspace_smoke.py --scope cie --json-out var\workspace-smoke-cie-2026-05-28-json-schema-v1-evidence.json` -> `2/2 PASS`

### Result
- Smoke evidence is now explicit about schema, completion status, and summary counts.

## 2026-05-28 (Atomic Workspace Smoke Evidence)

### Scope
- Workspace smoke runner JSON report writer.
- Quality-gate documentation for partial evidence safety.

### Changes
- `write_json_report()` now writes to a same-directory temporary file before atomically replacing the target JSON report.
- Added regression coverage that verifies an existing report is replaced and the temporary file is removed.
- Updated `docs/QUALITY_GATE.md` to state that incremental JSON writes are atomic.

### Verification
- `python -m pytest tests/test_workspace_smoke.py tests/test_security_gate_contracts.py apps/desci-platform/backend/tests/test_env_doctor.py -q -p no:cacheprovider` -> `56 passed`
- `python -m pytest tests/test_workspace_smoke.py::test_quality_gate_documents_incremental_json_evidence tests/test_workspace_smoke.py::test_write_json_report_replaces_existing_report_atomically -q -p no:cacheprovider` -> `2 passed`
- `python ops\scripts\run_workspace_smoke.py --scope cie --json-out var\workspace-smoke-cie-2026-05-28-atomic-json-evidence.json` -> `2/2 PASS`
- Temp file check for `var\workspace-smoke-cie-2026-05-28-atomic-json-evidence.json.tmp` -> not present

### Result
- Smoke evidence now survives both long-running partial execution and interrupted report writes more reliably.

## 2026-05-28 (Incremental Workspace Smoke Evidence)

### Scope
- Workspace smoke runner JSON evidence behavior.
- Quality-gate documentation for long `--scope all` runs.

### Changes
- `run_workspace_smoke.py --json-out` now writes the JSON report after each completed check, not only after the final summary.
- Added workspace smoke contract coverage for incremental JSON updates.
- Documented the partial-evidence behavior in `docs/QUALITY_GATE.md`.

### Verification
- `python -m pytest tests/test_workspace_smoke.py tests/test_security_gate_contracts.py apps/desci-platform/backend/tests/test_env_doctor.py -q -p no:cacheprovider` -> `55 passed`
- `python -m pytest tests/test_workspace_smoke.py::test_quality_gate_documents_incremental_json_evidence tests/test_workspace_smoke.py::test_main_updates_json_report_after_each_completed_check -q -p no:cacheprovider` -> `2 passed`
- `python ops\scripts\run_workspace_smoke.py --scope cie --json-out var\workspace-smoke-cie-2026-05-28-incremental-json-evidence.json` -> `2/2 PASS`

### Result
- Long canonical smoke runs now preserve completed-check evidence even if the shell stops before the run finishes.

## 2026-05-28 (Split-Scope Workspace Product Readiness)

### Scope
- Current canonical workspace smoke evidence across all supported scopes.
- Security contract false-positive cleanup for DeSci env-doctor test fixtures.

### Changes
- Replaced a PEM-shaped dummy private key in `test_env_doctor.py` with a non-secret test string so the high-risk secret scanner does not flag fixture text as a live private-key block.
- Recorded split-scope canonical smoke evidence after monolithic `--scope all` exceeded the interactive timeout before writing JSON.

### Verification
- `python ops\scripts\run_workspace_smoke.py --scope all --json-out var\workspace-smoke-all-2026-05-28-current-product-readiness.json` -> timed out before JSON output
- `python -m pytest tests/test_security_gate_contracts.py apps/desci-platform/backend/tests/test_env_doctor.py -q -p no:cacheprovider` -> `32 passed`
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-05-28-current-product-readiness.json` -> `7/7 PASS`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-28-release-readiness-doc-list-locked.json` -> `8/8 PASS`
- `python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-2026-05-28-current-product-readiness.json` -> `5/5 PASS`
- `python ops\scripts\run_workspace_smoke.py --scope mcp --json-out var\workspace-smoke-mcp-2026-05-28-current-product-readiness.json` -> `6/6 PASS`
- `python ops\scripts\run_workspace_smoke.py --scope getdaytrends --json-out var\workspace-smoke-getdaytrends-2026-05-28-current-product-readiness.json` -> `3/3 PASS`
- `python ops\scripts\run_workspace_smoke.py --scope cie --json-out var\workspace-smoke-cie-2026-05-28-current-product-readiness.json` -> `2/2 PASS`

### Result
- Current split-scope canonical evidence covers `31/31 PASS` across workspace, DeSci, AgriGuard, MCP, getdaytrends, and CIE.

## 2026-05-28 (Quality Gate Release-Readiness File List)

### Scope
- `docs/QUALITY_GATE.md` DeSci release-readiness documentation.
- Workspace smoke contract tests.

### Changes
- Added the exact DeSci release-readiness pytest file list to the quality-gate document.
- Strengthened the workspace smoke contract so the documented list must match `DESCI_RELEASE_READINESS_TESTS`.

### Verification
- `python -m pytest tests/test_workspace_smoke.py apps/desci-platform/backend/tests/test_worker.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `31 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_llm_fallback_policy.py apps/desci-platform/backend/tests/test_auth.py apps/desci-platform/backend/tests/test_worker.py -q -p no:cacheprovider` -> `122 passed`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-28-release-readiness-doc-list-locked.json` -> `8/8 PASS`

### Result
- Operators can inspect the quality-gate document and see the exact DeSci release-readiness pytest files that the canonical runner executes.

## 2026-05-28 (Release-Readiness Test List Contract)

### Scope
- Canonical DeSci release-readiness pytest command in `ops/scripts/run_workspace_smoke.py`.
- Workspace smoke contract tests.

### Changes
- Added `DESCI_RELEASE_READINESS_TESTS` as the single ordered source for the DeSci release-readiness pytest file list.
- Strengthened `tests/test_workspace_smoke.py` to assert the exact ordered file list used by the canonical smoke runner.

### Verification
- `python -m pytest tests/test_workspace_smoke.py apps/desci-platform/backend/tests/test_worker.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `31 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_llm_fallback_policy.py apps/desci-platform/backend/tests/test_auth.py apps/desci-platform/backend/tests/test_worker.py -q -p no:cacheprovider` -> `122 passed`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-28-release-readiness-list-locked.json` -> `8/8 PASS`

### Result
- The release-readiness test set is now locked as a deliberate contract instead of a manually duplicated command fragment.

## 2026-05-28 (Quality Gate Documentation Alignment)

### Scope
- Workspace quality-gate documentation.
- Workspace smoke contract tests.
- Canonical DeSci release-readiness smoke evidence.

### Changes
- Updated `docs/QUALITY_GATE.md` so the DeSci release-readiness description includes production auth, LLM fallback policy, and worker bootstrap/dispatch behavior.
- Added a workspace smoke contract assertion that keeps that quality-gate description aligned with the runner's canonical coverage.

### Verification
- `python -m pytest tests/test_workspace_smoke.py apps/desci-platform/backend/tests/test_worker.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `31 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_llm_fallback_policy.py apps/desci-platform/backend/tests/test_auth.py apps/desci-platform/backend/tests/test_worker.py -q -p no:cacheprovider` -> `122 passed`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-28-quality-gate-docs-worker-covered.json` -> `8/8 PASS`; `desci release readiness contracts` includes `test_worker.py`

### Result
- The documented quality gate now matches the actual DeSci release-readiness coverage.

## 2026-05-28 (Worker Env Bootstrap Readiness)

### Scope
- Backend worker import/bootstrap order in `backend/worker.py`.
- Canonical DeSci release-readiness smoke contract coverage.
- Operator docs for API and worker runtime env behavior.

### Changes
- Moved worker `load_dotenv()` before production logging setup.
- Added a worker source-order regression test for `.env` loading before env-sensitive bootstrap.
- Added `apps/desci-platform/backend/tests/test_worker.py` to canonical `desci release readiness contracts`.

### Verification
- `python -m py_compile apps/desci-platform/backend/main.py apps/desci-platform/backend/worker.py` -> PASS
- `python -m pytest apps/desci-platform/backend/tests/test_worker.py apps/desci-platform/backend/tests/test_api_endpoints.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `77 passed`
- `python -m pytest tests/test_workspace_smoke.py apps/desci-platform/backend/tests/test_worker.py -q -p no:cacheprovider` -> `25 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_llm_fallback_policy.py apps/desci-platform/backend/tests/test_auth.py apps/desci-platform/backend/tests/test_worker.py -q -p no:cacheprovider` -> `122 passed`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-28-worker-env-bootstrap-gated.json` -> `8/8 PASS`; `desci release readiness contracts` includes `test_worker.py`

### Result
- Worker runtime env bootstrap now matches the API runtime posture and is protected by the canonical DeSci smoke gate.

## 2026-05-28 (Runtime Env Bootstrap Ordering)

### Scope
- FastAPI runtime import/bootstrap order in `backend/main.py`.
- Runtime logging, auth import, and CORS initialization.
- Operator docs for local handoff/runtime env behavior.

### Changes
- Moved `load_dotenv()` before production logging setup, `get_current_user` import, and CORS default/origin calculation.
- Added a source-order contract test so `.env` loading remains ahead of env-sensitive bootstrap.
- Documented that runtime `.env` values are loaded before logging, authentication, and CORS bootstrap.

### Verification
- `python -m py_compile apps/desci-platform/backend/main.py` -> PASS
- `python -m pytest apps/desci-platform/backend/tests/test_api_endpoints.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `72 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_llm_fallback_policy.py apps/desci-platform/backend/tests/test_auth.py -q -p no:cacheprovider` -> `117 passed`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-28-runtime-env-bootstrap-gated.json` -> `8/8 PASS`

### Result
- Local/runtime handoff no longer risks booting env-sensitive services before `.env` values are available.

## 2026-05-27 (Runtime CORS Parser Alignment)

### Scope
- Runtime FastAPI CORS middleware registration.
- Runtime `/ready` CORS origin parsing.
- Operator docs for production CORS allowlists.

### Changes
- Added a shared origin-list parser for runtime CORS middleware and readiness checks.
- Trimmed and filtered comma-separated `ALLOWED_ORIGINS` entries before registering `CORSMiddleware`.
- Documented that CORS whitespace is normalized consistently at runtime and in readiness checks.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_api_endpoints.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `71 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_llm_fallback_policy.py apps/desci-platform/backend/tests/test_auth.py -q -p no:cacheprovider` -> `117 passed`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-cors-runtime-parser-aligned.json` -> `8/8 PASS`

### Result
- Production handoff no longer has a CORS parser mismatch where readiness strips whitespace but the actual middleware keeps it.

## 2026-05-27 (Production Frontend-Origin Readiness)

### Scope
- Runtime `/ready` CORS launch-readiness checks.
- `env_doctor.py --profile production` and `deploy_readiness.py` frontend/API URL relationship checks.
- Operator docs for production frontend origin handoff.

### Changes
- Runtime `/ready` rejects `ALLOWED_ORIGINS` when the only configured CORS origin matches `VITE_API_BASE_URL`'s API origin.
- Env-doctor and deploy-readiness require a deployed frontend HTTPS origin in `ALLOWED_ORIGINS`.
- Operator docs now state that using the API origin as the only CORS origin is not accepted for production handoff.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_api_endpoints.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `70 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_llm_fallback_policy.py apps/desci-platform/backend/tests/test_auth.py -q -p no:cacheprovider` -> `117 passed`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-production-frontend-origin-gated.json` -> `8/8 PASS`

### Result
- Production handoff no longer treats a backend/API origin-only CORS allowlist as proof that the deployed frontend can call the API.

## 2026-05-27 (Production URL Origin Readiness)

### Scope
- Runtime `/ready` CORS launch-readiness checks.
- `env_doctor.py --profile production` and `deploy_readiness.py` URL preflight checks.
- Operator docs for production frontend/backend URL handoff.

### Changes
- Runtime CORS readiness now requires every `ALLOWED_ORIGINS` entry to be a public `https://` origin.
- Runtime readiness, env-doctor, and deploy-readiness reject CORS origins with paths, queries, or fragments.
- Env-doctor and deploy-readiness require `VITE_API_BASE_URL` to be a public `https://` URL.
- Operator docs now state that production CORS entries are origin-only and the frontend API base must use HTTPS.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_api_endpoints.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `67 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_llm_fallback_policy.py apps/desci-platform/backend/tests/test_auth.py -q -p no:cacheprovider` -> `115 passed`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-production-url-origin-gated.json` -> `8/8 PASS`

### Result
- Production handoff no longer accepts HTTP API URLs or path-bearing CORS values as launch-ready.

## 2026-05-27 (Production CORS Readiness)

### Scope
- Runtime `/ready` launch-readiness checks.
- `env_doctor.py --profile production` and `deploy_readiness.py` CORS preflight checks.
- Operator docs for production CORS allowlists.

### Changes
- Added required runtime `/ready` `cors` check.
- Production readiness now fails missing `ALLOWED_ORIGINS`.
- Runtime readiness, env-doctor, and deploy-readiness reject wildcard, localhost, and documentation/example CORS origins.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_api_endpoints.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `62 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_llm_fallback_policy.py apps/desci-platform/backend/tests/test_auth.py -q -p no:cacheprovider` -> `111 passed`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-production-cors-gated.json` -> `8/8 PASS`

### Result
- Production launch handoff no longer accepts permissive or local-only CORS allowlists as ready.

## 2026-05-27 (Mounted Google Credentials Readiness)

### Scope
- Runtime `/ready` auth check.
- Operator docs for Firebase service-account file mounts.

### Changes
- `/ready` now requires `GOOGLE_APPLICATION_CREDENTIALS` to point to an existing file before auth is considered configured.
- Missing credential-file paths no longer produce a false-ready auth check.
- Kept deploy-preflight/env-doctor value checks separate because those often run before platform secrets are mounted.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_api_endpoints.py apps/desci-platform/backend/tests/test_auth.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `39 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_llm_fallback_policy.py apps/desci-platform/backend/tests/test_auth.py -q -p no:cacheprovider` -> `109 passed`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-google-credentials-file-gated.json` -> `8/8 PASS`

### Result
- Runtime readiness no longer reports auth ready when the credential-file mount is missing.

## 2026-05-27 (Firebase Service Account JSON Shape)

### Scope
- Runtime Firebase auth initialization.
- `/ready`, `env_doctor.py --profile production`, and `deploy_readiness.py` backend auth checks.
- Operator docs for secret-manager Firebase service-account JSON.

### Changes
- Added service-account JSON shape validation requiring `project_id`, `client_email`, and `private_key`.
- `/ready`, env-doctor, and deploy-readiness no longer treat incomplete or unparsable `FIREBASE_SERVICE_ACCOUNT_JSON` as backend auth configured.
- Runtime auth initialization now catches invalid JSON/certificate errors and leaves token verification disabled instead of crashing import.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_api_endpoints.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_auth.py -q -p no:cacheprovider` -> `63 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_llm_fallback_policy.py apps/desci-platform/backend/tests/test_auth.py -q -p no:cacheprovider` -> `108 passed`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-service-account-json-shape-gated.json` -> `8/8 PASS`

### Result
- Backend auth readiness now reflects credentials that can actually initialize Firebase token verification.

## 2026-05-27 (Backend Auth Credential Policy)

### Scope
- Runtime Firebase auth initialization.
- `/ready`, `env_doctor.py --profile production`, and `deploy_readiness.py` auth checks.
- Operator documentation for production backend auth credentials.

### Changes
- Removed `FIREBASE_PROJECT_ID` as a backend auth credential for `/ready`, env-doctor, and deploy-readiness.
- Kept `FIREBASE_PROJECT_ID` as frontend/project metadata only.
- Added runtime initialization support for `FIREBASE_SERVICE_ACCOUNT_JSON`.
- Added regression coverage proving project ID alone fails backend auth readiness.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_api_endpoints.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_auth.py -q -p no:cacheprovider` -> `58 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_llm_fallback_policy.py apps/desci-platform/backend/tests/test_auth.py -q -p no:cacheprovider` -> `104 passed`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-backend-auth-credential-gated.json` -> `8/8 PASS`

### Result
- Production handoff checks now require credentials that can actually verify Firebase ID tokens.

## 2026-05-27 (Production Web3 Mock-Mode Policy)

### Scope
- `/ready` Web3 launch-readiness checks and `env_doctor.py --profile production`.
- Operator documentation for production Web3 readiness.

### Changes
- `/ready` ignores `MOCK_MODE=true` as Web3 configured/available when `ENV=production`.
- `env_doctor.py --profile production` ignores `MOCK_MODE=true` as Web3 configuration.
- Local mock mode remains accepted for local env-doctor/readiness checks.
- Production Web3 readiness now requires real `WEB3_RPC_URL` plus at least one deployed contract address.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_api_endpoints.py -q -p no:cacheprovider` -> `40 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_llm_fallback_policy.py apps/desci-platform/backend/tests/test_auth.py -q -p no:cacheprovider` -> `102 passed`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-production-web3-mock-mode-docs-gated.json` -> `8/8 PASS`

### Result
- Production operator surfaces no longer show mock Web3 mode as launch-ready Web3 configuration.

## 2026-05-27 (Production Auth Bypass Policy)

### Scope
- FastAPI auth dependency and `/ready` launch-readiness auth checks.
- Canonical DeSci release-readiness coverage for production no-bypass behavior.

### Changes
- `ALLOW_TEST_BYPASS=true` only authenticates the test token outside production.
- `ALLOW_DEV_AUTH_FALLBACK=true` only returns a development user outside production.
- `/ready` ignores `ALLOW_TEST_BYPASS` as auth configuration when `ENV=production`.
- Added production auth-bypass regression coverage and included `test_auth.py` in canonical `desci release readiness contracts`.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_auth.py apps/desci-platform/backend/tests/test_api_endpoints.py tests/test_workspace_smoke.py -q -p no:cacheprovider` -> `47 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_auth.py tests/test_workspace_smoke.py -q -p no:cacheprovider` -> `31 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_llm_fallback_policy.py apps/desci-platform/backend/tests/test_auth.py -q -p no:cacheprovider` -> `100 passed`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-production-auth-bypass-docs-gated.json` -> `8/8 PASS`

### Result
- Production launch cannot pass auth readiness or authenticate users through local smoke/test bypass switches.

## 2026-05-27 (Production LLM Fallback Policy)

### Scope
- RFP analysis and proposal-generation paths that can otherwise return simulated AI output.
- Canonical DeSci release-readiness coverage for production no-mock behavior.

### Changes
- Added shared `simulated_llm_fallback_allowed()` policy: simulated LLM output is allowed outside production only.
- Changed RFP analysis to raise in production when no LLM provider is configured, when LLM generation fails, or when LLM output is invalid.
- Changed proposal generation, literature synthesis, and review to reject mock output in production.
- Added `test_llm_fallback_policy.py` and included it in canonical `desci release readiness contracts`.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_llm_fallback_policy.py apps/desci-platform/backend/tests/test_analyzer_keywords.py apps/desci-platform/backend/tests/test_smoke_pipeline.py -q -p no:cacheprovider` -> `13 passed`
- `python -m pytest tests/test_workspace_smoke.py apps/desci-platform/backend/tests/test_llm_fallback_policy.py -q -p no:cacheprovider` -> `23 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_llm_fallback_policy.py tests/test_workspace_smoke.py -q -p no:cacheprovider` -> `28 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_llm_fallback_policy.py -q -p no:cacheprovider` -> `94 passed`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-production-llm-fallback-docs-gated.json` -> `8/8 PASS`

### Result
- Production RFP/proposal paths no longer return simulated AI content as if it were real output.

## 2026-05-27 (Validation Failed Artifact Paths)

### Scope
- Parent release-gate visibility for the exact child evidence files that failed validation.
- Focused on making CI and handoff dashboards actionable without traversing nested artifact reports.

### Changes
- Added conditional `artifact_summary.validation_failed_artifact_paths` aggregation at result and top level.
- Preserved existing `artifact_summary.validation_failures` failure-message aggregation.
- Documented the failed-path field in README, deployment guide, and operations runbook.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `58 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `91 passed`
- `python scripts\release_gate.py --external-readiness --external-target railway --env-file .env.production.example --env-file contracts\.env.missing --ignore-process-env --env-evidence-dir ..\..\var --external-evidence-dir ..\..\var --skip-compose --skip-backend --skip-frontend --skip-contracts --continue-on-failure --json-out ..\..\var\desci-release-gate-validation-failed-paths-dry-run.json` -> expected non-zero; parent and result summaries exposed failed child artifact paths
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-validation-failed-paths.json` -> `8/8 PASS`

### Result
- Release handoff dashboards can now link directly from a failed parent summary to the child evidence files that need inspection.

## 2026-05-27 (Validation Failure Summary)

### Scope
- Parent release-gate visibility for child evidence validation failure reasons.
- Focused on making failed handoff reports actionable without drilling into each child artifact.

### Changes
- Added conditional `artifact_summary.validation_failures` aggregation at result and top level.
- Kept per-artifact `validation_failures` unchanged while exposing the deduplicated parent summary.
- Documented the aggregated failure field in README, deployment guide, and operations runbook.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `58 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `91 passed`
- `python scripts\release_gate.py --external-readiness --external-target railway --env-file .env.production.example --env-file contracts\.env.missing --ignore-process-env --env-evidence-dir ..\..\var --external-evidence-dir ..\..\var --skip-compose --skip-backend --skip-frontend --skip-contracts --continue-on-failure --json-out ..\..\var\desci-release-gate-validation-failure-summary-dry-run.json` -> expected non-zero; parent and result summaries exposed child validation failure messages
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-validation-failure-summary.json` -> `8/8 PASS`

### Result
- Release handoff dashboards can now show exact child evidence failure reasons directly from parent `artifact_summary` objects.

## 2026-05-27 (Missing Env Source Required)

### Scope
- Release-gate validation for explicitly requested env-file sources.
- Focused on preventing missing env files from silently passing preflight handoff validation.

### Changes
- Added validation failure for preflight child evidence whose `sources.env_files[]` entries report `exists=false`.
- Kept missing-source report fields so parent reports still identify which source file was missing.
- Documented that release-gate env-file sources must exist in README, deployment guide, and operations runbook.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `58 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `91 passed`
- `python scripts\release_gate.py --external-readiness --external-target railway --env-file .env.production.example --env-file contracts\.env.missing --ignore-process-env --env-evidence-dir ..\..\var --external-evidence-dir ..\..\var --skip-compose --skip-backend --skip-frontend --skip-contracts --continue-on-failure --json-out ..\..\var\desci-release-gate-missing-env-source-required-dry-run.json` -> expected non-zero; parent gate failed on missing env-doctor source evidence as expected
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-missing-env-source-required.json` -> `8/8 PASS`

### Result
- Release handoff validation now treats missing explicitly requested env files as a hard evidence failure.

## 2026-05-27 (Missing Env Source Summary)

### Scope
- Parent release-gate visibility for missing env-file source provenance.
- Focused on making missing env-file inputs visible without opening child JSON artifacts.

### Changes
- Added `json_missing_env_file_count` and `json_missing_env_files` to artifact reports for preflight child evidence.
- Added aggregate `json_missing_env_file_count`, `has_missing_env_files`, and `json_missing_env_files` to artifact summaries.
- Documented the missing-source fields in README, deployment guide, and operations runbook.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `57 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `90 passed`
- `python scripts\release_gate.py --external-readiness --external-target railway --env-file .env.production.example --env-file contracts\.env.missing --ignore-process-env --env-evidence-dir ..\..\var --external-evidence-dir ..\..\var --skip-compose --skip-backend --skip-frontend --skip-contracts --continue-on-failure --json-out ..\..\var\desci-release-gate-missing-env-source-summary-dry-run.json` -> expected non-zero on template config; parent summary exposed the missing env-file source
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-missing-env-source-summary.json` -> `8/8 PASS`

### Result
- Release handoff dashboards can now show missing env-file source inputs directly from the parent release-gate report.

## 2026-05-27 (Preflight Source Non-Empty Paths)

### Scope
- Release-gate source provenance quality for env-doctor and deploy-readiness child evidence.
- Focused on preventing empty env-file source paths from passing handoff validation.

### Changes
- Tightened `sources.env_files[]` validation to require non-empty `path` and `resolved_path`.
- Kept boolean `exists` validation for each source entry.
- Added regression coverage for empty env-file source path.
- Documented non-empty source path requirements in README, deployment guide, and operations runbook.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `57 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `90 passed`
- `python scripts\release_gate.py --external-readiness --external-target railway --env-file .env.production.example --ignore-process-env --env-evidence-dir ..\..\var --external-evidence-dir ..\..\var --skip-compose --skip-backend --skip-frontend --skip-contracts --continue-on-failure --json-out ..\..\var\desci-release-gate-preflight-source-nonempty-path-dry-run.json` -> expected non-zero on template config; env/deploy source path validation passed and deploy-readiness failed only for expected missing secrets
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-preflight-source-nonempty-path.json` -> `8/8 PASS`

### Result
- Parent release-gate handoffs now reject empty env-file provenance that would make preflight evidence harder to reproduce.

## 2026-05-27 (Preflight Source Schema)

### Scope
- Release-gate validation for env-doctor and deploy-readiness source provenance.
- Focused on ensuring parent handoff reports can trust and reproduce source metadata.

### Changes
- Added source provenance validation requiring boolean `sources.include_process_env`.
- Added `sources.env_files[]` entry validation for `path`, `resolved_path`, and `exists`.
- Added regression coverage for malformed deploy-readiness source mode and malformed env-doctor env-file source entries.
- Documented the source entry contract in README, deployment guide, and operations runbook.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `56 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `89 passed`
- `python scripts\release_gate.py --external-readiness --external-target railway --env-file .env.production.example --ignore-process-env --env-evidence-dir ..\..\var --external-evidence-dir ..\..\var --skip-compose --skip-backend --skip-frontend --skip-contracts --continue-on-failure --json-out ..\..\var\desci-release-gate-preflight-source-schema-dry-run.json` -> expected non-zero on template config; env/deploy source schemas passed and deploy-readiness failed only for expected missing secrets
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-preflight-source-schema.json` -> `8/8 PASS`

### Result
- Parent release-gate handoffs now reject malformed preflight source provenance instead of trusting incomplete source metadata.

## 2026-05-27 (Preflight Check Status Schema)

### Scope
- Release-gate validation for env-doctor and deploy-readiness child check rows.
- Focused on preventing malformed preflight checks from undermining summary consistency and dashboard triage.

### Changes
- Added preflight check schema validation requiring each child check to include a stable `id`.
- Restricted preflight child check `status` values to `pass`, `fail`, or `warn`.
- Added regression coverage for invalid deploy-readiness status and missing env-doctor check IDs.
- Documented the check row contract in README, deployment guide, and operations runbook.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `54 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `87 passed`
- `python scripts\release_gate.py --external-readiness --external-target railway --env-file .env.production.example --ignore-process-env --env-evidence-dir ..\..\var --external-evidence-dir ..\..\var --skip-compose --skip-backend --skip-frontend --skip-contracts --continue-on-failure --json-out ..\..\var\desci-release-gate-preflight-check-status-schema-dry-run.json` -> expected non-zero on template config; env/deploy child check schemas passed and deploy-readiness failed only for expected missing secrets
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-preflight-check-status-schema.json` -> `8/8 PASS`

### Result
- Parent release-gate handoffs now reject malformed preflight check rows before trusting summary counts or dashboard fields.

## 2026-05-27 (Preflight Summary Consistency)

### Scope
- Release-gate validation for env-doctor and deploy-readiness child evidence.
- Focused on preventing preflight artifacts whose summary counts disagree with their check rows.

### Changes
- Added preflight summary consistency validation for `total`, `passed`, `failed`, and `warnings` against `checks[].status`.
- Added regression coverage for inconsistent env-doctor and deploy-readiness child artifacts.
- Documented the consistency requirement in README, deployment guide, and operations runbook.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `52 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `85 passed`
- `python scripts\release_gate.py --external-readiness --external-target railway --env-file .env.production.example --ignore-process-env --env-evidence-dir ..\..\var --external-evidence-dir ..\..\var --skip-compose --skip-backend --skip-frontend --skip-contracts --continue-on-failure --json-out ..\..\var\desci-release-gate-preflight-summary-consistency-dry-run.json` -> expected non-zero on template config; env-doctor summary consistency passed and deploy-readiness failed only for expected missing secrets
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-preflight-summary-consistency.json` -> `8/8 PASS`

### Result
- Parent release-gate handoffs now reject inconsistent preflight evidence instead of trusting mismatched summary counts.

## 2026-05-27 (Artifact Summary Paths)

### Scope
- Parent release-gate summary navigation for env/deploy child evidence.
- Focused on showing which child artifact files back the failed/warning check summaries.

### Changes
- Added conditional `artifact_summary.artifact_paths` when failed/warning check-list summaries are present.
- Kept the field absent when summaries do not include failed/warning check lists, preserving runtime-only summary shape.
- Documented the `artifact_paths` summary field in README, deployment guide, and operations runbook.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `50 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `83 passed`
- `python scripts\release_gate.py --external-readiness --external-target railway --env-file .env.production.example --ignore-process-env --env-evidence-dir ..\..\var --external-evidence-dir ..\..\var --skip-compose --skip-backend --skip-frontend --skip-contracts --continue-on-failure --json-out ..\..\var\desci-release-gate-artifact-path-summary-dry-run.json` -> expected non-zero on template config; parent summary includes child evidence paths
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-artifact-summary-paths.json` -> `8/8 PASS`

### Result
- Release handoff dashboards can now link parent summary findings directly to the child evidence files.

## 2026-05-27 (Artifact Summary Check Lists)

### Scope
- Parent release-gate summary readability for env/deploy child evidence.
- Focused on showing exact failed and warning check IDs in summary blocks.

### Changes
- Added conditional `artifact_summary.json_failed_checks` and `artifact_summary.json_warning_checks` aggregation.
- Kept the fields absent when child evidence does not report check IDs, preserving runtime-only summary shape.
- Documented the summary check-list fields in README, deployment guide, and operations runbook.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `50 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `83 passed`
- `python scripts\release_gate.py --external-readiness --external-target railway --env-file .env.production.example --ignore-process-env --env-evidence-dir ..\..\var --external-evidence-dir ..\..\var --skip-compose --skip-backend --skip-frontend --skip-contracts --continue-on-failure --json-out ..\..\var\desci-release-gate-preflight-check-list-summary-dry-run.json` -> expected non-zero on template config; parent summary includes Railway failed IDs and env-doctor warning IDs
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-artifact-summary-check-lists.json` -> `8/8 PASS`

### Result
- Release handoff dashboards can now show exact problematic preflight checks directly from parent release-gate summaries.

## 2026-05-27 (Preflight Warning Summary)

### Scope
- Parent release-gate summary visibility for warning-level env/deploy child evidence.
- Focused on making top-level handoff reports show whether any child evidence contains warnings.

### Changes
- Added conditional `artifact_summary.json_warning_count` and `artifact_summary.has_warnings` when child evidence reports warning counts.
- Preserved existing runtime-only artifact summary shape unless warning-aware child evidence is present.
- Documented the warning summary fields in README, deployment guide, and operations runbook.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `50 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `83 passed`
- `python scripts\release_gate.py --external-readiness --external-target railway --env-file .env.production.example --ignore-process-env --env-evidence-dir ..\..\var --external-evidence-dir ..\..\var --skip-compose --skip-backend --skip-frontend --skip-contracts --continue-on-failure --json-out ..\..\var\desci-release-gate-preflight-warning-summary-dry-run.json` -> expected non-zero on template config; parent `artifact_summary` includes `json_warning_count=11` and `has_warnings=true`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-preflight-warning-summary.json` -> `8/8 PASS`

### Result
- Release handoff dashboards can now see package-level warning presence directly from parent release-gate summaries.

## 2026-05-27 (Preflight Warning Artifact Fields)

### Scope
- Parent release-gate triage for warning-level env/deploy child evidence.
- Focused on making warning counts and warning check IDs visible without requiring operators to open child JSON artifacts.

### Changes
- Added `json_check_warnings` and `json_warning_checks` to release-gate `artifact_reports` when child evidence includes warning counts.
- Kept failed external checks visible through `json_failed_checks`, including deploy-readiness check IDs.
- Documented warning and failed-check fields in README, deployment guide, and operations runbook.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `50 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `83 passed`
- `python scripts\release_gate.py --external-readiness --external-target railway --env-file .env.production.example --ignore-process-env --env-evidence-dir ..\..\var --external-evidence-dir ..\..\var --skip-compose --skip-backend --skip-frontend --skip-contracts --continue-on-failure --json-out ..\..\var\desci-release-gate-preflight-warning-artifact-dry-run.json` -> expected non-zero on template config; parent report includes env warning IDs and deploy failed check IDs
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-preflight-warning-artifact-fields.json` -> `8/8 PASS`

### Result
- Release handoff dashboards can now show both warning-level and failure-level preflight findings directly from the parent release-gate report.

## 2026-05-27 (Preflight Artifact Provenance Fields)

### Scope
- Parent release-gate readability for env-doctor and deploy-readiness child evidence.
- Focused on exposing checked profile, targets, env-file count, and process-env mode without requiring operators to open child JSON artifacts.

### Changes
- Added parsed preflight provenance fields to `artifact_reports`: `json_profile`, `json_targets`, `json_env_file_count`, and `json_include_process_env`.
- Expanded child failed-check extraction to support deploy-readiness `status=fail` checks by ID.
- Documented the fields in README, deployment guide, and operations runbook.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `50 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `83 passed`
- `python scripts\release_gate.py --external-readiness --external-target railway --env-file .env.production.example --ignore-process-env --env-evidence-dir ..\..\var --external-evidence-dir ..\..\var --skip-compose --skip-backend --skip-frontend --skip-contracts --continue-on-failure --json-out ..\..\var\desci-release-gate-preflight-provenance-artifact-dry-run.json` -> expected non-zero on template config; parent report includes preflight provenance fields and deploy failed check IDs
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-preflight-artifact-provenance-fields.json` -> `8/8 PASS`

### Result
- Release handoff dashboards can now read env/deploy provenance and failed external checks directly from the parent release-gate report.

## 2026-05-27 (Env-Doctor Artifact Handoff)

### Scope
- Release-gate handoff evidence for the baseline environment preflight.
- Focused on attaching env-doctor JSON evidence to the parent release-gate report.

### Changes
- Added `--env-evidence-dir` to `release_gate.py`.
- `release_gate.py` now passes `--json-out` to the default `env_doctor.py` step and writes `desci-env-doctor-release-gate.json`.
- Parent release-gate JSON reports now include the env-doctor child artifact in `artifact_reports` and aggregate it through `artifact_summary`.
- Added env-doctor artifact shape validation for schema version, timestamp, profile, summary counts, checks, and source provenance.
- Documented the env-doctor child artifact in README, deployment guide, and operations runbook.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `49 passed`
- `python scripts\release_gate.py --env-evidence-dir ..\..\var --skip-compose --skip-backend --skip-frontend --skip-contracts --dry-run --json-out ..\..\var\desci-release-gate-env-doctor-artifact-dry-run.json` -> dry-run OK; parent report records planned `desci-env-doctor-release-gate.json`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `82 passed`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-env-doctor-artifact.json` -> `8/8 PASS`

### Result
- Baseline env-doctor handoffs now include durable child evidence in the same parent report structure used for external readiness and runtime smoke artifacts.

## 2026-05-27 (External Readiness Artifact Handoff)

### Scope
- Release-gate handoff evidence for offline Railway/Vercel/Amoy/GitHub deployment readiness.
- Focused on attaching deploy-readiness JSON evidence to the parent release-gate report.

### Changes
- Added `--external-evidence-dir` to `release_gate.py`.
- `release_gate.py --external-readiness` now passes `--json-out` to `deploy_readiness.py` and writes `desci-deploy-readiness-release-gate.json`.
- Parent release-gate JSON reports now include the external readiness child artifact in `artifact_reports` and aggregate it through `artifact_summary`.
- Added deploy-readiness artifact shape validation for release-gate child evidence.
- Documented the external readiness child artifact in README, deployment guide, and operations runbook.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `46 passed`
- `python apps\desci-platform\scripts\release_gate.py --external-readiness --external-target railway --env-file .env.production.example --ignore-process-env --external-evidence-dir ..\..\var --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --dry-run --json-out ..\..\var\desci-release-gate-external-readiness-artifact-dry-run.json` -> dry-run OK; parent report records planned `desci-deploy-readiness-release-gate.json`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `79 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_release_gate.py tests/test_workspace_smoke.py -q -p no:cacheprovider` -> `79 passed`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-external-readiness-artifact.json` -> `8/8 PASS`

### Result
- External readiness handoffs now include durable deploy-readiness child evidence in the same parent report structure used for runtime smoke artifacts.

## 2026-05-27 (Preflight Source Provenance)

### Scope
- Reproducibility of env-doctor and deploy-readiness handoff evidence.
- Focused on recording which env files and process-env mode produced each preflight report.

### Changes
- Added `sources.env_files` to `env_doctor.py` CLI JSON reports, including original path, resolved path, and existence flag.
- Added `sources.include_process_env` to show whether process environment variables were overlaid.
- Added the same source provenance block to `deploy_readiness.py` CLI JSON reports.
- Documented source provenance fields in README, deployment guide, and operations runbook.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `25 passed`
- `python apps\desci-platform\scripts\env_doctor.py --profile production --env-file apps\desci-platform\.env.production.example --ignore-process-env --json-out var\desci-env-doctor-source-provenance.json` -> expected non-zero on template config; JSON includes `sources`
- `python apps\desci-platform\scripts\deploy_readiness.py --target all --env-file apps\desci-platform\.env.production.example --ignore-process-env --json-out var\desci-deploy-readiness-source-provenance.json` -> expected non-zero on template config; JSON includes `sources`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `76 passed`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-preflight-source-provenance.json` -> `8/8 PASS`

### Result
- Preflight evidence now records the exact configuration input sources needed to reproduce or audit an external-readiness decision.

## 2026-05-27 (Preflight Report Schema Version)

### Scope
- External readiness evidence format stability for env-doctor and deploy-readiness handoff reports.
- Focused on aligning preflight JSON reports with release-gate and runtime smoke report contracts.

### Changes
- Added `schema_version: 1` and `generated_at` to `env_doctor.py` JSON reports.
- Added `schema_version: 1` and `generated_at` to `deploy_readiness.py` JSON reports.
- Extended env/deploy/doc tests so the fields remain covered.
- Documented the versioned/timestamped preflight report contract in README, deployment guide, and operations runbook.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `23 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `74 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_release_gate.py tests/test_workspace_smoke.py -q -p no:cacheprovider` -> `76 passed`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-preflight-schema-version.json` -> `8/8 PASS`

### Result
- Preflight, release-gate, and runtime smoke evidence now share versioned/timestamped report semantics for handoff consumers.

## 2026-05-27 (Artifact Report Check Summary)

### Scope
- Parent release-gate failure triage for product/browser runtime child evidence.
- Focused on surfacing child check counts and failed check names without forcing operators to open child artifact JSON files.

### Changes
- Added parsed child evidence check summary fields to `artifact_reports`: `json_check_total`, `json_check_passed`, `json_check_failed`, and `json_failed_checks`.
- Added release-gate regression coverage for both passing child evidence and failed-check-name extraction.
- Documented the check summary fields in README, deployment guide, and operations runbook, with deployment-doc contracts preventing drift.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_release_gate.py -q -p no:cacheprovider` -> `43 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py -q -p no:cacheprovider` -> `38 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_release_gate.py tests/test_workspace_smoke.py -q -p no:cacheprovider` -> `76 passed`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-artifact-report-check-summary.json` -> `8/8 PASS`

### Result
- Parent release-gate reports now include enough parsed child evidence metadata for quick runtime smoke failure triage.

## 2026-05-27 (Artifact Report Audit Fields)

### Scope
- Parent release-gate report usability for dashboards and production handoff review.
- Focused on exposing child evidence target/timestamp metadata without requiring consumers to open every child artifact file.

### Changes
- Added parsed child evidence fields to release-gate `artifact_reports`: `json_generated_at`, `json_api`, and `json_frontend`.
- Extended release-gate tests so valid product-smoke artifacts expose these fields in the parent report.
- Documented the fields in README, deployment guide, and operations runbook, with deployment-doc contracts preventing drift.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_release_gate.py -q -p no:cacheprovider` -> `42 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py -q -p no:cacheprovider` -> `37 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_release_gate.py tests/test_workspace_smoke.py -q -p no:cacheprovider` -> `75 passed`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-artifact-report-audit-fields.json` -> `8/8 PASS`

### Result
- Parent release-gate reports now carry enough parsed audit metadata for operators to see which services were checked and when without dereferencing child artifacts.

## 2026-05-27 (Release Gate Parent Schema Version)

### Scope
- Parent release-gate JSON report format stability for production handoff packages.
- Focused on versioning the top-level report, not only product/browser child evidence.

### Changes
- Added `schema_version: 1` to the parent `release_gate.py` JSON report payload.
- Added release-gate regression assertions for the top-level schema version.
- Documented the parent report schema version in README, deployment guide, and operations runbook.
- Extended deployment-doc contracts so the docs mention parent and child schema versioning together.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_release_gate.py -q -p no:cacheprovider` -> `42 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py -q -p no:cacheprovider` -> `37 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_release_gate.py tests/test_workspace_smoke.py -q -p no:cacheprovider` -> `75 passed`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-release-gate-parent-schema-version.json` -> `8/8 PASS`

### Result
- Handoff consumers can now version their parser for the full release-gate JSON package as well as the runtime child evidence artifacts.

## 2026-05-27 (Runtime Smoke Audit Metadata)

### Scope
- Runtime smoke evidence auditability for production handoff and dashboard consumers.
- Focused on proving when evidence was generated and which running API/frontend targets were checked.

### Changes
- Added target and option metadata to product smoke JSON evidence: `generated_at`, `api`, `frontend`, `skip_frontend`, `timeout_seconds`, and `retries`.
- Added browser smoke JSON option metadata: `generated_at`, `frontend`, `timeout_seconds`, and `skip_protected`.
- Tightened release-gate child evidence validation so product/browser artifacts must include a parseable `generated_at` timestamp and required target URL fields.
- Documented the audit metadata in README, deployment guide, and operations runbook, with deployment-doc contracts preventing drift.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py -q -p no:cacheprovider` -> `37 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_release_gate.py -q -p no:cacheprovider` -> `50 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_release_gate.py tests/test_workspace_smoke.py -q -p no:cacheprovider` -> `75 passed`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-runtime-smoke-audit-metadata.json` -> `8/8 PASS`

### Result
- Release handoff evidence now identifies both the checked services and the generation time before the parent gate accepts product/browser child artifacts.

## 2026-05-27 (Release Gate Artifact Summary)

### Scope
- DeSci release handoff report hardening for runtime smoke child evidence.
- Focused on operator-readable aggregate status without changing product, contract, or deployment behavior.

### Changes
- Added `artifact_summary` to each release-gate result that carries expected runtime smoke artifacts.
- Added top-level `artifact_summary` to release-gate JSON reports so dashboards can aggregate child evidence existence, JSON validity, and validation failures without walking every artifact record.
- Extended release-gate contract assertions for dry-run and mixed valid/missing artifact scenarios.
- Documented the `artifact_summary` handoff field in the README, deployment guide, and operations runbook, with docs contract coverage.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py -q -p no:cacheprovider` -> `32 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py tests/test_workspace_smoke.py -q -p no:cacheprovider` -> `57 passed`
- `python apps\desci-platform\scripts\release_gate.py --runtime-smoke --runtime-smoke-strict-ready --runtime-api http://127.0.0.1:8000 --runtime-frontend http://127.0.0.1:5173 --runtime-evidence-dir var --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --dry-run --json-out var\desci-release-gate-runtime-smoke-artifact-summary-dry-run.json` -> dry-run OK with top-level and result-level artifact summaries.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-release-gate-artifact-summary.json` -> `8/8 PASS`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-release-gate-artifact-summary-docs.json` -> `8/8 PASS`

### Result
- Runtime-smoke handoff reports now expose both detailed per-file validation and aggregate artifact status.
- Dry-run reports remain skip-safe while making planned-but-unwritten child evidence explicit.

## 2026-05-27 (Product Smoke Check Failure Evidence)

### Scope
- Product/runtime smoke evidence hardening for production handoff diagnostics.

### Changes
- Added per-check `failures` arrays to `product_smoke.py` JSON evidence.
- Tightened release-gate product/browser child evidence validation so every check must expose a string `failures` list.
- Documented check-level failures in the operations runbook and locked the wording with deployment-doc tests.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_release_gate.py -q -p no:cacheprovider` -> `38 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py tests/test_workspace_smoke.py -q -p no:cacheprovider` -> `63 passed`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-product-smoke-check-failures.json` -> `8/8 PASS`

### Result
- Runtime smoke JSON is now self-contained enough for dashboards and handoffs to display check-specific failure causes without scraping logs.

## 2026-05-27 (Product Smoke Request Error Evidence)

### Scope
- Runtime smoke evidence consistency for network/request failures.

### Changes
- Updated `product_smoke.py` so request failures emit check reports with `ok=false`, `error`, and check-level `failures`.
- Added regression coverage for all-request-failure JSON evidence.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_product_smoke.py -q -p no:cacheprovider` -> `6 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py tests/test_workspace_smoke.py -q -p no:cacheprovider` -> `64 passed`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-product-smoke-request-error-evidence-rerun.json` -> `8/8 PASS`

### Result
- Product smoke evidence now has a stable per-check schema for both HTTP validation failures and request-level failures.

## 2026-05-27 (Smoke Summary Failed Check Semantics)

### Scope
- Runtime smoke evidence semantics for operator dashboards and release-gate validation.

### Changes
- Changed product smoke JSON `summary.failed` to count failed checks instead of failure messages, matching browser smoke semantics.
- Updated release-gate child evidence summary validation to compare `summary.failed` with failed check count.
- Added regressions for a single failed product check that produces multiple failure messages.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_release_gate.py -q -p no:cacheprovider` -> `41 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py tests/test_workspace_smoke.py -q -p no:cacheprovider` -> `72 passed`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-smoke-summary-failed-checks.json` -> `8/8 PASS`

### Result
- Product/browser runtime smoke summaries now expose check-count semantics consistently while preserving detailed failure-message arrays.

## 2026-05-27 (Runtime Smoke Evidence Schema Version)

### Scope
- Runtime smoke evidence format stability for release handoffs and dashboards.

### Changes
- Added `schema_version: 1` to product and browser smoke JSON evidence.
- Tightened release gate child evidence validation so product/browser runtime smoke artifacts must declare schema version 1.
- Added regression coverage for missing schema version rejection.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_release_gate.py -q -p no:cacheprovider` -> `48 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py tests/test_workspace_smoke.py -q -p no:cacheprovider` -> `73 passed`
- `python apps\desci-platform\scripts\release_gate.py --runtime-smoke --runtime-smoke-strict-ready --runtime-api http://127.0.0.1:8000 --runtime-frontend http://127.0.0.1:5173 --runtime-evidence-dir var --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --dry-run --json-out var\desci-release-gate-runtime-smoke-schema-version-dry-run.json` -> dry-run OK
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-smoke-schema-version.json` -> `8/8 PASS`

### Result
- Runtime smoke evidence is now versioned before production dashboards or handoff tooling depend on its JSON shape.

## 2026-05-27 (Release Gate Artifact Schema Version Reports)

### Scope
- Release gate JSON report readability for versioned runtime child evidence.

### Changes
- Added `json_schema_version` to release gate `artifact_reports` for existing JSON evidence artifacts.
- Kept artifact summary counts stable while exposing per-artifact schema version metadata.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py -q -p no:cacheprovider` -> `35 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py tests/test_workspace_smoke.py -q -p no:cacheprovider` -> `73 passed`
- `python apps\desci-platform\scripts\release_gate.py --runtime-smoke --runtime-smoke-strict-ready --runtime-api http://127.0.0.1:8000 --runtime-frontend http://127.0.0.1:5173 --runtime-evidence-dir var --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --dry-run --json-out var\desci-release-gate-runtime-smoke-artifact-schema-report-dry-run.json` -> dry-run OK
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-release-gate-artifact-schema-report.json` -> `8/8 PASS`

### Result
- Release gate reports now show both validation status and schema version for child evidence files.

## 2026-05-27 (Runtime Smoke Schema Version Docs)

### Scope
- Operator documentation alignment for versioned runtime smoke evidence.

### Changes
- Documented runtime child evidence `schema_version: 1` in the README, deployment guide, and operations runbook.
- Documented release-gate `artifact_reports[].json_schema_version` for dashboards and handoff packages.
- Added deployment-doc contracts to prevent docs/source drift.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `5 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_release_gate.py tests/test_workspace_smoke.py -q -p no:cacheprovider` -> `73 passed`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-smoke-schema-version-docs.json` -> `8/8 PASS`

### Result
- Runtime evidence schema versioning is now both enforced in code and visible in operator documentation.

## 2026-05-27 (Release Gate Artifact Schema Coverage Summary)

### Scope
- Release gate aggregate reporting for runtime child evidence schema-version coverage.

### Changes
- Added `schema_versioned` and `schema_unversioned` counts to release gate `artifact_summary`.
- Applied the counts at both per-result and top-level artifact summary levels.
- Documented the counts in the README, deployment guide, and operations runbook, with deployment-doc contracts preventing drift.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py -q -p no:cacheprovider` -> `35 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider` -> `5 passed`
- `python -m pytest apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py tests/test_workspace_smoke.py -q -p no:cacheprovider` -> `73 passed`
- `python apps\desci-platform\scripts\release_gate.py --runtime-smoke --runtime-smoke-strict-ready --runtime-api http://127.0.0.1:8000 --runtime-frontend http://127.0.0.1:5173 --runtime-evidence-dir var --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --dry-run --json-out var\desci-release-gate-runtime-smoke-artifact-schema-summary-dry-run.json` -> dry-run OK
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-release-gate-artifact-schema-summary-rerun.json` -> `8/8 PASS`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-05-27-release-gate-artifact-schema-summary-docs.json` -> `8/8 PASS`

### Result
- Dashboards can now summarize how much runtime child evidence is versioned without reading every artifact report, and the operator docs describe that field set explicitly.

## 2026-05-21 (Agentic Grant Discovery)

### Scope
- Product modernization pass for `apps/desci-platform`.
- Selected DeSci as the most promising differentiated product in this workspace based on current AI-for-science, DeSci, and grant-discovery market direction.

### Changes
- Added `GrantDiscoveryRequest`, `GrantOpportunity`, and `GrantDiscoveryResponse` models.
- Added `services/grant_discovery.py` to combine local RFP vector search, source/TRL filters, OpenAlex-derived concepts, explainable rationale, and next actions.
- Added `GrantApplicationBrief` so every recommendation can include readiness score, evidence checklist, preparation timeline, and risk flags.
- Added a bounded search timeout so slow or locked local vector backends degrade to an empty result with `research_signals.search_error` instead of hanging the API.
- Added public `POST /discover/grants` to the RFP router, protected by request rate limiting but not the authenticated usage counter so the Funding Radar can work as a low-friction discovery surface.
- Added a Grant Discovery Agent panel to the Funding Radar (`frontend/src/components/Notices.jsx`) with submission-readiness details and a handoff into Fit analysis.
- Stabilized `scripts/release_gate.py` by using direct local Node/Vite/Vitest/Hardhat entrypoints, retrying transient steps once, and seeding an isolated project-local Hardhat compiler cache for contract checks.
- Updated README API/product bullets.

### Verification
- `python -m py_compile apps/desci-platform/backend/models.py apps/desci-platform/backend/services/grant_discovery.py apps/desci-platform/backend/routers/rfp.py`
- `python -m pytest apps/desci-platform/backend/tests/test_grant_discovery.py apps/desci-platform/backend/tests/test_api_endpoints.py -q`
- `cmd /c npx vitest run src/__tests__/components/Notices.test.jsx --pool=threads --maxWorkers=1 --isolate --reporter=verbose` in `apps/desci-platform/frontend`
- `cmd /c npm run test` in `apps/desci-platform/frontend`
- `cmd /c npm run lint` in `apps/desci-platform/frontend`
- `cmd /c npm run test:lts` in `apps/desci-platform/frontend`
- `cmd /c npm run build:lts` in `apps/desci-platform/frontend`
- `cmd /c npm run test`, `cmd /c npm run deploy:smoke:core`, and `cmd /c npm run deploy:smoke:nft` in `apps/desci-platform/contracts`
- Runtime smoke: started `uvicorn main:app` and posted to `/discover/grants` with `GRANT_DISCOVERY_SEARCH_TIMEOUT=2`; response returned HTTP 200 with the expected response shape in ~2.7s while logging `grant_discovery_search_timeout`.
- `python apps/desci-platform/scripts/release_gate.py --continue-on-failure --json-out var\desci-release-gate-2026-05-21-seeded-hardhat-final.json`
- `python apps/desci-platform/scripts/release_gate.py --continue-on-failure --json-out var\desci-release-gate-2026-05-21-readiness-final.json`

### Result
- Backend grant discovery/API slice passed: `24 passed` before the readiness extension; targeted grant discovery regression passed again after the readiness extension: `4 passed`.
- Dedicated frontend Grant Discovery Agent component tests passed: `2 passed`.
- Full frontend Vitest suite passed: `17 files, 70 tests`.
- Frontend ESLint, typecheck, LTS build, and bundle checks passed in targeted or release-gate runs.
- Contract tests passed: `77 passing` Mocha plus `10` runtime-config tests.
- Contract local deploy smoke passed for both core contracts and NFT-only deployment.
- Runtime API smoke confirmed `/discover/grants` returns HTTP 200 and degrades cleanly when local vector search exceeds the configured timeout.
- Full release gate passed after the readiness extension: `13/13` steps, including `159` backend tests, `17` frontend test files / `70` frontend tests, production frontend build, bundle budget, `10` contract runtime-config tests, `77` Hardhat/Mocha contract tests, and both local deploy smoke commands.

### Remaining Risks
- Live OpenAlex enrichment is still best-effort and gracefully degrades when public APIs are unavailable.
- Production launch still depends on configured secrets, managed services, and strict runtime smoke.

## 2026-05-20 (Workspace Smoke Debt Closure)

### Scope
- Workspace smoke debt triage after `dashboard` and `AgriGuard` frontend gates failed from missing local JS dependencies.
- Dependency-environment repair only; no product code changes were made for this QC pass.

### Changes
- Restored local `node_modules` for `apps/dashboard` from its existing `package-lock.json`.
- Restored local `node_modules` for `apps/AgriGuard/frontend` from its existing `package-lock.json`.
- Reverted incidental `package-lock.json` and `.coverage` changes produced by install/smoke commands so the pass did not add lockfile churn.

### Verification
- `python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var\tmp\workspace_smoke_workspace_fixed_2026-05-20.json`
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\tmp\workspace_smoke_agriguard_fixed_2026-05-20.json`
- Earlier same-session confirmation:
  - `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var\tmp\workspace_smoke_desci_escalated_2026-05-20.json`
  - `python ops/scripts/run_workspace_smoke.py --scope getdaytrends --json-out var\tmp\workspace_smoke_getdaytrends_escalated_2026-05-20.json`
  - `python ops/scripts/run_workspace_smoke.py --scope mcp --json-out var\tmp\workspace_smoke_mcp_2026-05-20.json`
  - `python ops/scripts/run_workspace_smoke.py --scope cie --json-out var\tmp\workspace_smoke_cie_2026-05-20.json`

### Result
- Workspace scope passed: `6/6`.
- AgriGuard scope passed: `5/5`.
- DeSci, getdaytrends, MCP, and CIE scopes were already passing after network-enabled false-positive rechecks.
- The previously open smoke blockers were closed without changing application source.

### Remaining Risks
- The full `--scope all` command was not rerun after the fix because the failing scopes were rerun directly and the other scopes had already passed in the same session.
- The worktree still contains unrelated pre-existing changes and tracked pytest temp-file deletion noise under `.pytest-root`; those were not touched in this pass.

## 2026-05-16

### Scope
- DeSci launch-control finalization
- Runtime smoke alignment with operator go/no-go semantics
- Release gate report hardening and documentation cleanup

### Changes
- Added `GET /launch` to `backend/main.py` to convert `/ready` checks into an operator decision: `go`, `go-with-watch`, or `no-go`.
- Included readiness score, blocker count, warning count, launch blockers, and remediation-oriented next actions in the launch-control payload.
- Extended `scripts/product_smoke.py` so runtime smoke validates `/launch` and strict mode fails on a `no-go` release decision.
- Added `--continue-on-failure` to `scripts/release_gate.py` so operators can collect a full failure inventory instead of stopping at the first failed step.
- Expanded JSON release-gate reports with generated timestamp, total duration, pass/fail/skip counts, and failed-step summary.
- Rewrote `README.md` into a clean launch-oriented product and operations guide.
- Updated `OPERATIONS_RUNBOOK.md` to mention `/launch`, strict smoke expectations, and JSON release-gate reporting.

### Files
- `backend/main.py`
- `backend/tests/test_api_endpoints.py`
- `backend/tests/test_release_gate.py`
- `scripts/product_smoke.py`
- `scripts/release_gate.py`
- `README.md`
- `OPERATIONS_RUNBOOK.md`

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_api_endpoints.py -q`
- `python -m pytest apps/desci-platform/backend/tests/test_api_endpoints.py::test_launch_control_returns_operator_decision apps/desci-platform/backend/tests/test_api_endpoints.py::test_launch_control_is_no_go_when_required_check_fails apps/desci-platform/backend/tests/test_release_gate.py -q`
- `python -m py_compile apps/desci-platform/scripts/product_smoke.py apps/desci-platform/scripts/release_gate.py`
- `npm run test:config` in `apps/desci-platform/contracts`
- `python scripts/release_gate.py --dry-run --skip-compose --skip-frontend --skip-contracts --json-out NUL` in `apps/desci-platform`

### Result
- Backend API regression suite passed: `20 passed`.
- Targeted launch-control and release-gate suite passed: `7 passed`.
- Contract runtime-config suite passed: `10 passed`.
- Release gate dry-run confirmed the new reporting and control flags without leaving a generated report in the worktree.

### Remaining Risks
- Full release gate was not rerun in this recording pass because the request was to record the completed work.
- Production launch still depends on real secrets, managed services, deployed contract addresses, and a strict smoke run returning a non-`no-go` launch decision.

## 2026-05-15

### Scope
- Workspace contract regression gate hardening across DeSci and AgriGuard
- Hardhat runtime configuration safety checks for deployment and verification flows
- Documentation alignment after backend path unification and contract gate expansion

### Changes
- Added `desci contracts compile`, `desci contracts tests`, `agriguard contracts compile`, and `agriguard contracts tests` to `ops/scripts/run_workspace_smoke.py`.
- Extended `tests/test_workspace_smoke.py`, `docs/QUALITY_GATE.md`, and the smoke skill project matrix so the new contract checks are treated as first-class workspace gates.
- Hardened `apps/desci-platform/contracts/hardhat.config.js` with shared runtime validation for remote signer requirements, private key normalization, and explorer API-key validation.
- Added matching runtime-config helpers and config tests for `apps/AgriGuard/contracts`, and updated its Hardhat tests to the Hardhat 3 `network.create()` style with explicit custom-error assertions.
- Updated `apps/desci-platform/README.md`, `apps/desci-platform/DEPLOYMENT_GUIDE.md`, `apps/desci-platform/STACK_ALIGNMENT.md`, and `apps/AgriGuard/README.md` so contract checks and current backend paths match the live workspace layout.

### Files
- `ops/scripts/run_workspace_smoke.py`
- `tests/test_workspace_smoke.py`
- `docs/QUALITY_GATE.md`
- `.agents/skills/multi-project-smoke-check/references/project-matrix.md`
- `apps/desci-platform/contracts/hardhat.config.js`
- `apps/desci-platform/contracts/config/runtime-config.js`
- `apps/desci-platform/contracts/tests/runtime-config.test.js`
- `apps/desci-platform/contracts/package.json`
- `apps/desci-platform/contracts/.env.example`
- `apps/AgriGuard/contracts/hardhat.config.js`
- `apps/AgriGuard/contracts/config/runtime-config.js`
- `apps/AgriGuard/contracts/tests/runtime-config.test.js`
- `apps/AgriGuard/contracts/test/AgriGuard.test.js`
- `apps/desci-platform/README.md`
- `apps/desci-platform/DEPLOYMENT_GUIDE.md`
- `apps/desci-platform/STACK_ALIGNMENT.md`
- `apps/AgriGuard/README.md`

### Verification
- `npm run test` in `apps/desci-platform/contracts`
- `npm run test` in `apps/AgriGuard/contracts`
- `python -m pytest tests/test_workspace_smoke.py apps/desci-platform/backend/tests/test_release_gate.py -q`
- `python ops/scripts/run_workspace_smoke.py --scope desci`
- `python ops/scripts/run_workspace_smoke.py --scope agriguard`
- `python ops/scripts/run_workspace_smoke.py --scope all --json-out var/workspace-smoke-2026-05-15-final-all.json`

### Result
- Contract regression checks are now part of the default workspace smoke matrix for both DeSci and AgriGuard.
- DeSci contract tests now cover runtime config validation before Hardhat test execution.
- AgriGuard contract tests were repaired for Hardhat 3 and now pass under the same gate model.
- Full workspace smoke passed with `25/25 PASS`.

### Remaining Risks
- Superseded on 2026-05-27: README, deployment guide, stack alignment, API spec, and backend root metadata now use the current public product identity where they describe the product surface.
- Runtime validation protects local and CI usage, but actual remote deployment and explorer verification still depend on valid secrets and funded testnet wallets in the target environment.

### Scope
- Release hardening follow-up after contract, backend, and frontend improvements
- Governance state alignment between on-chain enum values and frontend rendering
- Local release gate expansion to include contract smoke validation

### Changes
- Added contract build, test, and smoke deployment steps to `scripts/release_gate.py`.
- Added `deploy:smoke:core` and `deploy:smoke:nft` scripts under `contracts/package.json`.
- Updated env doctor and `/ready` checks to treat `MOCK_MODE` and DAO contract wiring as first-class Web3 readiness signals.
- Hardened RabbitMQ imports and worker dispatch handling so lean environments without `pika` no longer fail during module import.
- Fixed governance UI state mapping for `Queued` and `Executed`, normalized large vote-count rendering, and limited vote actions to active proposals.
- Removed the remaining React 19 lint warnings across `AssetManager`, `BioLinker`, `Governance`, `Notices`, `PricingPage`, `ProductReadinessPanel`, `UploadPaper`, and `useMyLab`.

### Files
- `scripts/release_gate.py`
- `scripts/env_doctor.py`
- `contracts/package.json`
- `backend/main.py`
- `backend/services/rabbitmq_bus.py`
- `backend/services/web3_service.py`
- `backend/worker.py`
- `backend/tests/test_api_endpoints.py`
- `backend/tests/test_env_doctor.py`
- `backend/tests/test_release_gate.py`
- `backend/tests/test_worker.py`
- `frontend/src/components/AssetManager.jsx`
- `frontend/src/components/BioLinker.jsx`
- `frontend/src/components/Governance.jsx`
- `frontend/src/components/Notices.jsx`
- `frontend/src/components/PricingPage.jsx`
- `frontend/src/components/ProductReadinessPanel.jsx`
- `frontend/src/components/UploadPaper.jsx`
- `frontend/src/hooks/useMyLab.js`

### Verification
- `python scripts/release_gate.py`
- `docker compose config --quiet`
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_api_endpoints.py apps/desci-platform/backend/tests/test_worker.py -q`
- `npm run lint`
- `npm run typecheck`
- `npm run test`
- `npm run build:lts`
- `npm run check:bundle`

### Result
- Full release gate passed with 12 steps, including contract smoke validation.
- Backend targeted regression suite passed: 31 tests.
- Full backend suite passed through the gate: 89 tests.
- Frontend checks passed: lint, typecheck, tests, production build, and bundle budget.
- Frontend tests passed: 61 tests across 15 files.
- Contract suite passed: 77 tests, plus local smoke deployment for core contracts and NFT contract.

### Remaining Risks
- Local env doctor still reports recommended warnings for missing production secrets and managed services such as Firebase auth credentials, PostgreSQL, Supabase, Redis, RabbitMQ, Pinata, and Stripe.
- Static analysis with `slither` has still not been run in this environment because the tool is not installed.

## 2026-03-18

### Scope
- Frontend claymorphism rebrand follow-up QC
- Login layout and typography polish
- Korean locale copy and rendering cleanup

### Changes
- Reworked the login layout to remove excessive vertical stretching and align the two-panel composition to content height.
- Adjusted desktop and mobile spacing in the login shell for better card balance and reduced empty space.
- Added a Korean-safe font stack and Korean-specific heading fallback to prevent awkward mixed-script rendering.
- Reduced the visual noise overlay intensity on clay/glass surfaces so text remains clearer.
- Localized Korean login and shell labels that were still showing English marketplace terms.

### Files
- `frontend/src/components/Login.jsx`
- `frontend/src/index.css`
- `frontend/src/i18n/messages.js`

### Verification
- Browser QA on `/login` at desktop and mobile widths
- `npm run test`
- `npm run lint`
- `npm run build:lts`

### Result
- Login screen alignment is stable on desktop and mobile.
- Korean copy renders cleanly and no longer mixes the English panel heading on the login card.
- Automated checks passed after the fix.

## 2026-03-18 (QC rerun)

### Scope
- Frontend regression QC after login polish
- Browser smoke check for locale persistence and protected routes
- Test runner stability verification on Windows

### Changes
- Updated `frontend/vite.config.js` to use the Vitest `threads` pool instead of `forks`.
- Kept the suite single-worker to match the existing deterministic test setup.

### Verification
- `npm run test`
- `npm run lint`
- `npm run build:lts`
- Headless browser check on `/login`
- Locale persistence check for `KO -> EN`
- Unauthenticated redirect check for `/dashboard` and `/governance`
- Browser console error check

### Result
- `npm run test` now passes reliably in this Windows environment.
- Default locale initializes as `ko-KR` with `dsci.outputLanguage=ko`.
- Switching to English persists after reload with `dsci.locale=en-US`, `dsci.outputLanguage=en`, and `document.lang=en-US`.
- Unauthenticated access to protected routes redirects back to `/login`.
- No browser console errors were observed during the smoke check.

## 2026-05-11

### Scope
- Product-Ready Modernization & Structural Unification
- Web3 Feature Completion & On-chain Visibility
- Infrastructure Hardening (Health Monitoring)

### Changes
- Unified backend structure by renaming `biolinker` to `backend` and updating orchestration (`docker-compose.yml`).
- Enhanced `/health` endpoint to monitor Redis, RabbitMQ, and DB connectivity.
- Implemented `/papers/public` API for dynamic research feed.
- Modernized `ResearchFeed.jsx` (Explorer) with On-chain Verified badges, Polygonscan links, and a Live Activity ticker.
- Migrated contract addresses to environment variables for production portability.

### Verification
- `pytest tests/` (70/70 PASSED - 100% Success)
- `npm run lint` (0 errors)
- `docker-compose config` (Validated)
- Structural verification of consolidated `backend/` directory.

### Result
- The platform is now structurally unified and production-ready.
- All core infrastructure services (DB, Redis, MQ, Vector) are actively monitored.
- Research feed now provides real-time on-chain transparency and professional UI feedback.
- System stability confirmed with 100% backend test coverage pass.

## 2026-05-11 (Release Gate QC)

### Scope
- End-to-end DeSci platform release gate validation.
- Runtime API/frontend smoke check against local services.
- Browser route smoke check for core public and protected routes.
- CI quality alignment for backend, frontend, and bundle guardrails.

### Commands
- `python scripts/release_gate.py --json-out .tmp/release-gate-qc.json`
- `python scripts/product_smoke.py --api http://127.0.0.1:8000 --frontend http://127.0.0.1:4174`
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:4174`

### Verification
- Release gate passed all 8 steps.
- Backend tests passed: 72 tests.
- Frontend checks passed: lint, typecheck, tests, production build, bundle budget.
- Frontend tests passed: 59 tests across 14 files.
- Bundle budget passed: entry chunk `index-DEYF5bBV.js` at 254.5 KB, under the 260 KB entry limit.
- Runtime smoke passed: API 200, frontend 200.
- Browser smoke passed for `/`, `/pricing`, `/explore`, `/login`, `/does-not-exist`, `/dashboard`, and `/upload`.

### Result
- Release gate report written to `.tmp/release-gate-qc.json`.
- CI now has the same product gate signals used locally: backend tests, frontend lint/typecheck/test/build, and bundle checks.
- Local `/health` returned `degraded` and `/ready` returned `blocked`, which is expected until production dependencies and secrets are configured.

### Remaining Risks
- Local environment is still missing or using placeholder values for LLM, auth, CORS allowlist, PostgreSQL, Supabase, Redis, RabbitMQ, IPFS/Pinata, Web3, and Stripe configuration.
- Strict production readiness should be rerun after those services and secrets are available.
- Do not use `uv sync --extra dev` inside `apps/desci-platform/biolinker`; use the release gate or editable backend install flow instead.

## 2026-05-19 (Frontend Dependency Refresh)

### Scope
- Current npm wanted-version refresh for `apps/desci-platform/frontend`.
- Patch/minor upgrades only; ESLint 10 major migration deferred.
- Full local release gate validation after the dependency update.

### Changes
- Updated frontend runtime dependencies:
  - `@tanstack/react-query` to `5.100.11`
  - `framer-motion` to `12.39.0`
  - `lucide-react` to `1.16.0`
  - `react-router-dom` to `7.15.1`
- Updated frontend build dependencies:
  - `@rollup/wasm-node` to `4.60.4`
  - `@vitejs/plugin-react` to `6.0.2`
  - `vite` to `8.0.13`

### Verification
- `npm run lint`
- `npm run typecheck`
- `npm run test` (15 files, 61 tests)
- `npm run build`
- `python scripts/release_gate.py --profile local --continue-on-failure --json-out var\release-gate-after-frontend-upgrades.json`

### Result
- Release gate passed all 12 steps.
- Backend tests passed: 92 tests.
- Frontend checks passed: lint, typecheck, tests, LTS production build, and bundle budget.
- Contracts checks passed: build, tests, and deployment smoke.
- Local env doctor still reports expected local warnings for optional production services and secrets.

## 2026-05-27 (Release Readiness Contract Smoke)

### Scope
- Promoted DeSci release-readiness contracts into the canonical workspace smoke matrix.
- The `desci` smoke scope now checks deploy readiness, env doctor, release gate, and deployment docs alongside frontend, contracts, and backend smoke.
- Hardened `scripts/release_gate.py` so Python executable paths containing spaces, such as `D:\AI project\.venv\Scripts\python.exe`, are preserved as one command argument.

### Verification
- `python -m pytest tests/test_workspace_smoke.py -q -p no:cacheprovider`
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py -q -p no:cacheprovider`
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-2026-05-27-release-readiness-contracts.json`
- `python ops/scripts/run_workspace_smoke.py --scope all --json-out var/workspace-smoke-all-2026-05-27-final-product-readiness-31.json`

### Result
- DeSci smoke passed `8/8`, including `desci release readiness contracts`.
- Full workspace smoke passed `31/31`.
- CI contract coverage now verifies `.github/workflows/workspace-smoke.yml` runs the same canonical `run_workspace_smoke.py --scope all --json-out smoke-all.json` gate and uploads `workspace-smoke-report`.
- Current external blockers remain operational rather than local-code blockers: Railway/Vercel accounts and domains, funded Polygon Amoy wallet/RPC/explorer key, `GITLEAKS_LICENSE`, and approved observability follow-up work.

## 2026-05-27 (CI Scope Alignment)

### Scope
- Aligned `.github/workflows/desci-platform-quality.yml` with the canonical smoke scopes.
- Added `cie` to the workflow matrix and expanded path filters for content-intelligence and MCP packages.
- Installed DeSci/AgriGuard contract npm dependencies and Canva MCP npm dependencies before scoped smoke runs.

### Verification
- `python -m pytest tests/test_security_gate_contracts.py tests/test_workspace_smoke.py -q -p no:cacheprovider`
- `python ops/scripts/run_workspace_smoke.py --scope mcp --json-out var/workspace-smoke-mcp-2026-05-27-ci-scope-alignment.json`
- `python ops/scripts/run_workspace_smoke.py --scope cie --json-out var/workspace-smoke-cie-2026-05-27-ci-scope-alignment.json`

### Result
- Focused smoke/security contracts passed `32/32`.
- MCP smoke passed `6/6`.
- CIE smoke passed `2/2`.

## 2026-05-27 (Public Product Identity and Deployment Guide)

### Scope
- Aligned root API metadata and `API_SPEC.md` to the current public product name, `DSCI-DecentBio`.
- Replaced the stale deployment guide with clean executable Railway, Vercel, Polygon Amoy, GitHub secret-scan, release-gate, and final verification steps.
- Added release-readiness contract coverage so the API spec, README, deployment guide, and backend root metadata keep the same product identity.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_deploy_readiness.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_api_endpoints.py::test_root_returns_service_info -q -p no:cacheprovider`
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-2026-05-27-product-identity-docs.json`

### Result
- Product identity/docs contracts passed `36/36`.
- DeSci smoke passed `8/8`.

## 2026-05-27 (Operations Runbook Readiness Contract)

### Scope
- Added direct deployment-readiness JSON evidence guidance to `OPERATIONS_RUNBOOK.md`.
- Regression-covered the runbook against `release_gate.py` external readiness options and target names.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_release_gate.py -q -p no:cacheprovider`
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-2026-05-27-ops-runbook-readiness-contract.json`

### Result
- Docs/release contracts passed `18/18`.
- DeSci smoke passed `8/8`.

## 2026-05-27 (Product Smoke Identity Contract)

### Scope
- Updated `scripts/product_smoke.py` so runtime smoke validates the root API service identity as `DSCI-DecentBio`.
- Updated the product-smoke operator help text to remove the legacy BioLinker public name.
- Added `test_product_smoke.py` to the canonical `desci release readiness contracts` smoke command.

### Verification
- `python -m pytest tests/test_workspace_smoke.py apps/desci-platform/backend/tests/test_product_smoke.py -q -p no:cacheprovider`
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-2026-05-27-product-smoke-identity-contract.json`

### Result
- Focused smoke/doc contracts passed `24/24`.
- DeSci smoke passed `8/8`.

## 2026-05-27 (Product Smoke JSON Evidence)

### Scope
- Added `--json-out` to `scripts/product_smoke.py` so runtime smoke writes durable evidence for handoff packages and dashboards.
- Updated README and operations runbook smoke commands to write local and production JSON evidence files.
- Added documentation contract coverage to prevent product-smoke examples from regressing to console-only checks.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_product_smoke.py apps/desci-platform/backend/tests/test_deployment_docs.py tests/test_workspace_smoke.py -q -p no:cacheprovider`
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-2026-05-27-product-smoke-json-evidence.json`

### Result
- Product smoke/docs/workspace contracts passed `29/29`.
- DeSci smoke passed `8/8`.

## 2026-05-27 (Browser Smoke JSON Evidence)

### Scope
- Added `--json-out` to `scripts/browser_smoke.py` so Chromium route checks write durable browser/runtime evidence.
- Updated operations runbook local and production browser smoke commands to write JSON artifacts.
- Added browser smoke tests to the canonical `desci release readiness contracts` smoke command.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_deployment_docs.py tests/test_workspace_smoke.py -q -p no:cacheprovider`
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-2026-05-27-browser-smoke-json-evidence.json`

### Result
- Browser/docs/workspace contracts passed `29/29`.
- DeSci smoke passed `8/8`.

## 2026-05-27 (Browser Smoke Infrastructure-Failure Summary)

### Scope
- Hardened `scripts/browser_smoke.py --json-out` so infrastructure failures, including missing Playwright, increment `summary.failed` even when no route checks run.
- Added regression coverage for `ok=false`, `playwright_available=false`, and `summary.failed=1` in missing-Playwright reports.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/backend/tests/test_deployment_docs.py tests/test_workspace_smoke.py -q -p no:cacheprovider`
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-2026-05-27-browser-smoke-infra-failure-summary.json`

### Result
- Browser/docs/workspace contracts passed `30/30`.
- DeSci smoke passed `8/8`.

## 2026-05-27 (Release Gate Runtime Smoke Evidence)

### Scope
- Added `--runtime-smoke` to `scripts/release_gate.py` as an opt-in path for already-running backend/frontend services.
- The release gate now creates `product-smoke` and `browser-smoke` steps with JSON evidence outputs under the configured runtime evidence directory.
- Updated the operations runbook and documentation contracts so this handoff path stays discoverable.

### Verification
- `python apps/desci-platform/scripts/release_gate.py --runtime-smoke --runtime-smoke-strict-ready --runtime-api http://127.0.0.1:8000 --runtime-frontend http://127.0.0.1:5173 --runtime-evidence-dir var --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --dry-run --json-out var/desci-release-gate-runtime-smoke-dry-run.json`
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py tests/test_workspace_smoke.py -q -p no:cacheprovider`
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-2026-05-27-release-gate-runtime-smoke-evidence.json`

### Result
- Runtime smoke dry-run produced the expected release-gate steps.
- Release/docs/workspace contracts passed `41/41`.
- DeSci smoke passed `8/8`.

## 2026-05-27 (Runtime Smoke Handoff Docs Alignment)

### Scope
- Added the `release_gate.py --runtime-smoke` handoff command to README and deployment guide.
- Extended documentation contracts so README, deployment guide, and operations runbook stay aligned on runtime smoke evidence options.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/backend/tests/test_release_gate.py tests/test_workspace_smoke.py -q -p no:cacheprovider`
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-2026-05-27-runtime-smoke-doc-alignment.json`

### Result
- Release/docs/workspace contracts passed `41/41`.
- DeSci smoke passed `8/8`.

## 2026-05-27 (Release Gate Runtime Artifact Traceability)

### Scope
- Added `artifacts` to release gate JSON result entries when a step uses `--json-out`.
- Runtime smoke dry-run reports now point directly to `desci-product-smoke-release-gate.json` and `desci-browser-smoke-release-gate.json`.

### Verification
- `python apps/desci-platform/scripts/release_gate.py --runtime-smoke --runtime-smoke-strict-ready --runtime-api http://127.0.0.1:8000 --runtime-frontend http://127.0.0.1:5173 --runtime-evidence-dir var --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --dry-run --json-out var/desci-release-gate-runtime-smoke-artifacts-dry-run.json`
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py -q -p no:cacheprovider`
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py tests/test_workspace_smoke.py -q -p no:cacheprovider`
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-2026-05-27-release-gate-runtime-artifacts.json`

### Result
- Runtime artifact dry-run confirmed artifact paths in the release gate report.
- Release/docs contracts passed `23/23`; release/docs/workspace contracts passed `43/43`.
- DeSci smoke passed `8/8`.

## 2026-05-27 (Release Gate Artifact Status Metadata)

### Scope
- Added `artifact_reports` to release gate JSON result entries that already expose runtime smoke `artifacts`.
- Each artifact report includes the artifact path, whether the file exists, and its size in bytes when present.
- Preserved the existing `artifacts` list so existing consumers can keep resolving child evidence paths.

### Verification
- `python apps/desci-platform/scripts/release_gate.py --runtime-smoke --runtime-smoke-strict-ready --runtime-api http://127.0.0.1:8000 --runtime-frontend http://127.0.0.1:5173 --runtime-evidence-dir var --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --dry-run --json-out var/desci-release-gate-runtime-smoke-artifact-status-dry-run.json`
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py tests/test_workspace_smoke.py -q -p no:cacheprovider`
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-2026-05-27-release-gate-artifact-status.json`

### Result
- Runtime artifact dry-run confirmed `artifact_reports` marks expected child evidence files as `exists=false` before live smoke runs.
- Release/docs/workspace contracts passed `44/44`.
- DeSci smoke passed `8/8`.

## 2026-05-27 (Release Gate Required Artifact Enforcement)

### Scope
- Hardened `scripts/release_gate.py` so a subprocess that exits `0` still fails the gate if its expected `--json-out` evidence file was not created.
- Added `artifact_failures` to release gate JSON result entries for missing child evidence artifacts.
- Kept dry-run behavior skip-safe: dry-run reports planned artifact paths and missing status metadata without failing.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py -q -p no:cacheprovider`
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py tests/test_workspace_smoke.py -q -p no:cacheprovider`
- `python apps/desci-platform/scripts/release_gate.py --runtime-smoke --runtime-smoke-strict-ready --runtime-api http://127.0.0.1:8000 --runtime-frontend http://127.0.0.1:5173 --runtime-evidence-dir var --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --dry-run --json-out var/desci-release-gate-runtime-smoke-artifact-required-dry-run.json`
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-2026-05-27-release-gate-artifact-required.json`

### Result
- Release gate artifact enforcement tests passed `22/22`.
- Release/docs/workspace contracts passed `47/47`.
- DeSci smoke passed `8/8`.

## 2026-05-27 (Release Gate Artifact JSON Validation)

### Scope
- Hardened release gate evidence validation beyond file existence: expected `--json-out` artifacts must be parseable top-level JSON objects.
- A successful subprocess now fails the gate if its JSON evidence reports `ok=false`.
- `artifact_reports` now includes `json_valid` and `json_ok` for existing child evidence files.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py -q -p no:cacheprovider`
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py tests/test_workspace_smoke.py -q -p no:cacheprovider`
- `python apps/desci-platform/scripts/release_gate.py --runtime-smoke --runtime-smoke-strict-ready --runtime-api http://127.0.0.1:8000 --runtime-frontend http://127.0.0.1:5173 --runtime-evidence-dir var --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --dry-run --json-out var/desci-release-gate-runtime-smoke-artifact-json-validation-dry-run.json`
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-2026-05-27-release-gate-artifact-json-validation.json`

### Result
- Release gate tests passed `25/25`.
- Release/docs/workspace contracts passed `50/50`.
- DeSci smoke passed `8/8`.

## 2026-05-27 (Release Gate Evidence OK Contract)

### Scope
- Tightened release gate child evidence validation so expected `--json-out` artifacts must explicitly report `ok=true`.
- Parseable JSON artifacts that omit `ok` or use a non-true value now fail the parent release gate step.
- This keeps runtime-smoke handoff evidence unambiguous for operators and dashboards.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py -q -p no:cacheprovider`
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py tests/test_workspace_smoke.py -q -p no:cacheprovider`
- `python apps/desci-platform/scripts/release_gate.py --runtime-smoke --runtime-smoke-strict-ready --runtime-api http://127.0.0.1:8000 --runtime-frontend http://127.0.0.1:5173 --runtime-evidence-dir var --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --dry-run --json-out var/desci-release-gate-runtime-smoke-artifact-ok-required-dry-run.json`
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-2026-05-27-release-gate-artifact-ok-required.json`

### Result
- Release gate tests passed `26/26`.
- Release/docs/workspace contracts passed `51/51`.
- DeSci smoke passed `8/8`.

## 2026-05-27 (Release Gate Runtime Evidence Shape Contract)

### Scope
- Added release gate validation for product/browser runtime-smoke child evidence structure.
- Runtime-smoke evidence must now include a summary object, a failures list, and a non-empty checks list.
- Every check in product/browser runtime evidence must report `ok=true` before the parent release gate step can pass.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py -q -p no:cacheprovider`
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py tests/test_workspace_smoke.py -q -p no:cacheprovider`
- `python apps/desci-platform/scripts/release_gate.py --runtime-smoke --runtime-smoke-strict-ready --runtime-api http://127.0.0.1:8000 --runtime-frontend http://127.0.0.1:5173 --runtime-evidence-dir var --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --dry-run --json-out var/desci-release-gate-runtime-smoke-artifact-shape-dry-run.json`
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-2026-05-27-release-gate-artifact-shape.json`

### Result
- Release gate tests passed `29/29`.
- Release/docs/workspace contracts passed `54/54`.
- DeSci smoke passed `8/8`.

## 2026-05-27 (Release Gate Runtime Evidence Summary Consistency)

### Scope
- Added release gate consistency validation for product/browser runtime-smoke child evidence summaries.
- `summary.total`, `summary.passed`, and `summary.failed` must now match the actual `checks` and `failures` arrays.
- This prevents dashboards from trusting stale or contradictory child evidence counts during release handoff.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py -q -p no:cacheprovider`
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py tests/test_workspace_smoke.py -q -p no:cacheprovider`
- `python apps/desci-platform/scripts/release_gate.py --runtime-smoke --runtime-smoke-strict-ready --runtime-api http://127.0.0.1:8000 --runtime-frontend http://127.0.0.1:5173 --runtime-evidence-dir var --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --dry-run --json-out var/desci-release-gate-runtime-smoke-artifact-summary-consistency-dry-run.json`
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-2026-05-27-release-gate-artifact-summary-consistency.json`

### Result
- Release gate tests passed `31/31`.
- Release/docs/workspace contracts passed `56/56`.
- DeSci smoke passed `8/8`.

## 2026-05-27 (Release Gate Artifact Validation Reports)

### Scope
- Added per-artifact validation status to release gate JSON `artifact_reports`.
- Each child evidence artifact report now includes `validation_ok` and `validation_failures`.
- This lets dashboards and handoff reviewers identify the failing child artifact directly instead of relying only on aggregate `artifact_failures`.

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py -q -p no:cacheprovider`
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py tests/test_workspace_smoke.py -q -p no:cacheprovider`
- `python apps/desci-platform/scripts/release_gate.py --runtime-smoke --runtime-smoke-strict-ready --runtime-api http://127.0.0.1:8000 --runtime-frontend http://127.0.0.1:5173 --runtime-evidence-dir var --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --dry-run --json-out var/desci-release-gate-runtime-smoke-artifact-validation-report-dry-run.json`
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-2026-05-27-release-gate-artifact-validation-report.json`

### Result
- Release gate tests passed `32/32`.
- Release/docs/workspace contracts passed `57/57`.
- DeSci smoke passed `8/8`.

## 2026-06-05 (Notices Discovery I18n Browser QA)

### Scope
- Localized the authenticated `/notices` discovery-agent copy through `LocaleContext` so the Korean app shell no longer shows English-only discovery labels, placeholders, empty-state copy, or validation messages.
- Updated authenticated browser-smoke expectations to assert `공고 매칭 에이전트`.
- Hardened the dashboard quick-upload browser check to click the dashboard quick action by accessible name and verify the `/upload` page with either the English page title or Korean submit CTA.
- Refreshed the GitHub modernization manifest with live `Veritas-7/autoresearch-skill-system` HEAD `fa9a8bc77b53426002e9515313a097bb964c3246`.

### Verification
- `python apps/desci-platform/scripts/browser_smoke.py --frontend http://127.0.0.1:5175 --expect-dev-auth --json-out var/desci-browser-smoke-2026-06-05-notices-i18n-dev-auth-rerun.json`
- Playwright MCP direct `/notices` check: Korean title, placeholders, empty-state copy, empty-context validation toast, and zero warning/error console messages.
- `cmd /c npm run test` -> `20 files / 79 tests passed`.
- `cmd /c npm run lint`
- `cmd /c npm run build`
- `python -m pytest apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `9 passed`.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-05-notices-i18n-complete.json`
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-06-05-desci-notices-i18n.json`
- `python -m pytest tests\test_github_modernization_radar.py -q -p no:cacheprovider` -> `5 passed`.

### Result
- Dev-auth browser smoke passed `10/10`.
- DeSci canonical smoke passed `8/8`.
- Workspace canonical smoke passed `8/8`.

## 2026-06-05 (Wallet Extension Missing Browser UX)

### Scope
- Baseline browser click on `/wallet` showed no user-facing feedback when a clean Chromium session lacked a wallet extension.
- Added localized wallet failure mapping for missing extension and missing account selection.
- Updated the wallet page to show a persistent warning alert and toast after failed connection attempts.
- Updated the header wallet button to show success/failure toasts instead of silently discarding `connectWallet()` results.
- Extended dev-auth browser smoke with `wallet-authenticated` and `wallet-extension-missing` checks.

### Verification
- Playwright MCP baseline: `.playwright-mcp/desci-wallet-baseline-body-2026-06-05.txt` showed no failure guidance after click.
- Playwright MCP variant: `.playwright-mcp/desci-wallet-variant-body-2026-06-05.txt` includes `브라우저 지갑 확장 프로그램을 설치하거나 활성화한 뒤 다시 시도하세요.`
- `.playwright-mcp/desci-wallet-variant-console-2026-06-05.txt` -> `Errors: 0, Warnings: 0`.
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5175 --expect-dev-auth --json-out var\desci-browser-smoke-2026-06-05-wallet-ux-dev-auth.json`
- `cmd /c npm run test` -> `21 files / 81 tests passed`.
- `cmd /c npm run lint`
- `cmd /c npm run build`
- `python -m pytest apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `9 passed`.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-05-wallet-ux.json`
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-06-05-desci-wallet-ux.json`

### Result
- Dev-auth browser smoke passed `12/12`.
- DeSci canonical smoke passed `8/8`.
- Workspace canonical smoke passed `8/8`.

## 2026-06-05 (Protected Route Browser Coverage)

### Scope
- Expanded authenticated browser smoke coverage to every protected DeSci product route: dashboard, BioLinker, upload, my lab, VC portal, notices, AI lab, peer review, wallet, assets, and governance.
- The first expanded live run caught real `/vc-portal` API drift: the frontend still called removed `/vc/list` and recommendation endpoints, producing browser-console 404s.
- Updated `useVCDashboard` to load from `/vcs` and avoid removed recommendation calls; added a hook regression test for that API contract.

### Verification
- `var/desci-browser-smoke-2026-06-05-protected-route-coverage.json` -> `18/19 OK`, failing only `vc-portal-authenticated` before the fix.
- `var/desci-browser-smoke-2026-06-05-protected-route-coverage-rerun.json` -> `19/19 OK`.
- `cmd /c npm run test` -> `22 files / 82 tests passed`.
- `cmd /c npm run lint`
- `cmd /c npm run build`
- `python -m pytest apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `9 passed`.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-05-protected-route-coverage.json`
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-06-05-desci-protected-route-coverage.json`

### Result
- Expanded dev-auth browser smoke passed `19/19`.
- DeSci canonical smoke passed `8/8`.
- Workspace canonical smoke passed `8/8`.
- External modernization radar refreshed with Veritas `HEAD` `a7c36c2fadd929db92843dffc73d97f32c9f85d5`.

## 2026-06-05 (VC Portal Selector Browser Action)

### Scope
- Promoted the `/vc-portal` selector interaction into dev-auth browser smoke after route-only coverage exposed the previous VC API drift.
- Added `vc-portal-select` to the authenticated browser action sequence; the check selects the first venture firm and verifies the selected profile name plus profile detail labels render.
- Extracted the dev-auth action sequence into `AUTHENTICATED_ACTION_CHECKS` and added contract coverage so the VC selector check remains part of the smoke path.

### Verification
- `python -m py_compile apps\desci-platform\scripts\browser_smoke.py`
- `python -m pytest apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `10 passed`.
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5175 --expect-dev-auth --json-out var\desci-browser-smoke-2026-06-05-vc-selector-rerun-final.json`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-05-vc-selector.json`
- `python ops\scripts\github_modernization_radar.py --json-out var\github-modernization-radar-desci-vc-selector-2026-06-05.json --markdown-out docs\reports\2026-06\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_DESCI_VC_SELECTOR_2026-06-05.md`
- `python ops\scripts\auto_research_status.py --radar-json var\github-modernization-radar-desci-vc-selector-2026-06-05.json --live-source-commit 1eaf50627cece5c1c5f46f0d791397fb1e66be56 --json-out var\auto-research-status-desci-vc-selector-2026-06-05.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_OPERATOR_STATUS_DESCI_VC_SELECTOR_2026-06-05.md`
- `python -m pytest tests\test_workspace_smoke.py::test_handoff_current_baseline_matches_product_readiness_gate tests\test_github_modernization_radar.py tests\test_auto_research_status.py -q -p no:cacheprovider` -> `15 passed`.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-06-05-desci-vc-selector.json`

### Result
- Dev-auth browser smoke passed `20/20`, including `vc-portal-select`.
- DeSci canonical smoke passed `8/8`.
- Workspace canonical smoke passed `8/8`.
- Source-backed modernization radar passed with `7` adopted sources at Veritas `HEAD` `1eaf50627cece5c1c5f46f0d791397fb1e66be56`.

## 2026-06-06 (Upload Submission Readiness Browser Action)

### Scope
- Baseline `/upload` browser interaction allowed PDF-plus-terms to enable submit while title/authors were still blank, leaving only a transient required-field toast after click.
- Added a localized submission-readiness checklist for PDF, title, authors, and terms.
- Disabled submit until all required upload metadata is ready and trimmed title/authors before validation and `FormData`.
- Added `upload-form-readiness` to authenticated browser smoke so Chromium proves the missing-metadata disabled state and the ready enabled state without performing an upload POST.
- Hardened the mocked Amoy wallet-provider browser check to match the exact wallet address when multiple status areas render the same address.

### Verification
- Playwright MCP baseline and variant proof captured the disabled/missing and enabled/ready states; screenshot: `var/desci-upload-readiness-2026-06-06.png`.
- `python -m py_compile apps\desci-platform\scripts\browser_smoke.py`
- `python -m pytest apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `10 passed`.
- `cmd /c npm run test -- src/__tests__/components/UploadPaper.test.jsx` -> `1` file / `8` tests passed.
- `cmd /c npm run test` -> `23` files / `91` tests passed.
- `cmd /c npm run lint`
- `cmd /c npm run build`
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5175 --expect-dev-auth --json-out var\desci-browser-smoke-2026-06-06-upload-readiness-final.json`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-06-upload-readiness.json`
- `python ops\scripts\github_modernization_radar.py --json-out var\github-modernization-radar-desci-upload-readiness-2026-06-06.json --markdown-out docs\reports\2026-06\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_DESCI_UPLOAD_READINESS_2026-06-06.md`
- `python ops\scripts\auto_research_status.py --radar-json var\github-modernization-radar-desci-upload-readiness-2026-06-06.json --live-source-commit f598b95732bc4b148d265294a3ec7d805abf3dc9 --json-out var\auto-research-status-desci-upload-readiness-2026-06-06.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_OPERATOR_STATUS_DESCI_UPLOAD_READINESS_2026-06-06.md`
- `python -m pytest tests\test_workspace_smoke.py::test_handoff_current_baseline_matches_product_readiness_gate tests\test_github_modernization_radar.py tests\test_auto_research_status.py -q -p no:cacheprovider` -> `15 passed`.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-06-06-desci-upload-readiness.json`
- `python ops\scripts\dev_server_status.py --target desci-api --target desci-frontend --json-out var\dev-server-status-desci-after-upload-readiness-stop-2026-06-06.json` -> `0/2 ready`.

### Result
- Dev-auth browser smoke passed `22/22`, including `upload-form-readiness`.
- DeSci canonical smoke passed `8/8`.
- Workspace canonical smoke passed `8/8`.
- Source-backed modernization radar passed with `7/7` adopted sources at Veritas `HEAD` `f598b95732bc4b148d265294a3ec7d805abf3dc9`.

## 2026-06-06 (Governance Wallet-Required Browser Action)

### Scope
- Closed the no-wallet governance action gap by keeping proposals readable while requiring a connected wallet for proposal creation and active proposal voting.
- Added a persistent localized wallet-required panel to `frontend/src/components/Governance.jsx`.
- Disabled proposal submit plus active vote buttons when `walletAddress` is missing, with handler-level guards before API POST.
- Added `governance-wallet-required` to the authenticated browser action sequence before the mocked Amoy wallet-provider action.

### Verification
- `python -m py_compile apps\desci-platform\scripts\browser_smoke.py`
- `python -m pytest apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `10 passed`.
- `cmd /c npm run test -- src/__tests__/components/Governance.test.jsx` -> `1` file / `4` tests passed.
- `cmd /c npm run test` -> `24` files / `95` tests passed.
- `cmd /c npm run lint`
- `cmd /c npm run build`
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5188 --expect-dev-auth --timeout 25 --json-out var\desci-browser-smoke-governance-wallet-2026-06-06-final.json`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-06-governance-wallet.json`
- `python ops\scripts\github_modernization_radar.py --json-out var\github-modernization-radar-desci-governance-wallet-2026-06-06.json --markdown-out docs\reports\2026-06\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_DESCI_GOVERNANCE_WALLET_2026-06-06.md`

### Result
- Dev-auth browser smoke passed `23/23`, including `governance-wallet-required`.
- DeSci canonical smoke passed `8/8`.
- Workspace canonical smoke passed `8/8`.
- AutoResearch operator status is `ok` via `var/auto-research-status-desci-governance-wallet-2026-06-06.json`.
- Source-backed modernization radar passed with `7/7` adopted sources at Veritas `HEAD` `e1406c86c4b1e7c686530ed739ea6bbb8bbeeba2`.

## 2026-06-06 (Peer Review Critique Readiness Browser Action)

### Scope
- Closed the empty-critique Peer Review readiness gap by adding a persistent checklist/status panel.
- Disabled review submit until the selected paper has non-empty trimmed critique text.
- Added a focused component test for disabled/enabled readiness and the valid review POST payload.
- Added `peer-review-readiness` to authenticated browser smoke with a scoped `/papers/me` fixture and no-POST assertion.

### Verification
- `python -m py_compile apps\desci-platform\scripts\browser_smoke.py`
- `python -m pytest apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `10 passed`.
- `cmd /c npm run test -- src/__tests__/components/PeerReview.test.jsx` -> `1` file / `1` test passed.
- `cmd /c npm run test` -> `25` files / `96` tests passed.
- `cmd /c npm run lint`
- `cmd /c npm run build`
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5190 --expect-dev-auth --timeout 25 --json-out var\desci-browser-smoke-peer-review-readiness-2026-06-06-final.json`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-06-peer-review-readiness.json`
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-06-06-desci-peer-review-readiness.json`
- `python ops\scripts\github_modernization_radar.py --json-out var\github-modernization-radar-desci-peer-review-readiness-2026-06-06.json --markdown-out docs\reports\2026-06\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_DESCI_PEER_REVIEW_READINESS_2026-06-06.md`

### Result
- Dev-auth browser smoke passed `25/25`, including `peer-review-readiness`.
- DeSci canonical smoke passed `8/8`.
- Workspace canonical smoke passed `8/8`.
- AutoResearch operator status is `ok` via `var/auto-research-status-desci-peer-review-readiness-2026-06-06.json`.
- Source-backed modernization radar passed with `7/7` adopted sources at Veritas `HEAD` `b440e485039a7e4de19beb7c27316850cd57c562`.

## 2026-06-06 (BioLinker RFP Readiness Browser Action)

### Scope
- Closed the `/biolinker` pre-analysis readiness gap after baseline browser proof showed Analyze remained enabled with empty organization/team and RFP text fields.
- Added a localized RFP analysis checklist to `BioLinker` and `RFPInputPanel`.
- Disabled Analyze until both required fields are filled.
- Added `biolinker-rfp-readiness` to authenticated browser smoke, verifying missing/ready states without sending an `/analyze` POST.
- Adjusted `governance-wallet-required` smoke so vote buttons are only asserted when active proposal controls are rendered; disabled submit-proposal remains mandatory.

### Verification
- `python -m py_compile apps\desci-platform\scripts\browser_smoke.py`
- `python -m pytest apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `10 passed`.
- `cmd /c npm run test -- src/__tests__/components/BioLinker.test.jsx` -> `1` file / `2` tests passed.
- `cmd /c npm run test` -> `24` files / `95` tests passed.
- `cmd /c npm run lint`
- `cmd /c npm run build`
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5175 --expect-dev-auth --json-out var\desci-browser-smoke-2026-06-06-biolinker-rfp-readiness-stable-final.json`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-06-biolinker-rfp-readiness-final.json`
- `python ops\scripts\github_modernization_radar.py --json-out var\github-modernization-radar-desci-biolinker-rfp-readiness-2026-06-06.json --markdown-out docs\reports\2026-06\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_DESCI_BIOLINKER_RFP_READINESS_2026-06-06.md`
- `python ops\scripts\auto_research_status.py --radar-json var\github-modernization-radar-desci-biolinker-rfp-readiness-2026-06-06.json --live-source-commit 8fd5618179cca954ce3f4aa6888d120bc651cdbc --json-out var\auto-research-status-desci-biolinker-rfp-readiness-2026-06-06.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_OPERATOR_STATUS_DESCI_BIOLINKER_RFP_READINESS_2026-06-06.md`

### Result
- Dev-auth browser smoke passed `24/24`, including `biolinker-rfp-readiness`.
- DeSci canonical smoke passed `8/8`.
- Workspace canonical smoke passed `8/8`.
- AutoResearch operator status is `ok` via `var/auto-research-status-desci-biolinker-rfp-readiness-2026-06-06.json`.
- Source-backed modernization radar passed with `7/7` adopted sources at Veritas `HEAD` `8fd5618179cca954ce3f4aa6888d120bc651cdbc`.

## 2026-06-06 (Notices Discovery Readiness Browser Action)

### Scope
- Closed the empty-research-context grant discovery readiness gap by adding a persistent checklist/status panel.
- Disabled Discover until the research context has non-empty trimmed text.
- Added a focused component test for disabled/enabled readiness.
- Added `notices-discovery-readiness` to authenticated browser smoke with a scoped `/notices` fixture and no-POST assertion.

### Verification
- `python -m py_compile apps\desci-platform\scripts\browser_smoke.py`
- `python -m pytest apps\desci-platform\backend\tests\test_browser_smoke.py -q -p no:cacheprovider` -> `10 passed`.
- `cmd /c npm run test -- src/__tests__/components/Notices.test.jsx` -> `1` file / `3` tests passed.
- `cmd /c npm run test` -> `25` files / `98` tests passed.
- `cmd /c npm run lint`
- `cmd /c npm run build`
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5191 --expect-dev-auth --timeout 25 --json-out var\desci-browser-smoke-notices-discovery-readiness-2026-06-06-final.json`
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-2026-06-06-notices-discovery-readiness.json`
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-2026-06-06-desci-notices-discovery-readiness.json`
- `python ops\scripts\github_modernization_radar.py --json-out var\github-modernization-radar-desci-notices-discovery-readiness-2026-06-06.json --markdown-out docs\reports\2026-06\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_DESCI_NOTICES_DISCOVERY_READINESS_2026-06-06.md`

### Result
- Dev-auth browser smoke passed `27/27`, including `notices-discovery-readiness`.
- DeSci canonical smoke passed `8/8`.
- Workspace canonical smoke passed `8/8`.
- AutoResearch operator status is `ok` via `var/auto-research-status-desci-notices-discovery-readiness-2026-06-06.json`.
- Source-backed modernization radar passed with `7/7` adopted sources at Veritas `HEAD` `1c9ba4eb27eb58d102914894de0fb0a943c7f1b6`.

## 2026-06-06 (Frontend Vitest Split)

### Scope
- Reduced the slow DeSci frontend unit-test gate by adding a split Vitest runner.
- Kept Windows-stable `threads` and `maxWorkers=1`, while running only mock-sensitive files with isolation.
- Updated `npm run test`, `npm run test:lts`, and release-gate `frontend-tests` to use the helper.

### Verification
- Baseline isolated run: `29` files / `132` tests passed, Vitest duration `226.96s`, wall `249.05s`.
- Rejected global no-isolate run: failed `3` files / `8` tests, then identified `DashboardLists.test.jsx` as an additional isolated-bucket file under smoke-compatible args.
- `cmd /c "npm.cmd run test:lts"` -> `29` files / `132` tests passed, wall `82.38s`.
- `cmd /c "npm.cmd run test:lts -- --fileParallelism false"` -> `29` files / `132` tests passed, wall `80.74s`.
- `cmd /c "npm.cmd run test:lts -- src/lib/redirect.test.js"` -> `1` file / `3` tests passed.
- `python -m py_compile apps/desci-platform/scripts/release_gate.py` -> PASS.
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py -q` -> `55 passed`.
- `python apps/desci-platform/scripts/release_gate.py --skip-env --skip-compose --skip-backend --skip-contracts --json-out var/desci-release-gate-frontend-vitest-split-2026-06-06.json` -> `5/5` passed; `frontend-tests` elapsed `60738.8ms`.
- `python ops/scripts/run_workspace_smoke.py --scope desci --only-check "desci frontend unit tests" --json-out var/workspace-smoke-desci-frontend-vitest-split-rerun-2026-06-06.json` -> `1/1` passed.
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-vitest-split-full-2026-06-06.json` -> `8/8` passed.

### Result
- Direct frontend unit-test wall time dropped from `249.05s` to `82.38s`; smoke-compatible runner args passed in `80.74s`.
- Full DeSci smoke remains green at `8/8`.
- Report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_FRONTEND_VITEST_SPLIT_2026-06-06.md`.

## 2026-06-07 (Upload Connected-Wallet Receipt Browser Action)

### Scope
- Closed the connected-wallet `/upload` gap where upload/index receipt coverage did not prove the IP-NFT mint and DSCI reward calls.
- Added stable receipt anchors for upload IP-NFT and reward transaction links.
- Added receipt reward-status feedback so the successful connected-wallet path confirms mint/reward completion in the persisted receipt.
- Added component coverage for mint payload shape, consent hash/timestamp, reward call, and explorer links.
- Added `upload-submit-wallet-receipt` to authenticated browser smoke with a restored wallet, mocked `/nft/mint`, mocked `/reward/paper`, and payload assertions.

### Verification
- `python -m py_compile scripts/browser_smoke.py` -> pass.
- `python -m pytest backend/tests/test_browser_smoke.py` -> `15 passed`.
- `cmd /c npm test -- --run src/__tests__/components/UploadPaper.test.jsx` -> `1` file / `10` tests passed.
- `cmd /c npx eslint src/components/UploadPaper.jsx src/__tests__/components/UploadPaper.test.jsx` -> pass.
- `cmd /c npm run lint -- src/components/UploadPaper.jsx src/__tests__/components/UploadPaper.test.jsx` -> no errors; existing unrelated `BioLinker.jsx` `react-hooks/set-state-in-effect` warning remains.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5212 --expect-dev-auth --json-out var/desci-browser-smoke-upload-wallet.json` -> `50/50` passed.
- Strict runtime gate with `--runtime-smoke-strict-ready` intentionally failed on local launch-readiness blockers `stripe` and `cors`.
- Local runtime release gate without strict launch readiness passed `2/2`: `python scripts/release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-browser-expect-dev-auth --runtime-api http://127.0.0.1:8042 --runtime-frontend http://127.0.0.1:5212 --runtime-evidence-dir var --json-out var/desci-release-gate-upload-wallet-local.json`.

### Result
- Connected-wallet upload now verifies upload -> private indexing poll -> IP-NFT mint -> DSCI reward -> durable receipt links in Chromium.
- Runtime browser smoke is green at `50/50`, including `upload-submit-wallet-receipt`.
- Runtime release gate is green at `2/2` in local dev-auth mode.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_UPLOAD_WALLET_RECEIPT_2026-06-07.md`.

## 2026-06-07 (BioLinker Proposal Clipboard Failure Browser Action)

### Scope
- Closed the ProposalView clipboard-denial gap after baseline review showed `Copy all` fired `navigator.clipboard.writeText` without awaiting or catching failures.
- Added localized `proposal.copyFailed` messaging.
- Added stable ProposalView test IDs for modal, copy, export, and close controls.
- Added focused ProposalView tests for successful copy and denied clipboard permission.
- Added `biolinker-proposal-clipboard-failure` to authenticated browser smoke, covering paper match -> proposal generation -> proposal modal -> denied clipboard feedback.

### Verification
- `python -m py_compile scripts/browser_smoke.py` -> pass.
- `python -m pytest backend/tests/test_browser_smoke.py` -> `15 passed`.
- `cmd /c npm test -- --run src/__tests__/components/ProposalView.test.jsx` -> `1` file / `2` tests passed.
- `cmd /c npx eslint src/components/ProposalView.jsx src/__tests__/components/ProposalView.test.jsx` -> pass.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5212 --timeout 30 --expect-dev-auth --json-out var/desci-browser-smoke-proposal-clipboard.json` -> `51/51` passed.
- `python scripts/release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-browser-expect-dev-auth --runtime-api http://127.0.0.1:8042 --runtime-frontend http://127.0.0.1:5212 --runtime-evidence-dir var --json-out var/desci-release-gate-proposal-clipboard-local.json` -> `2/2` passed.

### Result
- Proposal copy now reports clipboard permission denial instead of producing an unhandled rejected promise.
- BioLinker proposal generation is now included in the live browser suite via deterministic private job fixtures.
- Runtime browser smoke is green at `51/51`, including `biolinker-proposal-clipboard-failure`.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_PROPOSAL_CLIPBOARD_FAILURE_2026-06-07.md`.

## 2026-06-07 (AI Lab Result Copy Failure Browser Action)

### Scope
- Closed the browser-level AI Lab result-copy gap: unit tests covered denied clipboard permission, but the authenticated browser suite did not click a successful generated result and copy it.
- Added a stable `ai-lab-copy-result` test ID to the generated-result copy button.
- Added `ai-lab-result-copy-failure` to authenticated browser smoke, covering agent success -> rendered markdown result -> bridge metadata -> denied clipboard feedback.
- The implementation path remained unchanged because `useAgentTools.copyResult` already awaited and caught clipboard failures; this cycle adopted coverage, not a behavior rewrite.

### Verification
- `python -m py_compile scripts/browser_smoke.py` -> pass.
- `python -m pytest backend/tests/test_browser_smoke.py` -> `15 passed`.
- `cmd /c npm test -- --run src/__tests__/components/AILab.test.jsx` -> `1` file / `5` tests passed.
- `cmd /c npx eslint src/components/AILab.jsx src/__tests__/components/AILab.test.jsx` -> pass.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5214 --timeout 30 --expect-dev-auth --json-out var/desci-browser-smoke-ai-lab-copy.json` -> `52/52` passed.
- `python scripts/release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-browser-expect-dev-auth --runtime-api http://127.0.0.1:8044 --runtime-frontend http://127.0.0.1:5214 --runtime-evidence-dir var --json-out var/desci-release-gate-ai-lab-copy-local.json` -> `2/2` passed.

### Result
- AI Lab generated-result copy failure is now verified in Chromium with denied clipboard permissions and no unhandled rejection.
- Runtime browser smoke is green at `52/52`, including `ai-lab-result-copy-failure`.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_RESULT_COPY_FAILURE_2026-06-07.md`.

## 2026-06-07 (Error Boundary Diagnostics Copy Feedback)

### Scope
- Closed the shared error fallback gap where denied clipboard permission while copying diagnostics failed silently.
- Added visible `errors.copyDiagnosticsFailed` feedback that tells the user to use the on-screen Support ID.
- Added a stable `error-diagnostics-copy` test ID and `error-diagnostics-copy-feedback` alert.
- Added focused component coverage for successful diagnostic copy and denied clipboard permission.

### Verification
- `cmd /c npm test -- --run src/__tests__/components/ErrorBoundary.test.jsx` -> `1` file / `2` tests passed.
- `cmd /c npx eslint src/components/ErrorBoundary.jsx src/__tests__/components/ErrorBoundary.test.jsx` -> pass.

### Result
- The global crash fallback now gives actionable feedback when diagnostics cannot be copied.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_ERROR_BOUNDARY_DIAGNOSTICS_COPY_2026-06-07.md`.

## 2026-06-07 (BioLinker Proposal Export Popup-Blocked Browser Action)

### Scope
- Closed the ProposalView PDF export popup-blocked verification gap: the component had a failure toast path, but no focused test or live browser click proof prevented a blocked popup from also reporting success.
- Added focused ProposalView coverage for `window.open()` returning `null`.
- Added `biolinker-proposal-export-popup-blocked` to authenticated browser smoke, covering paper context handoff -> match job -> proposal job -> proposal modal -> blocked PDF export feedback.

### Verification
- `python -m py_compile scripts/browser_smoke.py` -> pass.
- `python -m pytest backend/tests/test_browser_smoke.py` -> `15 passed`.
- `cmd /c npm test -- --run src/__tests__/components/ProposalView.test.jsx` -> `1` file / `3` tests passed.
- `cmd /c npx eslint src/components/ProposalView.jsx src/__tests__/components/ProposalView.test.jsx` -> pass.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5215 --timeout 30 --expect-dev-auth --json-out var/desci-browser-smoke-proposal-export.json` -> `53/53` passed.
- `python scripts/release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-browser-expect-dev-auth --runtime-api http://127.0.0.1:8045 --runtime-frontend http://127.0.0.1:5215 --runtime-evidence-dir var --json-out var/desci-release-gate-proposal-export-local.json` -> `2/2` passed.

### Result
- Proposal PDF export now has unit and Chromium proof that a blocked popup shows `proposal.popupBlocked`, does not show `proposal.exportOpened`, records one `_blank` open attempt, and avoids unhandled promise rejection noise.
- Runtime browser smoke is green at `53/53`, including `biolinker-proposal-export-popup-blocked`.
- Evidence archive: `var/desci-proposal-export-runtime-evidence-2026-06-07/`.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_PROPOSAL_EXPORT_POPUP_BLOCKED_2026-06-07.md`.

## 2026-06-07 (Pricing Enterprise Contact Safe Link)

### Scope
- Replaced the Enterprise plan contact action's JavaScript `window.open()` path with a semantic `mailto:` link.
- Added explicit `target="_blank"` plus `rel="noopener noreferrer"` to keep the sales contact flow safe and accessible.
- Strengthened `pricing-enterprise-contact-intent` browser smoke to assert the CTA is a link, has the expected sales address and subject, includes safe rel flags, stays on `/pricing`, and does not post checkout.

### Verification
- `python -m py_compile scripts/browser_smoke.py` -> pass.
- `python -m pytest backend/tests/test_browser_smoke.py` -> `15 passed`.
- `cmd /c npm test -- --run src/__tests__/components/PricingPage.test.jsx` -> `1` file / `10` tests passed.
- `cmd /c npx eslint src/components/PricingPage.jsx src/__tests__/components/PricingPage.test.jsx` -> pass.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5216 --timeout 30 --expect-dev-auth --json-out var/desci-browser-smoke-pricing-enterprise-link.json` -> `53/53` passed.
- `python scripts/release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-browser-expect-dev-auth --runtime-api http://127.0.0.1:8046 --runtime-frontend http://127.0.0.1:5216 --runtime-evidence-dir var --json-out var/desci-release-gate-pricing-enterprise-link-local.json` -> `2/2` passed.

### Result
- Enterprise sales contact is now a real link rather than a forced JavaScript popup, so users retain normal browser/mail-client controls and the app avoids ambiguous `window.open(..., "noopener")` return-value behavior.
- Runtime browser smoke remains green at `53/53`.
- Evidence archive: `var/desci-pricing-enterprise-link-runtime-evidence-2026-06-07/`.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_PRICING_ENTERPRISE_SAFE_LINK_2026-06-07.md`.

## 2026-06-07 (Dashboard Recommendation Source Link Fallback)

### Scope
- Removed the dashboard recommendation card fallback that turned missing notice URLs into `href="#"` external links.
- Added URL protocol validation so only HTTP(S) recommendation source URLs render as external links.
- Added a localized unavailable-source fallback for missing, fragment-only, or unsafe source URLs.
- Added `dashboard-recommendation-source-link-fallback` to authenticated browser smoke, covering a safe source URL plus missing and `javascript:` source URLs.
- Hardened the mocked pricing checkout smoke path with a deterministic `/subscription/tier` fixture after the first full rerun exposed unrelated transient `Failed to fetch` console noise.

### Verification
- `python -m py_compile scripts/browser_smoke.py` -> pass.
- `python -m pytest backend/tests/test_browser_smoke.py` -> `15 passed`.
- `cmd /c npm test -- --run src/__tests__/components/DashboardLists.test.jsx` -> `1` file / `7` tests passed.
- `cmd /c npx eslint src/components/dashboard/RecommendationList.jsx src/__tests__/components/DashboardLists.test.jsx` -> pass.
- First full browser-smoke rerun proved the new dashboard recommendation check passed but failed on the pre-existing pricing checkout tier-fetch console noise.
- After adding the pricing tier fixture, `python scripts/browser_smoke.py --frontend http://127.0.0.1:5217 --timeout 30 --expect-dev-auth --json-out var/desci-browser-smoke-dashboard-rec-link.json` -> `54/54` passed.
- `python scripts/release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-browser-expect-dev-auth --runtime-api http://127.0.0.1:8047 --runtime-frontend http://127.0.0.1:5217 --runtime-evidence-dir var --json-out var/desci-release-gate-dashboard-rec-link-local.json` -> `2/2` passed.

### Result
- Dashboard recommendations no longer create misleading external-link controls for missing or unsafe notice URLs.
- Runtime browser smoke is green at `54/54`, including `dashboard-recommendation-source-link-fallback`.
- Evidence archive: `var/desci-dashboard-rec-link-runtime-evidence-2026-06-07/`.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_DASHBOARD_RECOMMENDATION_SOURCE_LINK_2026-06-07.md`.

## 2026-06-07 (Notices Source Link Fallback)

### Scope
- Added HTTP(S)-only URL validation to Funding Radar original-notice links and grant-discovery opportunity links.
- Added localized unavailable-source fallback text for missing, malformed, or unsafe notice/discovery source URLs.
- Added `notices-source-link-fallback` to authenticated browser smoke with safe, missing, and `javascript:` URL fixtures across both `/notices` source-link surfaces.
- Added `--only-check` to `scripts/browser_smoke.py` so one browser workflow can be isolated before a full smoke rerun.

### Verification
- `cmd /c npm test -- --run src/__tests__/components/Notices.test.jsx` -> `1` file / `5` tests passed.
- `cmd /c npx eslint src/components/Notices.jsx src/__tests__/components/Notices.test.jsx` -> pass.
- `python -m py_compile scripts/browser_smoke.py` -> pass.
- `python -m pytest backend/tests/test_browser_smoke.py` -> `17 passed`.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5218 --timeout 30 --expect-dev-auth --only-check notices-source-link-fallback --json-out var/desci-browser-smoke-notices-source-link-focused.json` -> `1/1` passed.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5218 --timeout 30 --expect-dev-auth --json-out var/desci-browser-smoke-notices-source-link.json` -> `55/55` passed.
- `python scripts/release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-browser-expect-dev-auth --runtime-api http://127.0.0.1:8048 --runtime-frontend http://127.0.0.1:5218 --runtime-evidence-dir var --json-out var/desci-release-gate-notices-source-link-local.json` -> `2/2` passed.

### Result
- Funding Radar no longer renders source anchors for missing or unsafe API URL values on either original notices or discovery recommendations.
- Runtime browser smoke is green at `55/55`, including `notices-source-link-fallback`.
- Evidence archive: `var/desci-notices-source-link-runtime-evidence-2026-06-07/`.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_NOTICES_SOURCE_LINK_FALLBACK_2026-06-07.md`.

## 2026-06-07 (Investor Website Link Fallback)

### Scope
- Added HTTP(S)-only URL validation to VC website links in the investor directory.
- Added localized unavailable-website fallback text for missing, malformed, or unsafe VC website values.
- Extended `investors-filter-directory` browser smoke to cover a safe website, a missing website, a `javascript:` website, safe rel flags, and the existing filter workflow.

### Verification
- `cmd /c npm test -- --run src/__tests__/components/Investors.test.jsx` -> `1` file / `10` tests passed.
- `cmd /c npx eslint src/components/Investors.jsx src/__tests__/components/Investors.test.jsx` -> pass.
- `python -m py_compile scripts/browser_smoke.py` -> pass.
- `python -m pytest backend/tests/test_browser_smoke.py` -> `17 passed`.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5219 --timeout 30 --expect-dev-auth --only-check investors-filter-directory --json-out var/desci-browser-smoke-investor-link-focused.json` -> `1/1` passed.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5219 --timeout 30 --expect-dev-auth --json-out var/desci-browser-smoke-investor-link.json` -> `55/55` passed.
- `python scripts/release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-browser-expect-dev-auth --runtime-api http://127.0.0.1:8049 --runtime-frontend http://127.0.0.1:5219 --runtime-evidence-dir var --json-out var/desci-release-gate-investor-link-local.json` -> `2/2` passed.

### Result
- Investor directory cards no longer render outbound anchors for missing or unsafe API website values.
- Runtime browser smoke remains green at `55/55`.
- Evidence archive: `var/desci-investor-website-link-runtime-evidence-2026-06-07/`.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_INVESTOR_WEBSITE_LINK_FALLBACK_2026-06-07.md`.

## 2026-06-07 (Research Feed IPFS and Tx Link Fallback)

### Scope
- Added identifier validation before rendering public research-feed IPFS gateway links and Polygon Amoy transaction links.
- Valid IPFS CIDs now render as `https://ipfs.io/ipfs/{cid}` links only when they are bounded alphanumeric identifiers.
- Valid transaction hashes now render as Amoy explorer links only when they match `0x` plus 64 hexadecimal characters.
- Malformed CIDs and transaction hashes render non-clickable unavailable states.
- Extended `explore-analyze-intent` browser smoke to cover a safe paper, a malformed CID/transaction paper, safe rel flags, and the existing analyze login handoff.

### Verification
- `cmd /c npm test -- --run src/__tests__/components/ResearchFeed.test.jsx` -> `1` file / `4` tests passed.
- `cmd /c npx eslint src/components/ResearchFeed.jsx src/__tests__/components/ResearchFeed.test.jsx` -> pass.
- `python -m py_compile scripts/browser_smoke.py` -> pass.
- `python -m pytest backend/tests/test_browser_smoke.py` -> `17 passed`.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5220 --timeout 30 --expect-dev-auth --only-check explore-analyze-intent --json-out var/desci-browser-smoke-research-links-focused.json` -> `1/1` passed.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5220 --timeout 30 --expect-dev-auth --json-out var/desci-browser-smoke-research-links.json` -> `55/55` passed.
- `python scripts/release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-browser-expect-dev-auth --runtime-api http://127.0.0.1:8050 --runtime-frontend http://127.0.0.1:5220 --runtime-evidence-dir var --json-out var/desci-release-gate-research-links-local.json` -> `2/2` passed.

### Result
- Public research-feed cards no longer render IPFS or explorer anchors for malformed API identifier values.
- Runtime browser smoke remains green at `55/55`.
- Evidence archive: `var/desci-research-feed-link-runtime-evidence-2026-06-07/`.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_RESEARCH_FEED_LINK_FALLBACK_2026-06-07.md`.

## 2026-06-07 (Success Modal Transaction Link Fallback)

### Scope
- Added transaction-hash shape validation to the authenticated IP-NFT mint success modal.
- Valid hashes now render Polygon Amoy explorer links only when they match `0x` plus 64 hexadecimal characters.
- Malformed hashes remain visible as non-clickable receipt text instead of becoming explorer anchors.
- Extended `mylab-mint-success` browser smoke to use a valid 32-byte transaction hash fixture and assert safe `_blank` rel flags.

### Verification
- `cmd /c npm test -- --run src/__tests__/components/SuccessModal.test.jsx` -> `1` file / `2` tests passed.
- `cmd /c npx eslint src/components/ui/SuccessModal.jsx src/__tests__/components/SuccessModal.test.jsx` -> pass.
- `python -m py_compile scripts/browser_smoke.py` -> pass.
- `python -m pytest backend/tests/test_browser_smoke.py` -> `17 passed`.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5221 --timeout 30 --expect-dev-auth --only-check mylab-mint-success --json-out var/desci-browser-smoke-success-modal-tx-focused.json` -> `1/1` passed.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5221 --timeout 30 --expect-dev-auth --json-out var/desci-browser-smoke-success-modal-tx.json` -> `55/55` passed.
- `python scripts/release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-browser-expect-dev-auth --runtime-api http://127.0.0.1:8051 --runtime-frontend http://127.0.0.1:5221 --runtime-evidence-dir var --json-out var/desci-release-gate-success-modal-tx-local.json` -> `2/2` passed.

### Result
- Authenticated mint success receipts no longer render outbound explorer anchors for malformed transaction hashes.
- Runtime browser smoke remains green at `55/55`, including `mylab-mint-success`.
- Evidence archive: `var/desci-success-modal-tx-runtime-evidence-2026-06-07/`.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_SUCCESS_MODAL_TX_LINK_FALLBACK_2026-06-07.md`.

## 2026-06-07 (Authenticated Receipt Link Hardening)

### Scope
- Added shared IPFS CID and Amoy transaction hash link helpers for authenticated receipt surfaces.
- `UploadPaper` now canonicalizes valid IPFS receipt links, validates mint/reward tx hashes, and renders malformed identifiers as non-clickable fallback states.
- `useMyLab` now extracts a valid CID before sending mint `token_uri`, and `MyLab` now canonicalizes valid IPFS links while rendering malformed `paper.ipfs_url` values as fallback text.
- Updated browser smoke fixtures to use realistic CID-shaped values instead of paper ids or short fake strings.

### Verification
- `cmd /c npm test -- --run src/__tests__/components/UploadPaper.test.jsx src/__tests__/components/MyLab.test.jsx src/hooks/useMyLab.test.jsx` -> `3` files / `18` tests passed.
- `cmd /c npx eslint src/lib/decentralizedLinks.js src/components/UploadPaper.jsx src/components/MyLab.jsx src/hooks/useMyLab.js src/__tests__/components/UploadPaper.test.jsx src/__tests__/components/MyLab.test.jsx src/hooks/useMyLab.test.jsx` -> pass.
- `python -m py_compile scripts/browser_smoke.py` -> pass.
- `python -m pytest backend/tests/test_browser_smoke.py` -> `17 passed`.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5222 --timeout 30 --expect-dev-auth --only-check upload-submit-wallet-receipt --json-out var/desci-browser-smoke-receipt-links-upload-focused.json` -> `1/1` passed.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5222 --timeout 30 --expect-dev-auth --only-check mylab-mint-success --json-out var/desci-browser-smoke-receipt-links-mylab-focused.json` -> `1/1` passed.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5222 --timeout 30 --expect-dev-auth --only-check upload-submit-receipt --json-out var/desci-browser-smoke-receipt-links-upload-basic-focused.json` -> `1/1` passed.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5222 --timeout 30 --expect-dev-auth --json-out var/desci-browser-smoke-receipt-links.json` -> `55/55` passed.
- `python scripts/release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-browser-expect-dev-auth --runtime-api http://127.0.0.1:8052 --runtime-frontend http://127.0.0.1:5222 --runtime-evidence-dir var --json-out var/desci-release-gate-receipt-links-local.json` -> `2/2` passed.

### Result
- Authenticated upload and vault receipts no longer render outbound anchors from malformed IPFS or transaction values.
- Mint requests now send canonical `ipfs://{cid}` token URIs only after CID validation.
- Runtime browser smoke remains green at `55/55`.
- Evidence archive: `var/desci-authenticated-receipt-links-runtime-evidence-2026-06-07/`.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AUTHENTICATED_RECEIPT_LINKS_2026-06-07.md`.

## 2026-06-07 (Pricing Stripe Redirect Guard)

### Scope
- Added host validation before assigning backend-provided checkout and billing portal URLs to `window.location.assign`.
- Checkout redirects now allow Stripe Checkout session URLs, and Billing Portal redirects now allow Stripe Billing session URLs.
- Vite dev mode still allows same-origin mock redirect URLs so local browser-smoke success flows remain deterministic.
- Added PricingPage tests for blocked `javascript:` checkout URLs and blocked non-Stripe portal URLs.

### Verification
- `cmd /c npm test -- --run src/__tests__/components/PricingPage.test.jsx` -> `1` file / `12` tests passed.
- `cmd /c npx eslint src/components/PricingPage.jsx src/__tests__/components/PricingPage.test.jsx` -> pass.
- `python -m py_compile scripts/browser_smoke.py` -> pass.
- `python -m pytest backend/tests/test_browser_smoke.py` -> `17 passed`.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5223 --timeout 30 --expect-dev-auth --only-check pricing-checkout-mocked --only-check pricing-billing-portal --only-check pricing-checkout-error-visible --json-out var/desci-browser-smoke-pricing-redirect-focused.json` -> `3/3` passed.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5223 --timeout 30 --expect-dev-auth --json-out var/desci-browser-smoke-pricing-redirect.json` -> `55/55` passed.
- `python scripts/release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-browser-expect-dev-auth --runtime-api http://127.0.0.1:8053 --runtime-frontend http://127.0.0.1:5223 --runtime-evidence-dir var --json-out var/desci-release-gate-pricing-redirect-local.json` -> `2/2` passed.

### Result
- Pricing redirects now fail closed for unsafe schemes and unexpected external hosts.
- Checkout and billing portal local smoke paths remain green.
- Evidence archive: `var/desci-pricing-redirect-runtime-evidence-2026-06-07/`.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_PRICING_STRIPE_REDIRECT_GUARD_2026-06-07.md`.

## 2026-06-07 (Investor Email Link Fallback)

### Scope
- Added email-shape validation before composing public investor directory `mailto:` links.
- Valid contact emails still render as `mailto:{email}` anchors.
- Malformed truthy contact emails now render localized non-clickable unavailable state.
- Extended `investors-filter-directory` browser smoke to assert the unsafe email fallback and confirm no `mailto:javascript:` or empty-recipient `mailto:?` anchors render.

### Verification
- `cmd /c npm test -- --run src/__tests__/components/Investors.test.jsx` -> `1` file / `11` tests passed.
- `cmd /c npx eslint src/components/Investors.jsx src/__tests__/components/Investors.test.jsx` -> pass.
- `python -m py_compile scripts/browser_smoke.py` -> pass.
- `python -m pytest backend/tests/test_browser_smoke.py` -> `17 passed`.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5224 --timeout 30 --expect-dev-auth --only-check investors-filter-directory --json-out var/desci-browser-smoke-investor-email-focused.json` -> `1/1` passed.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5224 --timeout 30 --expect-dev-auth --json-out var/desci-browser-smoke-investor-email.json` -> `55/55` passed.
- First local runtime release-gate run preserved a transient `upload-form-readiness` failure (`54/55` browser smoke) for diagnostics.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5224 --timeout 30 --expect-dev-auth --only-check upload-form-readiness --json-out var/desci-browser-smoke-investor-email-upload-readiness-rerun.json` -> `1/1` passed.
- Rerunning the unchanged local runtime release gate passed `2/2` with `var/desci-release-gate-investor-email-local.json`.

### Result
- Public investor cards no longer render outbound mailto anchors for malformed API contact email values.
- Runtime browser smoke remains green at `55/55`.
- Evidence archive: `var/desci-investor-email-runtime-evidence-2026-06-07/`.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_INVESTOR_EMAIL_LINK_FALLBACK_2026-06-07.md`.

## 2026-06-07 (Browser Smoke Network Diagnostics)

### Scope
- Added per-check Playwright `requestfailed` and HTTP error-response collection in the fresh-page browser-smoke wrapper.
- Network diagnostics are appended only when the check already failed, preserving expected mocked error UI checks as passing flows.
- Added contract tests proving failed checks include request URL/method/status diagnostics and passing checks suppress those diagnostics.

### Verification
- `python -m py_compile scripts/browser_smoke.py` -> pass.
- `python -m pytest backend/tests/test_browser_smoke.py` -> `19 passed`.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5225 --timeout 30 --expect-dev-auth --only-check upload-form-readiness --json-out var/desci-browser-smoke-diagnostics-upload-readiness-focused.json` -> `1/1` passed.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5225 --timeout 30 --expect-dev-auth --json-out var/desci-browser-smoke-diagnostics.json` -> `55/55` passed.
- `python scripts/release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-browser-expect-dev-auth --runtime-api http://127.0.0.1:8055 --runtime-frontend http://127.0.0.1:5225 --runtime-evidence-dir var --json-out var/desci-release-gate-smoke-diagnostics-local.json` -> `2/2` passed.

### Result
- Future failed browser-smoke checks now include failed request URLs and HTTP error response details when available.
- Runtime browser smoke remains green at `55/55`.
- Evidence archive: `var/desci-browser-smoke-diagnostics-runtime-evidence-2026-06-07/`.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_BROWSER_SMOKE_NETWORK_DIAGNOSTICS_2026-06-07.md`.

## 2026-06-07 (AI Lab YouTube URL Validation)

### Scope
- Added allowlisted YouTube URL validation for the AI Lab YouTube Intelligence workflow.
- Malformed URL values now show a localized validation hint and keep the run button disabled.
- Supported YouTube video URLs are normalized before posting to `/api/agent/youtube`.
- Extended `ai-lab-readiness` browser smoke to prove malformed YouTube URLs do not trigger a runnable state.

### Verification
- `cmd /c npm test -- --run src/__tests__/components/AILab.test.jsx` -> `1` file / `6` tests passed.
- `cmd /c npx eslint src/components/AILab.jsx src/hooks/useAgentTools.js src/__tests__/components/AILab.test.jsx` -> pass.
- `python -m py_compile scripts/browser_smoke.py` -> pass.
- `python -m pytest backend/tests/test_browser_smoke.py` -> `19 passed`.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5226 --timeout 30 --expect-dev-auth --only-check ai-lab-readiness --json-out var/desci-browser-smoke-ai-lab-youtube-url-focused.json` -> `1/1` passed.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5226 --timeout 30 --expect-dev-auth --json-out var/desci-browser-smoke-ai-lab-youtube-url.json` -> `55/55` passed.
- `python scripts/release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-browser-expect-dev-auth --runtime-api http://127.0.0.1:8056 --runtime-frontend http://127.0.0.1:5226 --runtime-evidence-dir var --json-out var/desci-release-gate-ai-lab-youtube-url-local.json` -> `2/2` passed.

### Result
- AI Lab no longer treats arbitrary non-empty strings as runnable YouTube Intelligence URLs.
- Runtime browser smoke remains green at `55/55`.
- Evidence archive: `var/desci-ai-lab-youtube-url-runtime-evidence-2026-06-07/`.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_YOUTUBE_URL_VALIDATION_2026-06-07.md`.

## 2026-06-07 (Proposal Export HTML Escaping)

### Scope
- Replaced the BioLinker proposal export popup's `innerHTML` reuse with text extraction plus explicit HTML escaping.
- Escaped both printable proposal title and body before inserting them into the `document.write()` template.
- Extended the proposal export browser smoke to capture successful popup HTML, assert raw `<script>` / `<img onerror>` samples are escaped, confirm print still runs, and then verify the popup-blocked fallback.

### Verification
- `cmd /c npm test -- --run src/__tests__/components/ProposalView.test.jsx` -> `1` file / `4` tests passed.
- `cmd /c npx eslint src/components/ProposalView.jsx src/__tests__/components/ProposalView.test.jsx` -> pass.
- `python -m py_compile scripts/browser_smoke.py` -> pass.
- `python -m pytest backend/tests/test_browser_smoke.py` -> `19 passed`.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5227 --timeout 30 --expect-dev-auth --only-check biolinker-proposal-export-popup-blocked --json-out var/desci-browser-smoke-proposal-export-sanitized-focused.json` -> `1/1` passed.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5227 --timeout 30 --expect-dev-auth --json-out var/desci-browser-smoke-proposal-export-sanitized.json` -> `55/55` passed.
- `python scripts/release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-browser-expect-dev-auth --runtime-api http://127.0.0.1:8057 --runtime-frontend http://127.0.0.1:5227 --runtime-evidence-dir var --json-out var/desci-release-gate-proposal-export-sanitized-local.json` -> `2/2` passed.

### Result
- Proposal export no longer writes generated proposal markup directly into the printable popup document.
- Runtime browser smoke remains green at `55/55`.
- Evidence archive: `var/desci-proposal-export-sanitized-runtime-evidence-2026-06-07/`.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_PROPOSAL_EXPORT_HTML_ESCAPING_2026-06-07.md`.

## 2026-06-07 (Upload Legacy Cleanup)

### Scope
- Removed unused `frontend/src/components/Upload.jsx` legacy upload component.
- Confirmed the only routed `/upload` implementation is still `UploadPaper` via `App.jsx`.
- Preserved the actual upload workflow with focused tests, production build, focused browser smoke, full authenticated browser smoke, and release gate.

### Verification
- `rg -n "components/Upload|from './components/Upload'|from '../components/Upload'|<Upload\\b|export default function Upload\\(" frontend/src -g "*.jsx" -g "*.js"` -> no legacy component references; only `UploadPaper` route and icon usages remain.
- `cmd /c npm test -- --run src/__tests__/components/UploadPaper.test.jsx` -> `1` file / `12` tests passed.
- `cmd /c npx eslint src/App.jsx src/components/UploadPaper.jsx src/__tests__/components/UploadPaper.test.jsx` -> pass.
- `cmd /c npm run build` -> pass.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5228 --timeout 30 --expect-dev-auth --only-check upload-authenticated --only-check upload-form-readiness --only-check upload-submit-receipt --json-out var/desci-browser-smoke-upload-legacy-cleanup-focused.json` -> `3/3` passed.
- First full browser-smoke run preserved a runtime auth-profile setup failure caused by missing backend `ALLOW_TEST_BYPASS`.
- Heartbeat full browser-smoke rerun passed `55/55` with `var/desci-browser-smoke-upload-legacy-cleanup-rerun.json`.
- Heartbeat local runtime release gate passed `2/2` with `var/desci-release-gate-upload-legacy-cleanup-local.json`.

### Result
- The stale duplicate upload implementation is removed; `/upload` continues to render and submit through `UploadPaper`.
- Runtime browser smoke remains green at `55/55`.
- Evidence archive: `var/desci-upload-legacy-cleanup-runtime-evidence-2026-06-07/`.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_UPLOAD_LEGACY_CLEANUP_2026-06-07.md`.

## 2026-06-07 (Error Boundary Recovery Link)

### Scope
- Replaced ErrorBoundary dashboard recovery `button` plus `window.location.href` assignment with a semantic `<a href="/dashboard">`.
- Kept retry and diagnostics copy controls as buttons.
- Added a focused test proving the recovery control is exposed as a dashboard link with the expected href.

### Verification
- `cmd /c npm test -- --run src/__tests__/components/ErrorBoundary.test.jsx` -> `1` file / `3` tests passed.
- `cmd /c npx eslint src/components/ErrorBoundary.jsx src/__tests__/components/ErrorBoundary.test.jsx` -> pass.
- `cmd /c npm run build` -> pass.

### Result
- ErrorBoundary recovery navigation now uses the correct HTML primitive while preserving the existing visual style.
- Evidence archive: `var/desci-error-boundary-recovery-evidence-2026-06-07/`.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_ERROR_BOUNDARY_RECOVERY_LINK_2026-06-07.md`.

## 2026-06-07 (Browser Smoke Progress Flush)

### Scope
- Added `_print_progress()` to `scripts/browser_smoke.py`.
- Routed browser-smoke per-check, JSON-written, failure, and OK output through `print(..., flush=True)`.
- Added a contract test proving the progress print helper flushes output.

### Verification
- `python -m py_compile scripts/browser_smoke.py` -> pass.
- `python -m pytest backend/tests/test_browser_smoke.py` -> `20 passed`.
- `python scripts/browser_smoke.py --help` -> pass.

### Result
- Long browser-smoke runs now flush progress without requiring an external heartbeat wrapper.
- Evidence archive: `var/desci-browser-smoke-progress-flush-evidence-2026-06-07/`.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_BROWSER_SMOKE_PROGRESS_FLUSH_2026-06-07.md`.

## 2026-06-07 (Product Smoke Progress Flush)

### Scope
- Added `_print_progress()` to `scripts/product_smoke.py`.
- Routed product-smoke per-check, request-error, JSON-written, FAILED, and OK output through `print(..., flush=True)`.
- Added a product-smoke contract test proving the progress helper flushes output.

### Verification
- `python -m py_compile scripts/product_smoke.py` -> pass.
- `python -m pytest backend/tests/test_product_smoke.py` -> `9 passed`.
- `python scripts/product_smoke.py --help` -> pass.
- `python scripts/product_smoke.py --api http://127.0.0.1:9 --skip-frontend --timeout 0.2 --retries 0 --json-out var/desci-product-smoke-progress-flush-evidence-2026-06-07/product_smoke_negative.json` -> expected exit `1` with request-failure JSON evidence.
- `rg -n "print\\(" scripts\\product_smoke.py backend\\tests\\test_product_smoke.py` -> only `_print_progress()` and its test assertion remain.

### Result
- Product smoke progress now flushes without requiring an external heartbeat wrapper.
- Evidence archive: `var/desci-product-smoke-progress-flush-evidence-2026-06-07/`.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_PRODUCT_SMOKE_PROGRESS_FLUSH_2026-06-07.md`.

## 2026-06-07 (Release Gate Summary Flush)

### Scope
- Added `flush=True` to the final `FAILED at ...` and `OK (...)` summary prints in `scripts/release_gate.py`.
- Preserved existing step-level release-gate progress, retry, failure, and artifact-validation output.
- Added a dry-run `main()` test proving both final OK and FAILED summary paths print with `flush=True`.

### Verification
- `python -m py_compile scripts/release_gate.py` -> pass.
- `python -m pytest backend/tests/test_release_gate.py` -> `57 passed`.
- `python scripts/release_gate.py --dry-run --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts` -> pass.
- `rg -n "FAILED at|OK \\(|flush=True|test_release_gate_final_summary_prints_flush|print\\(" scripts\\release_gate.py backend\\tests\\test_release_gate.py` -> final OK and FAILED summary prints include `flush=True`, and the test asserts both paths.

### Result
- Release-gate output now flushes consistently from first step start through final OK/FAILED summary.
- Evidence archive: `var/desci-release-gate-summary-flush-evidence-2026-06-07/`.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_RELEASE_GATE_SUMMARY_FLUSH_2026-06-07.md`.

## 2026-06-07 (VC Modal Accessibility)

### Scope
- Moved VC match detail propagation handling off the `GlassCard` so the modal content no longer becomes an unintended focusable `role="button"`.
- Added `role="dialog"`, `aria-modal="true"`, title-based `aria-labelledby`, initial close-button focus, Escape dismissal, and an icon close button with an accessible label.
- Added `aria-haspopup="dialog"` and a deterministic test id to VC match cards.
- Extended `vc-portal-select` browser smoke to click a match card, verify dialog semantics, close by button, reopen, and close by Escape.

### Verification
- `python -m py_compile scripts/browser_smoke.py` -> pass.
- `python -m pytest backend/tests/test_browser_smoke.py` -> `20 passed`.
- `cmd /c npm test -- --run src/__tests__/components/VCDashboard.test.jsx` from `frontend/` -> `1` file / `1` test passed.
- `cmd /c npx eslint src/components/vc/MatchDetailModal.jsx src/components/vc/MatchCard.jsx src/__tests__/components/VCDashboard.test.jsx` from `frontend/` -> pass.
- First focused runtime smoke on `5230` failed due frontend startup env typo (`VITE_ENABLE_DEV_AUTH` instead of `VITE_ENABLE_DEV_AUTH_BYPASS`); evidence preserved as setup noise.
- Corrected focused runtime smoke on `5232` passed `1/1` with `var/desci-vc-modal-accessibility-runtime-evidence-2026-06-07/vc_portal_select_modal_escape.json`.
- Full dev-auth browser smoke passed `55/55` with `var/desci-vc-modal-accessibility-runtime-evidence-2026-06-07/browser_smoke_full_escape.json`.
- Runtime release gate passed `2/2` with `var/desci-vc-modal-accessibility-runtime-evidence-2026-06-07/release_gate_runtime_escape.json`.

### Result
- The VC Portal match detail path is now a real accessible modal workflow and is covered by direct browser clicking.
- Evidence archive: `var/desci-vc-modal-accessibility-runtime-evidence-2026-06-07/`.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_VC_MODAL_ACCESSIBILITY_2026-06-07.md`.

## 2026-06-07 (Peer Review Reward Receipt)

### Scope
- Added reward-function-specific mock amounts so `rewardPeerReview` returns the advertised `50` DSCI amount instead of the generic upload amount.
- Stored successful peer-review reward responses in `usePeerReview()` and rendered a stable `role="status"` receipt with title, score, amount, and transaction hash.
- Extended the connected-wallet peer-review browser smoke to click a paper, submit a review, verify the reward POST, receipt, and `Rewarded` badge.

### Verification
- `python -m py_compile backend/services/web3_service.py scripts/browser_smoke.py` -> pass.
- `python -m pytest backend/tests/test_smoke_pipeline.py backend/tests/test_browser_smoke.py` -> `30 passed`.
- `cmd /c npm test -- --run src/__tests__/components/PeerReview.test.jsx` from `frontend/` -> `1` file / `2` tests passed.
- `cmd /c npx eslint src/components/PeerReview.jsx src/hooks/usePeerReview.js src/__tests__/components/PeerReview.test.jsx` from `frontend/` -> pass.
- Focused runtime smoke `peer-review-submit-receipt` passed `1/1`.
- Full dev-auth browser smoke passed `56/56`.
- Runtime release gate passed `2/2`.

### Result
- Peer-review reward submission now has a durable visible receipt and direct browser-click coverage for the connected-wallet submit path.
- Evidence archive: `var/desci-peer-review-reward-receipt-runtime-evidence-2026-06-07/`.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_PEER_REVIEW_REWARD_RECEIPT_2026-06-07.md`.

## 2026-06-07 (Asset Receipt Stale Clear)

### Scope
- Cleared `lastUploadedAsset` when a new asset file is selected and when a new upload begins, preventing stale receipt evidence from remaining visible during repeat upload workflows.
- Extended the AssetManager component test to prove selecting a follow-up file removes the old receipt without posting again.
- Extended `asset-upload-readiness` browser smoke to verify receipt `role="status"`, `aria-atomic`, filename, indexing state, VC/RFP handoff links, and stale-receipt clearing after follow-up file selection.

### Verification
- `python -m py_compile scripts/browser_smoke.py` -> pass.
- `python -m pytest backend/tests/test_browser_smoke.py` -> `20 passed`.
- `cmd /c npm test -- --run src/__tests__/components/AssetManager.test.jsx` from `frontend/` -> `1` file / `4` tests passed.
- `cmd /c npx eslint src/components/AssetManager.jsx src/__tests__/components/AssetManager.test.jsx` from `frontend/` -> pass.
- Focused runtime smoke `asset-upload-readiness` passed `1/1`.
- Full dev-auth browser smoke passed `56/56`.
- Runtime release gate passed `2/2`.

### Result
- Asset upload receipts now stay tied to the completed upload and disappear when the operator starts a new asset handoff.
- Evidence archive: `var/desci-asset-receipt-stale-clear-runtime-evidence-2026-06-07/`.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_ASSET_RECEIPT_STALE_CLEAR_2026-06-07.md`.

## 2026-06-07 (AI Lab Executive Summary Concise Shape)

### Scope
- Tightened `executive_summary_decision_snapshot` so the Executive Summary must remain one paragraph and one to five sentence-like units.
- Added a regression that keeps recommendation, evidence basis, uncertainty, and next action markers present while expanding the summary to seven sentence-like units.
- Updated the BioLinker research prompt to keep the first summary block to five sentence-like statements or fewer and avoid a second summary paragraph.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `86 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- Strict sample scoring passed `74/74` with `paragraphs=1 sentence_like_units=5`.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `116 passed`.

### Result
- Executive Summary scoring now rejects overlong or multi-paragraph decision snapshots instead of accepting marker-only summaries.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EXECUTIVE_SUMMARY_CONCISE_SHAPE_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_EXECUTIVE_SUMMARY_CONCISE_SHAPE_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Audience Labeled Fields)

### Scope
- Tightened `audience_use_case_specificity` so Audience & Use Case must contain nonblank `Audience:`, `Use case:`, `Decision context:`, and `Destination:` details.
- Added a regression where the same concrete audience/workflow/destination facts appear only as unlabeled prose.
- Updated the BioLinker research prompt to require the same labeled fields.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `87 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- Strict sample scoring passed `74/74` with `complete_labels=audience,use_case,decision_context,destination`.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `117 passed`.

### Result
- Audience & Use Case scoring now rejects paragraph-only marker stuffing and requires scan-ready labeled fields for review-packet reuse.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_AUDIENCE_LABELED_FIELDS_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_AUDIENCE_LABELED_FIELDS_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Decision Labeled Fields)

### Scope
- Tightened `decision_recommendation_fields` so Recommendation / Decision must contain substantive `Recommendation:`, `Rationale:`, `Confidence:`, and `Change condition:` details.
- Added a regression where the same go/no-go, evidence basis, medium confidence, and hold-condition facts appear only as unlabeled prose.
- Updated the BioLinker research prompt to require labeled, nonblank decision fields.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `88 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- Strict sample scoring passed `74/74` with `complete_labels=recommendation,rationale,confidence,change_condition`.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `118 passed`.

### Result
- Recommendation / Decision scoring now rejects unlabeled paragraph-only decision facts and requires scan-ready fields.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_DECISION_LABELED_FIELDS_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_DECISION_LABELED_FIELDS_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Key Findings Nonempty Fields)

### Scope
- Tightened `key_finding_fields` so every Key Finding item must contain substantive detail after `Claim:`, `Evidence:`, `Uncertainty:`, and `Action meaning:`.
- Added a regression where one item keeps the `Evidence:` label but leaves it empty.
- Updated the BioLinker research prompt to forbid empty Key Finding fields.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `89 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- Strict sample scoring passed `74/74` with `items=3 complete=3 missing=none`.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `119 passed`.

### Result
- Key Findings scoring now rejects empty field labels instead of accepting marker-only findings.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_KEY_FINDINGS_NONEMPTY_FIELDS_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_KEY_FINDINGS_NONEMPTY_FIELDS_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Evidence Map Nonempty Follow-Up)

### Scope
- Tightened `evidence_map_confidence_followup` so every Evidence Map item must include a confidence level and substantive `Follow-up verification:` detail.
- Added a regression where one item keeps `Follow-up verification:` but leaves it empty.
- Updated the BioLinker research prompt to forbid empty Evidence Map confidence/follow-up details.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `90 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- Strict sample scoring passed `74/74` with `items=3 complete=3 missing=none`.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `120 passed`.

### Result
- Evidence Map scoring now rejects empty follow-up labels instead of accepting marker-only verification placeholders.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EVIDENCE_MAP_NONEMPTY_FOLLOWUP_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_EVIDENCE_MAP_NONEMPTY_FOLLOWUP_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Quality Criteria Nonempty Labels)

### Scope
- Tightened `quality_criteria_actionable_acceptance` so every required Quality Criteria label must contain substantive detail.
- Added a regression where `Do not use:` remains present but empty.
- Updated the BioLinker research prompt to forbid blank Quality Criteria labels.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `91 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- Strict sample scoring passed `74/74` with `complete_labels=ready_condition,reject_or_hold_condition,evidence_requirement,verification_owner,reuse_destination`.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `121 passed`.

### Result
- Quality Criteria scoring now rejects blank labeled lines instead of accepting section-level marker stuffing.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_QUALITY_CRITERIA_NONEMPTY_LABELS_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_QUALITY_CRITERIA_NONEMPTY_LABELS_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Risks Nonempty Fields)

### Scope
- Tightened `risks_open_questions_owner_verification` so every risk/open-question item must include substantive risk/question, owner, verification, status/review, and follow-up/mitigation detail.
- Added a regression where one item keeps `Verification:` but leaves its detail blank.
- Updated the BioLinker research prompt to forbid blank risk/open-question fields.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `92 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- Strict sample scoring passed `74/74` with `items=3 complete=3 missing=none`.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `122 passed`.

### Result
- Risks & Open Questions scoring now rejects blank item fields instead of accepting label-only verification placeholders.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_RISKS_NONEMPTY_FIELDS_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_RISKS_NONEMPTY_FIELDS_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Action Plan Nonempty Handoff)

### Scope
- Tightened `action_plan_handoff_fields` so every Action Plan work item must include substantive Owner, Inputs, Artifact, and Decision gate detail.
- Added a regression where one work item keeps `Artifact:` but blanks the artifact detail.
- Updated the BioLinker research prompt to forbid blank Action Plan handoff fields.
- Improved the static sample Day 6-7 artifact into a concrete compliance risk addendum with owner record, blocker status, and data-sharing constraint notes.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `93 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- Strict sample scoring passed `74/74` with `items=3 complete=3 missing=none`.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `123 passed`.

### Result
- Action Plan scoring now rejects blank handoff labels and the static sample now names a concrete Day 6-7 compliance artifact.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_PLAN_NONEMPTY_HANDOFF_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_ACTION_PLAN_NONEMPTY_HANDOFF_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Action Plan Nonempty Dependencies)

### Scope
- Tightened `action_plan_dependency_order` so every Action Plan work item must include concrete prerequisite and blocker/hold detail.
- Added a regression where one item keeps `Dependencies/blocked by:` but blanks the detail.
- Updated the BioLinker research prompt to forbid blank dependency/blocker lines.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `94 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- Strict sample scoring passed `74/74` with `items=3 complete=3 missing=none`.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `124 passed`.

### Result
- Action Plan dependency scoring now rejects blank dependency/blocker lines instead of accepting marker-only sequencing placeholders.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_PLAN_NONEMPTY_DEPENDENCIES_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_ACTION_PLAN_NONEMPTY_DEPENDENCIES_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Deep Dive Context Specificity)

### Scope
- Tightened `deep_dive_dimension_specificity` so Deep Dive dimensions must include topic-specific context markers in addition to generic operating-detail markers.
- Added a regression where dimensions stuff generic workflow/evidence/constraint terms but omit domain context.
- Updated the BioLinker research prompt and browser smoke fixture to require concrete sponsor, eligibility, patient, endpoint, compliance, budget, proposal, or commercialization context.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `95 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- Strict sample scoring passed `74/74` with `valid_dimensions=clinical,commercial,operations,regulatory,technical weak_dimensions=none`.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `125 passed`.

### Result
- Deep Dive scoring now rejects generic marker-stuffed dimension clauses instead of accepting topic-free operating-detail words.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_DEEP_DIVE_CONTEXT_SPECIFICITY_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_DEEP_DIVE_CONTEXT_SPECIFICITY_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Reusable Handoff Entry Specificity)

### Scope
- Tightened `reusable_handoff` so the copy-ready decision-log entry itself must include decision/action, confidence or change condition, stakeholder/reuse destination, and owner next-step detail.
- Added a regression where the copy-ready handoff entry stuffs marker words while artifact-ready labels remain valid.
- Updated the BioLinker research prompt to require usable handoff detail inside the copy-ready decision-log entry.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `96 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- Strict sample scoring passed `74/74` with `entry_fields=decision_action,confidence_or_change,stakeholder_destination,owner_next_step`.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `126 passed`.

### Result
- Reusable Handoff scoring now rejects marker-stuffed copy-ready entries instead of accepting artifact-ready labels as a substitute.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REUSABLE_HANDOFF_ENTRY_SPECIFICITY_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_REUSABLE_HANDOFF_ENTRY_SPECIFICITY_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab References Source Lead Specificity)

### Scope
- Tightened `references_search_queries` so References must include concrete verification queries and a substantive source lead/reference line.
- Added a regression where the three verification queries remain valid but `Source lead:` is reduced to placeholder marker text.
- Updated the BioLinker research prompt to require source title/URL, source type/category, and freshness/date context on source lead/reference lines.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `97 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- Strict sample scoring passed `74/74` with `concrete_queries=3 concrete_source_lines=2`.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `127 passed`.

### Result
- References scoring now rejects placeholder source-lead lines instead of accepting thin marker-bearing bullets.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REFERENCES_SOURCE_LEAD_SPECIFICITY_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_REFERENCES_SOURCE_LEAD_SPECIFICITY_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Evidence Map Category Coverage)

### Scope
- Tightened `evidence_map` so Evidence Map must include substantive `Strong:`, `Weak:`, and `Missing:` categories.
- Added a regression where the `Strong:` item remains complete but `Weak:` and `Missing:` are removed.
- Updated the BioLinker research prompt to forbid collapsing the Evidence Map into one category.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `98 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- Strict sample scoring passed `74/74` with `complete_categories=strong,weak,missing missing_categories=none`.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `128 passed`.

### Result
- Evidence Map scoring now rejects one-category maps instead of accepting whatever category happens to be present.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EVIDENCE_MAP_CATEGORY_COVERAGE_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_EVIDENCE_MAP_CATEGORY_COVERAGE_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Reviewer Red Flags Nonempty Fields)

### Scope
- Tightened `reviewer_red_flags_actionability` so each red-flag item must include substantive Red flag, Stop condition, Evidence blocker, and Escalation detail.
- Added a regression where one item keeps `Stop condition:` but blanks the stop-condition detail.
- Updated the BioLinker research prompt to forbid blank red-flag item fields.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `99 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- Strict sample scoring passed `74/74` with `items=1 complete=1 missing=none`.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `129 passed`.

### Result
- Reviewer Red Flags scoring now rejects blank item fields instead of accepting marker-only stop or escalation labels.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REVIEWER_RED_FLAGS_NONEMPTY_FIELDS_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_RED_FLAGS_NONEMPTY_FIELDS_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Risks Open Question Category)

### Scope
- Tightened `risks_open_questions` so the section must include at least one substantive `Risk:` item and one substantive `Open question:` item.
- Added a regression where the open-question item is converted into a complete Risk item, leaving owner/verification intact but removing the actual open-question category.
- Updated the BioLinker research prompt to require separate Risk and Open question items.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `100 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- Strict sample scoring passed `74/74` with `risks=2 open_questions=1`.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `130 passed`.

### Result
- Risks & Open Questions scoring now rejects sections that mention questions inside risk text without an actual `Open question:` item.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_RISKS_OPEN_QUESTION_CATEGORY_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_RISKS_OPEN_QUESTION_CATEGORY_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Seven Day Plan Shape)

### Scope
- Tightened `seven_day_action_plan` so the Action Plan must include at least two parsed work items and an early-to-late day span.
- Added a regression where a complete work-item plan is replaced with a one-line next-seven-day placeholder.
- Updated the BioLinker research prompt to require dated/priority work items across the next-seven-day window.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `101 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- Strict sample scoring passed `74/74` with `seven_day_window=True items=3 day_span=1-7`.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `131 passed`.

### Result
- Seven-day action-plan scoring now rejects one-line placeholders instead of accepting only a heading and next-seven-day phrase.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_SEVEN_DAY_PLAN_SHAPE_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_SEVEN_DAY_PLAN_SHAPE_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Action Plan Distinct Success Metrics)

### Scope
- Tightened `action_plan_measurable_success_criteria` so every success/done metric must be both measurable and distinct.
- Added a regression where the second work item reuses the first work item's measurable success metric.
- Updated the BioLinker research prompt to forbid duplicated success metrics across work items.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `102 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- Strict sample scoring passed `74/74` with `metrics=3 measurable=3 distinct=3`.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `132 passed`.

### Result
- Action Plan scoring now rejects duplicated success metrics instead of accepting repeated measurable outcomes across different work items.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_PLAN_DISTINCT_SUCCESS_METRICS_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_ACTION_PLAN_DISTINCT_SUCCESS_METRICS_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab References Query Source Scope)

### Scope
- Tightened `references_verification_search_plan` so useful queries must also span at least two source scopes.
- Added a regression where three different `.gov` queries are useful and distinct but still too narrow.
- Updated the BioLinker research prompt and browser smoke fixture to require source-scope diversity.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `103 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- Strict sample scoring passed `74/74` with `source_scopes=government,nonprofit,prior_award,registry,rfp,sponsor`.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `133 passed`.

### Result
- References verification planning now rejects single-source-scope query plans instead of accepting three lexical variants from the same source family.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REFERENCES_QUERY_SOURCE_SCOPE_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_REFERENCES_QUERY_SOURCE_SCOPE_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Evidence Source Freshness Specificity)

### Scope
- Tightened `evidence_sources_freshness_metadata` so source freshness metadata must be substantive rather than merely nonempty.
- Added a regression where every evidence source uses generic `freshness: fresh`.
- Updated the BioLinker research prompt to require checked/retrieved/accessed/date-style freshness metadata.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `104 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- Strict sample scoring passed `74/74` with `sources_with_freshness=2 total_sources=2`.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `134 passed`.

### Result
- Evidence-source freshness scoring now rejects generic freshness strings such as `fresh` instead of accepting any nonempty value.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EVIDENCE_SOURCE_FRESHNESS_SPECIFICITY_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_EVIDENCE_SOURCE_FRESHNESS_SPECIFICITY_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Evidence Source Type Specificity)

### Scope
- Tightened `evidence_sources_type_metadata` so source-type metadata must name a concrete source class rather than a generic label.
- Added a regression where every evidence source uses generic `source_type: guidance`.
- Updated the BioLinker research prompt to reject bare `document`, `article`, `guidance`, `database`, or `source` labels.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `105 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- Strict sample scoring passed `74/74` with `sources_with_type=2 total_sources=2`.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `135 passed`.

### Result
- Evidence-source type scoring now rejects generic source-type labels while preserving specific labels such as `official grant-planning guidance` or `funded-project database`.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EVIDENCE_SOURCE_TYPE_SPECIFICITY_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_EVIDENCE_SOURCE_TYPE_SPECIFICITY_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab References Freshness Specificity)

### Scope
- Tightened References freshness checks so source-bearing reference lines need substantive freshness context.
- Added a regression where the source lead uses only generic `source freshness: fresh`.
- Updated the BioLinker research prompt to reject generic freshness values on reference source lines.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `106 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- Strict sample scoring passed `74/74` with `source_lines=2 substantive_freshness=2`.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `136 passed`.

### Result
- References freshness scoring now rejects generic freshness strings such as `source freshness: fresh` instead of accepting a freshness marker alone.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REFERENCES_FRESHNESS_SPECIFICITY_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_REFERENCES_FRESHNESS_SPECIFICITY_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Confidence Trigger Specificity)

### Scope
- Tightened `confidence_calibration` so raise/lower confidence conditions must name concrete decision-changing triggers.
- Added a regression where a calibration uses only generic `more evidence` and `less evidence` triggers.
- Updated the BioLinker research prompt to require concrete confidence-change triggers.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `107 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- Strict sample scoring passed `74/74` with `concrete_raise=1 concrete_lower=1`.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `137 passed`.

### Result
- Confidence calibration now rejects generic raise/lower triggers and requires concrete source, sponsor, eligibility, credential, conflict, claim, or failure conditions.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_CONFIDENCE_TRIGGER_SPECIFICITY_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_CONFIDENCE_TRIGGER_SPECIFICITY_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab References Standalone Source Type)

### Scope
- Tightened standalone References source-lead scoring so source-bearing lines need substantive source type/category metadata.
- Added regressions for missing source type and generic `source type: source`.
- Updated the no-bundle scorer fixture to include `source type: sponsor program pages and prior-award lists`.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `109 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- Strict sample scoring passed `74/74` with `typed_source_lines=2`.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `139 passed`.

### Result
- References source-lead scoring now rejects source lines without source type/category or with generic source-type labels, even when no evidence bundle is supplied.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REFERENCES_STANDALONE_SOURCE_TYPE_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_REFERENCES_STANDALONE_SOURCE_TYPE_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Source Type Generic Vocabulary)

### Scope
- Expanded generic source-type vocabulary so vague labels such as `materials` and `background material` are rejected.
- Added evidence-bundle and standalone References regressions for `source_type: materials` / `source type: materials`.
- Updated the BioLinker research prompt to reject generic materials/background-material source-type labels.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `111 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- Strict sample scoring passed `74/74` with `typed_source_lines=2` and `sources_with_type=2`.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `141 passed`.

### Result
- Evidence-source and standalone References source-type checks now reject vague source-type labels such as `materials`, not only `source` or `guidance`.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_SOURCE_TYPE_GENERIC_VOCABULARY_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_SOURCE_TYPE_GENERIC_VOCABULARY_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Assumptions Specificity)

### Scope
- Tightened `assumptions_boundaries` so each labeled field must include concrete source, workflow, owner, artifact, credential, timing, scoring, or validation context.
- Added a regression where Assumption, Boundary, Constraint, and Validation are nonblank but boilerplate.
- Updated the BioLinker research prompt to reject generic assumptions/boundaries/constraints prose.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `112 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- Strict sample scoring passed `74/74` with all four Assumptions & Boundaries labels complete.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `142 passed`.

### Result
- Assumptions & Boundaries scoring now rejects label-complete boilerplate instead of accepting generic section prose.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ASSUMPTIONS_SPECIFICITY_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_ASSUMPTIONS_SPECIFICITY_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Risks Open Questions Specificity)

### Scope
- Tightened `risks_open_questions` and `risks_open_questions_owner_verification` so items need concrete risk/question and verification context.
- Added a regression where Risk/Open Question items have all labels but only generic boilerplate.
- Updated the BioLinker research prompt to reject generic risk/question prose.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `113 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- Strict sample scoring passed `74/74` with `risks=2 open_questions=1` and `complete=3`.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `143 passed`.

### Result
- Risks & Open Questions scoring now rejects label-complete boilerplate instead of accepting generic risk/question prose.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_RISKS_OPEN_QUESTIONS_SPECIFICITY_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_RISKS_OPEN_QUESTIONS_SPECIFICITY_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Reviewer Red Flags Specificity)

### Scope
- Tightened `reviewer_red_flags_actionability` so red-flag fields need concrete source/evidence/eligibility/claim/blocker/credential/launch/compliance context.
- Added a regression where Reviewer Red Flags has all labels but only generic warning prose and bare `owner` escalation.
- Updated the BioLinker research prompt to reject generic red-flag prose.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q` -> `114 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q` -> `8 passed`.
- Strict sample scoring passed `74/74` with `reviewer_red_flags_actionability` complete.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `144 passed`.

### Result
- Reviewer Red Flags scoring now rejects label-complete boilerplate instead of accepting generic warning prose.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REVIEWER_RED_FLAGS_SPECIFICITY_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_REVIEWER_RED_FLAGS_SPECIFICITY_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Decision Field Specificity)

### Scope
- Tightened `decision_recommendation_fields` so labeled Recommendation and Rationale details must include concrete source, sponsor, workflow, owner, artifact, or decision context.
- Added a regression where the decision section has all labels and verifiable confidence/change-condition markers but only generic `best option`, `seems reasonable`, and `evidence is useful` prose.
- Updated the BioLinker research prompt and browser smoke fixture to preserve concrete decision-field context.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `115 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict sample scoring passed `74/74` with all required decision fields complete.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `145 passed`.

### Result
- Recommendation / Decision scoring now rejects label-complete boilerplate instead of accepting generic decision prose.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_DECISION_FIELD_SPECIFICITY_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_DECISION_FIELD_SPECIFICITY_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Key Finding Specificity)

### Scope
- Tightened `key_finding_fields` so each Claim, Evidence, Uncertainty, and Action meaning detail must include concrete source, sponsor, workflow, owner, artifact, eligibility, provider, scorer, or decision context.
- Added a regression where three Key Findings have the required labels/count but only generic `important finding`, `evidence is useful`, and `things could change` prose.
- Updated the BioLinker research prompt and browser smoke fixture to preserve concrete Key Finding context.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `116 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict sample scoring passed `74/74` with all three Key Findings complete.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `146 passed`.

### Result
- Key Findings scoring now rejects label-complete boilerplate instead of accepting generic finding prose.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_KEY_FINDING_SPECIFICITY_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_KEY_FINDING_SPECIFICITY_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Executive Summary Specificity)

### Scope
- Tightened `executive_summary_decision_snapshot` so the summary must include concrete source, workflow, owner, artifact, or decision context in addition to decision/evidence/uncertainty/next-action markers.
- Added a regression where the Executive Summary has valid short-summary shape but only generic `best option`, `evidence is useful`, `some uncertainty remains`, and `make an artifact` prose.
- Updated the BioLinker research prompt to reject generic Executive Summary marker stuffing.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `117 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict sample scoring passed `74/74` with the Executive Summary snapshot complete.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `147 passed`.

### Result
- Executive Summary scoring now rejects marker-complete boilerplate instead of accepting generic summary prose.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EXECUTIVE_SUMMARY_SPECIFICITY_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_EXECUTIVE_SUMMARY_SPECIFICITY_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Evidence Map Specificity)

### Scope
- Tightened `evidence_map` so Strong, Weak, and Missing category details must include concrete source, sponsor, credential, scoring, owner, deadline, blocker, or evidence context.
- Tightened `evidence_map_confidence_followup` so Follow-up verification details must be concrete, not just nonblank.
- Added a regression where the Evidence Map has all categories plus confidence/follow-up labels but only generic evidence prose.
- Updated the BioLinker research prompt to reject generic Evidence Map category and follow-up details.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `118 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict sample scoring passed `74/74` with Evidence Map category and follow-up details complete.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `148 passed`.

### Result
- Evidence Map scoring now rejects label-complete boilerplate instead of accepting generic category and follow-up prose.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_EVIDENCE_MAP_SPECIFICITY_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_EVIDENCE_MAP_SPECIFICITY_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Action Plan Handoff Specificity)

### Scope
- Tightened `action_plan_handoff_fields` so each Owner, Inputs, Artifact, and Decision gate detail must include concrete source, sponsor, workflow, owner, artifact, eligibility, provider, packet, proposal, scoring, or compliance context.
- Added a regression where days, success metrics, and dependencies remain concrete but handoff fields are generic (`team lead`, `available materials`, `planning document`, `seems ready`).
- Updated the BioLinker research prompt to reject generic Action Plan handoff details.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `119 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict sample scoring passed `74/74` with all Action Plan handoff fields complete.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `149 passed`.

### Result
- Action Plan handoff scoring now rejects generic field boilerplate instead of accepting marker-complete plans with weak owner/input/artifact/gate details.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_PLAN_HANDOFF_SPECIFICITY_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_ACTION_PLAN_HANDOFF_SPECIFICITY_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Artifact Handoff Specificity)

### Scope
- Tightened `artifact_ready_handoff_format` so Decision log, Stakeholder ask, Owner next step, and Evidence attachment details must include concrete decision, stakeholder, owner, source, evidence, packet, memo, review, or artifact context.
- Added a regression where the reusable handoff paragraph is valid but artifact-ready fields are generic (`next discussion`, `review later`, `when possible`, `useful links`).
- Updated the BioLinker research prompt to reject generic artifact-ready handoff details.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `120 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict sample scoring passed `74/74` with artifact-ready handoff fields complete.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `150 passed`.

### Result
- Artifact-ready handoff scoring now rejects generic field boilerplate instead of accepting nonblank but weak handoff labels.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ARTIFACT_HANDOFF_SPECIFICITY_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_ARTIFACT_HANDOFF_SPECIFICITY_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Quality Criteria Specificity)

### Scope
- Tightened `quality_criteria_actionable_acceptance` so Ready to use, Do not use, Evidence required, Verifier/owner, and Reuse destination details must include concrete recommendation, source, eligibility, blocker, evidence, verifier, memo, packet, proposal, or review context.
- Added a regression where all Quality Criteria labels are present but the details are generic (`useful enough`, `important things`, `useful links`, `reviewer or owner`).
- Updated the BioLinker research prompt to reject generic Quality Criteria details.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `121 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict sample scoring passed `74/74` with Quality Criteria labels complete.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `151 passed`.

### Result
- Quality Criteria scoring now rejects label-complete boilerplate instead of accepting generic acceptance/reject/evidence/verifier/reuse prose.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_QUALITY_CRITERIA_SPECIFICITY_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_QUALITY_CRITERIA_SPECIFICITY_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Action Plan Dependency Specificity)

### Scope
- Tightened `action_plan_dependency_order` so Dependencies/blocked by details must include concrete source, credential, eligibility, budget, blocker, packet, proposal, risk, or scoring context.
- Added a regression where action-plan handoff fields, metrics, and days remain concrete but dependency details are generic (`required materials`, `important things`, `unresolved issues`, `missing context`).
- Updated the BioLinker research prompt to reject generic dependency and blocked-by details.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `122 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict sample scoring passed `74/74` with all Action Plan dependencies complete.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `152 passed`.

### Result
- Action Plan dependency scoring now rejects generic blocker prose instead of accepting marker-complete dependency labels.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_PLAN_DEPENDENCY_SPECIFICITY_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_ACTION_PLAN_DEPENDENCY_SPECIFICITY_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (Pricing Subscription Tier Route Mock)

### Scope
- Fixed DeSci browser-smoke false negatives for `pricing-checkout-yearly` and `pricing-checkout-cancelled`.
- Added the free-tier `/subscription/tier` route mock to those two checks, matching the existing monthly checkout smoke.
- Added a regression that verifies both checks register and remove the tier route.

### Verification
- Baseline pricing/subscription browser smoke: `5/7` passed; yearly and cancelled flows failed on background `/subscription/tier` fetch console errors.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py -k "pricing_subscription_browser_smoke_mocks_tier_fetch_after_redirects or dev_auth_action_checks" -q -p no:cacheprovider` -> `2 passed`.
- `python -m py_compile apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5204 --expect-dev-auth --only-check pricing-enterprise-contact-intent --only-check pricing-checkout-mocked --only-check pricing-checkout-yearly --only-check pricing-checkout-cancelled --only-check pricing-checkout-error-visible --only-check pricing-billing-portal --only-check pricing-billing-portal-error-visible --json-out var\desci-pricing-subscription-browser-smoke-tier-mock-2026-06-07.json` -> `7/7 PASS`.
- `python -m pytest apps/desci-platform/backend/tests/test_browser_smoke.py -q -p no:cacheprovider` -> `22 passed`.
- `cmd /c npm run test -- src/__tests__/components/PricingPage.test.jsx` -> `12 passed`.

### Result
- Pricing/subscription browser evidence no longer reports false background tier-fetch failures after success or cancelled checkout redirects.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_PRICING_SUBSCRIPTION_TIER_ROUTE_MOCK_2026-06-07.md`.

## 2026-06-07 (AI Lab Decision Change Verification Action)

### Scope
- Tightened `decision_change_condition_verifiable` so change conditions must include an explicit verification or validation action in addition to source/evidence criteria, decision effect, timing, and concrete trigger context.
- Added a regression where a review-only condition (`cannot be reviewed before next week`) previously passed.
- Updated the BioLinker research prompt and browser-smoke AI Lab fixture to require verified source evidence scoring or copied source packet parsing.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `166 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict sample scoring passed `74/74` with decision change verification action complete.
- Focused AI Lab browser smoke passed `1/1`.
- Browser smoke tests passed `21 passed`.
- Combined AI Lab/prompt/browser regression passed `196 passed`.

### Result
- Decision-change scoring now rejects passive review-only triggers instead of accepting them as verifiable change conditions.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_DECISION_CHANGE_VERIFICATION_ACTION_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_DECISION_CHANGE_VERIFICATION_ACTION_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Risk Verification Action)

### Scope
- Tightened `risks_open_questions_owner_verification` so every risk/open-question `Verification:` field needs an active verification action as well as concrete source, sponsor, scorer, threshold, or evidence anchors.
- Added a regression where passive `review source freshness`, `review prior award abstracts`, and `review sponsor call notes` details previously passed.
- Updated the BioLinker research prompt to request active risk verification actions and reject passive review-only risk verification fields.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `167 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict sample scoring passed `74/74` with risk verification actions complete.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `197 passed`.

### Result
- Risks & Open Questions scoring now rejects passive review-only verification details instead of accepting concrete nouns without an active check.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_RISK_VERIFICATION_ACTION_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_RISK_VERIFICATION_ACTION_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Action Plan Score Threshold)

### Scope
- Tightened `action_plan_measurable_success_criteria` so score-based success metrics must include a pass condition, failed-check target, threshold, score cutoff, or similar acceptance criterion.
- Added a regression where score-only metrics (`source URLs ... get a score`, `review slot score`) previously passed while handoff and dependency checks remained green.
- Updated the BioLinker research prompt to reject score-only success metrics.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `168 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict sample scoring passed `74/74` with Action Plan score thresholds complete.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `198 passed`.

### Result
- Action Plan scoring now rejects score-only success metrics instead of accepting metrics that do not define readiness.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_PLAN_SCORE_THRESHOLD_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_ACTION_PLAN_SCORE_THRESHOLD_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Artifact Evidence Bundle)

### Scope
- Tightened `artifact_ready_handoff_format` so `Evidence attachment:` needs a source/evidence locator and at least two concrete reusable bundle contents.
- Added a regression where broad `source URLs, sponsor context, and quality report` evidence attachment text previously passed.
- Updated the BioLinker research prompt to require concrete reusable evidence bundle contents in artifact-ready handoffs.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `169 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict sample scoring passed `74/74` with artifact evidence bundle complete.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `199 passed`.

### Result
- Artifact-ready handoff scoring now rejects broad evidence attachments that omit reusable evidence bundle contents.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ARTIFACT_EVIDENCE_BUNDLE_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_ARTIFACT_EVIDENCE_BUNDLE_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Competitive Reuse Artifact)

### Scope
- Tightened `competitive_reuse_value` so each Competitive reuse value clause must name a concrete reusable artifact pattern, not only abstract source-backed value.
- Added a regression where a broad `review packet and pursuit priority context` reuse-value clause previously passed.
- Updated the BioLinker research prompt to request named artifacts such as pursuit memo checklist, review-packet checklist, scorer-ready packet, or source-backed decision gate.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py apps/desci-platform/scripts/browser_smoke.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `170 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict sample scoring passed `74/74` with Competitive reuse artifact complete.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `200 passed`.

### Result
- Competitive reuse scoring now rejects abstract reusable-value claims that do not name the reusable artifact pattern.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_COMPETITIVE_REUSE_ARTIFACT_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_COMPETITIVE_REUSE_ARTIFACT_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Reviewer Red Flag Review-Only Escalation)

### Scope
- Tightened `reviewer_red_flags_actionability` so escalation text must include a resolution, validation, verification, or recovery action, not only a review assignment.
- Added a regression where `assign the PI, compliance reviewer, or BD owner to review the blocker before proposal planning` previously passed.
- Updated the BioLinker research prompt to reject review-only reviewer-red-flag escalation.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `171 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict sample scoring passed `74/74` with reviewer red flag review-only escalation rejected.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `201 passed`.

### Result
- Reviewer red flag scoring now rejects review-only escalation handoffs that do not define how the blocker will be resolved or verified.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REVIEWER_RED_FLAG_REVIEW_ONLY_ESCALATION_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_REVIEWER_RED_FLAG_REVIEW_ONLY_ESCALATION_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Deep Dive Artifact Noun List)

### Scope
- Tightened `deep_dive_dimension_specificity` so dimensions cannot pass by saying source/evidence artifacts `are included for the proposal review artifact` without operating detail.
- Added a regression where technical, clinical, and regulatory dimensions previously passed using marker-heavy artifact noun lists.
- Updated the BioLinker research prompt to reject present-tense artifact noun-list deep-dive wording.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `172 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict sample scoring passed `74/74` with deep-dive artifact noun-list rejection complete.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `203 passed`.

### Result
- Deep Dive scoring now rejects marker-heavy artifact noun lists that omit concrete operating action or decision detail.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_DEEP_DIVE_ARTIFACT_NOUN_LIST_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_DEEP_DIVE_ARTIFACT_NOUN_LIST_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Reference Future Freshness)

### Scope
- Tightened `references_source_freshness` and `references_each_source_freshness` so date-less future verification wording does not count as current freshness metadata.
- Added a regression where `source freshness: verify before pursuit` previously passed without a checked/retrieved/accessed date.
- Updated the BioLinker research prompt to reject date-less future freshness language in reference source lines.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `173 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict sample scoring passed `74/74` with reference future freshness rejection complete.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `204 passed`.

### Result
- References scoring now rejects source lines that only promise future freshness verification without recording current freshness evidence.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_REFERENCE_FUTURE_FRESHNESS_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_REFERENCE_FUTURE_FRESHNESS_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Decision Change Future Task)

### Scope
- Tightened `decision_change_condition_verifiable` so future-task wording does not count as a verifiable decision-change trigger.
- Added a regression where `hold if source freshness or eligibility must verify before pursuit` previously passed.
- Updated the BioLinker research prompt to reject future-task change-condition wording.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `174 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict sample scoring passed `74/74` with decision-change future-task rejection complete.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `205 passed`.

### Result
- Decision-change scoring now rejects future verification tasks that do not define a concrete failure condition or decision trigger.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_DECISION_CHANGE_FUTURE_TASK_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_DECISION_CHANGE_FUTURE_TASK_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Action Plan Unnamed Score Threshold)

### Scope
- Tightened `action_plan_measurable_success_criteria` so score-based success metrics must name an actual pass condition, failed-check target, strict-failure target, score cutoff, or numeric score expression.
- Added a regression where `review score threshold satisfied` previously passed without naming the threshold.
- Updated the BioLinker research prompt to reject unnamed score-threshold success metrics.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `175 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict sample scoring passed `74/74` with unnamed score-threshold rejection complete.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `206 passed`.

### Result
- Action Plan scoring now rejects score-threshold language that does not define the actual measurable threshold.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ACTION_PLAN_UNNAMED_SCORE_THRESHOLD_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_ACTION_PLAN_UNNAMED_SCORE_THRESHOLD_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Artifact Owner Destination)

### Scope
- Tightened `artifact_ready_handoff_format` so artifact-ready `Owner next step:` fields must include a concrete paste/reuse destination.
- Added a regression where `BD lead attaches source-check checklist and review packet before proposal drafting` previously passed without saying where the handoff should be used.
- Updated the BioLinker research prompt to require owner-step destinations such as meeting note, pursuit memo, review packet, review slot, release meeting, or proposal-planning handoff.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `176 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict sample scoring passed `74/74` with artifact owner destination complete.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `207 passed`.

### Result
- Artifact-ready handoff scoring now rejects owner steps that name artifacts but omit the concrete destination for reuse.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_ARTIFACT_OWNER_DESTINATION_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_ARTIFACT_OWNER_DESTINATION_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-07 (AI Lab Source Review Dependency)

### Scope
- Tightened `action_plan_dependency_order` so dependency lines reject generic `available before work`, `before source review`, and `starts after source URL review` sequencing even when approved source/proposal nouns are present.
- Added a regression where source URLs, prior-award abstracts, proposal drafting, source freshness, eligibility, and budget terms previously could satisfy a non-actionable dependency sequence.
- Updated the BioLinker research prompt to reject the same generic source-review dependency wording.

### Verification
- `python -m py_compile apps/desci-platform/scripts/ai_lab_output_quality.py` -> pass.
- `python -m pytest apps/desci-platform/backend/tests/test_ai_lab_output_quality.py -q -p no:cacheprovider` -> `177 passed`.
- `python -m pytest packages/shared/tests/test_prompt_notifier_metrics.py -q -p no:cacheprovider` -> `8 passed`.
- Strict sample scoring passed `74/74` with source-review dependency rejection complete.
- Focused AI Lab browser smoke passed `1/1`.
- Combined AI Lab/prompt/browser regression passed `208 passed`.

### Result
- Action Plan scoring now rejects source-review dependency marker stuffing that does not name an actionable memo, scoring, gate, or drafting handoff sequence.
- Evidence report: `docs/reports/2026-06/AUTO_RESEARCH_DESCI_AI_LAB_SOURCE_REVIEW_DEPENDENCY_2026-06-07.md`.
- Strict quality report: `docs/reports/2026-06/DESCI_AI_LAB_SOURCE_REVIEW_DEPENDENCY_QUALITY_SAMPLE_2026-06-07.md`.

## 2026-06-08 (Notices Test Isolation and Workspace Smoke Closure)

### Scope
- Isolated `src/__tests__/components/Notices.test.jsx` in the frontend Vitest split runner after the all-scope workspace smoke exposed a no-isolate bundle failure in the Notices source-link test.
- Preserved the existing source-link safety contract: safe HTTP(S) notice and discovery URLs render as external links, while missing or unsafe URLs render the unavailable state.

### Verification
- `npm.cmd run test:lts -- --fileParallelism false` from `apps/desci-platform/frontend` -> no-isolate `28/28` files and `141/141` tests passed; isolated `7/7` files and `26/26` tests passed.
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-autoresearch-2026-06-08-loop34.json` -> `8/8` passed.
- `python ops/scripts/run_workspace_smoke.py --scope all --json-out var/workspace-smoke-all-autoresearch-2026-06-08-loop34.json` -> completed all `41` checks with `40` passed and only the known getdaytrends live DB readiness blocker failing.

### Result
- The local DeSci frontend/unit-test smoke failure is cleared.
- The remaining all-scope workspace failure is external to DeSci: getdaytrends live DB doctor still fails with `InternalServerError: (ENOTFOUND) tenant/user *** not found`, pending a corrected Supabase Transaction pooler credential.

## 2026-06-09 (Redis Health Timeout and Gate Stability)

### Scope
- Investigated a canonical release-gate timeout where the parent report was not written before backend health tests stalled.
- Confirmed `main.health()` was blocking inside `redis-py` `ping()` against local Redis without explicit client timeouts.
- Added fast local Redis socket/connect timeouts, production defaults, failed-connect cooldown, and Redis/RabbitMQ test stubs so health/readiness tests do not hit real localhost services.
- Hardened the frontend Vitest split runner to re-exec under `node@24.15.0` when the current Node runtime is older and cannot start Vitest thread workers reliably.

### Verification
- `python -m py_compile backend/services/redis_store.py backend/tests/test_redis_store.py backend/tests/conftest.py` -> pass.
- `uv run pytest tests/test_redis_store.py tests/test_api_endpoints.py tests/test_smoke_pipeline.py tests/test_jobs.py -q --maxfail=1` -> `63 passed`.
- `uv run pytest -q` from `backend` -> `521 passed, 1 deselected`.
- `npm.cmd run lint` from `frontend` -> pass with one existing React hooks warning in `BioLinker.jsx`.
- `npm.cmd run typecheck` from `frontend` -> pass.
- `npm.cmd run test` from `frontend` -> no-isolate `28/28` files and isolated `7/7` files passed.
- `npm.cmd run build` from `frontend` -> pass.
- `npm.cmd run test` from `contracts` -> config `10/10` and contract `77 passing`.
- `python scripts/release_gate.py --continue-on-failure --json-out ../../var/desci-release-gate-loop1-after.json` -> `13/13` steps passed; JSON report `schema_version=1`, `ok=true`.

### Result
- `/health` and `/ready` no longer block on an unavailable local Redis socket, preserving Redis as a fallback dependency instead of a release-gate hang source.
- The user-facing frontend test command now survives the local Node 24.13 worker-startup issue by using the already validated Node 24.15 runner path.

## 2026-06-09 (BioLinker Lint and Targeted Vitest Stability)

### Scope
- Removed the remaining React hooks lint warning in `BioLinker.jsx` by eliminating an unnecessary effect-time error clear when no `paper_id` is present.
- Kept error reset on the real paper-match fetch path, where a new `paper_id` starts a new matching job.
- Stabilized `scripts/run-vitest-split.mjs` targeted-file runs by using `forks + isolate` for arbitrary test args while preserving the split runner for the canonical suite.

### Verification
- `npm.cmd run lint` from `frontend` -> pass.
- `npm.cmd run test -- src/__tests__/components/BioLinker.test.jsx` -> `1/1` files and `6/6` tests passed.
- `npm.cmd run test` from `frontend` -> no-isolate `28/28` files and isolated `7/7` files passed.
- `npm.cmd run typecheck` from `frontend` -> pass.
- `npm.cmd run build` from `frontend` -> pass.
- `python scripts/release_gate.py --continue-on-failure --json-out ../../var/desci-release-gate-loop2-after.json` -> `13/13` steps passed; JSON report `schema_version=1`, `ok=true`.

### Result
- Frontend lint is now clean.
- Targeted component-test invocation no longer falls back into the Vitest thread-worker startup timeout.
- Release-gate evidence remains green after the frontend polish change.

## 2026-06-09 (Release-Gate Failed Evidence Validation)

### Scope
- Hardened `scripts/release_gate.py` so child JSON evidence that reports `ok: false` still goes through schema, timestamp, target/source, summary, and check-shape validation.
- Preserved the existing parent failure behavior: non-OK child evidence still fails the gate, but malformed failed evidence can no longer hide behind the non-OK status alone.
- Updated `README.md`, `DEPLOYMENT_GUIDE.md`, and `OPERATIONS_RUNBOOK.md` to document that failed smoke/preflight evidence is still schema-validated.

### Verification
- `python -m py_compile scripts/release_gate.py backend/tests/test_release_gate.py` -> pass.
- `uv run pytest tests/test_release_gate.py -q --maxfail=1` from `backend` -> `57 passed`.
- `uv run pytest tests/test_release_gate.py tests/test_env_doctor.py tests/test_deploy_readiness.py tests/test_product_smoke.py -q --maxfail=1` from `backend` -> `110 passed`.
- `uv run pytest tests/test_deployment_docs.py tests/test_release_gate.py -q --maxfail=1` from `backend` -> `63 passed`.
- `python scripts/env_doctor.py --profile production --ignore-process-env --json-out ../../var/desci-env-doctor-loop3-baseline.json` -> expected blocked preflight: `11` failed, `2` warnings, JSON evidence written.
- `python scripts/deploy_readiness.py --ignore-process-env --json-out ../../var/desci-deploy-readiness-loop3-baseline.json` -> expected blocked preflight: `14` failed, `1` warning, JSON evidence written.
- `python scripts/release_gate.py --continue-on-failure --json-out ../../var/desci-release-gate-loop3-after.json` -> `13/13` steps passed; JSON report `schema_version=1`, `ok=true`.

### Result
- Failed child artifacts now remain audit-validatable instead of stopping validation at the first `ok=false` marker.
- The canonical release gate remains green after the stricter artifact-validation behavior.
- Production launch is still blocked by missing external environment and deployment secrets; no security checks were relaxed.

## 2026-06-09 (Production Dev Flag Preflight Blockers)

### Scope
- Added a production env-doctor check that fails when `ALLOW_TEST_BYPASS`, `ALLOW_DEV_AUTH_FALLBACK`, or `MOCK_MODE` are enabled under `ENV=production`.
- Added a Railway deploy-readiness check for the same local bypass/mock flags before external deployment.
- Updated `README.md`, `DEPLOYMENT_GUIDE.md`, and `OPERATIONS_RUNBOOK.md` so production preflight behavior says these flags fail the gate instead of being merely ignored.

### Verification
- `python -m py_compile scripts/env_doctor.py scripts/deploy_readiness.py backend/tests/test_env_doctor.py backend/tests/test_deploy_readiness.py` -> pass.
- `uv run pytest tests/test_env_doctor.py tests/test_deploy_readiness.py -q --maxfail=1` from `backend` -> `46 passed`.
- `uv run pytest tests/test_env_doctor.py tests/test_deploy_readiness.py tests/test_release_gate.py tests/test_deployment_docs.py -q --maxfail=1` from `backend` initially failed because the docs contract still expected explicit `MOCK_MODE=true` and `Web3 readiness` wording.
- After restoring those exact operator-facing terms, the same test command passed with `109 passed`.
- A direct synthetic preflight probe confirmed `production_safety_flags:fail` and `railway_production_safety_flags:fail` when the bypass/mock flags are truthy.
- `python scripts/env_doctor.py --profile production --ignore-process-env --json-out ../../var/desci-env-doctor-loop4-baseline.json` -> expected blocked preflight: `11` failed, `2` warnings, JSON evidence written.
- `python scripts/deploy_readiness.py --ignore-process-env --json-out ../../var/desci-deploy-readiness-loop4-baseline.json` -> expected blocked preflight: `14` failed, `1` warning, JSON evidence written.
- `python scripts/release_gate.py --continue-on-failure --json-out ../../var/desci-release-gate-loop4-after.json` -> `13/13` steps passed; backend `523 passed`, frontend lint/typecheck/tests/build/bundle passed, contracts `77 passing`, JSON report `schema_version=1`, `ok=true`.

### Result
- Production preflight now treats local auth bypass and mock Web3 mode as explicit blockers.
- The change does not reduce local demo flexibility; local profile still treats missing production services as warnings.
- Release-gate artifact validation and documentation contracts remain green after the stricter production preflight behavior.

## 2026-06-09 (Launch Control Smoke Contract)

### Scope
- Hardened `scripts/product_smoke.py` so runtime smoke validates the full `/launch` operator handoff contract, not just HTTP 200 plus decision labels.
- Added checks for product identity, `readiness_status`, score fields, summary counters, `launch_blockers`, `next_actions`, and decision/phase/score consistency.
- Updated `API_SPEC.md` to document the `/launch` required response fields and the smoke contract that catches drift.

### Verification
- `python -m py_compile scripts/product_smoke.py backend/tests/test_product_smoke.py` -> pass.
- `uv run pytest tests/test_product_smoke.py -q --maxfail=1` from `backend` -> `11 passed`.
- `uv run pytest tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `6 passed`.
- `uv run pytest tests/test_product_smoke.py tests/test_release_gate.py tests/test_deployment_docs.py tests/test_api_endpoints.py -q --maxfail=1` from `backend` -> `115 passed`.
- `python scripts/release_gate.py --continue-on-failure --json-out ../../var/desci-release-gate-loop5-after.json` -> `13/13` steps passed; backend `525 passed`, frontend lint/typecheck/tests/build/bundle passed after one Vitest retry, contracts `77 passing`, JSON report `schema_version=1`, `ok=true`.

### Result
- Runtime smoke now catches stale or internally inconsistent `/launch` responses before attaching product-smoke evidence to release-gate handoff reports.
- The stricter smoke contract stays aligned with current `/ready` and `/launch` endpoint tests.
- Production launch remains blocked by missing external environment and deployment secrets; no readiness or security checks were relaxed.

## 2026-06-09 (Ready Launch Smoke Drift Check)

### Scope
- Hardened `scripts/product_smoke.py` so a single runtime smoke run cross-checks `/ready` and `/launch`.
- Added drift detection for `/launch.readiness_status`, summary counts, and `launch_blockers` against the `/ready` response.
- Updated `API_SPEC.md` to document that `/launch` handoff fields must match `/ready` within one smoke run.

### Verification
- `python -m py_compile scripts/product_smoke.py backend/tests/test_product_smoke.py` -> pass.
- `uv run pytest tests/test_product_smoke.py -q --maxfail=1` from `backend` -> `13 passed`.
- `uv run pytest tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `6 passed`.
- `uv run pytest tests/test_product_smoke.py tests/test_release_gate.py tests/test_deployment_docs.py tests/test_api_endpoints.py -q --maxfail=1` from `backend` -> `117 passed`.
- `python scripts/release_gate.py --continue-on-failure --json-out ../../var/desci-release-gate-loop6-after.json` -> `13/13` steps passed; backend `527 passed`, frontend lint/typecheck/tests/build/bundle passed, contracts `77 passing`, JSON report `schema_version=1`, `ok=true`.

### Result
- Product smoke evidence now fails when `/launch` drifts from `/ready`, instead of treating individually valid but contradictory endpoint responses as a clean handoff.
- The cross-check failure is attached to the `launch` check report, so existing release-gate artifact validation and failed-check aggregation continue to work.
- Production launch remains blocked by missing external environment and deployment secrets; no readiness or security checks were relaxed.

## 2026-06-09 (Dashboard Launch Control Handoff)

### Scope
- Updated `ProductReadinessPanel` so the dashboard reads both `/ready` and `/launch` through TanStack Query-backed server state.
- Kept `/ready` as the source for service progress and check cards, while using `/launch` as the operator-facing source for release decision, operator phase, required readiness score, and launch next actions.
- Added visible drift warnings when `/launch` status, summary counts, or blockers do not match `/ready`, matching the product-smoke handoff contract.
- Updated the Dashboard/ProductReadinessPanel frontend tests and operations runbook to reflect the provider boundary and UI handoff contract.

### Verification
- `node scripts\run-vitest-split.mjs src/__tests__/components/ProductReadinessPanel.test.jsx` from `frontend` -> `1` file and `7` tests passed.
- `node scripts\run-vitest-split.mjs src/__tests__/components/Dashboard.test.jsx` from `frontend` -> `1` file and `11` tests passed.
- `npm run lint` from `frontend` -> pass.
- `npm run typecheck` from `frontend` -> pass.
- `npm run test` from `frontend` -> no-isolate `28/28` files and isolated `7/7` files passed; `169` tests passed.
- `npm run build` from `frontend` -> pass.
- `npm run check:bundle` from `frontend` -> pass; max chunk and entry budgets OK.
- `uv run pytest tests/test_product_smoke.py tests/test_api_endpoints.py -q --maxfail=1` from `backend` -> `54 passed`.
- `python scripts/release_gate.py --continue-on-failure --json-out ../../var/desci-release-gate-loop7-after.json` -> `13/13` steps passed; backend `527 passed`, frontend lint/typecheck/tests/build/bundle passed, contracts `77 passing`, JSON report `schema_version=1`, `ok=true`.

### Result
- The operator dashboard now surfaces the same `/launch` handoff decision that runtime smoke validates, instead of showing readiness progress without launch-control context.
- Launch action copy payloads now come from `/launch.next_actions` when available, reducing UI drift from backend operator handoff evidence.
- Production launch remains blocked by missing external environment and deployment secrets; no readiness or security checks were relaxed.

## 2026-06-10 (Dashboard Launch Control Browser Smoke)

### Scope
- Hardened `scripts/browser_smoke.py` so the dashboard readiness browser smoke now mocks both `/ready` and `/launch`.
- Added assertions for the visible launch-control panel, `no-go` release decision, `blocked` operator phase, required score, action queue, absence of drift warning for consistent fixtures, and refresh re-querying both endpoints.
- Reused the same launch handoff fixture in the clipboard-denial browser smoke so dashboard failure-path coverage stays aligned with the `/launch` UI contract.
- Tightened route smoke rendering waits so lazy-loaded Vite routes do not read the page body before expected route text has had a full Playwright polling window to appear.
- Updated `OPERATIONS_RUNBOOK.md` to document that browser smoke covers the dashboard `/ready` + `/launch` launch-control UI contract.

### Verification
- `python -m py_compile scripts\browser_smoke.py backend\tests\test_browser_smoke.py` -> pass.
- `uv run pytest tests/test_browser_smoke.py -q --maxfail=1` from `backend` -> `26 passed`.
- First runtime release-gate attempt with system Python reached product smoke but browser launch failed because that Python's Playwright 1.58.0 expected missing Chromium `chromium_headless_shell-1208`.
- `python scripts/release_gate.py --python-command "uv run python" --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-browser-expect-dev-auth --runtime-api http://127.0.0.1:55615 --runtime-frontend http://127.0.0.1:55616 --runtime-evidence-dir var --json-out var/desci-release-gate-loop8-runtime-20260610-003228.json` -> `2/2` steps passed.
- Runtime product smoke artifact passed `5/5` checks; browser smoke artifact passed `56/56` checks and validated JSON `schema_version=1`, `ok=true`.

### Result
- Runtime browser evidence now fails if the dashboard launch-control UI drifts from the `/launch` operator handoff or stops refreshing `/launch` with `/ready`.
- The full local runtime smoke path passes when release gate uses the project `uv` Python/Playwright runtime.
- Production launch remains blocked by missing external environment and deployment secrets; no readiness or security checks were relaxed.

## 2026-06-10 (Release Gate Auto Python Runtime)

### Scope
- Changed `scripts/release_gate.py` so `--python-command` defaults to `auto`.
- `auto` selects `uv run python` when a uv project environment is available, then falls back to `sys.executable`; `--python-command system` is the explicit opt-out.
- Updated README, deployment guide, and operations runbook so operators know the default child-runtime behavior.

### Verification
- `python -m py_compile scripts\release_gate.py backend\tests\test_release_gate.py` -> pass.
- `uv run pytest tests/test_release_gate.py -q --maxfail=1` from `backend` -> `61 passed`.
- `uv run pytest tests/test_deployment_docs.py tests/test_release_gate.py -q --maxfail=1` from `backend` -> `67 passed`.
- `python scripts\release_gate.py --dry-run --skip-env --skip-compose --skip-frontend --skip-contracts --backend-tests tests/test_release_gate.py --json-out var/desci-release-gate-loop9-default-python-dry-run.json` -> child command `uv run python -m pytest tests/test_release_gate.py -q`.
- `python scripts\release_gate.py --dry-run --runtime-smoke --runtime-browser-expect-dev-auth --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-evidence-dir var --json-out var/desci-release-gate-loop9-runtime-default-python-dry-run.json` -> child commands `uv run python scripts/product_smoke.py ...` and `uv run python scripts/browser_smoke.py ...`.
- `python scripts\release_gate.py --skip-env --skip-compose --skip-frontend --skip-contracts --backend-tests tests/test_release_gate.py --json-out var/desci-release-gate-loop9-targeted-backend.json` -> `1/1` passed with child command `uv run python -m pytest tests/test_release_gate.py -q`.

### Result
- Running release gate with plain `python scripts/release_gate.py` no longer defaults child checks to the system Python when the repo uv environment is available.
- The Loop 8 system-Playwright false failure class is prevented by default while retaining an explicit system interpreter escape hatch.
- Production launch remains blocked by missing external environment and deployment secrets; no readiness or security checks were relaxed.

## 2026-06-10 (Release Gate Python Runtime Provenance)

### Scope
- Added top-level `python_command` provenance to release-gate parent `--json-out` reports.
- The field records the requested runner, resolution strategy, resolved command list, and display string.
- Updated README, deployment guide, operations runbook, and deployment-doc tests so the new handoff metadata remains documented.

### Verification
- `python -m py_compile scripts\release_gate.py backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py` -> pass.
- `uv run pytest tests/test_release_gate.py tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `68 passed`.
- `python scripts\release_gate.py --dry-run --skip-env --skip-compose --skip-frontend --skip-contracts --backend-tests tests/test_release_gate.py --json-out var/desci-release-gate-loop10-python-provenance-dry-run.json` -> parent JSON includes `python_command.requested=auto`, `strategy=auto_uv_project`, and `resolved=["uv","run","python"]`.
- `python scripts\release_gate.py --skip-env --skip-compose --skip-frontend --skip-contracts --backend-tests tests/test_release_gate.py --json-out var/desci-release-gate-loop10-targeted-backend.json` -> `1/1` passed, backend `62 passed`, and parent JSON includes the same `python_command` provenance.

### Result
- Operators can now verify the child Python runtime from the parent release-gate JSON without parsing console logs or step command strings.
- The Loop 9 default `auto` behavior is now auditable in handoff artifacts.
- Production launch remains blocked by missing external environment and deployment secrets; no readiness or security checks were relaxed.

## 2026-06-10 (Release Gate Structured Step Command Evidence)

### Scope
- Added optional per-result `command_argv` arrays to release-gate parent JSON reports.
- Kept the existing shell-quoted `command` string for backwards compatibility while giving dashboards and operator tooling a structured command surface.
- Updated README, deployment guide, operations runbook, and deployment-doc tests to document the structured command evidence.

### Verification
- `python -m py_compile scripts\release_gate.py backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py` -> pass.
- `uv run pytest tests/test_release_gate.py tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `68 passed`.
- `python scripts\release_gate.py --dry-run --skip-env --skip-compose --skip-frontend --skip-contracts --backend-tests tests/test_release_gate.py --json-out var/desci-release-gate-loop11-command-argv-dry-run.json` -> parent JSON includes `python_command.strategy=auto_uv_project` and result `command_argv=["uv","run","python","-m","pytest","tests/test_release_gate.py","-q"]`.
- `python scripts\release_gate.py --skip-env --skip-compose --skip-frontend --skip-contracts --backend-tests tests/test_release_gate.py --json-out var/desci-release-gate-loop11-targeted-backend.json` -> `1/1` passed, backend `62 passed`, and parent JSON includes the same structured `command_argv`.

### Result
- Release-gate handoff artifacts no longer require shell-string parsing to confirm which command actually ran for a step.
- The structured argv field makes runtime mismatch detection easier for future dashboards or operator summary tooling.
- Production launch remains blocked by missing external environment and deployment secrets; no readiness or security checks were relaxed.

## 2026-06-10 (Product Smoke Launch Handoff Summary)

### Scope
- Added top-level `launch_handoff` to `scripts/product_smoke.py` JSON reports.
- The handoff captures the current release decision, operator phase, readiness status, score, summary, blockers, next actions, and launch-check failures.
- Extended `scripts/release_gate.py` child artifact parsing so parent `artifact_reports` expose `json_launch_*` fields from product-smoke evidence.
- Updated API spec, README, deployment guide, operations runbook, and deployment-doc tests to document the new handoff summary.

### Verification
- `python -m py_compile scripts\product_smoke.py scripts\release_gate.py backend\tests\test_product_smoke.py backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py` -> pass.
- `uv run pytest tests/test_product_smoke.py tests/test_release_gate.py tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `81 passed`.
- `python scripts\release_gate.py --skip-env --skip-compose --skip-frontend --skip-contracts --backend-tests tests/test_product_smoke.py tests/test_release_gate.py tests/test_deployment_docs.py --json-out var/desci-release-gate-loop12-targeted-backend.json` -> `1/1` passed, backend `81 passed`.
- Synthetic product-smoke parent parser evidence wrote `var/desci-product-smoke-loop12-launch-handoff.json` and `var/desci-release-gate-loop12-launch-handoff-parser.json`; parent artifact report exposed `json_launch_release_decision=go-with-watch`, `json_launch_operator_phase=operator-review`, `json_launch_readiness_status=degraded`, `json_launch_action_count=1`, and `json_launch_score_overall_percent=92`.

### Result
- Product-smoke handoff artifacts now carry a stable top-level launch summary instead of requiring dashboards to scrape the `checks` array.
- Release-gate parent JSON now surfaces the launch handoff summary from child evidence for operator triage.
- Production launch remains blocked by missing external environment and deployment secrets; no readiness or security checks were relaxed.

## 2026-06-10 (Release Gate Top-Level Launch Handoff Summary)

### Scope
- Promoted product-smoke child `launch_handoff` fields into top-level release-gate `launch_handoff_summary`.
- The parent summary includes artifact path, release decision, operator phase, readiness status, blocker/action counts, readiness summary, and score.
- Kept detailed `json_launch_*` fields in child `artifact_reports` as the source-of-truth detail surface.
- Updated README, deployment guide, operations runbook, and deployment-doc tests to document the parent summary.

### Verification
- `python -m py_compile scripts\release_gate.py backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py` -> pass.
- `uv run pytest tests/test_release_gate.py tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `68 passed`.
- `python scripts\release_gate.py --skip-env --skip-compose --skip-frontend --skip-contracts --backend-tests tests/test_release_gate.py tests/test_deployment_docs.py --json-out var/desci-release-gate-loop13-targeted-backend.json` -> `1/1` passed, backend `68 passed`.
- Synthetic product-smoke parent parser evidence wrote `var/desci-product-smoke-loop13-launch-handoff.json` and `var/desci-release-gate-loop13-launch-handoff-summary.json`; parent JSON includes `launch_handoff_summary.release_decision=go-with-watch`, `operator_phase=operator-review`, `readiness_status=degraded`, `next_action_count=1`, and score `overall_percent=92`.

### Result
- Release-gate parent reports now expose the operator launch decision without requiring consumers to scan child `artifact_reports`.
- Dashboards and handoff packages can still drill down to the child artifact path recorded in the summary.
- Production launch remains blocked by missing external environment and deployment secrets; no readiness or security checks were relaxed.

## 2026-06-10 (Release Gate Launch Handoff Validation)

### Scope
- Added product-smoke child `launch_handoff` shape and decision-consistency validation to `scripts/release_gate.py`.
- Changed parent `launch_handoff_summary` promotion to use only artifact reports with `validation_ok: true`.
- Updated API spec, README, deployment guide, operations runbook, and deployment-doc tests to document the validation-before-promotion contract.

### Verification
- `python -m py_compile scripts\release_gate.py backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py` -> pass.
- `uv run pytest tests/test_release_gate.py tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> first run failed on a newline-sensitive documentation assertion, then passed after fixing the assertion (`70 passed`).
- `python scripts\release_gate.py --skip-env --skip-compose --skip-frontend --skip-contracts --backend-tests tests/test_release_gate.py tests/test_deployment_docs.py --json-out var/desci-release-gate-loop14-targeted-backend.json` -> `1/1` passed, backend `70 passed`.

### Result
- Malformed product-smoke launch handoff evidence now fails the release gate instead of producing a partial or misleading parent launch summary.
- Invalid child handoff evidence remains visible through `artifact_reports.validation_failures` for operator triage.
- Production launch remains blocked by missing external environment and deployment secrets; no readiness or security checks were relaxed.

## 2026-06-10 (Release Gate Required Launch Handoff Evidence)

### Scope
- Made `launch_handoff` a required object for product-smoke JSON evidence validated by `scripts/release_gate.py`.
- Added a regression test for missing `launch_handoff` evidence and kept the malformed-handoff validation path from the prior loop.
- Updated API spec, README, deployment guide, operations runbook, and deployment-doc tests to document that missing or invalid handoff evidence is not promoted.

### Verification
- `python -m py_compile scripts\release_gate.py backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py` -> pass.
- `uv run pytest tests/test_release_gate.py tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `71 passed`.
- `python scripts\release_gate.py --skip-env --skip-compose --skip-frontend --skip-contracts --backend-tests tests/test_release_gate.py tests/test_deployment_docs.py --json-out var/desci-release-gate-loop15-targeted-backend.json` -> `1/1` passed, backend `71 passed`.

### Result
- Product-smoke runtime evidence must now carry an explicit `/launch` handoff before release-gate parent reports can treat it as launch-decision evidence.
- Missing handoff evidence fails artifact validation and remains visible in `artifact_reports.validation_failures`.
- Production launch remains blocked by missing external environment and deployment secrets; no readiness or security checks were relaxed.

## 2026-06-10 (Browser Launch-Control Evidence Summary)

### Scope
- Added structured `launch_control` evidence to `scripts/browser_smoke.py` JSON reports when the dashboard readiness refresh check runs.
- Extended `scripts/release_gate.py` so browser-smoke child artifacts expose `json_browser_launch_*` fields and validated evidence is promoted into top-level `browser_launch_control_summary`.
- Updated API spec, README, deployment guide, operations runbook, and deployment-doc tests to document the browser launch-control handoff surface.

### Verification
- `python -m py_compile scripts\browser_smoke.py scripts\release_gate.py backend\tests\test_browser_smoke.py backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py` -> pass.
- `uv run pytest tests/test_browser_smoke.py tests/test_release_gate.py tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `99 passed`.
- `python scripts\release_gate.py --skip-env --skip-compose --skip-frontend --skip-contracts --backend-tests tests/test_browser_smoke.py tests/test_release_gate.py tests/test_deployment_docs.py --json-out var/desci-release-gate-loop16-targeted-backend.json` -> `1/1` passed, backend `99 passed`.
- Synthetic browser-smoke parent parser evidence wrote `var/desci-browser-smoke-loop16-launch-control.json` and `var/desci-release-gate-loop16-browser-launch-control-summary.json`; parent JSON includes `browser_launch_control_summary.release_decision=no-go`, `operator_phase=blocked`, `readiness_status=blocked`, `next_action_count=5`, and score `required_percent=25`.

### Result
- Release-gate parent reports can now show both API `/launch` handoff evidence and frontend-rendered dashboard launch-control evidence.
- Browser launch-control evidence remains tied to the child artifact path for operator drill-down.
- Production launch remains blocked by missing external environment and deployment secrets; no readiness or security checks were relaxed.

## 2026-06-10 (Browser Launch-Control Provenance)

### Scope
- Added provenance fields to browser-smoke `launch_control` evidence: `evidence_source`, `api_mocked`, and `mocked_endpoints`.
- Extended release-gate browser launch-control validation and parent `browser_launch_control_summary` promotion to preserve those provenance fields.
- Updated API spec, README, deployment guide, operations runbook, and deployment-doc tests so fixture-backed dashboard proof is not confused with live API launch evidence.

### Verification
- `python -m py_compile scripts\browser_smoke.py scripts\release_gate.py backend\tests\test_browser_smoke.py backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py` -> pass.
- `uv run pytest tests/test_browser_smoke.py tests/test_release_gate.py tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `99 passed`.
- `python scripts\release_gate.py --skip-env --skip-compose --skip-frontend --skip-contracts --backend-tests tests/test_browser_smoke.py tests/test_release_gate.py tests/test_deployment_docs.py --json-out var/desci-release-gate-loop17-targeted-backend.json` -> `1/1` passed, backend `99 passed`.
- Synthetic browser-smoke parent parser evidence wrote `var/desci-browser-smoke-loop17-launch-control-provenance.json` and `var/desci-release-gate-loop17-browser-launch-control-provenance.json`; parent JSON includes `browser_launch_control_summary.evidence_source=browser-smoke-dashboard-fixture`, `api_mocked=true`, and `mocked_endpoints=["/ready","/launch"]`.

### Result
- Release-gate parent reports now distinguish live API product-smoke launch handoff evidence from fixture-backed frontend dashboard launch-control proof.
- Operator dashboards can safely use the browser summary for UI readiness triage without mistaking it for the live API launch decision.
- Production launch remains blocked by missing external environment and deployment secrets; no readiness or security checks were relaxed.

## 2026-06-10 (Browser Dashboard Readiness Dev Server Proof)

### Scope
- Reproduced `dashboard-readiness-refresh` against a real Vite dev server on `http://127.0.0.1:5187` with `VITE_ENABLE_DEV_AUTH_BYPASS=true`.
- Initial real-server run failed because the dashboard shell also requested `/vcs`, `/notices`, `/me`, `/papers/me`, and `/health` while the backend was intentionally not running.
- Hardened `scripts/browser_smoke.py` so the launch-control fixture still validates `/ready` and `/launch`, while surrounding dashboard GETs are mocked explicitly through Playwright routing.
- Expanded browser `launch_control.mocked_endpoints` provenance to list `/ready`, `/launch`, `/me`, `/papers/me`, `/health`, `/vcs`, and `/notices`.
- Updated API spec, README, deployment guide, operations runbook, and regression tests to document the wider fixture boundary.

### Verification
- First real-server probe: `uv run python scripts/browser_smoke.py --frontend http://127.0.0.1:5187 --expect-dev-auth --only-check dashboard-readiness-refresh --json-out var/desci-browser-smoke-loop18-dashboard-readiness-refresh.json` -> failed on `ERR_CONNECTION_REFUSED` for dashboard shell GETs.
- `uv run python -m py_compile scripts\browser_smoke.py scripts\release_gate.py backend\tests\test_browser_smoke.py backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py` -> pass.
- `uv run pytest tests/test_browser_smoke.py -q --maxfail=1` from `backend` -> `28 passed`.
- Real Vite dev-server rerun with the same `dashboard-readiness-refresh` command -> pass; evidence written to `var/desci-browser-smoke-loop18-dashboard-readiness-refresh.json` with `ok=true`, `summary.passed=1`, `failures=[]`, and `mocked_endpoints=["/ready","/launch","/me","/papers/me","/health","/vcs","/notices"]`.
- `uv run pytest tests/test_browser_smoke.py tests/test_release_gate.py tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `100 passed`.
- `uv run python scripts/release_gate.py --skip-env --skip-compose --skip-frontend --skip-contracts --backend-tests tests/test_browser_smoke.py tests/test_release_gate.py tests/test_deployment_docs.py --json-out var/desci-release-gate-loop18-targeted-backend.json` -> `1/1` passed, backend `100 passed`.

### Result
- The dashboard launch-control browser proof now works against an actual Vite dev server without requiring a live backend for unrelated dashboard widgets.
- Fixture provenance is more explicit, so release-gate consumers can see exactly which API paths were mocked for the frontend proof.
- Production launch remains blocked by missing external environment and deployment secrets; no readiness or security checks were relaxed.

## 2026-06-10 (Browser Smoke Failure Trace Artifacts)

### Scope
- Added optional Playwright trace capture to `scripts/browser_smoke.py` through `--trace-on-failure-dir`.
- The runner starts tracing before each isolated page check when the option is set, discards traces for passing checks, and keeps a per-check `.trace.zip` only when the check fails.
- Browser-smoke JSON now exposes failure trace evidence through top-level `trace_artifacts` and per-check `trace_path` fields.
- Updated README, deployment guide, operations runbook, and deployment-doc tests to document the trace-on-failure evidence path.

### Verification
- `uv run python -m py_compile scripts\browser_smoke.py scripts\release_gate.py backend\tests\test_browser_smoke.py backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py` -> pass.
- `uv run pytest tests/test_browser_smoke.py -q --maxfail=1` from `backend` -> `31 passed`.
- Negative trace probe: `uv run python scripts/browser_smoke.py --frontend http://127.0.0.1:9 --skip-protected --skip-login-validation --only-check home --timeout 0.5 --trace-on-failure-dir var/desci-browser-smoke-loop19-traces --json-out var/desci-browser-smoke-loop19-trace-negative.json` -> expected exit `1`; JSON includes `trace_artifacts[0].path=var\desci-browser-smoke-loop19-traces\home.trace.zip`, and the trace zip existed with non-zero size.
- Positive real Vite probe: `uv run python scripts/browser_smoke.py --frontend http://127.0.0.1:5188 --expect-dev-auth --only-check dashboard-readiness-refresh --trace-on-failure-dir var/desci-browser-smoke-loop19-traces-pass --json-out var/desci-browser-smoke-loop19-dashboard-readiness-trace-pass.json` -> pass; JSON has no `trace_artifacts` because the check passed.
- `uv run pytest tests/test_browser_smoke.py tests/test_release_gate.py tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> first run failed on a missing `guide` fixture variable in the docs test, then passed after fixing it (`103 passed`).
- `uv run python scripts/release_gate.py --skip-env --skip-compose --skip-frontend --skip-contracts --backend-tests tests/test_browser_smoke.py tests/test_release_gate.py tests/test_deployment_docs.py --json-out var/desci-release-gate-loop19-targeted-backend.json` -> `1/1` passed, backend `103 passed`.

### Result
- Failed browser-smoke checks now leave operator-debuggable Playwright trace archives without bloating successful smoke evidence.
- JSON handoff consumers can link directly from a failed check to its `trace_path`.
- Production launch remains blocked by missing external environment and deployment secrets; no readiness or security checks were relaxed.

## 2026-06-10 (Release Gate Browser Trace Evidence Promotion)

### Scope
- Added release-gate runtime forwarding for browser failure traces through `--runtime-browser-trace-on-failure-dir`.
- Extended browser-smoke child artifact reporting with `json_trace_artifact_count`, `json_trace_artifact_paths`, and `json_trace_artifact_checks`.
- Extended parent `artifact_summary` aggregation with `json_trace_artifact_count`, `has_trace_artifacts`, and `json_trace_artifact_paths`.
- Added validation for malformed browser-smoke `trace_artifacts` entries and invalid per-check `trace_path` values.
- Updated README, deployment guide, operations runbook, and deployment-doc tests to document the runtime trace handoff.

### Verification
- `uv run python -m py_compile scripts\release_gate.py backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py` -> pass.
- `uv run pytest tests/test_release_gate.py tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `75 passed`.
- Negative release-gate runtime trace probe against closed port `http://127.0.0.1:9` -> expected exit `1`; parent JSON written to `var/desci-release-gate-loop20-runtime-trace-negative.json`.
- The negative probe forwarded `--trace-on-failure-dir` to child `browser_smoke.py`; child JSON includes `56` trace artifacts and `56` check-level `trace_path` entries under `var/desci-release-gate-loop20-browser-traces`.
- Parent `artifact_summary` in the negative probe includes `json_trace_artifact_count=56`, `has_trace_artifacts=true`, and `56` `json_trace_artifact_paths`.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-frontend --skip-contracts --backend-tests tests/test_release_gate.py tests/test_deployment_docs.py --json-out ../../var/desci-release-gate-loop20-targeted-backend.json` -> `1/1` passed, backend `75 passed`.

### Result
- Release-gate runtime smoke now preserves failed browser-check Playwright traces without enabling trace capture by default.
- Parent release-gate JSON can surface trace evidence directly for operator handoff while retaining child artifact drill-down.
- Production launch remains blocked by missing external environment and deployment secrets; no readiness or security checks were relaxed.

## 2026-06-10 (Release Gate Targeted Runtime Browser Diagnostics)

### Scope
- Added `--runtime-smoke-step` to limit release-gate runtime smoke to `product` or `browser` child steps.
- Added `--runtime-browser-only-check` and `--runtime-browser-timeout` forwarding to child `browser_smoke.py`.
- Updated README, deployment guide, operations runbook, and deployment-doc tests to document targeted runtime browser diagnostics.

### Verification
- `uv run python -m py_compile scripts\release_gate.py backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py` -> pass.
- `uv run pytest tests/test_release_gate.py tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `77 passed`.
- Targeted negative runtime probe: `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-smoke-step browser --runtime-frontend http://127.0.0.1:9 --runtime-evidence-dir ../../var --runtime-browser-only-check home --runtime-browser-timeout 0.5 --runtime-browser-trace-on-failure-dir ../../var/desci-release-gate-loop21-targeted-traces --json-out ../../var/desci-release-gate-loop21-targeted-browser-negative.json --continue-on-failure` -> expected exit `1`; parent JSON includes only `browser-smoke`, `json_trace_artifact_count=1`, and `has_trace_artifacts=true`.
- Child browser evidence from the targeted probe has `summary.total=1` and one trace archive at `var/desci-release-gate-loop21-targeted-traces/home.trace.zip`.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-frontend --skip-contracts --backend-tests tests/test_release_gate.py tests/test_deployment_docs.py --json-out ../../var/desci-release-gate-loop21-targeted-backend.json` -> `1/1` passed, backend `77 passed`.

### Result
- Operators can now reproduce a failed browser smoke check through release gate without running product smoke or the full browser matrix.
- Targeted trace capture reduced the Loop 20 all-browser diagnostic from 56 trace archives to a single failed-check archive for the same closed-port class of failure.
- Production launch remains blocked by missing external environment and deployment secrets; no readiness or security checks were relaxed.

## 2026-06-10 (Release Gate Trace Artifact Existence Summary)

### Scope
- Resolved browser-smoke trace artifact paths from the child process cwd inside release-gate artifact reports.
- Added parent and per-result trace archive existence fields:
  `json_trace_artifact_resolved_paths`, `json_trace_artifact_existing_count`,
  `json_trace_artifact_missing_count`, `has_missing_trace_artifacts`, and
  `json_trace_artifact_missing_paths`.
- Added validation so browser-smoke child JSON that names a missing trace archive is surfaced as an artifact validation failure.
- Updated README, deployment guide, operations runbook, and deployment-doc tests to document trace path resolution and missing-archive reporting.

### Verification
- `uv run python -m py_compile scripts\release_gate.py backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py` -> pass.
- `uv run pytest tests/test_release_gate.py tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `78 passed`.
- Targeted negative runtime probe: `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-smoke-step browser --runtime-frontend http://127.0.0.1:9 --runtime-evidence-dir ../../var --runtime-browser-only-check home --runtime-browser-timeout 0.5 --runtime-browser-trace-on-failure-dir ../../var/desci-release-gate-loop22-targeted-traces --json-out ../../var/desci-release-gate-loop22-targeted-browser-negative.json --continue-on-failure` -> expected exit `1`; parent JSON includes only `browser-smoke`, `json_trace_artifact_count=1`, `json_trace_artifact_existing_count=1`, `json_trace_artifact_missing_count=0`, and `has_missing_trace_artifacts=false`.
- The targeted trace archive exists at `var/desci-release-gate-loop22-targeted-traces/home.trace.zip`.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-frontend --skip-contracts --backend-tests tests/test_release_gate.py tests/test_deployment_docs.py --json-out ../../var/desci-release-gate-loop22-targeted-backend.json` -> `1/1` passed, backend `78 passed`.

### Result
- Parent release-gate JSON now tells operators whether named browser trace archives actually exist and where they resolve on disk.
- Missing trace archive references no longer appear as successful forensic evidence; they are visible in artifact validation failures and top-level summary counts.
- Production launch remains blocked by missing external environment and deployment secrets; no readiness or security checks were relaxed.

## 2026-06-10 (Release Gate Dry-Run Stale Browser Trace Guard)

### Scope
- Added a dry-run regression test proving stale browser-smoke JSON with `trace_artifacts` is not parsed when the release-gate result is skipped.
- Covered the Loop 22 trace existence fields so dry-run reports cannot accidentally promote stale trace paths, missing trace counts, or validation failures from old child evidence.

### Verification
- `uv run python -m py_compile backend\tests\test_release_gate.py` -> pass.
- `uv run pytest tests/test_release_gate.py tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `79 passed`.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-frontend --skip-contracts --backend-tests tests/test_release_gate.py tests/test_deployment_docs.py --json-out ../../var/desci-release-gate-loop23-targeted-backend.json` -> `1/1` passed, backend `79 passed`.
- Dry-run stale browser probe with existing `desci-browser-smoke-release-gate.json` containing stale `trace_artifacts` -> `var/desci-release-gate-loop23-dry-run-stale-browser.json` reports `validation_skipped=1`, `json_valid=0`, and no trace artifact summary fields.

### Result
- Dry-run release-gate output remains a command preview and expected-artifact manifest, not a parser for stale child files.
- Trace artifact existence reporting stays fail-closed for executed child evidence while dry-run still avoids reading old output.
- Production launch remains blocked by missing external environment and deployment secrets; no readiness or security checks were relaxed.

## 2026-06-10 (Release Gate Browser Trace Artifact Summary)

### Scope
- Promoted browser trace artifact evidence into top-level `browser_trace_artifact_summary` in release-gate parent JSON.
- Added concise operator fields for trace count, existing/missing archive counts, missing trace signal, raw and resolved trace paths, missing trace paths, checks, and child artifact paths.
- Updated README, deployment guide, operations runbook, and deployment-doc tests to document the top-level trace summary.

### Verification
- `uv run python -m py_compile scripts\release_gate.py backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py` -> pass.
- `uv run pytest tests/test_release_gate.py tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `79 passed`.
- Targeted negative runtime probe: `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-smoke-step browser --runtime-frontend http://127.0.0.1:9 --runtime-evidence-dir ../../var --runtime-browser-only-check home --runtime-browser-timeout 0.5 --runtime-browser-trace-on-failure-dir ../../var/desci-release-gate-loop24-targeted-traces --json-out ../../var/desci-release-gate-loop24-targeted-browser-negative.json --continue-on-failure` -> expected exit `1`; parent JSON includes `browser_trace_artifact_summary.trace_artifact_count=1`, `existing_count=1`, `missing_count=0`, and `has_missing_trace_artifacts=false`.
- The targeted trace archive resolves to `D:\AI project\var\desci-release-gate-loop24-targeted-traces\home.trace.zip`.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-frontend --skip-contracts --backend-tests tests/test_release_gate.py tests/test_deployment_docs.py --json-out ../../var/desci-release-gate-loop24-targeted-backend.json` -> `1/1` passed, backend `79 passed`.

### Result
- Operator dashboards can now read browser trace forensic status from one top-level summary instead of reverse-engineering the nested `artifact_summary` trace fields.
- Missing trace archive references remain visible through both validation failures and the concise top-level missing-count signal.
- Production launch remains blocked by missing external environment and deployment secrets; no readiness or security checks were relaxed.

## 2026-06-10 (Release Gate Trace Viewer Command Handoff)

### Scope
- Added structured `trace_viewer_commands` entries to top-level `browser_trace_artifact_summary`.
- Each command entry includes the existing resolved trace archive path and an `argv` list for `npx playwright show-trace`.
- Kept missing trace archives out of `trace_viewer_commands` while preserving `missing_count`, `has_missing_trace_artifacts`, and `missing_paths`.
- Updated README, deployment guide, operations runbook, and deployment-doc tests to document the trace viewer handoff.

### Verification
- `uv run python -m py_compile scripts\release_gate.py backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py` -> pass.
- `git diff --check -- scripts\release_gate.py backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py README.md DEPLOYMENT_GUIDE.md OPERATIONS_RUNBOOK.md` -> pass; only existing CRLF replacement warnings.
- `uv run pytest tests/test_release_gate.py tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `79 passed`.
- Targeted negative runtime probe: `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-smoke-step browser --runtime-frontend http://127.0.0.1:9 --runtime-evidence-dir ../../var --runtime-browser-only-check home --runtime-browser-timeout 0.5 --runtime-browser-trace-on-failure-dir ../../var/desci-release-gate-loop25-targeted-traces --json-out ../../var/desci-release-gate-loop25-targeted-browser-negative.json --continue-on-failure` -> expected exit `1`; parent JSON includes `trace_viewer_commands[0].argv=["npx","playwright","show-trace","D:\AI project\var\desci-release-gate-loop25-targeted-traces\home.trace.zip"]`.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-frontend --skip-contracts --backend-tests tests/test_release_gate.py tests/test_deployment_docs.py --json-out ../../var/desci-release-gate-loop25-targeted-backend.json` -> `1/1` passed, backend `79 passed`.

### Result
- Runtime browser failure reports now carry a direct, structured Playwright trace viewer handoff without requiring dashboards to synthesize shell commands.
- The command hint is only emitted for existing trace archives, so missing trace references remain a validation signal rather than a broken operator action.
- Production launch remains blocked by missing external environment and deployment secrets; no readiness or security checks were relaxed.

## 2026-06-10 (Release Gate Parent Report Schema CLI)

### Scope
- Added `python scripts/release_gate.py --print-report-schema` to print the release-gate parent JSON report contract without running release checks.
- The schema uses JSON Schema draft 2020-12 metadata and documents required parent fields: `schema_version`, `ok`, `generated_at`, `duration_ms`, `summary`, and `results`.
- The schema also documents the browser trace handoff summary, including `browser_trace_artifact_summary` and `trace_viewer_commands` command entries.
- Updated README, deployment guide, operations runbook, and deployment-doc tests to document the machine-readable contract path.

### Verification
- `uv run python -m py_compile scripts\release_gate.py backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py` -> pass.
- `uv run python scripts\release_gate.py --print-report-schema | uv run python -m json.tool` -> pass; output includes `$schema=https://json-schema.org/draft/2020-12/schema` and `browser_trace_artifact_summary.properties.trace_viewer_commands`.
- `uv run pytest tests/test_release_gate.py tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `81 passed`.
- `git diff --check -- scripts\release_gate.py backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py README.md DEPLOYMENT_GUIDE.md OPERATIONS_RUNBOOK.md` -> pass; only existing CRLF replacement warnings.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-frontend --skip-contracts --backend-tests tests/test_release_gate.py tests/test_deployment_docs.py --json-out ../../var/desci-release-gate-loop26-targeted-backend.json` -> `1/1` passed, backend `81 passed`.

### Result
- Dashboard and CI parser integrations can now fetch a stable parent report contract before parsing live release-gate artifacts.
- The schema command exits before building or running release-gate steps, so it is safe for docs, parser tests, and lightweight integration probes.
- Production launch remains blocked by missing external environment and deployment secrets; no readiness or security checks were relaxed.

## 2026-06-10 (Grant Discovery Deadline Status Readiness)

### Scope
- Added `deadline_status` to `GrantApplicationBrief` with `unknown`, `closed`, `urgent`, `near`, and `open` states.
- Classified grant/RFP deadlines in `services/grant_discovery.py` and capped closed opportunities at low readiness.
- Added a closed-deadline next action and risk flag so expired opportunities are treated as historical context unless the sponsor posts a renewed or still-open notice.
- Added regression coverage for urgent active deadlines and closed deadline readiness capping.

### Verification
- `uv run python -m py_compile backend\models.py backend\services\grant_discovery.py backend\tests\test_grant_discovery.py` -> pass.
- `uv run pytest tests/test_grant_discovery.py -q --maxfail=1` from `backend` -> `5 passed`.
- `git diff --check -- backend\models.py backend\services\grant_discovery.py backend\tests\test_grant_discovery.py` -> pass; only existing CRLF replacement warning.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-frontend --skip-contracts --backend-tests tests/test_grant_discovery.py --json-out ../../var/desci-release-gate-loop27-grant-discovery.json` -> `1/1` passed, backend `5 passed`; parent JSON has `ok=true`, `summary.failed=0`, and `python_command.strategy=auto_uv_project`.

### Result
- Grant discovery no longer presents expired notices as high-readiness live submissions.
- Operators still keep closed opportunities for sponsor-history and fit context, but the application brief now clearly blocks live submission until a renewed/open notice is confirmed.
- API_SPEC and README now document `deadline_status`; deeper frontend copy/UI surfacing remains a follow-up.

## 2026-06-10 (Funding Radar Deadline Status Badges)

### Scope
- Surfaced grant discovery `application_brief.deadline_status` in Funding Radar recommendation cards.
- Added compact status badges for `unknown`, `closed`, `urgent`, `near`, and `open` states next to submission readiness.
- Added closed-deadline operator warning copy so expired opportunities are treated as sponsor context until a renewed or still-open notice is confirmed.
- Added English messages and Korean override strings for the new deadline status UI.

### External Checks
- NIH opportunity guidance emphasizes verifying opportunity details, contacts, and due dates before preparing an application: https://grants.nih.gov/grants-process/plan-to-apply/find-your-opportunity-contacts-and-due-dates
- Grants.gov search exposes current opportunity discovery filters: https://simpler.grants.gov/search
- Grants.gov search help documents opportunity status filtering across forecasted, posted, closed, and archived records: https://grants.gov/help/search-grants/search-grants-tab

### Verification
- `cmd /c "npx eslint src/components/Notices.jsx src/__tests__/components/Notices.test.jsx"` from `frontend` -> pass.
- `cmd /c "npx vitest run src/__tests__/components/Notices.test.jsx --pool=vmThreads --maxWorkers=1 --isolate"` from `frontend` -> `1 passed`, `6 passed`.
- `cmd /c "npm run build"` from `frontend` -> pass.
- Direct Vitest `threads` and `forks` pools timed out while starting workers on this Windows runner; `vmThreads` completed the same target test file successfully.

### Result
- Funding Radar now exposes deadline state directly in the operator workflow instead of forcing users to infer it from readiness score and evidence copy.
- Closed opportunities remain visible for sponsor-history research, but the UI now warns against treating them as live submission targets.

## 2026-06-10 (Funding Radar Match Studio Deadline Handoff)

### Scope
- Extended Funding Radar discovery `Analyze fit` handoff so Match Studio receives deadline status, evidence checklist, risk flags, and submission timeline context.
- Added a discovery-specific analyze button test id to cover the recommendation-card handoff separately from the original notice-list handoff.
- Added localized handoff section labels for deadline status, evidence, risk flags, and submission timeline.
- Hardened discovery handoff formatting to tolerate non-array or missing list values before composing the imported RFP text.

### External Checks
- React Router `useNavigate` supports programmatic navigation from interaction handlers and accepts navigation options/state: https://reactrouter.com/api/hooks/useNavigate
- MDN documents `sessionStorage` as origin- and tab-scoped storage for the current page session, matching the existing notice import handoff pattern: https://developer.mozilla.org/en-US/docs/Web/API/Window/sessionStorage
- Grants.gov search and help pages continue to expose opportunity status filters, reinforcing that status should travel with downstream fit analysis: https://simpler.grants.gov/search and https://grants.gov/help/search-grants/search-grants-tab

### Verification
- `cmd /c "npx eslint src/components/Notices.jsx src/__tests__/components/Notices.test.jsx"` from `frontend` -> pass.
- `cmd /c "npm run typecheck"` from `frontend` -> pass.
- `cmd /c "npx vitest run src/__tests__/components/Notices.test.jsx --pool=vmThreads --maxWorkers=1 --isolate"` from `frontend` -> `1 passed`, `7 passed`.
- `cmd /c "npm run build"` from `frontend` -> pass.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-contracts --json-out ..\..\var\desci-release-gate-loop29-frontend-handoff.json` -> frontend gate `5/5` passed; report has `ok=true`, `summary.failed=0`.

### Result
- Match Studio now receives the same deadline and risk context that Funding Radar shows, reducing the chance that an expired or risky opportunity is analyzed as a clean live submission.
- The release-gate frontend path confirms lint, typecheck, full frontend test split, build, and bundle budget after the handoff change.

## 2026-06-10 (BioLinker Imported Notice Context Callout)

### Scope
- Extended the Funding Radar -> BioLinker notice import payload with structured deadline status, deadline label, readiness score, evidence checklist, risk flags, and submission timeline fields while preserving the existing `rfp_text` contract.
- Rendered structured imported analysis context inside the BioLinker imported notice callout so operators can see deadline/risk/evidence context before running fit analysis.
- Added regression coverage for router-state and sessionStorage imported notice context, plus Funding Radar storage payload normalization.
- Kept the browser handoff storage as best-effort `sessionStorage`; no production auth or security checks were loosened.

### External Checks
- React Router `useLocation` documents reading the current location object, which supports the existing router-state import path: https://reactrouter.com/api/hooks/useLocation
- React Router changelog/release page confirms the project tracks v7 release notes outside older GitHub release pagination: https://reactrouter.com/changelog
- MDN documents `sessionStorage` as origin- and tab-scoped page-session storage, matching the fallback import handoff: https://developer.mozilla.org/en-US/docs/Web/API/Window/sessionStorage
- MDN ARIA alert guidance treats alerts as assertive, time-sensitive live regions; this callout remains normal page content rather than an assertive alert: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/alert_role

### Verification
- `cmd /c "npx eslint src/components/BioLinker.jsx src/components/Notices.jsx src/lib/noticeImport.js src/__tests__/components/BioLinker.test.jsx src/__tests__/components/Notices.test.jsx"` from `frontend` -> pass.
- `cmd /c "npm run typecheck"` from `frontend` -> pass.
- `cmd /c "npx vitest run src/__tests__/components/BioLinker.test.jsx src/__tests__/components/Notices.test.jsx --pool=vmThreads --maxWorkers=1 --isolate"` from `frontend` -> `2 passed`, `13 passed`.
- `cmd /c "npm run build"` from `frontend` -> pass.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-contracts --json-out ..\..\var\desci-release-gate-loop30-biolinker-import-context.json` -> frontend gate `5/5` passed; report has `ok=true`, `summary.failed=0`.
- Browser smoke: started local Vite with `VITE_ENABLE_DEV_AUTH_BYPASS=true` on `127.0.0.1:5175`, seeded `sessionStorage`, opened `/biolinker`, verified `[data-testid="biolinker-imported-notice-context"]` text includes deadline `Closed`, readiness `25%`, risk flag, evidence, and timeline; browser console errors were `0`. Screenshot saved as `desci-loop30-biolinker-import-context.png`. The launcher PID `44560` and remaining listener PID `44036` were stopped after verification.

### Result
- The Funding Radar -> Match Studio path now preserves context both as analysis input text and as visible pre-analysis UI.
- Operators can see when an imported opportunity is closed or risky before they add an organization profile and run fit analysis.

## 2026-06-10 (Discovery to BioLinker Browser Smoke Automation)

### Scope
- Added authenticated browser smoke check `notices-discovery-biolinker-handoff`.
- The check mocks `/notices` and `/discover/grants`, submits research context, clicks the discovery recommendation `Analyze fit` action, lands on `/biolinker`, and verifies imported deadline/readiness/risk/evidence/timeline context.
- The check also verifies the imported RFP textarea contains the closed-deadline/risk text, the sessionStorage handoff is cleared after BioLinker loads, and `/analyze` is not called prematurely.
- Added browser-smoke regression coverage so the authenticated action check list exposes the new check and the function keeps structured deadline/readiness context assertions.

### External Checks
- Playwright Python `route.fulfill` supports deterministic request mocking for browser tests: https://playwright.dev/python/docs/api/class-route
- Playwright Python locators support `get_by_test_id`, matching the repo's existing stable test-id smoke pattern: https://playwright.dev/python/docs/locators
- React Router `useNavigate` remains the official programmatic navigation path used by the Funding Radar action: https://reactrouter.com/api/hooks/useNavigate
- MDN documents `sessionStorage` as origin- and tab-scoped storage, matching the existing fallback handoff contract: https://developer.mozilla.org/en-US/docs/Web/API/Window/sessionStorage

### Verification
- `uv run python -m py_compile scripts\browser_smoke.py backend\tests\test_browser_smoke.py backend\tests\test_release_gate.py` -> pass.
- `uv run pytest tests/test_browser_smoke.py -q --maxfail=1` from `backend` -> `32 passed`.
- `uv run pytest tests/test_release_gate.py -q --maxfail=1` from `backend` -> `75 passed`.
- Browser smoke direct run: `uv run python scripts\browser_smoke.py --frontend http://127.0.0.1:5176 --expect-dev-auth --skip-login-validation --only-check notices-discovery-biolinker-handoff --timeout 25 --json-out ..\..\var\desci-browser-smoke-loop31-discovery-biolinker-handoff.json` -> pass; report has `ok=true`, `summary.passed=1`, `summary.failed=0`.
- Release gate browser-only runtime run: `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-smoke-step browser --runtime-frontend http://127.0.0.1:5176 --runtime-browser-expect-dev-auth --runtime-browser-only-check notices-discovery-biolinker-handoff --runtime-browser-timeout 25 --runtime-evidence-dir ..\..\var --json-out ..\..\var\desci-release-gate-loop31-browser-handoff.json` -> pass; report has `ok=true`, `summary.passed=1`, `summary.failed=0`.
- Local Vite dev-auth server ran on `127.0.0.1:5176`; launcher PID `45640` and remaining listener PID `33304` were stopped, and port `5176` was verified free.

### Result
- The Funding Radar discovery recommendation -> BioLinker imported-context path is now a named browser smoke check rather than a manual verification step.
- Release gate can target the same check through `--runtime-browser-only-check notices-discovery-biolinker-handoff`, making future regressions easier to reproduce with trace capture if needed.

## 2026-06-10 (Discovery Handoff Trace Targeting)

### Scope
- Added release-gate regression coverage that combines `--runtime-smoke-step browser`, `--runtime-browser-expect-dev-auth`, `--runtime-browser-trace-on-failure-dir`, and `--runtime-browser-only-check notices-discovery-biolinker-handoff`.
- Updated README, OPERATIONS_RUNBOOK, and DEPLOYMENT_GUIDE targeted runtime diagnostics so Funding Radar handoff regressions can be narrowed directly through release gate.
- Extended deployment-doc regression coverage to require the new handoff check name in browser smoke and the operator docs.
- Kept trace capture failure-only: passing targeted handoff checks do not emit `trace_artifacts`.

### External Checks
- Playwright Python tracing documents saving traces through `context.tracing` and opening the resulting archive in Trace Viewer: https://playwright.dev/python/docs/api/class-tracing
- Playwright Trace Viewer documentation describes traces as post-run debugging artifacts for failed tests and local/browser inspection: https://playwright.dev/python/docs/trace-viewer
- Playwright release notes keep `trace.zip` inspection through Trace Viewer as a documented debugging workflow: https://playwright.dev/docs/release-notes

### Verification
- `uv run python -m py_compile scripts\release_gate.py backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py` -> pass.
- `uv run pytest tests/test_release_gate.py::test_release_gate_runtime_smoke_can_trace_discovery_biolinker_handoff tests/test_deployment_docs.py::test_operations_runbook_tracks_release_gate_runtime_smoke -q` from `backend` -> `2 passed`.
- `uv run pytest tests/test_release_gate.py tests/test_browser_smoke.py tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `114 passed`.
- `git diff --check -- apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_deployment_docs.py apps/desci-platform/README.md apps/desci-platform/OPERATIONS_RUNBOOK.md apps/desci-platform/DEPLOYMENT_GUIDE.md` -> pass; only existing CRLF replacement warnings.
- Browser smoke direct run with trace option: `uv run python scripts\browser_smoke.py --frontend http://127.0.0.1:5176 --expect-dev-auth --skip-login-validation --only-check notices-discovery-biolinker-handoff --trace-on-failure-dir ..\..\var\desci-browser-traces-loop32 --timeout 25 --json-out ..\..\var\desci-browser-smoke-loop32-discovery-biolinker-handoff.json` -> pass; report has `ok=true`, `summary.passed=1`, `summary.failed=0`, and no `trace_artifacts`.
- Release gate browser-only runtime run with trace targeting: `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-smoke-step browser --runtime-frontend http://127.0.0.1:5176 --runtime-browser-expect-dev-auth --runtime-browser-trace-on-failure-dir ..\..\var\desci-browser-traces-loop32-gate --runtime-browser-only-check notices-discovery-biolinker-handoff --runtime-browser-timeout 25 --runtime-evidence-dir ..\..\var --json-out ..\..\var\desci-release-gate-loop32-browser-trace-handoff.json` -> pass; report has `ok=true`, `summary.failed=0`, `artifact_summary.validation_passed=1`, and no `browser_trace_artifact_summary` because the check passed.
- Local Vite dev-auth server ran on `127.0.0.1:5176`; process chain PIDs `39224`, `45400`, `45620`, and `36736` were stopped after verification, leaving no listening process on port `5176`.

### Result
- Operators now have a documented, tested release-gate command path for reproducing Funding Radar discovery -> BioLinker handoff regressions with trace-on-failure diagnostics.
- The new browser smoke remains failure-forensic only: successful handoff runs keep JSON evidence clean and do not leave trace archives behind.

## 2026-06-10 (Analyze Structured Notice Context)

### Scope
- Added `NoticeAnalysisContext` to the backend `/analyze` request schema so Funding Radar context is not carried only as free-form `rfp_text`.
- Passed optional `notice_context` through the RFP router into `RFPAnalyzer` while preserving compatibility with older two-argument analyzer stubs.
- Updated the analyzer prompt input body and simulated fallback result so deadline, readiness, evidence, risk, and timeline context influence analysis and fallback recommendations.
- Updated BioLinker to include imported Funding Radar context in `/analyze` POST payloads and to filter empty comma-split keywords before sending API requests.
- Extended the discovery -> BioLinker browser smoke to click Analyze fit after import and assert the `/analyze` payload contains the structured closed-deadline notice context.
- Documented optional `/analyze.notice_context` in API_SPEC.

### External Checks
- FastAPI documents Pydantic request bodies as the way to define, validate, and document API input contracts: https://fastapi.tiangolo.com/tutorial/body/
- FastAPI nested body model docs support arbitrarily deep nested request models through Pydantic: https://fastapi.tiangolo.com/tutorial/body-nested-models/
- Pydantic v2 model configuration documents that extra fields are ignored by default, so unmodeled context should be represented explicitly: https://pydantic.dev/docs/validation/2.0/usage/model_config/

### Verification
- `uv run python -m py_compile models.py routers\rfp.py services\analyzer.py tests\test_api_endpoints.py tests\test_llm_fallback_policy.py` from `backend` -> pass.
- `uv run python -m py_compile scripts\browser_smoke.py backend\tests\test_browser_smoke.py backend\tests\test_api_endpoints.py backend\tests\test_llm_fallback_policy.py` -> pass.
- `cmd /c "npx eslint src/components/BioLinker.jsx src/__tests__/components/BioLinker.test.jsx src/lib/noticeImport.js"` from `frontend` -> pass.
- `uv run pytest tests/test_api_endpoints.py::test_analyze_returns_200_with_mocked_llm tests/test_api_endpoints.py::test_analyze_passes_structured_notice_context tests/test_llm_fallback_policy.py -q --maxfail=1` from `backend` -> `6 passed`.
- `uv run pytest tests/test_browser_smoke.py::test_notices_discovery_biolinker_handoff_smoke_covers_structured_context tests/test_api_endpoints.py::test_analyze_passes_structured_notice_context tests/test_llm_fallback_policy.py::test_analyzer_simulated_result_preserves_notice_context -q` from `backend` -> `3 passed`.
- `uv run pytest tests/test_browser_smoke.py tests/test_api_endpoints.py tests/test_llm_fallback_policy.py -q --maxfail=1` from `backend` -> `78 passed`.
- `cmd /c "npx vitest run src/__tests__/components/BioLinker.test.jsx --pool=vmThreads --maxWorkers=1 --isolate"` from `frontend` -> `1 passed`, `7 passed`.
- `cmd /c "npx vitest run src/__tests__/components/BioLinker.test.jsx src/__tests__/components/Notices.test.jsx --pool=vmThreads --maxWorkers=1 --isolate"` from `frontend` -> `2 passed`, `14 passed`.
- `cmd /c "npm run typecheck"` from `frontend` -> pass.
- `cmd /c "npm run build"` from `frontend` -> pass.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-contracts --backend-tests tests/test_api_endpoints.py tests/test_llm_fallback_policy.py --json-out ..\..\var\desci-release-gate-loop33-analyze-context-backend-frontend.json` -> pass; backend `46 passed`, frontend lint/typecheck/tests/build/bundle all passed, `6` gate steps OK.
- Browser smoke direct run: `uv run python scripts\browser_smoke.py --frontend http://127.0.0.1:5176 --expect-dev-auth --skip-login-validation --only-check notices-discovery-biolinker-handoff --timeout 25 --json-out ..\..\var\desci-browser-smoke-loop33-analyze-context-handoff.json` -> pass; report has `ok=true`, `summary.passed=1`, `summary.failed=0`.
- Release gate browser-only runtime run: `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-smoke-step browser --runtime-frontend http://127.0.0.1:5176 --runtime-browser-expect-dev-auth --runtime-browser-only-check notices-discovery-biolinker-handoff --runtime-browser-timeout 25 --runtime-evidence-dir ..\..\var --json-out ..\..\var\desci-release-gate-loop33-browser-analyze-context.json` -> pass; report has `ok=true`, `summary.failed=0`, `artifact_summary.validation_passed=1`.
- `git diff --check -- apps/desci-platform/backend/models.py apps/desci-platform/backend/routers/rfp.py apps/desci-platform/backend/services/analyzer.py apps/desci-platform/backend/tests/test_api_endpoints.py apps/desci-platform/backend/tests/test_llm_fallback_policy.py apps/desci-platform/backend/tests/test_browser_smoke.py apps/desci-platform/frontend/src/components/BioLinker.jsx apps/desci-platform/frontend/src/__tests__/components/BioLinker.test.jsx apps/desci-platform/API_SPEC.md apps/desci-platform/scripts/browser_smoke.py` -> pass; only existing CRLF replacement warnings.
- Local Vite dev-auth server ran on `127.0.0.1:5176`; process chain PIDs `35404`, `48748`, `48256`, and `35168` were stopped after verification, leaving no listener on port `5176`.

### Result
- Funding Radar deadline/readiness/risk context is now a first-class `/analyze` API field, not only text embedded in the imported notice body.
- The browser smoke now proves the real discovery recommendation -> Match Studio -> Analyze fit path preserves that structured context through the API payload.

## 2026-06-10 (Proposal Evidence Gap Handoff)

### Scope
- Extended `ProposalGenerationJobRequest` with optional Funding Radar `notice_context`.
- Passed structured deadline/readiness/evidence/risk/timeline context through `/jobs/proposal/generate` into proposal draft and review generation while preserving compatibility with older two-argument generator stubs.
- Added deterministic `missing_evidence` output for proposal generation jobs by comparing Funding Radar evidence checklist items against the supplied paper title, abstract, and body context.
- Added a mock proposal Evidence Readiness section so fallback drafts surface checklist items, unresolved evidence, risk flags, and timeline anchors before submission.
- Documented the proposal job request and terminal result shape in `API_SPEC.md`.

### External Checks
- NIH application guidance treats the Research Strategy as the core application evidence narrative and tells applicants to follow application-guide and opportunity instructions: https://grants.nih.gov/grants-process/write-application/advice-on-application-sections and https://grants.nih.gov/grants-process/write-application/how-to-apply-application-guide
- NIH budget guidance shows proposal preparation must select and justify the applicable budget form, reinforcing that budget evidence should be explicit before submission: https://grants.nih.gov/grants-process/write-application/advice-on-application-sections/develop-your-budget
- Grants.gov Workspace guidance exposes form/subform and attachment handling as part of application package completion, supporting an explicit missing-evidence checklist: https://www.grants.gov/help/manage-workspaces/download-pdf-forms and https://www.grants.gov/help/manage-workspaces/manage-subforms
- FastAPI nested body model docs support arbitrarily deep Pydantic request models for this optional `notice_context` API contract: https://fastapi.tiangolo.com/tutorial/body-nested-models/

### Verification
- `uv run python -m py_compile models.py routers\jobs.py services\proposal_generator.py tests\test_jobs.py tests\test_smoke_pipeline.py` from `backend` -> pass.
- `git diff --check -- apps/desci-platform/backend/models.py apps/desci-platform/backend/routers/jobs.py apps/desci-platform/backend/services/proposal_generator.py apps/desci-platform/backend/tests/test_jobs.py apps/desci-platform/backend/tests/test_smoke_pipeline.py apps/desci-platform/API_SPEC.md` -> pass; only existing CRLF replacement warnings.
- `uv run pytest tests/test_jobs.py::test_proposal_generation_job_completes tests/test_jobs.py::test_proposal_generation_job_preserves_notice_context tests/test_smoke_pipeline.py::test_proposal_generator_fallback_without_llm tests/test_smoke_pipeline.py::test_proposal_generator_flags_missing_notice_evidence -q --maxfail=1` from `backend` -> `4 passed`.
- `uv run pytest tests/test_jobs.py::test_proposal_generation_job_returns_404_for_missing_rfp -q --maxfail=1` from `backend` -> `1 passed`.
- `uv run pytest tests/test_jobs.py tests/test_smoke_pipeline.py -q --maxfail=1` from `backend` -> `21 passed`.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-frontend --skip-contracts --backend-tests tests/test_jobs.py tests/test_smoke_pipeline.py --json-out ..\..\var\desci-release-gate-loop34-proposal-evidence.json` -> pass; backend gate `1/1` passed, `21 passed`.

### Result
- Proposal jobs can now carry Funding Radar context beyond fit analysis and return a machine-readable list of evidence still missing from the current paper context.
- Existing proposal generation callers and older test stubs remain compatible because `notice_context` is optional and the job runner falls back to the legacy generator signatures.

## 2026-06-10 (Proposal Evidence Frontend Handoff)

### Scope
- Updated BioLinker proposal generation so paper-scoped matches include imported Funding Radar `notice_context` in `/jobs/proposal/generate`.
- Preserved the paper-match tab when a paper handoff and imported notice context arrive together, preventing the imported-notice effect from hiding proposal matches.
- Rendered proposal job `missing_evidence` as an explicit review section in `ProposalView` before the draft body.
- Added Korean and English copy for the missing-evidence section.
- Extended BioLinker and ProposalView component tests to cover proposal context payloads and returned evidence gaps.
- Extended the `biolinker-proposal-clipboard-failure` browser smoke to seed imported notice context, assert the proposal payload includes structured context, and verify the returned missing-evidence UI.

### External Checks
- React conditional rendering and list rendering docs support the UI approach for optional missing-evidence sections and normalized list output: https://react.dev/learn/conditional-rendering and https://react.dev/learn/rendering-lists
- MDN documents `sessionStorage` as tab-scoped storage, matching the Funding Radar import fallback used by the browser smoke: https://developer.mozilla.org/en-US/docs/Web/API/Window/sessionStorage
- React Testing Library documents testing components through rendered DOM behavior, matching the BioLinker and ProposalView regression tests: https://testing-library.com/docs/react-testing-library/intro/
- Playwright Python `route.fulfill` supports deterministic API mocking for the focused browser smoke: https://playwright.dev/python/docs/api/class-route

### Verification
- `cmd /c "npx vitest run src/__tests__/components/BioLinker.test.jsx src/__tests__/components/ProposalView.test.jsx --pool=vmThreads --maxWorkers=1 --isolate"` from `frontend` -> `2 passed`, `13 passed`.
- `cmd /c "npx eslint src/components/BioLinker.jsx src/components/ProposalView.jsx src/__tests__/components/BioLinker.test.jsx src/__tests__/components/ProposalView.test.jsx src/i18n/messages.js"` from `frontend` -> pass.
- `uv run python -m py_compile scripts\browser_smoke.py` -> pass.
- `git diff --check -- frontend\src\components\BioLinker.jsx frontend\src\components\ProposalView.jsx frontend\src\__tests__\components\BioLinker.test.jsx frontend\src\__tests__\components\ProposalView.test.jsx frontend\src\i18n\messages.js scripts\browser_smoke.py` -> pass; only existing CRLF replacement warnings.
- `cmd /c "npm run typecheck"` from `frontend` -> pass.
- `cmd /c "npm run build"` from `frontend` -> pass.
- `uv run pytest tests/test_browser_smoke.py -q` from `backend` -> `32 passed`.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-contracts --json-out ..\..\var\desci-release-gate-loop35-proposal-evidence-frontend.json` -> pass; frontend lint/typecheck/tests/build/bundle all passed, `5` gate steps OK.
- Browser smoke direct run: `uv run python scripts\browser_smoke.py --frontend http://127.0.0.1:5176 --expect-dev-auth --skip-login-validation --only-check biolinker-proposal-clipboard-failure --timeout 25 --json-out ..\..\var\desci-browser-smoke-loop35-proposal-evidence.json` -> pass.
- Release gate browser-only runtime run: `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-smoke-step browser --runtime-frontend http://127.0.0.1:5176 --runtime-browser-expect-dev-auth --runtime-browser-only-check biolinker-proposal-clipboard-failure --runtime-browser-timeout 25 --runtime-evidence-dir ..\..\var --json-out ..\..\var\desci-release-gate-loop35-browser-proposal-evidence.json` -> pass; browser-smoke `1` step OK.
- Local Vite dev-auth server ran on `127.0.0.1:5176`; the listener was stopped after verification, leaving no listener on port `5176`.

### Result
- The Funding Radar -> paper match -> proposal generation path now preserves structured notice context through the frontend job request.
- Proposal reviewers see machine-readable evidence gaps returned by the backend before they copy or export the generated draft.

## 2026-06-10 (Proposal Evidence Action Links)

### Scope
- Converted the proposal missing-evidence section from a passive warning into an operator action surface.
- Added direct links from unresolved Funding Radar evidence gaps to the existing `/upload` paper intake and `/assets` asset library workflows.
- Added Korean and English labels for the proposal evidence actions.
- Extended ProposalView tests to assert the missing-evidence section includes `/upload` and `/assets` actions.
- Extended the `biolinker-proposal-clipboard-failure` browser smoke to verify those action links while preserving the existing clipboard-denial and proposal payload checks.

### External Checks
- React Router documents `Link` as a progressively enhanced anchor wrapper for client-side routing, matching the modal action links to existing protected routes: https://reactrouter.com/api/components/Link
- NIH application guidance treats opportunity instructions and required attachments/sections as the key source of submission requirements, supporting a direct path from missing evidence to intake workflows: https://grants.nih.gov/grants-process/write-application/advice-on-application-sections
- Grants.gov applicant guidance calls out attachment handling and package limits, reinforcing that unresolved evidence should route to document preparation rather than remain only narrative text: https://www.grants.gov/applicants/applicant-faqs

### Verification
- `cmd /c "npx eslint src/components/ProposalView.jsx src/__tests__/components/ProposalView.test.jsx src/i18n/messages.js"` from `frontend` -> pass.
- `cmd /c "npx vitest run src/__tests__/components/ProposalView.test.jsx --pool=vmThreads --maxWorkers=1 --isolate"` from `frontend` -> `1 passed`, `5 passed`.
- `cmd /c "npx vitest run src/__tests__/components/BioLinker.test.jsx src/__tests__/components/ProposalView.test.jsx --pool=vmThreads --maxWorkers=1 --isolate"` from `frontend` -> `2 passed`, `13 passed`.
- `cmd /c "npm run typecheck"` from `frontend` -> pass.
- `cmd /c "npm run build"` from `frontend` -> pass.
- `uv run python -m py_compile scripts\browser_smoke.py` -> pass.
- `uv run pytest tests/test_browser_smoke.py -q` from `backend` -> `32 passed`.
- `git diff --check -- frontend\src\components\ProposalView.jsx frontend\src\__tests__\components\ProposalView.test.jsx frontend\src\i18n\messages.js scripts\browser_smoke.py` -> pass; only existing CRLF replacement warnings.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-contracts --json-out ..\..\var\desci-release-gate-loop36-proposal-evidence-actions-frontend.json` -> pass; frontend lint/typecheck/tests/build/bundle all passed, `5` gate steps OK.
- Browser smoke direct run: `uv run python scripts\browser_smoke.py --frontend http://127.0.0.1:5176 --expect-dev-auth --skip-login-validation --only-check biolinker-proposal-clipboard-failure --timeout 25 --json-out ..\..\var\desci-browser-smoke-loop36-proposal-evidence-actions.json` -> pass.
- Release gate browser-only runtime run: `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-smoke-step browser --runtime-frontend http://127.0.0.1:5176 --runtime-browser-expect-dev-auth --runtime-browser-only-check biolinker-proposal-clipboard-failure --runtime-browser-timeout 25 --runtime-evidence-dir ..\..\var --json-out ..\..\var\desci-release-gate-loop36-browser-proposal-evidence-actions.json` -> pass; browser-smoke `1` step OK.
- Local Vite dev-auth server ran on `127.0.0.1:5176`; the listener was stopped after verification, leaving no listener on port `5176`.

### Result
- Proposal reviewers can now move from a returned evidence gap directly into the existing paper intake or asset-library workflow.
- The browser smoke proves the proposal modal still surfaces missing evidence, preserves the structured proposal job payload, handles clipboard denial, and exposes the new evidence actions.

## 2026-06-10 (Proposal Evidence Destination Handoff)

### Scope
- Added a shared `proposalEvidenceHandoff` route-state helper so the proposal missing-evidence section can carry normalized RFP title, source, and missing evidence into downstream routes.
- Passed that handoff state through the proposal `/upload` and `/assets` action links.
- Added a proposal evidence banner to `/upload` with the unresolved evidence checklist and a link onward to `/assets`.
- Added a proposal evidence banner to `/assets`, defaulting the asset type selector to `Technical Paper` when entered from the proposal evidence handoff.
- Added English/Korean copy and component test coverage for the new destination handoff UI.
- Extended the `biolinker-proposal-clipboard-failure` browser smoke so it clicks into `/upload`, then into `/assets`, and verifies the destination banners plus the `paper` asset-type default.

### External Checks
- React Router documents `Link` route `state` for passing client-side navigation state to the next location: https://reactrouter.com/api/components/Link
- React Router documents `useLocation` as the hook for reading the current location object, including route state: https://reactrouter.com/api/hooks/useLocation
- NIH application guidance treats required application sections and opportunity instructions as the source of proposal evidence requirements: https://grants.nih.gov/grants-process/write-application/advice-on-application-sections
- Grants.gov applicant guidance covers attachments and package constraints, supporting explicit document-preparation handoffs for unresolved evidence: https://www.grants.gov/applicants/applicant-faqs

### Verification
- `cmd /c "npx eslint src/components/ProposalView.jsx src/components/UploadPaper.jsx src/components/AssetManager.jsx src/__tests__/components/ProposalView.test.jsx src/__tests__/components/UploadPaper.test.jsx src/__tests__/components/AssetManager.test.jsx src/__tests__/mocks/locale-messages.js src/i18n/messages.js src/lib/proposalEvidenceHandoff.js"` from `frontend` -> pass.
- `cmd /c "npx vitest run src/__tests__/components/ProposalView.test.jsx src/__tests__/components/UploadPaper.test.jsx src/__tests__/components/AssetManager.test.jsx --pool=vmThreads --maxWorkers=1 --isolate"` from `frontend` -> `3 passed`, `21 passed`.
- `cmd /c "npm run typecheck"` from `frontend` -> pass.
- `cmd /c "npm run build"` from `frontend` -> pass.
- `uv run python -m py_compile scripts\browser_smoke.py` -> pass.
- `uv run pytest backend/tests/test_browser_smoke.py -q` -> `32 passed`.
- `git diff --check -- frontend/src/components/ProposalView.jsx frontend/src/components/UploadPaper.jsx frontend/src/components/AssetManager.jsx frontend/src/__tests__/components/ProposalView.test.jsx frontend/src/__tests__/components/UploadPaper.test.jsx frontend/src/__tests__/components/AssetManager.test.jsx frontend/src/__tests__/mocks/locale-messages.js frontend/src/i18n/messages.js frontend/src/lib/proposalEvidenceHandoff.js scripts/browser_smoke.py` -> pass; only existing CRLF replacement warnings.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-contracts --json-out ..\..\var\desci-release-gate-loop37-proposal-evidence-handoff-frontend.json` -> pass; frontend lint/typecheck/tests/build/bundle all passed, `5` gate steps OK.
- Browser smoke direct run: `uv run python scripts\browser_smoke.py --frontend http://127.0.0.1:5176 --expect-dev-auth --skip-login-validation --only-check biolinker-proposal-clipboard-failure --timeout 25 --json-out ..\..\var\desci-browser-smoke-loop37-proposal-evidence-handoff.json` -> pass.
- Release gate browser-only runtime run: `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-smoke-step browser --runtime-frontend http://127.0.0.1:5176 --runtime-browser-expect-dev-auth --runtime-browser-only-check biolinker-proposal-clipboard-failure --runtime-browser-timeout 25 --runtime-evidence-dir ..\..\var --json-out ..\..\var\desci-release-gate-loop37-browser-proposal-evidence-handoff.json` -> pass; browser-smoke `1` step OK.
- Local Vite dev-auth server ran on `127.0.0.1:5176`; listener PID `45928` was stopped after verification, leaving no listener on port `5176`.

### Result
- Proposal reviewers now keep the unresolved evidence context when they leave the draft modal and enter paper upload or asset-library workflows.
- The focused browser smoke proves both destination pages receive the handoff state, `/assets` defaults to Technical Paper, and the existing proposal clipboard-denial path remains stable.

## 2026-06-10 (Proposal Evidence Asset Context)

### Scope
- Extended `/assets/upload` with optional `proposal_evidence_context` multipart JSON while preserving compatibility with legacy two-argument asset-manager stubs.
- Normalized proposal evidence context in `AssetManager` and stored it in the asset upload response plus local asset manifest.
- Kept vector metadata scalar-safe by storing a JSON string and an RFP title field in vector metadata.
- Updated `/assets` UI so proposal evidence uploads send the context, show a proposal-evidence receipt panel, and mark persisted assets with a proposal evidence chip.
- Documented the optional upload field and returned manifest shape in `API_SPEC.md`.
- Extended the proposal browser smoke so it actually uploads a small supporting TXT asset and verifies the multipart payload carries `proposal_evidence_context`.

### External Checks
- FastAPI documents defining uploaded files and form fields together with `File` and `Form`: https://fastapi.tiangolo.com/tutorial/request-forms-and-files/
- React Router documents `Link state` and reading it from `useLocation`, matching the route-state to multipart handoff: https://reactrouter.com/api/components/Link and https://reactrouter.com/api/hooks/useLocation
- NIH budget guidance states budget justification needs explicit personnel and project-cost evidence, supporting durable evidence attachment context: https://grants.nih.gov/grants-process/write-application/advice-on-application-sections/develop-your-budget
- Grants.gov applicant FAQ notes attachment filename/rule restrictions vary by agency and form, supporting explicit tracking of uploaded evidence files: https://www.grants.gov/applicants/applicant-faqs

### Verification
- `uv run python -m py_compile services\asset_manager.py routers\web3.py tests\test_asset_manager.py` from `backend` -> pass.
- `uv run pytest tests/test_asset_manager.py -q` from `backend` -> `4 passed`.
- `uv run pytest tests/test_asset_manager.py tests/test_smoke_pipeline.py tests/test_e2e_proposal_flow.py -q --maxfail=1` from `backend` -> `16 passed`.
- `cmd /c "npx eslint src/components/AssetManager.jsx src/__tests__/components/AssetManager.test.jsx src/__tests__/mocks/locale-messages.js src/i18n/messages.js src/lib/proposalEvidenceHandoff.js"` from `frontend` -> pass.
- `cmd /c "npx vitest run src/__tests__/components/AssetManager.test.jsx --pool=vmThreads --maxWorkers=1 --isolate"` from `frontend` -> `1 passed`, `5 passed`.
- `cmd /c "npx vitest run src/__tests__/components/ProposalView.test.jsx src/__tests__/components/UploadPaper.test.jsx src/__tests__/components/AssetManager.test.jsx --pool=vmThreads --maxWorkers=1 --isolate"` from `frontend` -> `3 passed`, `21 passed`.
- `cmd /c "npm run typecheck"` from `frontend` -> pass.
- `cmd /c "npm run build"` from `frontend` -> pass.
- `uv run python -m py_compile scripts\browser_smoke.py backend\tests\test_browser_smoke.py` -> pass.
- `uv run pytest backend/tests/test_browser_smoke.py -q` -> `32 passed`.
- Browser smoke direct run: `uv run python scripts\browser_smoke.py --frontend http://127.0.0.1:5176 --expect-dev-auth --skip-login-validation --only-check biolinker-proposal-clipboard-failure --timeout 25 --json-out ..\..\var\desci-browser-smoke-loop38-proposal-evidence-asset-context.json` -> pass.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-contracts --backend-tests tests/test_asset_manager.py tests/test_smoke_pipeline.py tests/test_e2e_proposal_flow.py --json-out ..\..\var\desci-release-gate-loop38-proposal-evidence-asset-context.json` -> pass; backend targeted tests and frontend lint/typecheck/tests/build/bundle all passed, `6` gate steps OK.
- Release gate browser-only runtime run: `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-smoke-step browser --runtime-frontend http://127.0.0.1:5176 --runtime-browser-expect-dev-auth --runtime-browser-only-check biolinker-proposal-clipboard-failure --runtime-browser-timeout 25 --runtime-evidence-dir ..\..\var --json-out ..\..\var\desci-release-gate-loop38-browser-proposal-evidence-asset-context.json` -> pass; browser-smoke `1` step OK.
- `git diff --check -- API_SPEC.md backend/services/asset_manager.py backend/routers/web3.py backend/tests/test_asset_manager.py frontend/src/components/AssetManager.jsx frontend/src/__tests__/components/AssetManager.test.jsx frontend/src/__tests__/mocks/locale-messages.js frontend/src/i18n/messages.js frontend/src/lib/proposalEvidenceHandoff.js scripts/browser_smoke.py` -> pass; only existing CRLF replacement warnings.
- Local Vite dev-auth server ran on `127.0.0.1:5176`; listener PID `33008` was stopped after verification, leaving no listener on port `5176`.

### Result
- Evidence-gap uploads are no longer only visually associated with a proposal; the asset upload contract can now persist the proposal evidence context in the returned manifest.
- The real browser smoke proves the modal -> upload -> asset library path carries the evidence context into an actual asset upload payload.

## 2026-06-10 (Proposal Supporting Evidence Assets)

### Scope
- Enriched proposal-generation jobs with matching uploaded asset manifests that carry `proposal_evidence_context`.
- Added `supporting_evidence_assets` to the notice context, proposal job result, fallback draft, and proposal-review missing-evidence checks.
- Allowed uploaded evidence assets to satisfy matching `evidence_to_prepare` checklist items when regenerating or reviewing proposal drafts.
- Rendered linked supporting evidence assets in the proposal modal before the remaining missing-evidence list.
- Documented the new proposal job result shape in `API_SPEC.md`.
- Extended the proposal browser smoke so it verifies returned supporting assets appear in the proposal UI.

### External Checks
- FastAPI documents combining uploaded files and form fields with `File` and `Form`, matching the previous asset-upload context handoff: https://fastapi.tiangolo.com/tutorial/request-forms-and-files/
- React Router documents route `state` on `Link` and reading it with `useLocation`, matching the proposal-to-assets context path: https://reactrouter.com/api/components/Link and https://reactrouter.com/api/hooks/useLocation
- NIH budget guidance treats budget justification and cost details as explicit application evidence, supporting checklist-driven evidence resolution: https://grants.nih.gov/grants-process/write-application/advice-on-application-sections/develop-your-budget
- Grants.gov applicant FAQ describes agency/form-specific attachment constraints, supporting visible linked-asset evidence tracking: https://www.grants.gov/applicants/applicant-faqs

### Verification
- `uv run python -m py_compile routers\jobs.py services\proposal_generator.py tests\test_jobs.py tests\test_smoke_pipeline.py` from `backend` -> pass.
- `uv run pytest tests/test_jobs.py::test_proposal_generation_job_preserves_notice_context tests/test_jobs.py::test_proposal_generation_job_uses_supporting_evidence_assets tests/test_smoke_pipeline.py::test_proposal_generator_flags_missing_notice_evidence tests/test_smoke_pipeline.py::test_proposal_generator_resolves_notice_evidence_with_supporting_assets -q` from `backend` -> `4 passed`.
- `uv run pytest tests/test_jobs.py tests/test_smoke_pipeline.py tests/test_asset_manager.py -q --maxfail=1` from `backend` -> `27 passed`.
- `cmd /c "npx eslint src/components/BioLinker.jsx src/components/ProposalView.jsx src/__tests__/components/BioLinker.test.jsx src/__tests__/components/ProposalView.test.jsx src/i18n/messages.js"` from `frontend` -> pass.
- `cmd /c "npx vitest run src/__tests__/components/BioLinker.test.jsx src/__tests__/components/ProposalView.test.jsx --pool=vmThreads --maxWorkers=1 --isolate"` from `frontend` -> `2 passed`, `14 passed`.
- `cmd /c "npx vitest run src/__tests__/components/BioLinker.test.jsx src/__tests__/components/ProposalView.test.jsx src/__tests__/components/UploadPaper.test.jsx src/__tests__/components/AssetManager.test.jsx --pool=vmThreads --maxWorkers=1 --isolate"` from `frontend` -> `4 passed`, `30 passed`.
- `cmd /c "npm run typecheck"` from `frontend` -> pass.
- `cmd /c "npm run build"` from `frontend` -> pass.
- `uv run python -m py_compile scripts\browser_smoke.py backend\tests\test_browser_smoke.py` -> pass.
- `uv run pytest backend/tests/test_browser_smoke.py -q` -> `32 passed`.
- `git diff --check -- API_SPEC.md backend/services/proposal_generator.py backend/routers/jobs.py backend/tests/test_jobs.py backend/tests/test_smoke_pipeline.py frontend/src/components/BioLinker.jsx frontend/src/components/ProposalView.jsx frontend/src/__tests__/components/BioLinker.test.jsx frontend/src/__tests__/components/ProposalView.test.jsx frontend/src/i18n/messages.js scripts/browser_smoke.py` -> pass; only existing CRLF replacement warnings.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-contracts --backend-tests tests/test_jobs.py tests/test_smoke_pipeline.py tests/test_asset_manager.py --json-out ..\..\var\desci-release-gate-loop39-proposal-supporting-assets.json` -> pass; backend targeted tests and frontend lint/typecheck/tests/build/bundle all passed, `6` gate steps OK.
- Browser smoke direct run: `uv run python scripts\browser_smoke.py --frontend http://127.0.0.1:5176 --expect-dev-auth --skip-login-validation --only-check biolinker-proposal-clipboard-failure --timeout 25 --json-out ..\..\var\desci-browser-smoke-loop39-proposal-supporting-assets.json` -> pass.
- Release gate browser-only runtime run: `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-smoke-step browser --runtime-frontend http://127.0.0.1:5176 --runtime-browser-expect-dev-auth --runtime-browser-only-check biolinker-proposal-clipboard-failure --runtime-browser-timeout 25 --runtime-evidence-dir ..\..\var --json-out ..\..\var\desci-release-gate-loop39-browser-proposal-supporting-assets.json` -> pass; browser-smoke `1` step OK.
- Local Vite dev-auth server ran on `127.0.0.1:5176`; listener PID `45444` was stopped after verification, leaving no listener on port `5176`.

### Result
- Proposal regeneration and review can now consume uploaded supporting-evidence assets instead of only showing unresolved checklist gaps.
- The browser smoke proves the proposal modal renders linked supporting assets while the existing clipboard-denial path remains stable.

## 2026-06-10 (Amoy RPC Readiness)

### Scope
- Tightened deploy readiness so `AMOY_RPC_URL` or `WEB3_RPC_URL` must be a public `https://` URL before the Amoy deployment target passes.
- Tightened env doctor Web3 readiness so production does not treat malformed or non-HTTPS `WEB3_RPC_URL` values as real Web3 configuration.
- Updated frontend wallet add-chain defaults to the current Polygon Amoy RPC endpoint and kept the POL native currency metadata.
- Updated Hardhat Amoy default RPC plus `.env` examples and deployment/runbook docs to use `https://polygon-amoy.drpc.org`.
- Extended the `wallet-provider-amoy` browser smoke to exercise the MetaMask unknown-chain `4902` fallback and verify the `wallet_addEthereumChain` payload includes the Amoy chain ID, RPC URL, explorer URL, and POL symbol.

### External Checks
- MetaMask documents `wallet_switchEthereumChain` and error `4902` as the path for unknown chains that should be added with `wallet_addEthereumChain`: https://docs.metamask.io/metamask-connect/evm/reference/json-rpc-api/wallet_switchEthereumChain/
- MetaMask documents `wallet_addEthereumChain` metadata fields and successful `null` return: https://docs.metamask.io/metamask-connect/evm/reference/json-rpc-api/wallet_addEthereumChain/
- EIP-3085 requires wallet add-chain `rpcUrls` to be valid URLs and the chain ID to be a valid hex chain ID: https://eips.ethereum.org/EIPS/eip-3085
- Polygon's current RPC endpoint reference lists Amoy chain ID `80002`, gas token `POL`, RPC `https://polygon-amoy.drpc.org`, and explorer `https://amoy.polygonscan.com/`: https://docs.polygon.technology/pos/reference/rpc-endpoints

### Verification
- `uv run python -m py_compile scripts\deploy_readiness.py scripts\env_doctor.py backend\tests\test_deploy_readiness.py backend\tests\test_env_doctor.py` -> pass.
- `uv run pytest backend/tests/test_deploy_readiness.py::test_amoy_accepts_web3_rpc_fallback_and_ethplorer_key backend/tests/test_deploy_readiness.py::test_amoy_rejects_non_https_or_malformed_rpc_urls backend/tests/test_env_doctor.py::test_production_env_accepts_real_web3_contract_config backend/tests/test_env_doctor.py::test_production_env_rejects_non_https_or_malformed_web3_rpc_url -q` -> `4 passed`.
- `cmd /c "npx eslint src/lib/walletConnection.js src/__tests__/lib/walletConnection.test.js"` from `frontend` -> pass.
- `uv run pytest backend/tests/test_deploy_readiness.py backend/tests/test_env_doctor.py backend/tests/test_deployment_docs.py -q --maxfail=1` -> `54 passed`.
- `cmd /c "npx vitest run src/__tests__/lib/walletConnection.test.js src/__tests__/components/Wallet.test.jsx src/__tests__/components/Layout.test.jsx --pool=vmThreads --maxWorkers=1 --isolate"` from `frontend` -> `3 passed`, `20 passed`.
- `cmd /c "node --test tests/runtime-config.test.js"` from `contracts` -> `10 passed`.
- `cmd /c "node node_modules/hardhat/dist/src/cli.js --build-profile default build"` from `contracts` -> pass; no contracts needed compilation.
- `uv run python -m py_compile scripts\browser_smoke.py scripts\deploy_readiness.py scripts\env_doctor.py backend\tests\test_browser_smoke.py backend\tests\test_deploy_readiness.py backend\tests\test_env_doctor.py` -> pass.
- `uv run pytest backend/tests/test_browser_smoke.py backend/tests/test_deploy_readiness.py backend/tests/test_env_doctor.py backend/tests/test_deployment_docs.py -q --maxfail=1` -> `86 passed`.
- `git diff --check -- scripts/deploy_readiness.py scripts/env_doctor.py scripts/browser_smoke.py backend/tests/test_deploy_readiness.py backend/tests/test_env_doctor.py frontend/src/lib/walletConnection.js frontend/src/__tests__/lib/walletConnection.test.js contracts/hardhat.config.js .env.example .env.production.example frontend/.env.example contracts/.env.example README.md DEPLOYMENT_GUIDE.md OPERATIONS_RUNBOOK.md` -> pass; only existing CRLF replacement warnings.
- `cmd /c "npm run typecheck"` from `frontend` -> pass.
- `cmd /c "npm run build"` from `frontend` -> pass.
- Browser smoke direct run: `uv run python scripts\browser_smoke.py --frontend http://127.0.0.1:5177 --expect-dev-auth --skip-login-validation --only-check wallet-provider-amoy --timeout 25 --json-out ..\..\var\desci-browser-smoke-loop40-wallet-amoy-rpc.json` -> pass.
- Release gate browser-only runtime run: `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-smoke-step browser --runtime-frontend http://127.0.0.1:5177 --runtime-browser-expect-dev-auth --runtime-browser-only-check wallet-provider-amoy --runtime-browser-timeout 25 --runtime-evidence-dir ..\..\var --json-out ..\..\var\desci-release-gate-loop40-browser-wallet-amoy-rpc.json` -> pass; browser-smoke `1` step OK.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-contracts --backend-tests tests/test_browser_smoke.py tests/test_deploy_readiness.py tests/test_env_doctor.py tests/test_deployment_docs.py --json-out ..\..\var\desci-release-gate-loop40-amoy-rpc-readiness.json` -> pass; backend targeted tests and frontend lint/typecheck/tests/build/bundle all passed, `6` gate steps OK.
- Local Vite dev-auth server ran on `127.0.0.1:5177`; listener PID `33604` was stopped after verification, leaving no listener on port `5177`.

### Result
- Amoy deploy/readiness checks no longer pass malformed RPC strings that would fail real wallet or contract operations.
- Wallet browser smoke now proves the app can recover from an unknown-chain wallet by sending a complete Polygon Amoy add-chain payload with current official RPC metadata.

## 2026-06-10 (Wallet RPC Override Readiness)

### Scope
- Added comma-separated public HTTPS validation for optional `VITE_WALLET_RPC_URL` overrides.
- Added a dedicated `vercel_wallet_rpc` deploy-readiness check so malformed frontend wallet RPC overrides fail Vercel preflight without masking chain-ID or contract-address failures.
- Extended env doctor's `frontend_wallet` check so production wallet config fails when `VITE_WALLET_RPC_URL` is set to malformed or non-HTTPS values.
- Updated README, deployment guide, and operations runbook language to state that every configured frontend wallet RPC override must be public `https://`.

### External Checks
- MetaMask documents `wallet_addEthereumChain` as accepting network metadata including `rpcUrls`: https://docs.metamask.io/metamask-connect/evm/reference/json-rpc-api/wallet_addEthereumChain/
- EIP-3085 requires `wallet_addEthereumChain` `rpcUrls` to contain valid URLs and recommends wallets reject malformed chain metadata: https://eips.ethereum.org/EIPS/eip-3085
- Polygon's current endpoint reference lists Polygon Amoy RPC as `https://polygon-amoy.drpc.org`: https://docs.polygon.technology/pos/reference/rpc-endpoints

### Verification
- `uv run python -m py_compile scripts\deploy_readiness.py scripts\env_doctor.py backend\tests\test_deploy_readiness.py backend\tests\test_env_doctor.py` -> pass.
- `uv run pytest backend/tests/test_deploy_readiness.py::test_ready_env_passes_required_external_targets backend/tests/test_deploy_readiness.py::test_vercel_wallet_provider_requires_amoy_and_deployed_contract_addresses backend/tests/test_deploy_readiness.py::test_vercel_wallet_rpc_override_rejects_malformed_or_non_https_urls backend/tests/test_env_doctor.py::test_production_env_required_checks_pass backend/tests/test_env_doctor.py::test_production_env_rejects_incomplete_frontend_wallet_provider_config backend/tests/test_env_doctor.py::test_production_env_rejects_malformed_frontend_wallet_rpc_override -q` -> `6 passed`.
- `uv run pytest backend/tests/test_deploy_readiness.py backend/tests/test_env_doctor.py backend/tests/test_deployment_docs.py -q --maxfail=1` -> `56 passed`.
- `git diff --check -- scripts/deploy_readiness.py scripts/env_doctor.py backend/tests/test_deploy_readiness.py backend/tests/test_env_doctor.py README.md DEPLOYMENT_GUIDE.md OPERATIONS_RUNBOOK.md` -> pass; only existing CRLF replacement warnings.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-contracts --backend-tests tests/test_deploy_readiness.py tests/test_env_doctor.py tests/test_deployment_docs.py --json-out ..\..\var\desci-release-gate-loop41-wallet-rpc-override-readiness.json` -> pass; backend targeted tests and frontend lint/typecheck/tests/build/bundle all passed, `6` gate steps OK.

### Result
- Production preflight now catches broken frontend wallet RPC overrides before Vercel builds a bundle that cannot add Polygon Amoy in user wallets.
- Operators can still leave `VITE_WALLET_RPC_URL` unset and rely on the bundled Polygon Amoy default from Loop 40.

## 2026-06-10 (Ready Web3 Details)

### Scope
- Added non-secret `/ready.checks.web3.details` triage fields for public HTTPS RPC shape, valid Web3 contract-env count, per-contract env validity booleans, and mock-mode status.
- Tightened `/ready` production Web3 configuration so a configured RPC must be public `https://` and at least one recognized contract env value must be a non-zero EVM address.
- Extended product smoke validation so Web3 readiness detail schema drift fails before launch handoff.
- Updated API, README, and operations docs to explain the Web3 readiness details without exposing secret values or contract addresses.

### External Checks
- MetaMask documents `wallet_addEthereumChain` network metadata including `rpcUrls`: https://docs.metamask.io/metamask-connect/evm/reference/json-rpc-api/wallet_addEthereumChain/
- EIP-3085 requires add-chain `rpcUrls` to be valid URLs: https://eips.ethereum.org/EIPS/eip-3085
- Polygon's current endpoint reference lists Polygon Amoy RPC metadata used by the Web3 readiness path: https://docs.polygon.technology/pos/reference/rpc-endpoints

### Verification
- `uv run python -m py_compile main.py tests\test_api_endpoints.py tests\test_product_smoke.py` from `backend` -> pass.
- `uv run pytest tests/test_api_endpoints.py::test_ready_marks_web3_available_in_mock_mode tests/test_api_endpoints.py::test_ready_does_not_accept_mock_mode_as_production_web3 tests/test_api_endpoints.py::test_ready_does_not_accept_non_https_production_web3_rpc tests/test_api_endpoints.py::test_ready_does_not_accept_malformed_production_web3_contract_address tests/test_product_smoke.py::test_product_smoke_validates_web3_readiness_detail_shape -q` from `backend` -> `5 passed`.
- `uv run pytest tests/test_api_endpoints.py tests/test_product_smoke.py tests/test_release_gate.py -q --maxfail=1` from `backend` -> `133 passed`.
- `git diff --check -- backend/main.py backend/tests/test_api_endpoints.py backend/tests/test_product_smoke.py scripts/product_smoke.py API_SPEC.md README.md OPERATIONS_RUNBOOK.md` -> pass; only existing CRLF replacement warnings.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-contracts --backend-tests tests/test_api_endpoints.py tests/test_product_smoke.py tests/test_release_gate.py --json-out ..\..\var\desci-release-gate-loop42-ready-web3-details.json` -> pass; backend targeted tests and frontend lint/typecheck/tests/build/bundle all passed, `6` gate steps OK.

### Result
- `/ready` now gives operators actionable Web3 triage without leaking RPC secret values or deployed contract addresses.
- Product smoke and release gate now catch malformed Web3 detail payloads before handoff.

## 2026-06-10 (Ready Web3 Handoff Summary)

### Scope
- Added product-smoke `ready_web3` evidence that copies the non-secret `/ready` Web3 triage object into runtime smoke JSON.
- Added release-gate parsing, validation, artifact-report fields, and parent `ready_web3_summary` promotion for product-smoke child evidence.
- Updated release-gate parent JSON Schema so dashboards and CI parsers can discover `ready_web3_summary`.
- Updated API, README, and operations docs to describe `ready_web3` and `ready_web3_summary` handoff behavior.

### External Checks
- MetaMask documents `wallet_addEthereumChain` as requiring chain ID plus chain metadata and shows HTTPS RPC URLs in example payloads: https://docs.metamask.io/metamask-connect/evm/reference/json-rpc-api/wallet_addEthereumChain/
- EIP-3085 requires `wallet_addEthereumChain` URL fields such as `rpcUrls` to be valid URLs and notes wallets should use web security practices such as HTTPS: https://eips.ethereum.org/EIPS/eip-3085
- Polygon's current Amoy endpoint reference lists chain ID `80002`, POL gas token, RPC `https://polygon-amoy.drpc.org`, and explorer `https://amoy.polygonscan.com/`: https://docs.polygon.technology/pos/reference/rpc-endpoints
- GitHub issue evidence from MetaMask and WalletConnect shows malformed or unsupported `wallet_addEthereumChain` RPC metadata remains a recurring integration failure mode, supporting explicit handoff visibility for RPC shape.

### Verification
- `uv run python -m py_compile ..\scripts\product_smoke.py ..\scripts\release_gate.py tests\test_product_smoke.py tests\test_release_gate.py` from `backend` -> pass.
- `uv run pytest tests/test_product_smoke.py::test_product_smoke_writes_json_evidence tests/test_product_smoke.py::test_product_smoke_validates_web3_readiness_detail_shape tests/test_release_gate.py::test_release_gate_fails_product_smoke_artifact_with_malformed_ready_web3 tests/test_release_gate.py::test_release_gate_json_report_exposes_runtime_smoke_artifacts tests/test_release_gate.py::test_release_gate_report_schema_documents_parent_contract -q` from `backend` -> `5 passed`.
- `uv run pytest tests/test_product_smoke.py tests/test_release_gate.py -q --maxfail=1` from `backend` -> `91 passed`.
- `uv run pytest tests/test_api_endpoints.py tests/test_product_smoke.py tests/test_release_gate.py -q --maxfail=1` from `backend` -> `134 passed`.
- `git diff --check -- scripts/product_smoke.py scripts/release_gate.py backend/tests/test_product_smoke.py backend/tests/test_release_gate.py API_SPEC.md README.md OPERATIONS_RUNBOOK.md` -> pass; only existing CRLF replacement warnings.
- `uv run python scripts\release_gate.py --print-report-schema | Select-String -Pattern 'ready_web3_summary' -Context 0,3` -> confirms schema output includes `ready_web3_summary`.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-contracts --backend-tests tests/test_api_endpoints.py tests/test_product_smoke.py tests/test_release_gate.py --json-out ..\..\var\desci-release-gate-loop43-ready-web3-handoff-summary.json` -> pass; backend targeted tests and frontend lint/typecheck/tests/build/bundle all passed, `6` gate steps OK.

### Result
- Runtime product-smoke artifacts now preserve Web3 readiness triage as a first-class non-secret handoff object.
- Release-gate parent reports can promote that Web3 triage into `ready_web3_summary`, so operators do not have to open child smoke JSON to see RPC/contract/mock-mode readiness.

## 2026-06-10 (Web3 Readiness Triage UI)

### Scope
- Added a compact Web3 launch triage band to `ProductReadinessPanel` so operators can see non-secret RPC shape, contract-env coverage, and mock-mode status directly on `/dashboard`.
- Kept the frontend whitelist-based: it renders only boolean/count fields from `/ready.checks.web3.details` and ignores unknown secret-shaped fields such as raw RPC URLs or contract addresses.
- Extended component tests and the `dashboard-readiness-refresh` browser smoke fixture to verify visible Web3 triage details and assert that secret-shaped fixture values are not rendered.

### External Checks
- W3C WCAG status-message guidance supports making dynamic readiness results perceivable without relying on hidden state: https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html
- Backstage documents entity `status` as human-readable health/state items with severity and messages, supporting compact operator-facing readiness summaries: https://backstage.io/docs/features/software-catalog/descriptor-format/#common-to-all-kinds-status
- Grafana's state timeline documentation describes visualizing service/application status and recurring health issues at a glance, supporting dense launch/ops dashboards: https://grafana.com/docs/grafana/latest/visualizations/panels-visualizations/visualizations/state-timeline/

### Verification
- `cmd /c "npx vitest run src/__tests__/components/ProductReadinessPanel.test.jsx --pool=vmThreads --maxWorkers=1 --isolate"` from `frontend` -> `1` test file passed, `8` tests passed.
- `uv run python -m py_compile scripts\browser_smoke.py` -> pass.
- `uv run pytest backend/tests/test_browser_smoke.py -q --maxfail=1` -> `32 passed`.
- `cmd /c "npx eslint src/components/ProductReadinessPanel.jsx src/__tests__/components/ProductReadinessPanel.test.jsx"` from `frontend` -> pass.
- `cmd /c "npm run typecheck"` from `frontend` -> pass.
- `git diff --check -- frontend/src/components/ProductReadinessPanel.jsx frontend/src/__tests__/components/ProductReadinessPanel.test.jsx scripts/browser_smoke.py` -> pass; only existing CRLF replacement warnings.
- Initial browser smoke against `127.0.0.1:5178` failed because the temporary Vite server had been started without `VITE_ENABLE_DEV_AUTH_BYPASS=true`, so `/dashboard` correctly redirected to `/login?next=/dashboard`.
- Restarted the Vite dev-auth server on `127.0.0.1:5178`, then `uv run python scripts\browser_smoke.py --frontend http://127.0.0.1:5178 --expect-dev-auth --skip-login-validation --only-check dashboard-readiness-refresh --timeout 25 --json-out ..\..\var\desci-browser-smoke-loop44-web3-readiness-triage.json` -> pass.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-smoke-step browser --runtime-frontend http://127.0.0.1:5178 --runtime-browser-expect-dev-auth --runtime-browser-only-check dashboard-readiness-refresh --runtime-browser-timeout 25 --runtime-evidence-dir ..\..\var --json-out ..\..\var\desci-release-gate-loop44-browser-web3-readiness-triage.json` -> pass; browser-smoke `1` step OK.
- Local Vite dev-auth server listener PID `39612` was stopped after verification, leaving no listener on port `5178`.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-contracts --backend-tests tests/test_browser_smoke.py --json-out ..\..\var\desci-release-gate-loop44-web3-readiness-triage.json` -> pass; backend browser-smoke tests plus frontend lint/typecheck/tests/build/bundle all passed, `6` gate steps OK.

### Result
- `/dashboard` now exposes the Web3 readiness handoff from `/ready` as actionable operator triage instead of requiring users to inspect JSON artifacts.
- The browser smoke and release gate prove the UI renders the expected RPC/contract/mock-mode status while suppressing raw secret-shaped RPC and contract values.

## 2026-06-10 (Web3 Launch Action Details)

### Scope
- Made `/launch.next_actions` detail-aware for the `web3` warning action.
- The Web3 action now derives remediation and `required_env` from non-secret `/ready.checks.web3.details` fields, naming only env keys to fix.
- Added backend coverage that production `MOCK_MODE`, non-public `WEB3_RPC_URL`, and missing NFT/DAO contract env values produce a concrete Web3 action without leaking raw RPC URLs or contract addresses.
- Updated ProductReadiness and dashboard browser-smoke fixtures so copy-all launch action payloads include the specific Web3 env fixes.
- Updated API, README, and operations docs to describe the Web3 action handoff behavior.

### External Checks
- MetaMask documents `wallet_addEthereumChain` as requiring chain ID plus chain metadata and HTTPS RPC URL examples: https://docs.metamask.io/metamask-connect/evm/reference/json-rpc-api/wallet_addEthereumChain/
- EIP-3085 requires `wallet_addEthereumChain` `rpcUrls` to be provided and valid URLs, supporting explicit RPC-shape remediation: https://eips.ethereum.org/EIPS/eip-3085
- Polygon's endpoint reference lists Amoy chain ID `80002`, gas token `POL`, RPC `https://polygon-amoy.drpc.org`, and explorer `https://amoy.polygonscan.com/`: https://docs.polygon.technology/pos/reference/rpc-endpoints

### Verification
- `uv run pytest tests/test_api_endpoints.py::test_launch_control_web3_action_uses_non_secret_readiness_details tests/test_api_endpoints.py::test_ready_does_not_accept_non_https_production_web3_rpc tests/test_api_endpoints.py::test_ready_does_not_accept_mock_mode_as_production_web3 -q` from `backend` -> `3 passed`.
- `cmd /c "npx vitest run src/__tests__/components/ProductReadinessPanel.test.jsx --pool=vmThreads --maxWorkers=1 --isolate"` from `frontend` -> `1` test file passed, `8` tests passed.
- `uv run python -m py_compile backend\main.py backend\tests\test_api_endpoints.py scripts\browser_smoke.py` -> pass.
- `uv run pytest tests/test_api_endpoints.py tests/test_browser_smoke.py -q --maxfail=1` from `backend` -> `76 passed`.
- `cmd /c "npx eslint src/__tests__/components/ProductReadinessPanel.test.jsx"` from `frontend` -> pass.
- `cmd /c "npm run typecheck"` from `frontend` -> pass.
- `git diff --check -- backend/main.py backend/tests/test_api_endpoints.py frontend/src/__tests__/components/ProductReadinessPanel.test.jsx scripts/browser_smoke.py API_SPEC.md README.md OPERATIONS_RUNBOOK.md` -> pass; only existing CRLF replacement warnings.
- Browser smoke direct run: `uv run python scripts\browser_smoke.py --frontend http://127.0.0.1:5179 --expect-dev-auth --skip-login-validation --only-check dashboard-readiness-refresh --timeout 25 --json-out ..\..\var\desci-browser-smoke-loop45-web3-action-details.json` -> pass.
- Release gate browser-only runtime run: `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-smoke-step browser --runtime-frontend http://127.0.0.1:5179 --runtime-browser-expect-dev-auth --runtime-browser-only-check dashboard-readiness-refresh --runtime-browser-timeout 25 --runtime-evidence-dir ..\..\var --json-out ..\..\var\desci-release-gate-loop45-browser-web3-action-details.json` -> pass; browser-smoke `1` step OK.
- Local Vite dev-auth server ran on `127.0.0.1:5179`; listener PID `25212` was stopped after verification, leaving no listener on port `5179`.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-contracts --backend-tests tests/test_api_endpoints.py tests/test_browser_smoke.py tests/test_product_smoke.py tests/test_release_gate.py --json-out ..\..\var\desci-release-gate-loop45-web3-action-details.json` -> pass; backend targeted tests and frontend lint/typecheck/tests/build/bundle all passed, `6` gate steps OK.

### Result
- Operators copying the Web3 launch action now get concrete env-key work: disable production `MOCK_MODE`, replace non-public `WEB3_RPC_URL`, and set missing DSCI/NFT/DAO contract address variables as applicable.
- The Web3 action remains non-secret: tests and browser smoke prove raw RPC URLs and contract addresses are not copied or rendered.

## 2026-06-10 (Launch Action Artifact Validation)

### Scope
- Strengthened `scripts/product_smoke.py` so live `/launch.next_actions` must contain object items with `id`, `required`, `status`, `remediation`, and `required_env`.
- Strengthened `scripts/release_gate.py` so product-smoke child artifacts with malformed launch-action items fail artifact validation instead of being promoted.
- Added raw-value guardrails that reject URLs, EVM addresses, and common secret-shaped tokens in launch action remediation or required-env payloads.
- Added regression coverage for malformed/secret-shaped launch actions in product-smoke and release-gate tests.
- Updated API, README, and operations docs to describe launch action item validation and non-secret payload requirements.

### External Checks
- JSON Schema's object validation model uses explicit properties and required fields, matching the launch-action item contract: https://json-schema.org/understanding-json-schema/reference/object
- GitHub secret scanning documentation treats token leakage as pattern-detectable evidence, supporting fail-closed checks for secret-shaped action payloads: https://docs.github.com/en/code-security/secret-scanning/introduction/about-secret-scanning
- OWASP Secrets Management guidance recommends preventing secrets from being logged or exposed in operational outputs: https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html

### Verification
- `uv run python -m py_compile scripts\product_smoke.py scripts\release_gate.py backend\tests\test_product_smoke.py backend\tests\test_release_gate.py` -> pass.
- `uv run pytest tests/test_product_smoke.py::test_assert_launch_rejects_malformed_or_secret_shaped_next_actions tests/test_release_gate.py::test_release_gate_fails_product_smoke_artifact_with_malformed_launch_action -q` from `backend` -> `2 passed`.
- `uv run pytest tests/test_product_smoke.py tests/test_release_gate.py -q --maxfail=1` from `backend` -> `93 passed`.
- Initial broader `tests/test_product_smoke.py tests/test_release_gate.py` run failed because two older release-gate fixtures still used the pre-validation `next_actions` item shape; updated those fixtures to keep their original schema-version and report-promotion test intent.
- `git diff --check -- scripts/product_smoke.py scripts/release_gate.py backend/tests/test_product_smoke.py backend/tests/test_release_gate.py` -> pass; only existing CRLF replacement warnings.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-contracts --backend-tests tests/test_product_smoke.py tests/test_release_gate.py --json-out ..\..\var\desci-release-gate-loop46-launch-action-artifact-validation.json` -> pass; backend targeted tests and frontend lint/typecheck/tests/build/bundle all passed, `6` gate steps OK.
- `uv run pytest tests/test_deployment_docs.py -q` from `backend` -> `6 passed`.
- `git diff --check -- scripts/product_smoke.py scripts/release_gate.py backend/tests/test_product_smoke.py backend/tests/test_release_gate.py API_SPEC.md README.md OPERATIONS_RUNBOOK.md` -> pass; only existing CRLF replacement warnings.

### Result
- Launch-action handoff evidence is now validated at both live smoke and release-gate artifact layers.
- Product-smoke/release-gate reports can no longer silently pass launch-action payloads that omit operator-critical fields or expose raw URLs, EVM addresses, or secret-shaped tokens.

## 2026-06-10 (Launch Action Summary Coverage)

### Scope
- Promoted validated product-smoke launch-action coverage into release-gate parent reports.
- `launch_handoff_summary` now includes `next_action_ids` and deduplicated `next_action_required_env` when the child product-smoke artifact validates successfully.
- Per-artifact reports now expose `json_launch_action_ids` and `json_launch_action_required_env` for dashboards and CI parsers.
- Updated the parent JSON Schema and operator docs to describe the new launch-action coverage fields.

### External Checks
- JSON Schema array documentation supports explicitly modeling item lists such as `next_action_ids` and `next_action_required_env`: https://json-schema.org/understanding-json-schema/reference/array
- JSON Schema object documentation supports named `properties` for parent report fields: https://json-schema.org/understanding-json-schema/reference/object
- GitHub Actions documents structured outputs as named values that later steps can consume, supporting machine-readable action coverage rather than prose-only handoff: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands

### Verification
- `uv run python -m py_compile scripts\release_gate.py backend\tests\test_release_gate.py` -> pass.
- `uv run pytest tests/test_release_gate.py::test_release_gate_launch_action_coverage_preserves_order_and_dedupes tests/test_release_gate.py::test_release_gate_json_report_exposes_runtime_smoke_artifacts tests/test_release_gate.py::test_release_gate_report_schema_documents_parent_contract -q` from `backend` -> `3 passed`.
- `uv run python scripts\release_gate.py --print-report-schema | Select-String -Pattern 'next_action_ids|next_action_required_env' -Context 0,2` -> confirms schema output includes both fields.
- `uv run pytest tests/test_release_gate.py tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `85 passed`.
- `git diff --check -- scripts/release_gate.py backend/tests/test_release_gate.py API_SPEC.md README.md OPERATIONS_RUNBOOK.md` -> pass; only existing CRLF replacement warnings.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-contracts --backend-tests tests/test_release_gate.py tests/test_deployment_docs.py --json-out ..\..\var\desci-release-gate-loop47-launch-action-summary-coverage.json` -> pass; backend targeted tests and frontend lint/typecheck/tests/build/bundle all passed, `6` gate steps OK.

### Result
- Validated runtime smoke handoff reports can now show which launch actions and env keys require operator attention without opening the child product-smoke JSON.
- Invalid launch handoff artifacts still do not get promoted, so the new summary fields remain tied to validated evidence only.

## 2026-06-10 (Browser Launch Action Coverage)

### Scope
- Extended browser-smoke `launch_control` JSON evidence with fixture-derived `next_action_ids` and deduplicated `next_action_required_env`.
- Strengthened release-gate browser launch-control validation so action coverage must be present, count-aligned, and env-key only.
- Promoted validated browser action coverage into per-artifact `json_browser_launch_action_ids`, `json_browser_launch_action_required_env`, and top-level `browser_launch_control_summary`.
- Updated the parent JSON Schema and operator docs to describe browser fixture action coverage alongside live API `launch_handoff_summary` coverage.

### External Checks
- JSON Schema array documentation supports explicit machine-readable string lists for `next_action_ids` and `next_action_required_env`: https://json-schema.org/understanding-json-schema/reference/array
- JSON Schema object documentation supports named parent-report properties for nested summaries: https://json-schema.org/understanding-json-schema/reference/object
- GitHub Actions workflow commands document named outputs for downstream automation, supporting structured action coverage over prose-only handoff: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands

### Verification
- `uv run python -m py_compile scripts\browser_smoke.py scripts\release_gate.py backend\tests\test_browser_smoke.py backend\tests\test_release_gate.py` -> pass.
- `uv run pytest tests/test_browser_smoke.py::test_browser_smoke_json_evidence_exposes_launch_control tests/test_release_gate.py::test_release_gate_json_report_exposes_browser_launch_control_summary tests/test_release_gate.py::test_release_gate_report_schema_documents_parent_contract -q` from `backend` -> `3 passed`.
- `uv run pytest tests/test_browser_smoke.py tests/test_release_gate.py -q --maxfail=1` from `backend` -> `111 passed`.
- `git diff --check -- scripts/browser_smoke.py scripts/release_gate.py backend/tests/test_browser_smoke.py backend/tests/test_release_gate.py API_SPEC.md README.md OPERATIONS_RUNBOOK.md` -> pass; only existing LF/CRLF replacement warnings.
- Dev-auth Vite on `http://127.0.0.1:5180` plus `uv run python scripts\browser_smoke.py --frontend http://127.0.0.1:5180 --expect-dev-auth --skip-login-validation --only-check dashboard-readiness-refresh --timeout 25 --json-out ..\..\var\desci-browser-smoke-loop48-browser-launch-action-summary.json` -> pass; JSON contains `stripe,stripe_return_url,auth,stripe_portal,web3` and the expected deduplicated env-key list.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-smoke-step browser --runtime-frontend http://127.0.0.1:5180 --runtime-browser-expect-dev-auth --runtime-browser-only-check dashboard-readiness-refresh --runtime-browser-timeout 25 --runtime-evidence-dir ..\..\var --json-out ..\..\var\desci-release-gate-loop48-browser-launch-action-summary.json` -> pass; parent summary and artifact report preserve the same action/env coverage.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-contracts --backend-tests tests/test_browser_smoke.py tests/test_release_gate.py --json-out ..\..\var\desci-release-gate-loop48-browser-launch-action-coverage.json` -> pass; backend targeted tests and frontend lint/typecheck/tests/build/bundle all passed, `6` gate steps OK.
- `uv run python scripts\release_gate.py --print-report-schema | Select-String -Pattern 'browser_launch_control_summary|next_action_ids|next_action_required_env' -Context 0,2` -> confirms the browser summary schema exposes both action coverage fields.

### Result
- Browser fixture-backed launch-control proof now carries the same operator action ids and env-key coverage shape as live API handoff proof.
- Release-gate parent reports can compare `browser_launch_control_summary` and `launch_handoff_summary` action coverage without opening child JSON artifacts.

## 2026-06-10 (Launch Action Coverage Comparison)

### Scope
- Added top-level release-gate `launch_action_coverage_comparison` when both validated live product-smoke `launch_handoff_summary` and browser-smoke `browser_launch_control_summary` are present.
- The comparison reports `match` or `drift`, exact action/env list match booleans, shared action/env keys, and live-only or browser-only gaps.
- Documented the comparison field in API spec, README, deployment guide, and operations runbook.
- Added regression coverage for both direct drift calculation and parent-report promotion from validated product/browser child artifacts.

### External Checks
- JSON Schema object documentation supports named nested `properties` for parent-report comparison objects: https://json-schema.org/understanding-json-schema/reference/object
- GitHub Actions job summaries are intended to surface important run information without opening logs, supporting a top-level comparison summary in release-gate reports: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands
- OpenTelemetry semantic conventions emphasize consistent naming for easier correlation and consumption, supporting stable live/browser comparison field names: https://opentelemetry.io/docs/specs/semconv/

### Verification
- `uv run python -m py_compile scripts\release_gate.py backend\tests\test_release_gate.py` -> pass.
- `uv run pytest tests/test_release_gate.py::test_release_gate_launch_action_coverage_comparison_reports_drift tests/test_release_gate.py::test_release_gate_json_report_compares_live_and_browser_launch_action_coverage tests/test_release_gate.py::test_release_gate_report_schema_documents_parent_contract -q` from `backend` -> `3 passed`.
- `uv run pytest tests/test_deployment_docs.py -q` from `backend` -> `6 passed`.
- `uv run python scripts\release_gate.py --print-report-schema | Select-String -Pattern 'launch_action_coverage_comparison|live_only_action_ids|browser_only_required_env' -Context 0,2` -> confirms the parent schema exposes the comparison object and gap fields.
- `uv run pytest tests/test_release_gate.py tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `87 passed`.
- `git diff --check -- scripts/release_gate.py backend/tests/test_release_gate.py API_SPEC.md README.md OPERATIONS_RUNBOOK.md DEPLOYMENT_GUIDE.md` -> pass; only existing LF/CRLF replacement warnings.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-contracts --backend-tests tests/test_release_gate.py tests/test_deployment_docs.py --json-out ..\..\var\desci-release-gate-loop49-launch-action-coverage-comparison.json` -> pass; backend targeted tests and frontend lint/typecheck/tests/build/bundle all passed, `6` gate steps OK. This static scoped gate has no runtime child artifacts, so it correctly does not include `launch_action_coverage_comparison`.

### Result
- Release-gate parent reports can now expose whether live launch handoff and browser dashboard proof agree on operator action/env coverage.
- Operators can triage live-only and browser-only action/env gaps without opening product-smoke or browser-smoke child JSON artifacts.

## 2026-06-10 (Strict Launch Action Coverage Gate)

### Scope
- Added release-gate `--runtime-smoke-strict-action-coverage` for production handoff runs that must fail when live `/launch` action coverage drifts from browser dashboard launch-control proof.
- The strict mode evaluates only after normal steps pass and is skipped for `--dry-run`, preserving dry-run's stale-artifact-safe behavior.
- On drift, release-gate appends a synthetic `launch-action-coverage` failed result with explicit live-only and browser-only action/env gaps.
- Updated API spec, README, deployment guide, and operations runbook to distinguish evidence-only comparison from strict failure mode.

### External Checks
- GitHub Actions uses nonzero exit codes to mark an action/check as failed, supporting a nonzero release-gate exit when strict handoff drift is detected: https://docs.github.com/actions/creating-actions/setting-exit-codes-for-actions
- GitHub Actions contexts expose previous step information for conditional behavior, supporting a parent-level check that runs after runtime smoke steps have produced evidence: https://docs.github.com/en/actions/reference/workflows-and-actions/contexts
- JSON Schema `enum` constrains status values to a fixed set, supporting the existing `match`/`drift` comparison status contract: https://json-schema.org/understanding-json-schema/reference/enum

### Verification
- `uv run python -m py_compile scripts\release_gate.py backend\tests\test_release_gate.py` -> pass.
- `uv run pytest tests/test_release_gate.py::test_release_gate_strict_launch_action_coverage_result_reports_drift tests/test_release_gate.py::test_release_gate_strict_launch_action_coverage_result_passes_match tests/test_release_gate.py::test_release_gate_cli_strict_action_coverage_fails_on_drift -q` from `backend` -> `3 passed`.
- `uv run pytest tests/test_release_gate.py::test_release_gate_cli_strict_action_coverage_fails_on_drift tests/test_release_gate.py::test_release_gate_cli_strict_action_coverage_skips_dry_run tests/test_release_gate.py::test_release_gate_strict_launch_action_coverage_result_reports_drift -q` from `backend` -> `3 passed`.
- `uv run pytest tests/test_release_gate.py tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `91 passed`.
- `git diff --check -- scripts\release_gate.py backend\tests\test_release_gate.py API_SPEC.md README.md OPERATIONS_RUNBOOK.md DEPLOYMENT_GUIDE.md` -> pass; only existing LF/CRLF replacement warnings.
- `uv run python scripts\release_gate.py --runtime-smoke --runtime-smoke-strict-action-coverage --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --dry-run --json-out ..\..\var\desci-release-gate-loop50-strict-action-coverage-dry-run.json` -> pass; dry-run report has only product/browser smoke dry-run results and no comparison evaluation.
- `uv run python scripts\release_gate.py --help | Select-String -Pattern 'runtime-smoke-strict-action-coverage' -Context 0,2` -> confirms the new CLI flag is visible.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-contracts --backend-tests tests/test_release_gate.py tests/test_deployment_docs.py --json-out ..\..\var\desci-release-gate-loop50-strict-action-coverage.json` -> pass; backend targeted tests and frontend lint/typecheck/tests/build/bundle all passed, `6` gate steps OK.

### Result
- Production handoff runs can now choose fail-closed launch action coverage comparison without changing default local/runtime evidence behavior.
- Dry-run remains non-destructive and does not parse stale runtime artifacts even when the strict action coverage flag is supplied.

## 2026-06-10 (Strict Launch Action Coverage Runtime Fixture)

### Scope
- Added `scripts/launch_fixture_server.py`, a stdlib local API harness that serves `/`, `/health`, `/ready`, and `/launch` for product-smoke action-coverage parity checks.
- The fixture reuses browser-smoke dashboard readiness and launch payload functions so the local product-smoke API and browser dashboard launch-control proof share the same launch action source.
- Tightened the browser dashboard fixture shape by adding `required_env: []` to the `auth` launch action and `configured`/`available` booleans to the Web3 readiness check, matching product-smoke and release-gate artifact validation.
- Documented the local strict action-coverage proof path in README, deployment guide, and operations runbook, including the warning to omit `--runtime-smoke-strict-ready` because the fixture intentionally serves a blocked no-go launch payload.

### External Checks
- Python `http.server` documents that `BaseHTTPRequestHandler` must be subclassed to implement request methods, matching the lightweight local fixture handler: https://docs.python.org/3/library/http.server.html
- GitHub Actions service-container guidance documents localhost access for runner-host services and health checks before dependent steps, matching the local service-before-gate verification model: https://docs.github.com/en/actions/tutorials/use-containerized-services/create-postgresql-service-containers

### Verification
- `uv run python -m py_compile scripts\launch_fixture_server.py scripts\browser_smoke.py backend\tests\test_launch_fixture_server.py` -> pass.
- `uv run pytest tests/test_launch_fixture_server.py tests/test_browser_smoke.py::test_dashboard_smoke_fixtures_keep_ready_and_launch_consistent tests/test_browser_smoke.py::test_browser_smoke_json_evidence_exposes_launch_control -q` from `backend` -> `4 passed`.
- Strict runtime release gate with fixture API on `127.0.0.1:8077` and dev-auth Vite on `127.0.0.1:5181`: `uv run python scripts\release_gate.py --runtime-smoke --runtime-smoke-strict-action-coverage --runtime-api http://127.0.0.1:8077 --runtime-frontend http://127.0.0.1:5181 --runtime-browser-expect-dev-auth --runtime-browser-only-check dashboard-readiness-refresh --runtime-browser-timeout 25 --runtime-evidence-dir ..\..\var --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --json-out ..\..\var\desci-release-gate-loop51-strict-action-match.json` -> pass; parent JSON has `ok=true`, `summary.failed=0`, `launch_action_coverage_comparison.status=match`, `action_ids_match=true`, and `required_env_match=true`.
- `uv run pytest tests/test_launch_fixture_server.py tests/test_browser_smoke.py::test_dashboard_smoke_fixtures_keep_ready_and_launch_consistent tests/test_browser_smoke.py::test_browser_smoke_json_evidence_exposes_launch_control tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `10 passed`.
- `git diff --check -- scripts/launch_fixture_server.py scripts/browser_smoke.py backend/tests/test_launch_fixture_server.py README.md OPERATIONS_RUNBOOK.md DEPLOYMENT_GUIDE.md` -> pass; only existing LF-to-CRLF working-copy warnings.
- Scoped release gate with frontend enabled: backend tests, frontend lint, and frontend typecheck passed, but `frontend-tests` failed twice with `[vitest-pool-runner]: Timeout waiting for worker to respond`; this was recorded in `var/desci-release-gate-loop51-fixture-harness.json` as an environment/runtime worker-startup failure unrelated to the fixture API.
- Backend/documentation-only release gate: `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-contracts --skip-frontend --backend-tests tests/test_launch_fixture_server.py tests/test_browser_smoke.py tests/test_deployment_docs.py --json-out ..\..\var\desci-release-gate-loop51-fixture-harness-backend-only.json` -> pass; `40 passed`, `1` gate step OK.

### Result
- Operators can now reproduce a strict action-coverage `match` path locally with real product-smoke, browser-smoke, and release-gate child artifacts before live endpoints are available.
- The browser dashboard fixture now satisfies the same launch action and Web3 readiness artifact shape required by product-smoke and release-gate validation.

## 2026-06-10 (Frontend Vitest Worker Fallback)

### Scope
- Hardened `frontend/scripts/run-vitest-split.mjs` so the canonical frontend test runner detects Vitest worker startup failures and retries only that infrastructure failure mode with `vmThreads + isolate`.
- Preserved the faster baseline path: the no-isolate subset still starts with `threads --maxWorkers=1 --no-isolate`, and isolated files still start with `threads --maxWorkers=1 --isolate`.
- Targeted test invocations that use the runner keep the existing `forks + isolate` first attempt and gain the same worker-startup fallback.
- Added deployment-doc regression coverage that checks the runner contains the worker-startup signature and the `vmThreads` fallback.

### External Checks
- Vitest performance docs state isolated test files map to pool-specific mechanisms, and that disabling file parallelism can improve startup time: https://vitest.dev/guide/improving-performance
- Vitest pool docs list `threads`, `forks`, `vmThreads`, and `vmForks`, and warn about `vmThreads` caveats; this supports using it as a fallback rather than the default path: https://vitest.dev/config/pool
- Vitest advanced pool docs describe the built-in pool runners and their isolation mechanisms, supporting explicit pool selection for this Windows runner: https://vitest.dev/guide/advanced/pool

### A/B Decision
- A: keep the current `threads` split runner only. Fast when workers start, but the Loop 51 release gate failed twice at `frontend-tests` with `[vitest-pool-runner]: Timeout waiting for worker to respond`.
- B: keep `threads` as the default, but retry only recognized worker startup failures with `vmThreads + isolate`. This is slower only on infrastructure failure and does not hide normal test assertion failures.
- Selected B because `npm run test` proved the exact failure recovered: first `threads` attempt hit the worker timeout, fallback passed `28` fast files / `145` tests and `7` isolated files / `32` tests.

### Verification
- `node --check scripts\run-vitest-split.mjs` from `frontend` -> pass.
- `uv run pytest tests/test_deployment_docs.py::test_frontend_vitest_split_runner_has_worker_startup_fallback -q` from `backend` -> `1 passed`.
- `git diff --check -- frontend/scripts/run-vitest-split.mjs backend/tests/test_deployment_docs.py` -> pass.
- `npm run test` from `frontend` -> pass; initial no-isolate `threads` run emitted `[vitest-pool-runner]: Timeout waiting for worker to respond`, fallback retried with `vmThreads + isolate`, then `28` files / `145` tests and `7` files / `32` tests passed.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-contracts --backend-tests tests/test_launch_fixture_server.py tests/test_browser_smoke.py tests/test_deployment_docs.py --json-out ..\..\var\desci-release-gate-loop52-vitest-worker-fallback.json` -> pass; backend tests, frontend lint, frontend typecheck, frontend tests, frontend build, and frontend bundle all passed (`6` gate steps OK).

### Result
- The release-gate frontend test step no longer fails solely because the Windows runner cannot start the first Vitest thread worker.
- Real test failures still return nonzero because fallback is gated on the explicit Vitest pool startup error signature and must pass the same test file set.

## 2026-06-10 (Readiness Panel Launch Drift Coverage)

### Scope
- Extended `ProductReadinessPanel` launch drift detection beyond status, summary, and blocker mismatches to include `/ready` failed/warning check coverage versus `/launch.next_actions` action IDs and required env keys.
- Compared action/env coverage as sets, not queue order, so `/launch` can still prioritize required blockers before warnings without creating a false dashboard drift alert.
- Added visible warning copy for action ID and required env drift in English and Korean message catalogs.
- Added component regression coverage for true action/env drift and for the non-drift case where `/launch` reorders the same `/ready` coverage.

### External Checks
- MDN documents `role="alert"` as an assertive live region for important, time-sensitive messages, supporting the existing alert surface for launch-control drift: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/alert_role
- Testing Library documents `queryBy...` returning `null` when an element is absent, supporting the regression assertion that reordered matching coverage does not render a drift alert: https://testing-library.com/docs/queries/about/

### A/B Decision
- A: keep the panel drift alert limited to status, summary, and launch blockers. This avoids UI change but leaves a gap where the release gate can fail strict action coverage while the dashboard does not show why.
- B: add action ID and required env coverage drift to the panel while treating queue order as non-semantic. This exposes the same operator handoff class the gate now checks without penalizing normal blocker-first ordering.
- Selected B because it makes runtime drift actionable in the dashboard and keeps the browser fixture's blocker-priority ordering clean.

### Verification
- `cmd /c "npx vitest run src/__tests__/components/ProductReadinessPanel.test.jsx --pool=vmThreads --maxWorkers=1 --isolate"` from `frontend` -> `9 passed`.
- `uv run pytest tests/test_browser_smoke.py::test_dashboard_smoke_fixtures_keep_ready_and_launch_consistent -q` from `backend` -> `1 passed`.
- `git diff --check -- frontend/src/components/ProductReadinessPanel.jsx frontend/src/__tests__/components/ProductReadinessPanel.test.jsx frontend/src/i18n/messages.js` -> pass; only existing LF-to-CRLF working-copy warnings.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-contracts --backend-tests tests/test_browser_smoke.py::test_dashboard_smoke_fixtures_keep_ready_and_launch_consistent --json-out ..\..\var\desci-release-gate-loop53-readiness-drift-ui.json` -> pass; backend fixture consistency, frontend lint, typecheck, tests, build, and bundle all passed (`6` gate steps OK).

### Result
- The dashboard now gives operators visible action/env drift evidence when `/ready` and `/launch` disagree.
- Matching action/env coverage stays quiet even when `/launch` reorders the same work queue for handoff priority.

## 2026-06-10 (Product Smoke Ready/Launch Action Coverage)

### Scope
- Strengthened `scripts/product_smoke.py` so one live product-smoke run now checks that `/launch.next_actions` action IDs and deduplicated required env keys match the failed/warning `/ready.checks` coverage.
- Kept the comparison order-insensitive so `/launch` can present required blockers before warnings without creating a false drift failure.
- Added Web3-specific expected env derivation from `/ready.checks.web3.details`, matching the backend `/launch` behavior that returns only the non-secret mock/RPC/missing-contract env keys needing operator action.
- Documented the single-run ready/launch action coverage contract in API, README, deployment guide, and operations runbook handoff notes.

### External Checks
- JSON Schema array documentation treats JSON arrays as ordered elements and documents uniqueness constraints, supporting explicit action/env coverage lists with deduped operator keys: https://json-schema.org/understanding-json-schema/reference/array
- GitHub Actions documents nonzero exit codes as failed check-run status, supporting product-smoke failures when live `/ready` and `/launch` action evidence drifts: https://docs.github.com/en/actions/how-tos/create-and-publish-actions/set-exit-codes

### A/B Decision
- A: rely only on release-gate live-vs-browser action coverage comparison. This catches handoff drift late, but a live API can still emit internally inconsistent `/ready` and `/launch` evidence in the child product-smoke artifact.
- B: add product-smoke single-run ready/launch action coverage validation before release-gate artifact promotion. This fails closer to the live runtime source and keeps the parent comparison based on cleaner child evidence.
- Selected B because it closes the remaining live API consistency gap without changing endpoint behavior or broadening environment requirements.

### Verification
- `uv run python -m py_compile scripts\product_smoke.py backend\tests\test_product_smoke.py` -> pass.
- `uv run pytest tests/test_product_smoke.py::test_ready_launch_consistency_rejects_action_coverage_drift tests/test_product_smoke.py::test_ready_launch_consistency_allows_reordered_action_coverage tests/test_product_smoke.py::test_ready_launch_consistency_derives_web3_action_env_from_details -q` from `backend` -> `3 passed`.
- `uv run pytest tests/test_product_smoke.py -q --maxfail=1` from `backend` -> `18 passed`.
- `uv run pytest tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `7 passed`.
- `git diff --check -- scripts/product_smoke.py backend/tests/test_product_smoke.py API_SPEC.md README.md OPERATIONS_RUNBOOK.md DEPLOYMENT_GUIDE.md` -> pass; only existing LF-to-CRLF working-copy warnings.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-contracts --backend-tests tests/test_product_smoke.py tests/test_deployment_docs.py --json-out ..\..\var\desci-release-gate-loop54-product-smoke-action-coverage.json` -> pass; backend product/docs tests, frontend lint, typecheck, tests, build, and bundle all passed (`6` gate steps OK).

### Result
- Product smoke now fails live runtime handoff drift before release-gate parent comparison, including action IDs and required env coverage.
- Web3 remains precise: smoke expects the same details-derived env action set that `/launch` returns, avoiding false failures from the broader static Web3 readiness checklist.

## 2026-06-10 (Product Smoke Ready/Launch Coverage Artifact)

### Scope
- Added structured `ready_launch_action_coverage` evidence to product-smoke JSON so same-run `/ready` and `/launch` action drift can be triaged without parsing failure strings.
- The object is emitted at the top level and copied into the `launch` check report when both endpoint responses are available.
- The artifact records `match` or `drift`, action/env match booleans, ready/launch action IDs, shared IDs, ready-only IDs, launch-only IDs, ready/launch required env keys, shared env keys, and ready-only/launch-only env gaps.
- Added regression coverage for both the clean match artifact and a drift artifact that disagrees on action ID and required env keys.
- Extended deployment-doc regression coverage so API spec, README, operations runbook, deployment guide, and product-smoke code all keep the new evidence field visible.

### External Checks
- JSON Schema object documentation defines object properties as named key-value pairs with per-property schemas, supporting a nested evidence object instead of opaque error text: https://json-schema.org/understanding-json-schema/reference/object
- GitHub Actions workflow-command documentation describes job summaries as a way to show important run information without opening raw logs, reinforcing that CI handoff data should be consumable outside console failure strings: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands

### A/B Decision
- A: keep same-run action/env drift only in product-smoke failure strings and launch check failures. This is minimal but forces release dashboards and CI operators to parse text to understand which side drifted.
- B: add a version-compatible structured `ready_launch_action_coverage` object to the product-smoke child JSON while preserving existing failure strings. This keeps current failure behavior and makes drift gaps machine-readable.
- Selected B because it is additive, does not change endpoint behavior, and gives release-gate/dashboard consumers explicit ready-only and launch-only action/env evidence.

### Verification
- `uv run python -m py_compile scripts\product_smoke.py backend\tests\test_product_smoke.py backend\tests\test_deployment_docs.py` -> pass.
- `uv run pytest tests/test_product_smoke.py::test_product_smoke_writes_json_evidence tests/test_product_smoke.py::test_product_smoke_json_evidence_exposes_ready_launch_action_coverage_drift -q` from `backend` -> `2 passed`.
- `uv run pytest tests/test_product_smoke.py -q --maxfail=1` from `backend` -> `19 passed`.
- `uv run pytest tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `7 passed`.
- `git diff --check -- scripts/product_smoke.py backend/tests/test_product_smoke.py backend/tests/test_deployment_docs.py API_SPEC.md README.md OPERATIONS_RUNBOOK.md DEPLOYMENT_GUIDE.md QC_LOG.md` -> pass; only existing LF-to-CRLF working-copy warnings.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-contracts --backend-tests tests/test_product_smoke.py tests/test_deployment_docs.py --json-out ..\..\var\desci-release-gate-loop55-ready-launch-action-coverage-artifact.json` -> pass; backend product/docs tests, frontend lint, typecheck, tests, build, and bundle all passed (`6` gate steps OK). The frontend Vitest no-isolate subset hit the known worker startup timeout once, retried through the existing `vmThreads + isolate` fallback, and the release gate still completed with `ok=true`.

### Result
- Product-smoke child evidence now names the exact ready-vs-launch action/env coverage gaps for both failure triage and downstream dashboard/CI consumption.
- Existing failure strings remain intact, but structured consumers no longer need to parse those strings to identify ready-only or launch-only drift.

## 2026-06-10 (Release Gate Ready/Launch Coverage Parent Summary)

### Scope
- Promoted validated product-smoke `ready_launch_action_coverage` child evidence into top-level release-gate `ready_launch_action_coverage_summary`.
- Added release-gate artifact validation for the coverage object when present, including status enum, action/env match booleans, and string-list gap fields.
- Added artifact flattening fields under `json_ready_launch_*` so `artifact_reports` expose the child coverage object without requiring dashboards to open the child JSON.
- Added parent schema coverage for `ready_launch_action_coverage_summary`.
- Updated API spec, README, deployment guide, and operations runbook to document the parent summary field.

### External Checks
- GitHub Actions job summaries document surfacing important run information outside raw logs, supporting parent-level triage summaries: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands
- GitHub Actions artifacts documentation describes build/test outputs as debuggable workflow artifacts, supporting validated child evidence plus parent summaries: https://docs.github.com/en/actions/tutorials/store-and-share-data
- `pytest-json-report` documents JSON reports for processing by other applications and supports summary-only reports, matching the parent-summary pattern for downstream release dashboards: https://github.com/numirias/pytest-json-report

### A/B Decision
- A: keep `ready_launch_action_coverage` only in the product-smoke child artifact. This preserves raw evidence but forces parent-report consumers to locate and parse the child JSON.
- B: validate and promote the same-run coverage object into the release-gate parent report while preserving the child artifact as source evidence.
- Selected B because it matches existing `launch_handoff_summary` and `ready_web3_summary` patterns, is additive to schema version 1, and improves dashboard/CI triage without changing endpoint behavior.

### Verification
- `uv run python -m py_compile scripts\release_gate.py backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py` -> pass.
- `uv run pytest tests/test_release_gate.py::test_release_gate_report_schema_documents_parent_contract tests/test_release_gate.py::test_release_gate_json_report_exposes_runtime_smoke_artifacts tests/test_release_gate.py::test_release_gate_fails_product_smoke_artifact_with_malformed_ready_launch_coverage -q` from `backend` -> `3 passed`.
- `uv run pytest tests/test_release_gate.py -q --maxfail=1` from `backend` -> `86 passed`.
- `uv run pytest tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `7 passed`.
- `uv run pytest tests/test_product_smoke.py -q --maxfail=1` from `backend` -> `19 passed`.
- `git diff --check -- scripts/release_gate.py scripts/product_smoke.py backend/tests/test_release_gate.py backend/tests/test_product_smoke.py backend/tests/test_deployment_docs.py API_SPEC.md README.md OPERATIONS_RUNBOOK.md DEPLOYMENT_GUIDE.md QC_LOG.md` -> pass; only existing LF-to-CRLF working-copy warnings.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-contracts --backend-tests tests/test_release_gate.py tests/test_product_smoke.py tests/test_deployment_docs.py --json-out ..\..\var\desci-release-gate-loop56-ready-launch-coverage-parent-summary.json` -> pass; backend release/product/docs tests, frontend lint, typecheck, tests, build, and bundle all passed (`6` gate steps OK). The frontend Vitest no-isolate subset hit the known worker startup timeout once, retried through the existing `vmThreads + isolate` fallback, and the release gate completed with `ok=true`.
- Fixture runtime product smoke through release gate: `uv run python scripts\release_gate.py --runtime-smoke --runtime-smoke-step product --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-api http://127.0.0.1:8091 --runtime-frontend http://127.0.0.1:8091 --runtime-evidence-dir ..\..\var\loop56-runtime --json-out ..\..\var\desci-release-gate-loop56-runtime-product-parent-summary.json` -> pass; parent `ready_launch_action_coverage_summary.status=match`.

### Result
- Release-gate parent reports now expose same-run `/ready` vs `/launch` action/env coverage gaps directly.
- Invalid coverage objects remain blocked at child artifact validation and are not promoted into parent handoff summaries.

## 2026-06-10 (Ready/Launch Coverage Drift Fail-Closed Validation)

### Scope
- Strengthened release-gate product-smoke artifact validation so `ready_launch_action_coverage.status=drift` cannot be paired with child artifact `ok=true`.
- Kept the existing structured validation for coverage status, match booleans, and ready/launch gap arrays.
- Added a regression test for the inconsistent stale/hand-edited artifact case where same-run coverage drifts but the child artifact still claims success.
- Documented the fail-closed condition in API spec, README, deployment guide, and operations runbook.

### External Checks
- JSON Schema conditional validation documents that conditional subschemas should enforce consistency when one field implies another, supporting the status/boolean consistency guard: https://json-schema.org/understanding-json-schema/reference/conditionals
- GitHub Actions exit-code documentation maps nonzero exit codes to failed check-run status, supporting the rule that drift evidence must not remain an `ok=true` release artifact: https://docs.github.com/en/actions/how-tos/create-and-publish-actions/set-exit-codes
- `pytest-json-report` documents JSON reports for processing by other applications, reinforcing that summary/status fields must remain internally consistent for downstream consumers: https://github.com/numirias/pytest-json-report

### A/B Decision
- A: keep validation limited to shape and allow a child artifact to say `status=drift` while still claiming `ok=true`. This keeps the schema loose but risks promoting contradictory parent evidence.
- B: fail artifact validation when same-run ready/launch coverage drifts but product-smoke reports `ok=true`.
- Selected B because product-smoke is supposed to return nonzero on drift, so this catches stale or edited evidence without changing the normal runtime path.

### Verification
- `uv run python -m py_compile scripts\release_gate.py backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py` -> pass.
- `uv run pytest tests/test_release_gate.py::test_release_gate_fails_product_smoke_artifact_when_ready_launch_coverage_drifts_but_ok tests/test_release_gate.py::test_release_gate_fails_product_smoke_artifact_with_malformed_ready_launch_coverage tests/test_release_gate.py::test_release_gate_json_report_exposes_runtime_smoke_artifacts -q` from `backend` -> `3 passed`.
- `uv run pytest tests/test_release_gate.py -q --maxfail=1` from `backend` -> `87 passed`.
- `uv run pytest tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `7 passed`.
- `uv run pytest tests/test_product_smoke.py -q --maxfail=1` from `backend` -> `19 passed`.
- `git diff --check -- scripts\release_gate.py scripts\product_smoke.py backend\tests\test_release_gate.py backend\tests\test_product_smoke.py backend\tests\test_deployment_docs.py API_SPEC.md README.md OPERATIONS_RUNBOOK.md DEPLOYMENT_GUIDE.md QC_LOG.md` -> pass; only existing LF-to-CRLF working-copy warnings.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-contracts --backend-tests tests/test_release_gate.py tests/test_product_smoke.py tests/test_deployment_docs.py --json-out ..\..\var\desci-release-gate-loop57-ready-launch-coverage-fail-closed.json` -> pass; backend release/product/docs tests, frontend lint, typecheck, tests, build, and bundle all passed (`6` gate steps OK).

### Result
- Same-run ready/launch coverage drift now fails closed at the release-gate child artifact boundary.
- Contradictory `drift` plus `ok=true` evidence cannot be promoted into parent `ready_launch_action_coverage_summary`.

## 2026-06-10 (Grant Discovery Missing Source Package Readiness)

### Scope
- Strengthened grant discovery application briefs so indexed opportunities without an original sponsor URL are treated as incomplete source/package evidence.
- Changed the first next action for missing-source notices from "open the original notice" to locating the original sponsor notice or application package before committing effort.
- Added a readiness penalty and explicit risk/evidence entries when the source URL or application package is missing.
- Updated API and README documentation for `/discover/grants` source/package risk.

### External Checks
- Grants.gov Search Grants documentation distinguishes Forecasted, Posted, Closed, and Archived statuses and instructs applicants to open opportunity details from search results: https://www.grants.gov/help/search-grants/search-grants-tab
- Grants.gov applicant guidance says Workspace starts from selecting a grant opportunity and then applying through a workspace package: https://www.grants.gov/quick-start-guide/applicants
- Grants.gov Workspace help documents individual form downloads from the application package Forms tab, supporting source/package evidence as a readiness requirement: https://www.grants.gov/help/manage-workspaces/download-pdf-forms
- Grants.gov applicant FAQs recommend verifying submitted application package contents from the Workspace details tab: https://www.grants.gov/applicants/applicant-faqs

### A/B Decision
- A: keep the existing frontend-only "source unavailable" display. This warns the visible Funding Radar card but loses the risk when Match Studio, proposal generation, or downstream automation consumes only `application_brief`.
- B: make the backend `application_brief` itself carry missing source/application-package evidence, risk, readiness impact, and a corrected next action.
- Selected B because the Grants.gov application flow depends on opportunity/package/form evidence, and the backend brief is the shared contract across UI handoff, matching, and proposal preparation.

### Verification
- `uv run python -m py_compile backend\services\grant_discovery.py backend\tests\test_grant_discovery.py` -> pass.
- `uv run pytest tests/test_grant_discovery.py -q --maxfail=1` from `backend` -> `6 passed`.
- `uv run pytest tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `7 passed`.
- `git diff --check -- backend/services/grant_discovery.py backend/tests/test_grant_discovery.py API_SPEC.md README.md QC_LOG.md` -> pass; only existing LF-to-CRLF working-copy warnings.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-contracts --backend-tests tests/test_grant_discovery.py tests/test_deployment_docs.py --json-out ..\..\var\desci-release-gate-loop58-grant-discovery-source-package.json` -> pass; backend grant/docs tests, frontend lint, typecheck, tests, build, and bundle all passed (`6` gate steps OK).

### Result
- Grant discovery now fail-softly demotes missing-source opportunities instead of letting them look application-ready.
- Downstream consumers of `application_brief` get the same source/package warning even if they do not render the Funding Radar source-link UI.

## 2026-06-10 (Proposal Review Funding Radar Risk Context)

### Scope
- Strengthened proposal review prompts so Funding Radar context is included in the LLM review request, not only in draft generation.
- Updated simulated review fallback to include `risk_flags` from `notice_context`, preserving missing-source/application-package risks during local non-production demos.
- Added prompt-capture coverage to prove source/package evidence and risk text reach the review prompt.
- Updated API and README wording for proposal generation/review risk context.

### External Checks
- Grants.gov Workspace is the standard grant application path and allows teams to complete different application forms online or offline: https://www.grants.gov/applicants/workspace-overview
- Grants.gov Quick Start requires selecting a grant opportunity, opening the opportunity, and applying through Workspace before completing forms: https://www.grants.gov/quick-start-guide/applicants
- Grants.gov applicant FAQs recommend verifying submitted application package contents and agency-specific attachment instructions: https://www.grants.gov/applicants/applicant-faqs
- OpenAI prompt engineering guidance recommends including relevant context information in prompts when the model needs proprietary or constrained source data: https://developers.openai.com/api/docs/guides/prompt-engineering

### A/B Decision
- A: leave proposal review context limited to the missing-evidence list. This keeps the prompt smaller but can lose why a source/package gap is risky.
- B: include the full formatted Funding Radar context in the review prompt and echo `risk_flags` in simulated review fallback.
- Selected B because source/package readiness is an application-flow risk, and review critique is the operator-facing checkpoint before submission.

### Verification
- `uv run python -m py_compile backend\services\proposal_generator.py backend\tests\test_smoke_pipeline.py` -> pass.
- `uv run pytest tests/test_smoke_pipeline.py::test_proposal_generator_flags_missing_notice_evidence tests/test_smoke_pipeline.py::test_proposal_review_prompt_includes_notice_context_risks tests/test_smoke_pipeline.py::test_proposal_generator_resolves_notice_evidence_with_supporting_assets -q` from `backend` -> `3 passed`.
- `uv run pytest tests/test_smoke_pipeline.py -q --maxfail=1` from `backend` -> `13 passed`.
- `uv run pytest tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `7 passed`.
- `git diff --check -- backend/services/proposal_generator.py backend/tests/test_smoke_pipeline.py API_SPEC.md README.md QC_LOG.md` -> pass; only existing LF-to-CRLF working-copy warnings.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-contracts --backend-tests tests/test_smoke_pipeline.py tests/test_deployment_docs.py --json-out ..\..\var\desci-release-gate-loop59-proposal-risk-context.json` -> pass; backend smoke/docs tests, frontend lint, typecheck, tests, build, and bundle all passed (`6` gate steps OK). The frontend Vitest no-isolate subset hit the known worker startup timeout once, retried through the existing `vmThreads + isolate` fallback, and the release gate completed with `ok=true`.

### Result
- Proposal critique now sees the same Funding Radar risk context that draft generation sees.
- Missing original sponsor notice/application package risk no longer depends only on the missing-evidence list to reach review output.

## 2026-06-10 (Proposal Direct Upload Evidence Handoff)

### Scope
- Extended the direct `/upload` paper intake so proposal evidence route-state is submitted as `proposal_evidence_context`.
- Normalized and persisted proposal evidence context in paper upload responses, paper manifests, and vector-store metadata while preserving older vector-store stubs that do not accept the new parameter.
- Added proposal evidence paper manifests to the proposal-generation supporting asset lookup, so uploaded source packages can satisfy matching `evidence_to_prepare` checklist gaps.
- Documented the `/upload` multipart field and the proposal job behavior for paper and asset manifests.

### External Checks
- React Router documents `Link` route `state`, matching the proposal-to-upload handoff path: https://reactrouter.com/api/components/Link
- FastAPI documents combining `File` and `Form` fields in one multipart request, matching the `/upload` contract: https://fastapi.tiangolo.com/tutorial/request-forms-and-files/
- Grants.gov Workspace is the standard applicant package workflow, supporting original sponsor notice/application package evidence as a proposal-readiness artifact: https://www.grants.gov/applicants/workspace-overview
- Grants.gov Quick Start requires selecting an opportunity and applying through Workspace, reinforcing that source/package evidence should be attached before proposal submission: https://www.grants.gov/quick-start-guide/applicants

### A/B Decision
- A: keep `/upload` as a general paper intake and rely on `/assets/upload` for proposal evidence. This preserves the existing paper path but loses context when the operator follows the proposal modal's direct paper upload action.
- B: let `/upload` carry the same normalized proposal evidence context as `/assets/upload`, persist it with the paper manifest, and let proposal generation discover both paper and asset manifests.
- Selected B because the proposal UI exposes `/upload` as a first-class evidence action, and source/application-package PDFs should be usable as supporting evidence without forcing operators through the asset library.

### Verification
- `uv run python -m py_compile backend\services\asset_manager.py backend\routers\web3.py backend\routers\jobs.py backend\services\vector_store.py backend\services\qdrant_store.py backend\tests\test_asset_manager.py backend\tests\test_api_endpoints.py backend\tests\test_jobs.py` -> pass.
- `uv run pytest tests/test_asset_manager.py::test_upload_paper_persists_proposal_evidence_context tests/test_api_endpoints.py::test_upload_route_passes_proposal_evidence_context tests/test_jobs.py::test_proposal_generation_job_uses_uploaded_paper_evidence_assets -q` from `backend` -> `3 passed`.
- `cmd /c "npm run test -- src/__tests__/components/UploadPaper.test.jsx --run"` from `frontend` -> targeted retry passed, `12 passed`; first worker pool startup hit the known Vitest timeout and the split runner retried with `vmThreads + isolate`.
- `uv run pytest tests/test_asset_manager.py tests/test_jobs.py tests/test_api_endpoints.py -q --maxfail=1` from `backend` -> `62 passed`.
- `uv run pytest tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `7 passed`.
- `git diff --check -- API_SPEC.md README.md backend\services\asset_manager.py backend\routers\web3.py backend\routers\jobs.py backend\services\vector_store.py backend\services\qdrant_store.py backend\tests\test_asset_manager.py backend\tests\test_api_endpoints.py backend\tests\test_jobs.py frontend\src\components\UploadPaper.jsx frontend\src\__tests__\components\UploadPaper.test.jsx QC_LOG.md` -> pass; only existing LF-to-CRLF working-copy warnings.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-contracts --backend-tests tests/test_asset_manager.py tests/test_jobs.py tests/test_api_endpoints.py tests/test_deployment_docs.py --json-out ..\..\var\desci-release-gate-loop60-proposal-upload-evidence-handoff.json` -> pass; backend tests `69 passed`, frontend lint/typecheck/tests/build/bundle all passed, `6` gate steps OK.

### Result
- Direct proposal evidence uploads through `/upload` now preserve the sponsor/source package context instead of ending as generic papers.
- Proposal generation can resolve the `Original sponsor notice URL or application package` gap from either asset manifests or paper upload manifests.

## 2026-06-10 (Proposal Evidence Browser Direct Upload Proof)

### Scope
- Extended the `biolinker-proposal-clipboard-failure` browser smoke so it submits a source-package PDF through the proposal handoff `/upload` page before moving on to the asset library.
- Captured the direct paper upload multipart payload and asserted it contains `proposal_evidence_context` plus the unresolved evidence item.
- Verified the follow-up paper indexing job receives the uploaded paper ID, proving the browser path keeps the evidence upload attached to the actual indexed paper.

### External Checks
- Playwright Python actions documentation recommends `locator.set_input_files()` for file upload controls, matching the browser smoke implementation: https://playwright.dev/python/docs/input#upload-files
- Playwright network documentation supports `page.expect_response()` and `page.route()` for request/response assertions and API mocking, matching the direct upload and index-job proof: https://playwright.dev/python/docs/network

### A/B Decision
- A: rely on component and backend tests for `/upload` evidence context. This is fast, but it does not prove the proposal modal's real browser handoff can submit the file and payload together.
- B: extend the existing proposal browser smoke to click the proposal evidence upload action, select a PDF, submit it, inspect the multipart payload, and then continue to the existing `/assets` evidence proof.
- Selected B because it reuses the established proposal smoke, adds one direct user-path assertion, and avoids creating a second long-running browser scenario.

### Verification
- `uv run python -m py_compile scripts\browser_smoke.py` -> pass.
- `uv run python scripts\browser_smoke.py --frontend http://127.0.0.1:5176 --expect-dev-auth --skip-login-validation --only-check biolinker-proposal-clipboard-failure --timeout 25 --json-out ..\..\var\desci-browser-smoke-loop61-proposal-direct-upload-evidence.json` -> pass.
- `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-smoke-step browser --runtime-frontend http://127.0.0.1:5176 --runtime-browser-expect-dev-auth --runtime-browser-only-check biolinker-proposal-clipboard-failure --runtime-browser-timeout 25 --runtime-evidence-dir ..\..\var --json-out ..\..\var\desci-release-gate-loop61-browser-proposal-direct-upload-evidence.json` -> pass; browser-smoke `1` step OK.

### Result
- The live browser smoke now proves proposal modal route-state reaches `/upload`, survives real PDF selection/submission, and reaches the paper-indexing job as the uploaded evidence paper.
- The previous asset-library proposal evidence proof remains in the same smoke path, so both direct paper and asset evidence routes are covered.

## 2026-06-10 (Proposal Supporting Evidence Source Labels)

### Scope
- Added source metadata to proposal supporting evidence results so operators can distinguish `/assets` Asset Library evidence from `/upload` paper evidence stored in Research Vault.
- Enriched local proposal evidence asset listing with `evidence_origin`, `source_label`, and `source_route`.
- Rendered source labels and purpose-specific source links in the proposal modal supporting-evidence section.
- Updated proposal prompt formatting so supporting evidence source labels are visible to draft/review context.
- Documented the additive proposal job result fields in `API_SPEC.md`.

### External Checks
- WCAG link purpose guidance says link purpose should be determinable from link text or context, supporting source-specific labels instead of generic file-only evidence rows: https://www.w3.org/WAI/WCAG22/Understanding/link-purpose-in-context.html
- WAI-ARIA status-role guidance emphasizes conveying status context programmatically when content updates, reinforcing explicit evidence source/status text in the proposal panel: https://www.w3.org/WAI/ARIA/apg/patterns/status/

### A/B Decision
- A: keep supporting evidence rows as filename plus checklist item only. This is compact but leaves operators unable to tell whether the evidence record lives in Research Vault or Asset Library.
- B: add origin/label/route metadata to the proposal job result and show a source chip plus source-record link in `ProposalView`.
- Selected B because it is additive to the API, follows the existing `Link` UI pattern, and makes the evidence handoff auditable without changing proposal generation semantics.

### Verification
- `uv run python -m py_compile backend\services\asset_manager.py backend\routers\jobs.py backend\services\proposal_generator.py backend\tests\test_asset_manager.py backend\tests\test_jobs.py backend\tests\test_smoke_pipeline.py scripts\browser_smoke.py` -> pass.
- `uv run pytest tests/test_asset_manager.py::test_upload_asset_persists_proposal_evidence_context tests/test_asset_manager.py::test_upload_paper_persists_proposal_evidence_context tests/test_jobs.py::test_proposal_generation_job_uses_supporting_evidence_assets tests/test_jobs.py::test_proposal_generation_job_uses_uploaded_paper_evidence_assets tests/test_smoke_pipeline.py::test_proposal_generator_resolves_notice_evidence_with_supporting_assets -q` from `backend` -> `5 passed`.
- `uv run pytest tests/test_asset_manager.py tests/test_jobs.py tests/test_smoke_pipeline.py -q --maxfail=1` from `backend` -> `30 passed`.
- `cmd /c "npx vitest run src/__tests__/components/ProposalView.test.jsx --pool=vmThreads --isolate --reporter=dot"` from `frontend` -> `6 passed`.
- `cmd /c "node_modules\.bin\eslint.cmd src/components/ProposalView.jsx src/__tests__/components/ProposalView.test.jsx src/i18n/messages.js"` from `frontend` -> pass.
- Browser smoke first run at `--timeout 25` hit a cold-load `Page.goto` timeout before assertions; Vite logs had no runtime errors.
- Retry: `uv run python scripts\browser_smoke.py --frontend http://127.0.0.1:5176 --expect-dev-auth --skip-login-validation --only-check biolinker-proposal-clipboard-failure --timeout 60 --json-out ..\..\var\desci-browser-smoke-loop62-proposal-evidence-source-label-retry.json` -> pass.
- Browser-only release gate: `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --runtime-smoke --runtime-smoke-step browser --runtime-frontend http://127.0.0.1:5176 --runtime-browser-expect-dev-auth --runtime-browser-only-check biolinker-proposal-clipboard-failure --runtime-browser-timeout 60 --runtime-evidence-dir ..\..\var --json-out ..\..\var\desci-release-gate-loop62-browser-proposal-evidence-source-label.json` -> pass; browser-smoke `1` step OK.
- Full scoped release gate attempt with backend/frontend checks timed out after 15 minutes during the frontend Vitest split runner and did not write a JSON artifact; remaining loop62 release/Vitest child processes were terminated.
- `cmd /c "npm run typecheck"` from `frontend` -> pass.
- `cmd /c "npm run build"` from `frontend` -> pass.
- `cmd /c "npm run check:bundle"` from `frontend` -> pass; max chunk and entry budgets OK.
- `uv run pytest tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `7 passed`.
- `git diff --check -- API_SPEC.md QC_LOG.md backend\services\asset_manager.py backend\routers\jobs.py backend\services\proposal_generator.py backend\tests\test_asset_manager.py backend\tests\test_jobs.py backend\tests\test_smoke_pipeline.py frontend\src\components\ProposalView.jsx frontend\src\__tests__\components\ProposalView.test.jsx frontend\src\i18n\messages.js scripts\browser_smoke.py` -> pass; only existing LF-to-CRLF working-copy warnings.

### Result
- Proposal supporting evidence is no longer an ambiguous filename list; each item can now show whether the source record is in Asset Library or Research Vault.
- The proposal prompt and browser smoke both preserve that source label, so downstream review context and visible UI stay aligned.

## 2026-06-10 (Release Gate Frontend Test Timeout Evidence)

### Scope
- Added a parent timeout to the release-gate `frontend-tests` step so Vitest hangs fail with a recorded `GateResult` instead of leaving no parent JSON evidence.
- Added `--frontend-test-timeout <seconds>` with a 600-second default and `0` as the opt-out value.
- Passed `DESCI_VITEST_TIMEOUT_MS` into `run-vitest-split.mjs` at 90% of the parent timeout so the Node runner can emit its own timeout diagnostic before the parent timeout expires.
- Added `spawnSync` timeout handling in `run-vitest-split.mjs`, returning exit code `124` for timed-out Vitest or LTS Node re-exec child processes.
- Documented the timeout behavior in README, deployment guide, and operations runbook.

### External Checks
- Python `subprocess.run` documents `timeout` as killing and waiting for the child process before raising `TimeoutExpired`, matching the parent release-gate timeout path: https://docs.python.org/3/library/subprocess.html
- Node.js `child_process.spawnSync` supports synchronous child process execution and timeout handling, matching the Vitest runner timeout path: https://nodejs.org/api/child_process.html

### A/B Decision
- A: add timeout only inside `run-vitest-split.mjs`. This helps Vitest child hangs but still leaves the release-gate parent exposed if another frontend step or runner wrapper blocks.
- B: add a release-gate parent timeout for `frontend-tests` and pass a slightly shorter child timeout into the Vitest split runner.
- Selected B because the parent release-gate JSON is the durable operator artifact, while the child timeout preserves a more specific Vitest diagnostic when possible.

### Verification
- `uv run python -m py_compile scripts\release_gate.py backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py` -> pass.
- `cmd /c "node --check scripts/run-vitest-split.mjs"` from `frontend` -> pass.
- `uv run pytest tests/test_release_gate.py::test_release_gate_uses_lts_frontend_test_runner tests/test_release_gate.py::test_release_gate_frontend_test_timeout_sets_vitest_child_timeout tests/test_release_gate.py::test_release_gate_step_timeout_is_reported -q` from `backend` -> `3 passed`.
- Forced Vitest child timeout: `DESCI_VITEST_LTS_REEXEC=1 DESCI_VITEST_TIMEOUT_MS=1 node scripts/run-vitest-split.mjs src/__tests__/components/ProposalView.test.jsx --run` from `frontend` -> expected exit `124` with `[vitest-split] Vitest command timed out after 1ms`.
- Release-gate timeout proof via `run_step` wrote `D:\AI project\var\desci-release-gate-loop63-timeout-proof.json`; report has `ok=false`, `failed_step=timeout-proof`, `returncode=124`, `command_argv`, and `failures=["timed out after 0.2s"]`.
- `uv run pytest tests/test_release_gate.py -q --maxfail=1` from `backend` -> `89 passed`.
- `uv run pytest tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `7 passed`.
- `git diff --check -- scripts\release_gate.py frontend\scripts\run-vitest-split.mjs backend\tests\test_release_gate.py README.md OPERATIONS_RUNBOOK.md DEPLOYMENT_GUIDE.md QC_LOG.md` -> pass; only existing LF-to-CRLF working-copy warnings.

### Warnings
- A direct CLI proof with `uv run python scripts\release_gate.py --skip-env --skip-compose --skip-backend --skip-contracts --frontend-test-timeout 1 --json-out ..\..\var\desci-release-gate-loop63-frontend-timeout-proof.json` did not reach `frontend-tests`; it hung earlier in `frontend-lint` and produced no artifact before the shell timeout. The loop63 release-gate and frontend ESLint child processes from that proof were terminated.
- A normal `run-vitest-split` targeted run with forced `DESCI_VITEST_LTS_REEXEC=1` also exceeded the shell timeout and was terminated. This forced mode bypasses the normal stable-node re-exec path, but it reinforces that child timeouts are needed.

### Result
- Frontend Vitest hangs in release gate now have a bounded parent failure path with return code `124` and JSON evidence.
- The remaining uncovered gap is broader: `frontend-lint` can also hang before the `frontend-tests` timeout applies, so the next loop should generalize timeout evidence beyond Vitest.

## 2026-06-10 (Release Gate Frontend Step Timeout Evidence)

### Scope
- Added `--frontend-step-timeout <seconds>` with a 600-second default and `0` as the opt-out value.
- Applied that parent timeout to `frontend-lint`, `frontend-typecheck`, `frontend-build`, and `frontend-bundle`, while keeping `frontend-tests` on the dedicated `--frontend-test-timeout` path.
- Kept Vitest child timeout propagation limited to `frontend-tests` through `DESCI_VITEST_TIMEOUT_MS`.
- Updated README, deployment guide, operations runbook, and docs tests so operators see both frontend timeout knobs and the parent JSON failure contract.

### External Checks
- Python `subprocess.run` documents `timeout` as killing and waiting for the child process before raising `TimeoutExpired`, matching the parent release-gate timeout path for lint/typecheck/build/bundle: https://docs.python.org/3/library/subprocess.html
- Node.js `child_process.spawnSync` documents synchronous child process timeout handling, matching the existing Vitest child timeout path that remains separate from non-test frontend steps: https://nodejs.org/api/child_process.html

### A/B Decision
- A: keep only the `frontend-tests` parent timeout. This preserves Loop 63 behavior but leaves `frontend-lint`, `frontend-typecheck`, `frontend-build`, and `frontend-bundle` able to hang before any parent JSON evidence is written.
- B: add a separate `frontend-step-timeout` for non-test frontend steps and keep `frontend-test-timeout` for Vitest.
- Selected B because the timeout semantics stay explicit by step type while every frontend release-gate phase can now fail with a durable parent `GateResult`.

### Verification
- `uv run python -m py_compile scripts\release_gate.py backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py` -> pass.
- `uv run pytest tests/test_release_gate.py::test_release_gate_cli_defaults_to_auto_python_command tests/test_release_gate.py::test_release_gate_cli_can_disable_frontend_parent_timeouts tests/test_release_gate.py::test_release_gate_frontend_non_test_steps_have_parent_timeout tests/test_release_gate.py::test_release_gate_frontend_test_timeout_sets_vitest_child_timeout tests/test_release_gate.py::test_release_gate_step_timeout_is_reported -q` from `backend` -> `5 passed`.
- `uv run pytest tests/test_deployment_docs.py::test_operations_docs_track_frontend_release_gate_timeouts -q` from `backend` -> `1 passed`.
- `uv run pytest tests/test_release_gate.py -q --maxfail=1` from `backend` -> `91 passed`.
- `uv run pytest tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `8 passed`.
- Release-gate non-test frontend timeout proof via `run_step` wrote `D:\AI project\var\desci-release-gate-loop64-frontend-step-timeout-proof.json`; report has `ok=false`, `failed_step=frontend-lint`, `returncode=124`, `command_argv`, and `failures=["timed out after 0.2s"]`.
- `git diff --check -- scripts\release_gate.py frontend\scripts\run-vitest-split.mjs backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py README.md OPERATIONS_RUNBOOK.md DEPLOYMENT_GUIDE.md QC_LOG.md` -> pass; only existing LF-to-CRLF working-copy warnings.

### Warnings
- This loop intentionally did not run the full frontend release gate because Loop 63 proved the real `frontend-lint` path can hang on this machine before reaching Vitest. The direct `frontend-lint` `run_step` proof covers the parent timeout behavior without invoking the broad lint command.
- `frontend/scripts/run-vitest-split.mjs` remains an untracked working-tree file from Loop 63; this loop did not broaden its write scope.

### Result
- Frontend lint, typecheck, build, bundle, and tests now all have bounded release-gate parent failure paths with return code `124` and JSON evidence.
- Operators can tune or disable non-test and Vitest frontend timeouts independently without losing the parent handoff contract.

## 2026-06-10 (Release Gate Result Schema Contract)

### Scope
- Tightened `python scripts/release_gate.py --print-report-schema` so `results.items` describes the real per-step `GateResult` report shape instead of accepting any object.
- Added schema coverage for required result fields: `name`, `command`, `cwd`, `returncode`, `elapsed_ms`, `skipped`, `attempts`, and `ok`.
- Added optional result field coverage for `command_argv`, `artifacts`, `artifact_failures`, `artifact_reports`, `artifact_summary`, and `failures`.
- Updated README, deployment guide, operations runbook, and docs tests so dashboard/CI parser guidance names the per-step result fields.

### External Checks
- JSON Schema draft 2020-12 defines JSON Schema as a JSON-based format for describing the structure of JSON data, supporting the release-gate choice to publish concrete result item structure rather than an unconstrained object: https://json-schema.org/draft/2020-12/json-schema-core

### A/B Decision
- A: update docs only to say dashboards should inspect result fields. This improves operator guidance but does not let schema consumers detect missing `returncode`, `command_argv`, or timeout `failures` contracts.
- B: encode the per-step result contract directly in `json_report_schema()` and keep docs aligned with that stricter schema.
- Selected B because `--print-report-schema` is the machine-readable integration point for dashboards and CI parsers.

### Verification
- `uv run python -m py_compile scripts\release_gate.py backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py` -> pass.
- `uv run pytest tests/test_release_gate.py::test_release_gate_cli_prints_report_schema_without_running_steps -q` from `backend` -> `1 passed`.
- `uv run pytest tests/test_deployment_docs.py::test_operations_runbook_tracks_release_gate_runtime_smoke -q` from `backend` -> `1 passed`.
- Parsed live CLI schema output from `uv run python scripts\release_gate.py --print-report-schema` and confirmed `results.items.required` is `name,command,cwd,returncode,elapsed_ms,skipped,attempts,ok` with `returncode`, `elapsed_ms`, `command_argv`, `failures`, and `ok` properties present.
- `uv run pytest tests/test_release_gate.py -q --maxfail=1` from `backend` -> `91 passed`.
- `uv run pytest tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `8 passed`.
- `git diff --check -- scripts\release_gate.py frontend\scripts\run-vitest-split.mjs backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py README.md OPERATIONS_RUNBOOK.md DEPLOYMENT_GUIDE.md QC_LOG.md` -> pass; only existing LF-to-CRLF working-copy warnings.

### Result
- Release-gate schema consumers can now validate the same per-step fields that timeout and artifact handoff logic depends on.
- Timeout failures are no longer just a documented convention; `returncode`, `elapsed_ms`, `command_argv`, and `failures` are part of the printed parent report schema.

## 2026-06-10 (Release Gate Command Argv Schema Consistency)

### Scope
- Made `command_argv` present in every `result_report()` output, using an empty list only for manually constructed results that do not provide argv.
- Added synthetic `command_argv` to the strict launch-action-coverage drift result.
- Promoted `command_argv` into the required `results.items` fields in the printed release-gate JSON Schema.
- Updated strict action coverage tests so synthetic failure results keep the same argv contract as subprocess-backed gate steps.

### External Checks
- JSON Schema draft 2020-12 defines JSON Schema as a JSON-based format for describing JSON data structure, supporting required `command_argv` in the printed parent schema when docs promise it is available: https://json-schema.org/draft/2020-12/json-schema-core

### A/B Decision
- A: keep `command_argv` optional in the schema while docs say every result includes it. This avoids test churn but leaves dashboards to handle a contract mismatch.
- B: ensure every parent result report includes `command_argv` and make the schema require it.
- Selected B because `command_argv` is the parser-safe alternative to the display-only shell command string.

### Verification
- `uv run python -m py_compile scripts\release_gate.py backend\tests\test_release_gate.py` -> pass.
- `uv run pytest tests/test_release_gate.py::test_release_gate_cli_prints_report_schema_without_running_steps tests/test_release_gate.py::test_release_gate_strict_launch_action_coverage_result_reports_drift -q` from `backend` -> `2 passed`.
- Parsed live CLI schema output from `uv run python scripts\release_gate.py --print-report-schema` and confirmed `results.items.required` is `name,command,cwd,returncode,elapsed_ms,command_argv,skipped,attempts,ok`.
- `uv run pytest tests/test_release_gate.py::test_release_gate_cli_strict_action_coverage_fails_on_drift -q` from `backend` -> `1 passed`.
- `uv run pytest tests/test_release_gate.py -q --maxfail=1` from `backend` -> `91 passed`.
- `git diff --check -- scripts\release_gate.py frontend\scripts\run-vitest-split.mjs backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py README.md OPERATIONS_RUNBOOK.md DEPLOYMENT_GUIDE.md QC_LOG.md` -> pass; only existing LF-to-CRLF working-copy warnings.

### Result
- The release-gate parent report schema, docs, subprocess-backed steps, and synthetic strict drift result now agree that `command_argv` is always present.
- CI/dashboard integrations no longer need to special-case strict launch-action-coverage drift results for argv shape.

## 2026-06-10 (Release Gate Timeout Seconds Visibility)

### Scope
- Added `timeout_seconds` to `GateResult` and parent result reports whenever a gate step has a configured parent timeout.
- Populated `timeout_seconds` for dry-run, missing-executable, timeout, and normal subprocess result paths.
- Added `timeout_seconds` to the printed parent JSON Schema result item properties.
- Updated README, deployment guide, operations runbook, and docs tests so timeout handoff documentation names the structured timeout value.

### External Checks
- Python `subprocess.run` documents `timeout` behavior at the child process boundary, supporting explicit parent-report visibility for the configured timeout value: https://docs.python.org/3/library/subprocess.html
- JSON Schema draft 2020-12 defines JSON Schema as a way to describe JSON data structure, supporting the new `timeout_seconds` property in printed schema output: https://json-schema.org/draft/2020-12/json-schema-core

### A/B Decision
- A: keep timeout duration only in the human-readable failure message. This is enough for a person but forces dashboards to parse text and gives no timeout config on successful steps.
- B: add a structured `timeout_seconds` field to parent result reports when a step has a configured timeout.
- Selected B because it preserves the existing message while giving dashboards a parser-safe timeout configuration field.

### Verification
- `uv run python -m py_compile scripts\release_gate.py backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py` -> pass.
- `uv run pytest tests/test_release_gate.py::test_release_gate_cli_prints_report_schema_without_running_steps tests/test_release_gate.py::test_release_gate_step_timeout_is_reported -q` from `backend` -> `2 passed`.
- `uv run pytest tests/test_deployment_docs.py::test_operations_docs_track_frontend_release_gate_timeouts -q` from `backend` -> `1 passed`.
- Release-gate timeout proof via `run_step` wrote `D:\AI project\var\desci-release-gate-loop67-timeout-seconds-proof.json`; report has `failed_step=frontend-lint`, `returncode=124`, `command_argv`, `timeout_seconds=0.2`, and timeout `failures`.
- Parsed live CLI schema output from `uv run python scripts\release_gate.py --print-report-schema` and confirmed `results.items.properties.timeout_seconds.type=number`.
- `uv run pytest tests/test_release_gate.py -q --maxfail=1` from `backend` -> `91 passed`.
- `uv run pytest tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `8 passed`.
- `git diff --check -- scripts\release_gate.py frontend\scripts\run-vitest-split.mjs backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py README.md OPERATIONS_RUNBOOK.md DEPLOYMENT_GUIDE.md QC_LOG.md` -> pass; only existing LF-to-CRLF working-copy warnings.

### Result
- Timeout-enabled release-gate steps now expose both the failure message and a structured `timeout_seconds` field in parent JSON.
- Operators and dashboards can audit configured timeout bounds without scraping the `failures` text.

## 2026-06-10 (Release Gate Backend Test Timeout Evidence)

### Scope
- Added `--backend-test-timeout <seconds>` with a 600-second default and `0` as the opt-out value.
- Applied that parent timeout to the `backend-tests` pytest release-gate step.
- Kept backend, frontend non-test, and frontend Vitest timeouts as separate knobs because they wrap different runtimes and failure modes.
- Updated README, deployment guide, operations runbook, and docs tests so backend timeout behavior is included in the handoff contract.

### External Checks
- Python `subprocess.run` documents `timeout` behavior at the child process boundary, matching the backend pytest parent timeout path: https://docs.python.org/3/library/subprocess.html

### A/B Decision
- A: rely on frontend timeouts only. This fixes the observed Loop 63/64 hang path but still allows backend pytest to stall before parent JSON evidence is written.
- B: add a dedicated backend pytest parent timeout, separate from frontend timeout knobs.
- Selected B because backend pytest and frontend Node/Vitest have different runtime behavior and should be tuned independently.

### Verification
- `uv run python -m py_compile scripts\release_gate.py backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py` -> pass.
- `uv run pytest tests/test_release_gate.py::test_release_gate_preserves_uv_python_runner tests/test_release_gate.py::test_release_gate_cli_defaults_to_auto_python_command tests/test_release_gate.py::test_release_gate_cli_can_disable_backend_and_frontend_parent_timeouts -q` from `backend` -> `3 passed`.
- `uv run pytest tests/test_deployment_docs.py::test_operations_docs_track_backend_and_frontend_release_gate_timeouts -q` from `backend` -> `1 passed`.
- Release-gate backend timeout proof via `run_step` wrote `D:\AI project\var\desci-release-gate-loop68-backend-timeout-proof.json`; report has `failed_step=backend-tests`, `returncode=124`, `command_argv`, `timeout_seconds=0.2`, and timeout `failures`.
- CLI dry-run proof wrote `D:\AI project\var\desci-release-gate-loop68-backend-timeout-dry-run.json`; result `backend-tests` has `skipped=true`, `command_argv`, and `timeout_seconds=600.0`.
- `uv run pytest tests/test_release_gate.py -q --maxfail=1` from `backend` -> `91 passed`.
- `uv run pytest tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `8 passed`.
- `git diff --check -- scripts\release_gate.py frontend\scripts\run-vitest-split.mjs backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py README.md OPERATIONS_RUNBOOK.md DEPLOYMENT_GUIDE.md QC_LOG.md` -> pass; only existing LF-to-CRLF working-copy warnings.

### Result
- Backend pytest hangs now have the same parent JSON timeout evidence path as frontend gate steps.
- Operators can tune backend pytest, frontend lint/typecheck/build/bundle, and frontend Vitest timeouts independently.

## 2026-06-10 (Release Gate Contract Step Timeout Evidence)

### Scope
- Added `--contract-step-timeout <seconds>` with a 600-second default and `0` as the opt-out value.
- Applied that parent timeout to `contracts-build`, `contracts-config-tests`, `contracts-tests`, `contracts-deploy-core`, and `contracts-deploy-nft`.
- Kept contract timeout separate from backend pytest and frontend timeout knobs because Hardhat build/test/deploy phases have different runtime characteristics.
- Updated README, deployment guide, operations runbook, and docs tests so contract timeout behavior is included in the handoff contract.

### External Checks
- Python `subprocess.run` documents `timeout` behavior at the child process boundary, matching the contract parent timeout path: https://docs.python.org/3/library/subprocess.html
- Hardhat 3 official docs remain the current contract toolchain reference for this project: https://hardhat.org/docs/getting-started

### A/B Decision
- A: leave contract steps unbounded and rely on isolated Hardhat compiler cache plus retry behavior. This preserves the current happy path but can still lose parent JSON evidence if Hardhat build/test/deploy stalls.
- B: add a dedicated contract parent timeout for Hardhat build, config test, test, and local deploy smoke steps.
- Selected B because contract checks are launch-gate critical and should fail with the same durable parent JSON timeout evidence as backend/frontend steps.

### Verification
- `uv run python -m py_compile scripts\release_gate.py backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py` -> pass.
- `uv run pytest tests/test_release_gate.py::test_release_gate_cli_defaults_to_auto_python_command tests/test_release_gate.py::test_release_gate_cli_can_disable_backend_and_frontend_parent_timeouts tests/test_release_gate.py::test_release_gate_contract_steps_have_parent_timeout -q` from `backend` -> `3 passed`.
- `uv run pytest tests/test_deployment_docs.py::test_operations_docs_track_backend_contract_and_frontend_release_gate_timeouts -q` from `backend` -> `1 passed`.
- Release-gate contract timeout proof via `run_step` wrote `D:\AI project\var\desci-release-gate-loop69-contract-timeout-proof.json`; report has `failed_step=contracts-build`, `returncode=124`, `command_argv`, `timeout_seconds=0.2`, and timeout `failures`.
- CLI dry-run proof wrote `D:\AI project\var\desci-release-gate-loop69-contract-timeout-dry-run.json`; every contract result has `skipped=true` and `timeout_seconds=600.0`.
- `uv run pytest tests/test_release_gate.py -q --maxfail=1` from `backend` -> `92 passed`.
- `uv run pytest tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `8 passed`.
- `git diff --check -- scripts\release_gate.py frontend\scripts\run-vitest-split.mjs backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py README.md OPERATIONS_RUNBOOK.md DEPLOYMENT_GUIDE.md QC_LOG.md` -> pass; only existing LF-to-CRLF working-copy warnings.

### Result
- Hardhat contract build/test/local deploy smoke hangs now fail with parent JSON timeout evidence instead of blocking release-gate handoff indefinitely.
- Backend, frontend, and contract release-gate timeout knobs are now independently tunable.

## 2026-06-10 (Release Gate Preflight Runtime Timeout Evidence)

### Scope
- Added `--preflight-step-timeout <seconds>` with a 600-second default and `0` as the opt-out value.
- Applied that parent timeout to `env-doctor`, `deploy-readiness`, and `compose-config`.
- Added `--runtime-smoke-timeout <seconds>` with a 600-second default and `0` as the opt-out value.
- Applied that parent timeout to `product-smoke` and `browser-smoke`, while preserving `--runtime-browser-timeout` as the child browser-smoke timeout knob for targeted diagnostics.
- Updated README, deployment guide, operations runbook, and docs tests so every release-gate phase has a documented parent timeout path.

### External Checks
- Python `subprocess.run` documents `timeout` behavior at the child process boundary, matching the preflight and runtime smoke parent timeout path: https://docs.python.org/3/library/subprocess.html
- Docker Compose documents `docker compose config` as the compose-file validation/render command, supporting the release-gate decision to treat `compose-config` as a bounded preflight step: https://docs.docker.com/reference/cli/docker/compose/config/

### A/B Decision
- A: keep env/deploy/compose/runtime smoke unbounded now that backend/frontend/contracts are bounded. This leaves the release gate able to hang before or after the core test phases.
- B: add separate preflight and runtime-smoke parent timeout knobs while preserving the browser-smoke child timeout forwarding.
- Selected B because preflight and runtime smoke are different operational phases, but both need durable parent JSON timeout evidence.

### Verification
- `uv run python -m py_compile scripts\release_gate.py backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py` -> pass.
- `uv run pytest tests/test_release_gate.py::test_release_gate_cli_defaults_to_auto_python_command tests/test_release_gate.py::test_release_gate_cli_can_disable_parent_timeouts tests/test_release_gate.py::test_release_gate_preflight_steps_have_parent_timeout tests/test_release_gate.py::test_release_gate_runtime_smoke_steps_have_parent_timeout -q` from `backend` -> `4 passed`.
- `uv run pytest tests/test_deployment_docs.py::test_operations_docs_track_release_gate_parent_timeouts -q` from `backend` -> `1 passed`.
- Preflight timeout proof via `run_step` wrote `D:\AI project\var\desci-release-gate-loop70-preflight-timeout-proof.json`; report has `failed_step=env-doctor`, `returncode=124`, `command_argv`, `timeout_seconds=0.2`, and timeout `failures`.
- Runtime timeout proof via `run_step` wrote `D:\AI project\var\desci-release-gate-loop70-runtime-timeout-proof.json`; report has `failed_step=product-smoke`, `returncode=124`, `command_argv`, `timeout_seconds=0.2`, and timeout `failures`.
- CLI dry-run proof wrote `D:\AI project\var\desci-release-gate-loop70-preflight-runtime-timeout-dry-run.json`; env-doctor, deploy-readiness, compose-config, product-smoke, and browser-smoke results have `skipped=true` and `timeout_seconds=600.0`.
- `uv run pytest tests/test_release_gate.py -q --maxfail=1` from `backend` -> `94 passed`.
- `uv run pytest tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `8 passed`.
- `git diff --check -- scripts\release_gate.py frontend\scripts\run-vitest-split.mjs backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py README.md OPERATIONS_RUNBOOK.md DEPLOYMENT_GUIDE.md QC_LOG.md` -> pass; only existing LF-to-CRLF working-copy warnings.

### Result
- Every default release-gate phase now has a parent timeout path with structured parent JSON evidence.
- Runtime browser-smoke keeps both layers: parent `--runtime-smoke-timeout` and child `--runtime-browser-timeout` for targeted browser diagnostics.

## 2026-06-10 (Release Gate Timeout Invariant Guard)

### Scope
- Added invariant coverage so every default release-gate `GateStep` must have a parent timeout.
- Added invariant coverage so optional external readiness and runtime smoke `GateStep` entries must also have parent timeouts.
- Generated a full dry-run parent report with default, external-readiness, and runtime-smoke steps enabled to verify every emitted result includes `timeout_seconds`.

### External Checks
- Python `subprocess.run` documents that a timeout kills and waits for the child before re-raising `TimeoutExpired`, supporting the invariant that release-gate child processes should be parent-bounded: https://docs.python.org/3/library/subprocess.html
- JSON Schema draft 2020-12 describes JSON Schema as a structure description format, supporting parser-visible `timeout_seconds` in release-gate result objects: https://json-schema.org/draft/2020-12/json-schema-core

### A/B Decision
- A: keep the individual per-phase timeout tests only. This proves today's named steps but can miss a future `GateStep` added without timeout coverage.
- B: add an invariant test over all default and optional release-gate steps, and verify a full dry-run parent JSON report.
- Selected B because it turns the timeout contract into a fail-closed release-gate maintenance rule.

### Verification
- `uv run python -m py_compile backend\tests\test_release_gate.py` -> pass.
- `uv run pytest tests/test_release_gate.py::test_release_gate_default_steps_all_have_parent_timeout tests/test_release_gate.py::test_release_gate_optional_external_and_runtime_steps_all_have_parent_timeout -q` from `backend` -> `2 passed`.
- `uv run python scripts\release_gate.py --dry-run --continue-on-failure --external-readiness --runtime-smoke --json-out ..\..\var\desci-release-gate-loop71-all-timeout-dry-run.json` -> pass; `16` dry-run steps emitted.
- Parsed `D:\AI project\var\desci-release-gate-loop71-all-timeout-dry-run.json` and confirmed every result has `timeout_seconds`; result names were `env-doctor`, `deploy-readiness`, `compose-config`, `backend-tests`, `frontend-lint`, `frontend-typecheck`, `frontend-tests`, `frontend-build`, `frontend-bundle`, `contracts-build`, `contracts-config-tests`, `contracts-tests`, `contracts-deploy-core`, `contracts-deploy-nft`, `product-smoke`, and `browser-smoke`.
- `uv run pytest tests/test_release_gate.py -q --maxfail=1` from `backend` -> `96 passed`.
- `uv run pytest tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `8 passed`.
- `git diff --check -- scripts\release_gate.py frontend\scripts\run-vitest-split.mjs backend\tests\test_release_gate.py backend\tests\test_deployment_docs.py README.md OPERATIONS_RUNBOOK.md DEPLOYMENT_GUIDE.md QC_LOG.md` -> pass; only existing LF-to-CRLF working-copy warnings.

### Result
- Future release-gate steps now fail tests if they are added without a parent timeout by default.
- The full dry-run handoff report proves all current default, external-readiness, and runtime-smoke results expose structured `timeout_seconds`.

## 2026-06-10 (Release Gate Timeout Help Discoverability Guard)

### Scope
- Added a CLI help regression test so every release-gate timeout knob remains visible in `release_gate.py --help`.
- Covered parent timeout options for preflight, backend, contracts, runtime smoke, frontend non-test steps, and frontend Vitest.
- Also covered the child `--runtime-browser-timeout` diagnostic knob so operators can discover both parent and browser-smoke timeout layers.
- Generated a machine-readable help-output proof for the timeout option list.

### External Checks
- Python `argparse` documents `--help` as a generated help option for command-line interfaces, supporting a regression test around operator-facing option discoverability: https://docs.python.org/3/library/argparse.html

### A/B Decision
- A: rely on parser argument tests and docs only. This verifies runtime behavior but can miss a future help-text regression where operators cannot discover the timeout controls.
- B: add a direct `--help` regression test and record a JSON proof of the timeout options shown in help output.
- Selected B because timeout controls are operational handoff features and must be discoverable without reading source code.

### Verification
- `uv run python -m py_compile backend\tests\test_release_gate.py` -> pass.
- `uv run pytest tests/test_release_gate.py::test_release_gate_cli_help_lists_timeout_options -q` from `backend` -> `1 passed`.
- `uv run pytest tests/test_release_gate.py -q --maxfail=1` from `backend` -> `97 passed`.
- `uv run pytest tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `8 passed`.
- Help-output proof wrote `D:\AI project\var\desci-release-gate-loop72-help-options-proof.json`; it confirms all seven timeout options are present and parent timeout opt-out text is present.

### Result
- The timeout behavior now has three guard layers: step construction invariants, structured JSON result evidence, and CLI help discoverability.
- Future timeout option drift should fail before operators lose the handoff path.

## 2026-06-10 (Release Gate Parent Child Timeout Docs Guard)

### Scope
- Clarified README, deployment guide, and operations runbook wording so parent timeout opt-out applies only to parent release-gate timeout options.
- Kept `--runtime-browser-timeout` documented as a child browser-smoke timeout for targeted diagnostics, not as part of the parent-timeout opt-out contract.
- Added a deployment-docs regression assertion that rejects the old ambiguous `Use any timeout option with 0` wording.

### External Checks
- Playwright Python docs describe per-action `timeout` arguments as operation-level waits, supporting the distinction between release-gate parent process timeouts and browser-smoke child action timeouts: https://playwright.dev/python/docs/api/class-page

### A/B Decision
- A: leave the docs as-is because the runtime behavior is already correct. This risks operators treating `--runtime-browser-timeout` as another parent timeout opt-out knob.
- B: tighten the docs and add a docs regression test that separates parent timeout options from the child browser-smoke timeout.
- Selected B because the timeout handoff is now operationally important enough that misleading docs should fail tests.

### Verification
- `uv run python -m py_compile backend\tests\test_deployment_docs.py` -> pass.
- `uv run pytest tests/test_deployment_docs.py::test_operations_docs_track_release_gate_parent_timeouts -q` from `backend` -> `1 passed`.
- `uv run pytest tests/test_deployment_docs.py -q --maxfail=1` from `backend` -> `8 passed`.
- `uv run pytest tests/test_release_gate.py -q --maxfail=1` from `backend` -> `97 passed`.
- Normalized doc phrase proof wrote `D:\AI project\var\desci-release-gate-loop73-parent-child-timeout-doc-proof.json`; it confirms all three docs have the parent/child wording and no longer contain the old ambiguous phrase.

### Result
- Operator docs now match the actual timeout layering: parent release-gate process timeout versus child browser-smoke diagnostic timeout.
- Future docs drift around that distinction is covered by `test_deployment_docs.py`.

## 2026-06-10 (Workspace DeSci Smoke Revalidation)

### Scope
- Ran the canonical `desci` workspace smoke after the release-gate timeout and docs hardening work.
- Confirmed the smoke runner writes partial JSON while long checks are still running, then updates the same report to `complete`.
- Separated the initial shell wrapper timeout from the actual smoke result: the spawned runner continued and finished successfully.

### External Checks
- No live external deployment checks were required for this loop; this was a local canonical workspace smoke revalidation.

### A/B Decision
- A: stop at targeted release-gate and docs tests. This proves the edited files but does not exercise the project-level smoke contract.
- B: run `ops/scripts/run_workspace_smoke.py --scope desci` and use its JSON artifact as the project-level proof.
- Selected B because the timeout work changed the release-gate handoff surface, and the canonical DeSci smoke is the better end-to-end local confidence check.

### Verification
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-loop74.json` initially exceeded the shell wrapper's 600-second limit, but the runner process continued and completed.
- Final `D:\AI project\var\workspace-smoke-desci-loop74.json` status is `complete` with `8` total, `8` completed, `8` passed, `0` failed, `0` remaining.
- Completed checks: frontend lint, frontend unit tests, frontend build, bundle budget, contracts compile, contracts tests, backend smoke, and release readiness contracts.
- Backend smoke result: `13 passed, 1 warning`.
- Release readiness contracts result: `223 passed, 1 warning`.
- Contracts result: `77 passing`.

### Result
- The DeSci local smoke path is currently green after the timeout/help/docs work.
- The remaining caveat is runtime cost: isolated uv bootstrap installed `159` packages for backend smoke, so the canonical smoke can exceed short shell wrapper limits even when checks pass.

## 2026-06-10 (Workspace Smoke Elapsed Timing Evidence)

### Scope
- Added per-check `elapsed_ms` timing to `ops/scripts/run_workspace_smoke.py` result payloads.
- Added shared smoke-reader validation so optional `results[].elapsed_ms` must be a nonnegative integer when present.
- Updated `docs/QUALITY_GATE.md` and workspace smoke/report tests so the JSON evidence contract documents and verifies elapsed timing.

### External Checks
- Python `time.perf_counter()` is documented as a performance counter suitable for measuring short durations by taking the difference between calls: https://docs.python.org/3/library/time.html#time.perf_counter

### A/B Decision
- A: keep relying on external shell timing and stdout tail clues. This leaves long-running partial smoke reports unable to identify whether a check is slow, stuck, or just bootstrapping dependencies.
- B: write per-check elapsed timing into the canonical smoke JSON and validate it in the shared reader.
- Selected B because Loop 74 showed the DeSci smoke could exceed a short shell wrapper while still passing; the JSON artifact should carry enough timing evidence for handoff without terminal scrollback.

### Verification
- `python -m py_compile ops\scripts\run_workspace_smoke.py ops\scripts\workspace_smoke_report.py tests\test_workspace_smoke.py tests\test_ops_scripts_reports.py` -> pass.
- `python -m pytest tests/test_workspace_smoke.py::test_run_one_reports_elapsed_ms tests/test_workspace_smoke.py::test_run_one_uses_configured_check_timeout tests/test_ops_scripts_reports.py::test_smoke_report_summary_rejects_invalid_schema_v1_result_elapsed_ms -q` -> `6 passed`.
- `python -m pytest tests/test_workspace_smoke.py tests/test_ops_scripts_reports.py -q --maxfail=1` -> `93 passed`.
- `python ops/scripts/run_workspace_smoke.py --scope desci --only-check "desci frontend lint" --json-out var/workspace-smoke-desci-loop75-elapsed-proof.json` -> pass.
- Parsed `D:\AI project\var\workspace-smoke-desci-loop75-elapsed-proof.json`; status `complete`, summary `1/1 passed`, result `desci frontend lint`, `elapsed_ms=137715`.
- Shared reader direct parse of the proof artifact -> `1/1 PASS (workspace-smoke-desci-loop75-elapsed-proof.json)`.

### Result
- Workspace smoke JSON now explains slow-but-passing checks with machine-readable elapsed timing.
- Release handoff tools can keep using the same schema v1 report while gaining optional timing evidence for runtime-cost triage.

## 2026-06-10 (Workspace Smoke Summary Timing Evidence)

### Scope
- Added `summary.elapsed_ms_total` and `summary.slowest_results` to workspace smoke schema v1 JSON reports when result timing data is available.
- Added shared smoke-reader validation so summary timing must match the per-result `elapsed_ms` values exactly.
- Updated `docs/QUALITY_GATE.md` and workspace smoke/report tests so handoff consumers can rely on summary-level timing without scanning every result entry.

### External Checks
- Python `time.perf_counter()` is documented as a performance counter suitable for measuring short durations by taking the difference between calls: https://docs.python.org/3/library/time.html#time.perf_counter

### A/B Decision
- A: keep per-check `elapsed_ms` only. This preserves the Loop 75 evidence but requires every operator or report consumer to scan all result entries to find bottlenecks.
- B: add summary timing fields and validate them in the shared report reader.
- Selected B because workspace smoke reports are used as handoff artifacts, and the slowest checks should be visible directly from the summary block.

### Verification
- `python -m py_compile ops\scripts\run_workspace_smoke.py ops\scripts\workspace_smoke_report.py tests\test_workspace_smoke.py tests\test_ops_scripts_reports.py` -> pass.
- `python -m pytest tests/test_workspace_smoke.py::test_json_report_payload_includes_elapsed_summary tests/test_ops_scripts_reports.py::test_smoke_report_summary_accepts_matching_summary_elapsed_fields tests/test_ops_scripts_reports.py::test_smoke_report_summary_rejects_mismatched_summary_elapsed_fields -q` -> `5 passed`.
- `python -m pytest tests/test_workspace_smoke.py tests/test_ops_scripts_reports.py -q --maxfail=1` -> `98 passed`.
- `python ops/scripts/run_workspace_smoke.py --scope desci --only-check "desci bundle budget" --json-out var/workspace-smoke-desci-loop76-summary-timing-proof.json` -> pass.
- Parsed `D:\AI project\var\workspace-smoke-desci-loop76-summary-timing-proof.json`; status `complete`, summary `1/1 passed`, `elapsed_ms_total=3486`, result `desci bundle budget`, `elapsed_ms=3486`.
- Shared reader direct parse of the proof artifact -> `1/1 PASS (workspace-smoke-desci-loop76-summary-timing-proof.json)`.

### Result
- Workspace smoke JSON now has both detailed per-check timing and summary-level bottleneck evidence.
- Shared consumers reject mismatched summary timing fields, so report corruption or partial manual edits fail loudly instead of drifting silently.

## 2026-06-10 (Workspace Smoke Timing Display Surface)

### Scope
- Preserved validated summary timing in `SmokeReportSummary` so shared smoke-reader callers can display total elapsed time and the slowest check.
- Updated `SmokeReportSummary.format()` to append a compact `elapsed=...; slowest=...` suffix only when summary timing exists.
- Documented the display suffix contract in `docs/QUALITY_GATE.md` and extended tests to cover the human-readable timing surface.

### External Checks
- No new live external dependency check was required for this display loop. It builds on the Loop 76 timing contract, which uses Python `time.perf_counter()` as the duration source.

### A/B Decision
- A: keep timing fields machine-readable only. This leaves status surfaces such as session bootstrap and auto-research reports with the old `N/N PASS` summary, requiring operators to open JSON for timing context.
- B: preserve timing in the shared summary object and include a compact suffix in formatted displays when timing exists.
- Selected B because the smoke reader already owns the canonical display string, so one narrow change improves all callers that use `summary.format()`.

### Verification
- `python -m py_compile ops\scripts\workspace_smoke_report.py tests\test_ops_scripts_reports.py tests\test_workspace_smoke.py` -> pass.
- `python -m pytest tests/test_ops_scripts_reports.py::test_smoke_report_summary_accepts_matching_summary_elapsed_fields tests/test_workspace_smoke.py::test_quality_gate_documents_incremental_json_evidence -q` -> `2 passed`.
- `python -m pytest tests/test_workspace_smoke.py tests/test_ops_scripts_reports.py -q --maxfail=1` -> `98 passed`.
- Parsed `D:\AI project\var\workspace-smoke-desci-loop76-summary-timing-proof.json` with the updated reader and wrote `D:\AI project\var\desci-workspace-smoke-loop77-timing-display-proof.json`.
- Timing display proof: `1/1 PASS (workspace-smoke-desci-loop76-summary-timing-proof.json; elapsed=3.5s; slowest=desci bundle budget 3.5s)`.

### Result
- Operators now see the smoke bottleneck directly in shared status strings when the report contains summary timing.
- Older reports without summary timing keep the previous display shape.

## 2026-06-10 (Workspace Smoke Timing Metadata Handoff)

### Scope
- Added `SmokeReportSummary.timing_metadata()` so consumers can reuse validated `elapsed_ms_total` and `slowest_results` without rebuilding schema details.
- Preserved optional timing metadata in `session_bootstrap.py` `latest_smoke_evidence`.
- Preserved optional timing metadata in AutoResearch smoke status dictionaries, including latest workspace smoke and topic-specific smoke consumers that use the shared summary.

### External Checks
- No new live external dependency check was required. This loop only carried the already-validated schema timing fields through local handoff surfaces.

### A/B Decision
- A: expose timing only in display strings. This is readable for operators but leaves downstream machines parsing prose or opening raw smoke JSON.
- B: expose timing in display strings and structured metadata.
- Selected B because `latest_smoke_evidence` and AutoResearch JSON are machine handoff surfaces, so timing should remain structured after the shared reader validates it.

### Verification
- `python -m py_compile ops\scripts\workspace_smoke_report.py ops\scripts\session_bootstrap.py ops\scripts\auto_research_status.py tests\test_ops_scripts_reports.py tests\test_auto_research_status.py tests\test_workspace_smoke.py` -> pass.
- `python -m pytest tests/test_ops_scripts_reports.py::test_smoke_report_summary_accepts_matching_summary_elapsed_fields tests/test_ops_scripts_reports.py::test_session_bootstrap_preserves_schema_v1_smoke_timing_metadata tests/test_auto_research_status.py::test_auto_research_status_preserves_latest_smoke_timing_metadata tests/test_workspace_smoke.py::test_quality_gate_documents_incremental_json_evidence -q` -> `4 passed`.
- `python -m pytest tests/test_auto_research_status.py -q --maxfail=1` -> `109 passed`.
- `python -m pytest tests/test_workspace_smoke.py tests/test_ops_scripts_reports.py -q --maxfail=1` -> `99 passed`.
- Wrote `D:\AI project\var\desci-workspace-smoke-loop78-timing-metadata-proof.json`.
- Actual session bootstrap proof carries `elapsed_ms_total=3486` and slowest result `desci bundle budget`.
- AutoResearch timed fixture proof carries display `2/2 PASS (workspace-smoke-workspace.json; elapsed=95ms; slowest=two 80ms)` plus structured `elapsed_ms_total=95` and `slowest_results`.

### Result
- Timing now survives the full path from smoke JSON to shared display strings and structured handoff metadata.
- Current real AutoResearch latest workspace smoke remains an older `9/9 PASS` report without timing, so its actual metadata correctly has no optional timing fields until the next workspace-scope timed smoke run.

## 2026-06-10 (Workspace Smoke Terminal Timing Summary)

### Scope
- Added compact elapsed-time formatting to `ops/scripts/run_workspace_smoke.py`.
- Updated the smoke CLI final summary to print total elapsed timing and the slowest timed checks when result timing is available.
- Documented the terminal timing summary in `docs/QUALITY_GATE.md` and added stdout-capture coverage.

### External Checks
- No new live external dependency check was required. This loop exposed existing local timing data in the CLI terminal summary.

### A/B Decision
- A: leave timing only in JSON and status surfaces. This keeps machine artifacts rich but makes live terminal runs harder to triage while they are fresh.
- B: print a compact timing block in the final smoke CLI summary.
- Selected B because operators running the smoke command should see the bottleneck immediately without opening the JSON artifact.

### Verification
- `python -m py_compile ops\scripts\run_workspace_smoke.py tests\test_workspace_smoke.py` -> pass.
- `python -m pytest tests/test_workspace_smoke.py::test_print_results_summary_includes_elapsed_timing tests/test_workspace_smoke.py::test_quality_gate_documents_incremental_json_evidence -q` -> `2 passed`.
- `python -m pytest tests/test_workspace_smoke.py -q --maxfail=1` -> `42 passed`.
- `python ops/scripts/run_workspace_smoke.py --scope desci --only-check "desci bundle budget" --json-out var/workspace-smoke-desci-loop79-terminal-timing-proof.json` -> pass.
- Terminal output included `[smoke] timing: elapsed=3.6s` and `- [PASS] desci bundle budget elapsed=3.6s`.
- Parsed `D:\AI project\var\workspace-smoke-desci-loop79-terminal-timing-proof.json`; status `complete`, summary `1/1 passed`, `elapsed_ms_total=3630`, slowest result `desci bundle budget`.
- Shared reader display: `1/1 PASS (workspace-smoke-desci-loop79-terminal-timing-proof.json; elapsed=3.6s; slowest=desci bundle budget 3.6s)`.

### Result
- The smoke command now exposes timing in all three relevant places: terminal output, JSON summary, and shared reader/status surfaces.

## 2026-06-10 (Workspace Smoke Scope Preference for Health Snapshots)

### Scope
- Fixed session bootstrap and context snapshot smoke selection so focused app-scope smoke proofs do not displace canonical workspace-scope health evidence.
- Added shared smoke-reader helpers for `workspace-smoke-workspace*.json` candidates and complete all-pass preference.
- Kept fallback behavior: if no valid workspace-scope smoke exists, consumers still use the newest valid focused smoke; if no valid smoke exists, they report the newest corrupt candidate.
- Reused the shared preference helper in AutoResearch status to avoid duplicated smoke-selection logic.

### External Checks
- Python `pathlib.Path.stat()` official docs confirm path metadata access through `Path.stat()`, which supports the existing mtime-based candidate ordering used by the shared smoke reader: https://docs.python.org/3/library/pathlib.html#pathlib.Path.stat

### A/B Decision
- A: keep selecting the newest valid smoke report by mtime for session bootstrap and context snapshot. This can make a focused `1/1 PASS` proof look like the latest overall workspace health.
- B: prefer canonical `workspace-smoke-workspace*.json` reports for health snapshots, then fall back to newest valid focused reports only when no valid workspace-scope report exists.
- Selected B because these surfaces are workspace health summaries, not focused-check proof selectors.

### Verification
- `python -m py_compile ops\scripts\workspace_smoke_report.py ops\scripts\session_bootstrap.py ops\scripts\generate_context_snapshot.py ops\scripts\auto_research_status.py tests\test_ops_scripts_reports.py tests\test_workspace_smoke.py` -> pass.
- `python -m pytest tests/test_ops_scripts_reports.py::test_smoke_consumers_prefer_workspace_scope_over_newer_focused_report tests/test_workspace_smoke.py::test_quality_gate_documents_incremental_json_evidence -q` -> `2 passed`.
- `python -m pytest tests/test_ops_scripts_reports.py tests/test_auto_research_status.py tests/test_workspace_smoke.py -q --maxfail=1` -> `210 passed`.
- Wrote `D:\AI project\var\desci-workspace-smoke-loop80-workspace-preference-proof.json`.
- Actual session bootstrap proof now reports `9/9 PASS (workspace-smoke-workspace-after-static-2026-06-08.json)` despite newer focused DeSci smoke artifacts.
- Actual context snapshot `_test_status()` now reports `9/9 PASS (workspace-smoke-workspace-after-static-2026-06-08)`.
- Actual AutoResearch latest smoke remains `9/9 PASS (workspace-smoke-workspace-after-static-2026-06-08.json)`.
- `python ops/scripts/session_bootstrap.py --json-out var/session-bootstrap-loop80-workspace-preference-proof.json` -> pass and wrote proof JSON.

### Result
- Focused smoke artifacts can be generated for loop proofs without degrading the workspace-level health summary shown at session startup or in generated context snapshots.

## 2026-06-10 (Release Manifest Health Snapshot Path Guard)

### Scope
- Added `ops/scripts/generate_context_snapshot.py` and `ops/scripts/session_bootstrap.py` to the release manifest refresh required changed-path contract.
- Added the same health snapshot scripts to `release_approval_check.py` required changed-path validation.
- Added regression coverage so stale or manually edited release manifests cannot omit health snapshot consumers when the smoke evidence contract changes.
- Updated `docs/QUALITY_GATE.md` to state that release manifests must include session bootstrap/context snapshot consumers alongside the smoke runner, reader, tests, and quality-gate document.

### External Checks
- Git official `git status` documentation says `--porcelain` produces an easy-to-parse, stable format for scripts. This supports keeping release approval tied to explicit dirty worktree paths rather than relying on prose summaries: https://git-scm.com/docs/git-status

### A/B Decision
- A: keep only the smoke runner/reader/test paths as required manifest paths. This misses the health snapshot consumers that now interpret canonical workspace smoke preference.
- B: require the health snapshot consumers in manifest refresh and release approval changed-path lists.
- Selected B because session bootstrap and context snapshot are operator-facing launch-readiness surfaces; if their smoke-selection contract changes, release approval should require that path to be represented in the manifest.

### Verification
- `python -m py_compile ops\scripts\refresh_complete_goal_release_manifest.py ops\scripts\release_approval_check.py tests\test_refresh_complete_goal_release_manifest.py tests\test_release_approval_check.py tests\test_workspace_smoke.py` -> pass.
- `python -m pytest tests/test_release_approval_check.py::test_release_approval_requires_health_snapshot_worktree_paths tests/test_refresh_complete_goal_release_manifest.py::test_refresh_manifest_rebuilds_external_step_evidence_from_current_artifacts tests/test_workspace_smoke.py::test_quality_gate_documents_incremental_json_evidence -q` -> `3 passed`.
- `python -m pytest tests/test_release_approval_check.py tests/test_refresh_complete_goal_release_manifest.py -q --maxfail=1` -> `114 passed`.
- `python ops/scripts/refresh_complete_goal_release_manifest.py --json-out var/complete-goal-release-manifest-refresh-loop81-health-snapshot-paths-proof.json` -> pass; `missing_sources=[]`, `allowed_missing_sources=[]`.
- Refreshed manifest includes both `ops/scripts/generate_context_snapshot.py` and `ops/scripts/session_bootstrap.py` in `worktree.changed_paths`.
- `python ops/scripts/release_approval_check.py docs/reports/2026-06/RELEASE_APPROVAL_WORKSPACE_COMPLETION_AUDIT_2026-06-06.json --json-out var/release-approval-check-loop81-health-snapshot-paths-proof.json` -> exit `1`; current approval remains blocked by existing completion-audit/live credential/readiness issues, but no `worktree.changed_paths` failure was reported.

### Result
- The release manifest and release approval checker now guard the health snapshot smoke-selection contract, not just the raw smoke report parser and runner.

## 2026-06-10 (MCP Direct Probe Next Action Approval Proof)

### Scope
- Rechecked the current release approval manifest after the MCP direct session probe snapshot was refreshed with unresolved-probe `next_action` fields.
- Added regression coverage that accepts multiple unresolved MCP direct probes only when each unresolved probe carries an actionable `next_action`.
- Confirmed the release approval checker no longer reports `mcp-direct-session-probe probes[*].next_action` failures for the current manifest snapshot.

### External Checks
- The official Model Context Protocol specification describes MCP servers as exposing capabilities such as tools, resources, and prompts for clients. Since these connectors mediate tool access, unresolved connector probes need explicit operator next actions rather than silent approval bypasses: https://modelcontextprotocol.io/specification/2025-11-25

### A/B Decision
- A: relax release approval so missing MCP direct probe actions are ignored when MCP is supplemental. This would hide an operator repair requirement.
- B: keep release approval strict, refresh the proof, and add a regression that unresolved probes are accepted only when each has a non-empty `next_action`.
- Selected B because MCP readiness is supplemental for approval clearing, but unresolved connector state still needs actionable operator handoff.

### Verification
- `python -m py_compile tests\test_release_approval_check.py` -> pass.
- `python -m pytest tests/test_release_approval_check.py::test_release_approval_accepts_unresolved_mcp_direct_probes_with_next_actions tests/test_release_approval_check.py::test_release_approval_rejects_mcp_direct_probe_that_is_not_supplemental -q` -> `2 passed`.
- `python -m pytest tests/test_release_approval_check.py -q --maxfail=1` -> `100 passed`.
- `python ops/scripts/release_approval_check.py docs/reports/2026-06/RELEASE_APPROVAL_WORKSPACE_COMPLETION_AUDIT_2026-06-06.json --json-out var/release-approval-check-loop82-mcp-direct-next-action-proof.json` -> exit `1`, expected while external blockers remain.
- Parsed `D:\AI project\var\release-approval-check-loop82-mcp-direct-next-action-proof.json`; status `blocked_expected_external`, `failure_count=8`, `mcp_direct_failures=[]`, `generated_at_failures=[]`.
- Current manifest MCP direct probe snapshot has three unresolved probes and all three carry non-empty `next_action` values.

### Result
- The local MCP direct-probe handoff failure is cleared from release approval.
- The remaining approval failures are the existing external/live readiness blockers, not missing local MCP direct-probe repair instructions.

## 2026-06-10 (Connector Auth Action Plan Date Alignment)

### Scope
- Inspected current MCP connector auth readiness after Loop 82 release approval proof.
- Confirmed the current connector auth blocker is still external/operator-bound: `canva-local` is `transport_closed` and `notion` is `auth_required`.
- Removed stale hardcoded 2026-06-09 connector-auth output paths from `complete_goal_release_evidence_refresh.py`.
- Added regression coverage so the connector-auth operator action plan follows `CURRENT_DATE_STAMP` and `REPORT_MONTH`, while still excluding OAuth authorize URLs from commands.

### External Checks
- The official MCP specification identifies MCP as a protocol for connecting LLM applications to external tools/data and highlights explicit user consent and authorization for data/tool access. This supports keeping Notion/Canva OAuth completion as an operator action rather than recording OAuth URLs or secrets in reports: https://modelcontextprotocol.io/specification/2025-11-25

### A/B Decision
- A: keep the connector-auth operator action plan pinned to 2026-06-09 output paths. This can make a current rerun write or inspect stale artifacts.
- B: make connector-auth readiness and Canva transport diagnostic paths derive from the current release-evidence date constants.
- Selected B because the release handoff should direct operators to current-day artifacts while preserving the existing external-auth blocker semantics.

### Verification
- `python -m py_compile ops\scripts\complete_goal_release_evidence_refresh.py tests\test_complete_goal_release_evidence_refresh.py` -> pass.
- `python -m pytest tests/test_complete_goal_release_evidence_refresh.py -q --maxfail=1 -k "connector_auth or report_date"` -> `2 passed, 60 deselected`.
- `python -m pytest tests/test_complete_goal_release_evidence_refresh.py -q --maxfail=1` -> `62 passed`.
- Wrote `D:\AI project\var\desci-loop83-connector-auth-action-plan-proof.json`; proof reports `ok=true`, `old_date_present=false`, `current_date_present=true`, and `oauth_url_present=false`.
- `python ops/scripts/mcp_connector_auth_readiness_report.py --json-out var\mcp-connector-auth-readiness-loop83-recheck.json --markdown-out docs\reports\2026-06\MCP_CONNECTOR_AUTH_READINESS_LOOP83_RECHECK.md --allow-action-required` -> action required; configured `2/2`, auth `0/2`.
- `python ops/scripts/refresh_complete_goal_release_manifest.py --json-out var\complete-goal-release-manifest-refresh-loop83-connector-auth-action-plan-proof.json` -> refreshed manifest at `2026-06-10T13:46:00.722516+09:00`; `missing_sources=0`, `allowed_missing_sources=0`, `snapshot_count=72`.
- `python ops/scripts/release_approval_check.py docs\reports\2026-06\RELEASE_APPROVAL_WORKSPACE_COMPLETION_AUDIT_2026-06-06.json --json-out var\release-approval-check-loop83-connector-auth-action-plan-proof-after-manifest-refresh.json` -> exit `1`, expected while external blockers remain; parsed status `blocked_expected_external`, `failure_count=8`, `generated_at_failure_count=0`, `mcp_direct_failure_count=0`.

### Result
- Connector-auth operator rerun instructions now point at the current report date instead of stale 2026-06-09 artifacts.
- Release approval remains blocked by the expected external/operator auth requirements plus the previously listed live readiness blockers; this loop did not bypass those gates.

## 2026-06-10 (Release Approval Completion Context)

### Scope
- Inspected the current completion audit gate failures after Loop 83.
- Confirmed the completion audit remains blocked by expected external/operator readiness: `dailynews_first_run_launch_ready`, `getdaytrends_strict_readiness_pass`, and `getdaytrends_canonical_smoke_pass`.
- Added structured `completion_audit_gate_context` to `release_approval_check.py` JSON output so the release approval report carries blocker names, topic failed checks, `completion_audit_ready` detail, and agent readiness context without weakening the gate.
- Added regression coverage for the top-level expected-external report and the standalone context helper, including redaction of raw database URL shapes in check detail text.

### External Checks
- Python official `json` docs describe the JSON module command-line interface for validating and pretty-printing JSON documents. This supports keeping release approval handoff evidence machine-readable and parser-valid instead of relying only on stderr text: https://docs.python.org/3/library/json.html

### A/B Decision
- A: keep release approval output limited to failure strings. This preserves strictness but forces operators to reopen the completion audit artifact to identify the actual blockers.
- B: keep the same strict failure behavior and add a structured completion-audit context object to the JSON report.
- Selected B because it improves handoff diagnostics while leaving `completion_audit_gate.ok`, status, blocker, freshness, and secret-hygiene validation unchanged.

### Verification
- `python -m py_compile ops\scripts\release_approval_check.py tests\test_release_approval_check.py` -> pass.
- `python -m pytest tests/test_release_approval_check.py -q --maxfail=1 -k "completion_audit_gate_context or expected_external_analysis or expected_external_failures"` -> `3 passed, 98 deselected`.
- `python -m pytest tests/test_release_approval_check.py -q --maxfail=1` -> `101 passed`.
- `python ops/scripts/refresh_complete_goal_release_manifest.py --json-out var\complete-goal-release-manifest-refresh-loop84-completion-context-proof.json` -> refreshed manifest at `2026-06-10T13:51:50.551380+09:00`; `missing_sources=0`, `allowed_missing_sources=0`, `snapshot_count=72`.
- `python ops/scripts/release_approval_check.py docs\reports\2026-06\RELEASE_APPROVAL_WORKSPACE_COMPLETION_AUDIT_2026-06-06.json --json-out var\release-approval-check-loop84-completion-context-proof-after-manifest-refresh.json` -> exit `1`, expected while external blockers remain; parsed status `blocked_expected_external`, `failure_count=8`, `generated_at_failure_count=0`, context `status=loaded`, `blocking_requirement_count=3`.
- `python -m json.tool var\release-approval-check-loop84-completion-context-proof-after-manifest-refresh.json` -> pass.
- `python -m json.tool var\complete-goal-release-manifest-refresh-loop84-completion-context-proof.json` -> pass.

### Result
- Release approval reports now carry structured completion-audit blocker context for operator handoff.
- Approval still fails closed on the same expected external blockers; this loop only improved diagnosis and evidence quality.

## 2026-06-10 (Release Approval MCP Context)

### Scope
- Inspected the current MCP live health and connector-auth release evidence after Loop 84.
- Confirmed MCP release approval blockers remain expected external/operator states: Codex MCP live probes are blocked by session/quota availability, `canva-local` is `transport_closed`, and `notion` is `auth_required`.
- Added structured `mcp_gate_context` to `release_approval_check.py` JSON output so release approval reports carry live CLI/live probe counts, failure categories, retry timing, bridge missing-live-checks, connector configured/auth counts, and per-connector required actions.
- Added redaction for OAuth authorize URLs, secret assignments, and Supabase access-token shapes in diagnostic context strings.
- Added regression coverage for both the approved MCP context path and the action-required live/auth path without relaxing any release approval gates.

### External Checks
- The official Model Context Protocol specification describes MCP as the protocol layer for connecting applications to external tools and data, which supports keeping live connector readiness explicit in operator handoff evidence: https://modelcontextprotocol.io/specification/2025-11-25
- Python official `json` docs describe the JSON module command-line interface for validating and pretty-printing JSON documents, which supports the parser-valid proof check for the release approval report: https://docs.python.org/3/library/json.html

### A/B Decision
- A: leave MCP live/auth blockers as failure strings only. This preserves strictness but forces operators to open separate MCP artifacts to see counts, retry timing, and connector-specific actions.
- B: keep the same strict failure behavior and add a structured `mcp_gate_context` object to the JSON report.
- Selected B because it improves MCP handoff diagnostics while leaving live health, connector auth, freshness, safety, and secret-hygiene validation unchanged.

### Verification
- `python -m py_compile ops\scripts\release_approval_check.py tests\test_release_approval_check.py` -> pass.
- `python -m pytest tests\test_release_approval_check.py -q --maxfail=1 -k "mcp_gate_context or expected_external_analysis or expected_external_failures"` -> `3 passed, 99 deselected`.
- `python -m pytest tests\test_release_approval_check.py -q --maxfail=1` -> `102 passed`.
- `python ops\scripts\release_approval_check.py docs\reports\2026-06\RELEASE_APPROVAL_WORKSPACE_COMPLETION_AUDIT_2026-06-06.json --json-out var\release-approval-check-loop85-mcp-context-proof.json` -> exit `1`, expected while external blockers remain.
- Parsed `D:\AI project\var\release-approval-check-loop85-mcp-context-proof.json`; status `blocked_expected_external`, `failure_count=8`, `generated_at_failure_count=0`, `mcp_gate_context.live_health.status=loaded`, live `0/5`, live failure categories `{codex_usage_limit: 1, skipped_after_codex_usage_limit: 4}`, retry after `Jun 12th, 2026 6:27 PM`, connector auth `0/2`, `auth_required_count=1`, `transport_closed_count=1`.
- `python -m json.tool var\release-approval-check-loop85-mcp-context-proof.json` -> pass.

### Result
- Release approval reports now carry structured MCP live/auth blocker context for operator handoff.
- Approval still fails closed on the same expected external completion, MCP live, connector-auth, DailyNews, and getdaytrends blockers; this loop only improved diagnosis and evidence quality.

## 2026-06-10 (Release Approval External Steps Context)

### Scope
- Inspected the current release approval `external_steps` manifest entries after Loop 85.
- Confirmed the remaining blocked external steps are still DailyNews Supabase live database readiness and getdaytrends Supabase launch readiness, both with required evidence markers and operator actions present.
- Added structured `external_steps_context` to `release_approval_check.py` JSON output so release approval reports carry item counts, blocked/resolved/not-applicable counts, blocked step names, missing required evidence markers, evidence excerpts, and extracted operator actions.
- Added regression coverage for approved reports, expected-external reports, and explicit blocked external-step evidence contracts without relaxing any release approval gates.

### External Checks
- Supabase official database connection docs state that connection strings are obtained from the project dashboard Connect panel and document pooler/direct connection options: https://supabase.com/docs/guides/database/connecting-to-postgres
- Supabase official environment-management docs describe separate local/staging/production projects and GitHub Actions-backed schema release flows, supporting explicit production credential handoff instead of implicit local fallback: https://supabase.com/docs/guides/deployment/managing-environments

### A/B Decision
- A: keep external step blockers as failure strings plus long manifest evidence only. This preserves strictness but makes operators reopen the manifest to find required markers and the current remediation command.
- B: keep the same strict failure behavior and add a structured `external_steps_context` object to the JSON report.
- Selected B because it improves DailyNews/getdaytrends launch-readiness handoff while leaving external-step status, evidence-marker, secret-hygiene, and expected-blocker validation unchanged.

### Verification
- `python -m py_compile ops\scripts\release_approval_check.py tests\test_release_approval_check.py` -> pass.
- `python -m pytest tests\test_release_approval_check.py -q --maxfail=1 -k "external_steps_context or expected_external_step or expected_external_analysis or expected_external_failures"` -> `5 passed, 97 deselected`.
- `python -m pytest tests\test_release_approval_check.py -q --maxfail=1` -> `102 passed`.
- `python ops\scripts\release_approval_check.py docs\reports\2026-06\RELEASE_APPROVAL_WORKSPACE_COMPLETION_AUDIT_2026-06-06.json --json-out var\release-approval-check-loop86-external-steps-context-proof.json` -> exit `1`, expected while external blockers remain.
- Parsed `D:\AI project\var\release-approval-check-loop86-external-steps-context-proof.json`; status `blocked_expected_external`, `failure_count=8`, `generated_at_failure_count=0`, `external_steps_context.status=loaded`, `item_count=3`, `blocked_count=2`, blocked names are DailyNews Supabase live database readiness and getdaytrends Supabase launch readiness, missing marker lists are empty, and both blocked steps include extracted operator actions.
- `python -m json.tool var\release-approval-check-loop86-external-steps-context-proof.json` -> pass.

### Result
- Release approval reports now carry structured external-step blocker context for operator handoff.
- Approval still fails closed on the same expected external completion, MCP live, connector-auth, DailyNews, and getdaytrends blockers; this loop only improved diagnosis and evidence quality.

## 2026-06-10 (Release Approval Operator Handoff Summary)

### Scope
- Inspected the release approval JSON after Loop 86 and confirmed completion audit, MCP, and external-step blocker context existed but still required readers to correlate three separate objects.
- Added `operator_handoff_summary` to `release_approval_check.py` JSON output so release approval reports carry one compact release decision, unresolved area list, and deduplicated next operator actions.
- Kept the detailed context objects intact and did not relax completion, MCP live/auth, external-step marker, freshness, or secret-hygiene validation.
- Added regression coverage for approved, completion-only, MCP action-required, and external-step action-required handoff summary cases.

### External Checks
- Supabase official production checklist states production readiness should be checked for security, expected load, and availability before launch: https://supabase.com/docs/guides/deployment/going-into-prod
- GitHub official workflow command docs describe job summaries as Markdown summaries independent of raw logs via `GITHUB_STEP_SUMMARY`, supporting a compact operator-facing summary beside detailed logs: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands

### A/B Decision
- A: leave completion, MCP, and external-step contexts as separate JSON objects. This preserves detail but still forces manual correlation before an operator can act.
- B: keep all detailed objects and add a compact `operator_handoff_summary` that lists unresolved areas and deduplicated next actions.
- Selected B because it improves release handoff ergonomics while preserving all existing validation and fail-closed approval behavior.

### Verification
- `python -m py_compile ops\scripts\release_approval_check.py tests\test_release_approval_check.py` -> pass.
- `python -m pytest tests\test_release_approval_check.py -q --maxfail=1 -k "operator_handoff_summary or mcp_gate_context or external_steps_context or expected_external_step or expected_external_analysis"` -> `5 passed, 97 deselected`.
- `python -m pytest tests\test_release_approval_check.py -q --maxfail=1` -> `102 passed`.
- `python ops\scripts\release_approval_check.py docs\reports\2026-06\RELEASE_APPROVAL_WORKSPACE_COMPLETION_AUDIT_2026-06-06.json --json-out var\release-approval-check-loop87-operator-handoff-summary-proof.json` -> exit `1`, expected while external blockers remain.
- Parsed `D:\AI project\var\release-approval-check-loop87-operator-handoff-summary-proof.json`; status `blocked_expected_external`, `failure_count=8`, `generated_at_failure_count=0`, `operator_handoff_summary.status=blocked_expected_external`, `unresolved_area_count=4`, areas are `completion_audit`, `mcp_live_health`, `mcp_connector_auth`, and `external_steps`, with `next_operator_action_count=7`.
- `python -m json.tool var\release-approval-check-loop87-operator-handoff-summary-proof.json` -> pass.
- Parsed `operator_handoff_summary` for raw `postgres://`, `postgresql://`, `mcp.notion.com/authorize`, `Bearer `, `sbp_`, and `sb_secret_` markers -> all absent.

### Result
- Release approval reports now include a single operator handoff summary over completion, MCP, and external launch blockers.
- Approval still fails closed on the same expected external completion, MCP live, connector-auth, DailyNews, and getdaytrends blockers; this loop only improved diagnosis and evidence quality.

## 2026-06-10 (Release Approval Markdown Handoff Artifact)

### Scope
- Inspected the Loop 87 `operator_handoff_summary` and confirmed it was machine-readable but not directly usable as a CI/job-summary or operator-facing Markdown artifact.
- Added `--markdown-out` support to `release_approval_check.py`.
- Added `render_operator_handoff_markdown()` so release approval can emit a compact Markdown decision, unresolved-area table, next operator actions, and failure summary.
- Kept JSON output and fail-closed release approval behavior unchanged.
- Added regression coverage for Markdown generation and redaction of database URLs and OAuth authorize URLs in the Markdown handoff.

### External Checks
- GitHub official workflow command docs state that job summaries support GitHub-flavored Markdown via `GITHUB_STEP_SUMMARY`, which supports emitting a Markdown handoff artifact beside machine JSON: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands
- Supabase official production checklist states production readiness should be checked for security, expected load, and availability before launch, supporting a concise operator-facing release-readiness handoff: https://supabase.com/docs/guides/deployment/going-into-prod

### A/B Decision
- A: keep only JSON `operator_handoff_summary`. This is complete for machines but less useful for CI pages and operators.
- B: preserve JSON and add optional Markdown output from the same redacted summary data.
- Selected B because it improves handoff usability without changing approval validation or adding dependencies.

### Verification
- `python -m py_compile ops\scripts\release_approval_check.py tests\test_release_approval_check.py` -> pass.
- `python -m pytest tests\test_release_approval_check.py -q --maxfail=1 -k "markdown_handoff or operator_handoff_summary or expected_external_analysis"` -> `2 passed, 101 deselected`.
- `python -m pytest tests\test_release_approval_check.py -q --maxfail=1` -> `103 passed`.
- `python ops\scripts\release_approval_check.py docs\reports\2026-06\RELEASE_APPROVAL_WORKSPACE_COMPLETION_AUDIT_2026-06-06.json --json-out var\release-approval-check-loop88-markdown-handoff-proof.json --markdown-out docs\reports\2026-06\RELEASE_APPROVAL_OPERATOR_HANDOFF_LOOP88.md` -> exit `1`, expected while external blockers remain.
- `python -m json.tool var\release-approval-check-loop88-markdown-handoff-proof.json` -> pass.
- Parsed `D:\AI project\docs\reports\2026-06\RELEASE_APPROVAL_OPERATOR_HANDOFF_LOOP88.md`; includes `completion_audit`, `mcp_live_health`, `mcp_connector_auth`, and `external_steps` unresolved-area rows.
- Parsed Markdown for raw `postgres://`, `postgresql://`, `mcp.notion.com/authorize`, `Bearer `, `sbp_`, and `sb_secret_` markers -> all absent.

### Result
- Release approval can now emit both machine JSON and operator-facing Markdown handoff artifacts.
- Approval still fails closed on the same expected external completion, MCP live, connector-auth, DailyNews, and getdaytrends blockers; this loop only improved diagnosis and evidence usability.

## 2026-06-10 (Release Gate Handoff Reference Summary)

### Scope
- Inspected `apps/desci-platform/scripts/release_gate.py` after Loop 88 and confirmed the parent release-gate JSON could summarize child smoke artifacts but could not reference the new release approval Markdown handoff artifact.
- Added `--release-approval-handoff` support to `release_gate.py`.
- Added top-level `release_approval_handoff_summary` to the parent release-gate JSON report when a handoff path is supplied.
- The summary records path, resolved path, existence, title presence, required Markdown section coverage, line count, unsafe marker count, and `ready_for_job_summary`.
- Kept release-gate execution and child artifact validation unchanged; this only references an already generated handoff artifact.

### External Checks
- GitHub official workflow command docs state that job summaries support GitHub-flavored Markdown and are shown on the workflow run summary page, supporting a release-gate reference to a Markdown handoff artifact: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands
- Supabase official production checklist states production readiness should be checked for security, expected load, and availability before launch, supporting operator-visible launch-readiness evidence: https://supabase.com/docs/guides/deployment/going-into-prod

### A/B Decision
- A: make release gate directly run the release approval checker and generate the Markdown handoff. This would increase coupling and duplicate release-approval orchestration inside the product release gate.
- B: keep release approval generation separate and let release gate reference a supplied Markdown handoff artifact in its parent JSON.
- Selected B because it gives CI/operator discoverability with a smaller blast radius and no change to existing gate execution semantics.

### Verification
- `python -m py_compile apps\desci-platform\scripts\release_gate.py apps\desci-platform\backend\tests\test_release_gate.py` -> pass.
- `python -m pytest apps\desci-platform\backend\tests\test_release_gate.py -q --maxfail=1 -k "release_approval_handoff or parent_contract or operator_summary"` -> `4 passed, 95 deselected`.
- `python -m pytest apps\desci-platform\backend\tests\test_release_gate.py -q --maxfail=1` -> `99 passed`.
- `python scripts\release_gate.py --dry-run --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --release-approval-handoff ..\..\docs\reports\2026-06\RELEASE_APPROVAL_OPERATOR_HANDOFF_LOOP88.md --json-out ..\..\var\desci-release-gate-loop89-handoff-reference-proof.json` from `apps/desci-platform` -> pass.
- `python -m json.tool var\desci-release-gate-loop89-handoff-reference-proof.json` -> pass.
- Parsed `D:\AI project\var\desci-release-gate-loop89-handoff-reference-proof.json`; `release_approval_handoff_summary.exists=true`, `ready_for_job_summary=true`, `missing_sections=[]`, `unsafe_marker_count=0`, `line_count=40`.
- Parsed the release-gate handoff summary for raw `postgres://`, `postgresql://`, `mcp.notion.com/authorize`, `Bearer `, `sbp_`, and `sb_secret_` markers -> all absent.

### Result
- Release gate parent JSON can now reference and validate the release approval Markdown handoff artifact for CI/operator visibility.
- Approval still fails closed on the same expected external completion, MCP live, connector-auth, DailyNews, and getdaytrends blockers; this loop only improved handoff discoverability.

## 2026-06-10 (Release Gate Handoff Fail-Closed Validation)

### Scope
- Inspected the Loop 89 release-gate handoff reference behavior and found that `--release-approval-handoff` summarized missing or unsafe Markdown but did not affect the release-gate result.
- Added a synthetic `release-approval-handoff` gate result when `--release-approval-handoff` is supplied.
- The synthetic result fails if the handoff artifact is missing, lacks the expected title/sections, contains unsafe secret-shaped markers, or is not ready for job-summary use.
- Kept default release-gate behavior unchanged when `--release-approval-handoff` is not supplied.

### External Checks
- GitHub official workflow command docs state that job summaries support GitHub-flavored Markdown via `GITHUB_STEP_SUMMARY`, supporting fail-closed validation when a CI handoff summary is explicitly supplied: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands
- JSON Schema 2020-12 documentation describes object keyword validation such as `additionalProperties`, supporting explicit parent-report schema contracts for optional handoff summary fields: https://json-schema.org/understanding-json-schema/keywords

### A/B Decision
- A: keep `--release-approval-handoff` as a non-blocking reference. This avoids changing gate status but can let CI report OK while pointing at a missing or unsafe handoff.
- B: fail the release gate only when the operator explicitly supplies an invalid handoff artifact.
- Selected B because an explicit CI/operator handoff artifact should be trustworthy; default release-gate execution remains unchanged when the option is omitted.

### Verification
- `python -m py_compile apps\desci-platform\scripts\release_gate.py apps\desci-platform\backend\tests\test_release_gate.py` -> pass.
- `python -m pytest apps\desci-platform\backend\tests\test_release_gate.py -q --maxfail=1 -k "release_approval_handoff or parent_contract or operator_summary"` -> `5 passed, 96 deselected`.
- `python -m pytest apps\desci-platform\backend\tests\test_release_gate.py -q --maxfail=1` -> `101 passed`.
- Valid handoff proof: `python scripts\release_gate.py --dry-run --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --release-approval-handoff ..\..\docs\reports\2026-06\RELEASE_APPROVAL_OPERATOR_HANDOFF_LOOP88.md --json-out ..\..\var\desci-release-gate-loop90-valid-handoff-validation-proof.json` from `apps/desci-platform` -> pass.
- Missing handoff proof: same command with `MISSING_RELEASE_APPROVAL_OPERATOR_HANDOFF.md` -> exit `1`, expected.
- `python -m json.tool var\desci-release-gate-loop90-valid-handoff-validation-proof.json` -> pass.
- `python -m json.tool var\desci-release-gate-loop90-missing-handoff-validation-proof.json` -> pass.
- Parsed valid proof: `ok=true`, `failed=0`, `result_names=['release-approval-handoff']`, `ready_for_job_summary=true`, `missing_sections=[]`, `unsafe_marker_count=0`.
- Parsed missing proof: `ok=false`, `failed=1`, `failed_step=release-approval-handoff`, `exists=false`, `ready_for_job_summary=false`, and the synthetic result failure names the missing handoff path.

### Result
- Release gate now fails closed when an explicitly supplied release approval Markdown handoff artifact is missing or unsafe.
- Approval still fails closed on the same expected external completion, MCP live, connector-auth, DailyNews, and getdaytrends blockers; this loop only hardened handoff artifact trust.

## 2026-06-10 (Release Approval Handoff Quality-Gate Docs)

### Scope
- Inspected the current quality-gate documentation after Loop 90 and found that the code/test path supported release approval Markdown handoff generation and release-gate validation, but the operator ordering was not documented in `docs/QUALITY_GATE.md`.
- Documented the release approval handoff sequence: generate machine JSON and Markdown from `ops/scripts/release_approval_check.py --json-out ... --markdown-out ...`, optionally append the Markdown to `GITHUB_STEP_SUMMARY`, then pass the artifact to DeSci release gate with `--release-approval-handoff`.
- Documented that `--release-approval-handoff` adds the synthetic `release-approval-handoff` result and fails closed only when an explicitly supplied handoff artifact is missing, lacks required Markdown structure, contains unsafe secret-shaped markers, or is not ready for job-summary use.
- Added workspace smoke documentation-contract assertions so future documentation drift fails before operators lose the handoff path.

### External Checks
- GitHub official workflow command docs state that job summaries support GitHub-flavored Markdown via `GITHUB_STEP_SUMMARY`, supporting the documented CI handoff path: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands
- JSON Schema documentation describes object keyword validation such as `additionalProperties`, supporting explicit schema/report contracts for optional handoff fields: https://json-schema.org/understanding-json-schema/keywords

### A/B Decision
- A: leave the new handoff sequence documented only in individual loop logs. This keeps docs smaller but forces operators to reconstruct the ordering from implementation history.
- B: promote the sequence into `docs/QUALITY_GATE.md` and pin it with a smoke documentation test.
- Selected B because the release approval Markdown handoff and release-gate fail-closed validation are operator-facing quality-gate contracts.

### Verification
- `python -m py_compile tests\test_workspace_smoke.py` -> pass.
- `python -m pytest tests\test_workspace_smoke.py::test_quality_gate_documents_incremental_json_evidence -q` -> `1 passed`.
- `python -m pytest tests\test_workspace_smoke.py -q --maxfail=1` -> `43 passed`.

### Result
- Quality-gate docs now describe the full release approval handoff chain from release approval JSON/Markdown generation through DeSci release-gate `--release-approval-handoff` validation.
- Future docs drift around `--markdown-out`, `RELEASE_APPROVAL_OPERATOR_HANDOFF`, `GITHUB_STEP_SUMMARY`, `--release-approval-handoff`, and `release-approval-handoff` now fails the workspace smoke documentation test.

## 2026-06-10 (Release Approval Handoff Product Docs)

### Scope
- Inspected the DeSci product operations docs after Loop 91 and found that `docs/QUALITY_GATE.md` documented the release approval Markdown handoff flow, while `README.md`, `DEPLOYMENT_GUIDE.md`, and `OPERATIONS_RUNBOOK.md` still described release-gate parent reports without the new `--release-approval-handoff` path.
- Documented how to pass `RELEASE_APPROVAL_OPERATOR_HANDOFF.md` through product release gate with `--release-approval-handoff`.
- Documented the parent `release_approval_handoff_summary` fields that dashboards should read: `ready_for_job_summary`, required-section coverage, `missing_sections`, `unsafe_marker_count`, and resolved path metadata.
- Documented the fail-closed behavior of the synthetic `release-approval-handoff` result when an explicitly supplied handoff artifact is missing, malformed, unsafe, or not ready for GitHub Actions `GITHUB_STEP_SUMMARY`.
- Added deployment-doc contract coverage so `README.md`, `DEPLOYMENT_GUIDE.md`, and `OPERATIONS_RUNBOOK.md` must stay aligned with `release_gate.py`.

### External Checks
- GitHub official workflow command docs state that job summaries support GitHub-flavored Markdown via `GITHUB_STEP_SUMMARY`, and are shown on the workflow run summary page: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands
- JSON Schema documentation lists object/property keywords such as `properties`, `additionalProperties`, and `const`, supporting explicit parent-report contracts for optional release-gate summary objects: https://json-schema.org/understanding-json-schema/keywords

### A/B Decision
- A: keep the release approval handoff sequence only in `docs/QUALITY_GATE.md`. This is sufficient for workspace-level release approval but leaves DeSci product operators and dashboards to infer the release-gate option from source code.
- B: also document the sequence in the DeSci README, deployment guide, and operations runbook, then pin those docs with `test_deployment_docs.py`.
- Selected B because `--release-approval-handoff` is a product release-gate operator surface, not only a workspace quality-gate note.

### Verification
- `python -m py_compile apps\desci-platform\backend\tests\test_deployment_docs.py` -> pass.
- `python -m pytest apps\desci-platform\backend\tests\test_deployment_docs.py::test_operations_docs_track_release_approval_handoff_summary -q` -> `1 passed`.
- `python -m pytest apps\desci-platform\backend\tests\test_release_gate.py -q --maxfail=1 -k "release_approval_handoff or parent_contract"` -> `4 passed, 97 deselected`.
- `python -m pytest apps\desci-platform\backend\tests\test_deployment_docs.py -q --maxfail=1` -> `9 passed`.

### Result
- DeSci product docs now describe how release approval Markdown handoffs flow into release-gate parent JSON and CI/operator summaries.
- Future docs drift around `--release-approval-handoff`, `release_approval_handoff_summary`, `release-approval-handoff`, `ready_for_job_summary`, `missing_sections`, `unsafe_marker_count`, `RELEASE_APPROVAL_OPERATOR_HANDOFF`, and `GITHUB_STEP_SUMMARY` now fails the deployment-doc test.

## 2026-06-10 (Release Approval Machine Wrapper)

### Scope
- Inspected the release approval operational checklist and found it pointed to `ops/scripts/run_release_approval_gate_machine.ps1`, but the wrapper did not exist in `ops/scripts`.
- Added `ops/scripts/run_release_approval_gate_machine.ps1` as the one-shot machine wrapper documented by `docs/QUALITY_GATE.md`.
- The wrapper auto-discovers the current release approval artifact, runs workspace smoke unless skipped, runs `release_approval_check.py` with both `--json-out` and `--markdown-out`, appends the Markdown handoff to `GITHUB_STEP_SUMMARY` when present, and refreshes session bootstrap evidence unless skipped.
- Kept release approval fail-closed semantics unchanged: the wrapper exits with the release approval checker's nonzero code when current evidence is blocked or stale.
- Added quality-gate documentation coverage so the wrapper file must exist and contain the smoke, release approval, Markdown, job-summary, and session-bootstrap path markers.

### External Checks
- GitHub official workflow command docs state that job summaries support GitHub-flavored Markdown via `GITHUB_STEP_SUMMARY` and are shown on the workflow run summary page: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands
- JSON Schema documentation lists object/property keywords such as `properties`, `additionalProperties`, and `const`, supporting explicit report contracts for the machine-readable approval artifacts: https://json-schema.org/understanding-json-schema/keywords

### A/B Decision
- A: only update `docs/QUALITY_GATE.md` to remove the missing wrapper reference. This would avoid adding a script but lose the one-command operator path.
- B: implement the documented wrapper and make the docs test assert that the wrapper remains present and wired to JSON, Markdown, job-summary, and session-bootstrap outputs.
- Selected B because the documented operator command should be executable, and GitHub job-summary handoff is now part of the launch-readiness evidence flow.

### Verification
- PowerShell parser check for `ops\scripts\run_release_approval_gate_machine.ps1` -> `parsed`.
- `python -m py_compile tests\test_workspace_smoke.py` -> pass.
- `python -m pytest tests\test_workspace_smoke.py::test_quality_gate_release_approval_machine_wrapper_exists -q` -> `1 passed`.
- `python -m pytest tests\test_workspace_smoke.py::test_quality_gate_documents_incremental_json_evidence tests\test_workspace_smoke.py::test_quality_gate_release_approval_machine_wrapper_exists -q` -> `2 passed`.
- Wrapper proof with `-SkipSmoke -SkipSessionBootstrap`, `GITHUB_STEP_SUMMARY=var\release-approval-wrapper-loop93-step-summary.md`, `--json-out var\release-approval-check-loop93-wrapper-proof.json`, and `--markdown-out docs\reports\2026-06\RELEASE_APPROVAL_OPERATOR_HANDOFF_LOOP93_WRAPPER.md` -> exit `1`, expected fail-closed.
- `python -m json.tool var\release-approval-check-loop93-wrapper-proof.json` -> pass.
- Parsed wrapper proof: `status=blocked_unexpected`, `failure_count=11`, unresolved areas `completion_audit,mcp_live_health,mcp_connector_auth,external_steps`, `next_operator_action_count=7`.
- Parsed Markdown and step-summary files: both include `Release Approval Operator Handoff`, unresolved-area table rows, `Next Operator Actions`, and `Failure Summary`.
- Scanned the generated Markdown and step-summary for raw `postgres://`, `postgresql://`, `mcp.notion.com/authorize`, `Bearer `, `sbp_`, and `sb_secret_` markers -> none found.

### Result
- The release approval machine-gate command documented in `QUALITY_GATE.md` now exists and can produce both machine JSON and operator Markdown handoff evidence.
- The current release approval manifest remains blocked and stale in the expected fail-closed way; this loop made the operator/CI handoff path executable, not easier to pass.

## 2026-06-10 (Release Approval Handoff Workflow Dispatch)

### Scope
- Inspected `.github/workflows/desci-platform-quality.yml` after Loop 93 and found that the local release approval wrapper existed, but no GitHub Actions entrypoint could run it or append its Markdown handoff to a workflow summary.
- Added a manual `workflow_dispatch` boolean input named `release_approval_handoff`.
- Added a separate `release-approval-handoff` job that runs only when an operator explicitly dispatches the workflow with that input enabled.
- The manual job checks out the repo without persisted credentials, sets up uv/Python and Node dependencies, runs `ops/scripts/run_release_approval_gate_machine.ps1` with `-PythonCommand "uv run python"`, writes machine JSON and `RELEASE_APPROVAL_OPERATOR_HANDOFF_MACHINE.md`, and uploads the smoke, approval, session-bootstrap, and Markdown handoff artifacts.
- Kept ordinary PR/push matrix quality gates unchanged so current expected external release-approval blockers do not break routine deterministic CI.
- Updated workflow/security contract tests and `docs/QUALITY_GATE.md` so the manual CI handoff path is discoverable and pinned.

### External Checks
- GitHub official workflow syntax docs support `workflow_dispatch` inputs and `jobs.<job_id>.if` conditions, which are used to keep the release approval handoff job manual and explicit: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- GitHub official workflow command docs state that job summaries support GitHub-flavored Markdown via `GITHUB_STEP_SUMMARY`: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands

### A/B Decision
- A: run the release approval wrapper automatically on every PR/push quality workflow. This would surface handoff state everywhere but would fail routine CI while release approval remains blocked by external/operator requirements.
- B: add a manual `workflow_dispatch` input and a separate gated job that fails closed only when an operator explicitly runs the release approval handoff.
- Selected B because it provides a real CI/operator entrypoint without weakening or destabilizing deterministic PR/push gates.

### Verification
- `python -m py_compile tests\test_security_gate_contracts.py` -> pass.
- `python -m pytest tests\test_security_gate_contracts.py::test_github_workflows_are_valid_yaml tests\test_security_gate_contracts.py::test_desci_platform_quality_workflow_covers_all_workspace_scopes tests\test_security_gate_contracts.py::test_desci_platform_quality_workflow_has_manual_release_approval_handoff -q` -> `3 passed`.
- `python -m pytest tests\test_security_gate_contracts.py -q --maxfail=1` -> `14 passed`.
- `python -m pytest tests\test_workspace_smoke.py::test_quality_gate_release_approval_machine_wrapper_exists -q` -> `1 passed`.
- `python -m pytest tests\test_workspace_smoke.py -q --maxfail=1` -> `44 passed`.

### Result
- The release approval Markdown handoff now has a manual GitHub Actions entrypoint that appends to job summary through the wrapper and archives the relevant machine artifacts.
- Routine PR/push quality gates remain unchanged; release approval still fails closed only on explicit handoff runs while current blockers remain unresolved.

## 2026-06-10 (Release Approval Handoff Product Gate CI Chain)

### Scope
- Inspected the manual release approval handoff workflow job after Loop 94 and found it generated/uploaded release approval artifacts, but did not validate the generated Markdown handoff through the DeSci product release gate in the same CI chain.
- Added a `Validate handoff through DeSci release gate` workflow step that runs `apps/desci-platform/scripts/release_gate.py --dry-run --release-approval-handoff ../../docs/reports/2026-06/RELEASE_APPROVAL_OPERATOR_HANDOFF_MACHINE.md`.
- The workflow now records the wrapper exit code and the product release-gate handoff validation exit code separately, uploads artifacts, then fails closed in a final step if either code is missing or nonzero.
- Added the product release-gate parent JSON `var/desci-release-gate-release-approval-handoff-machine.json` to the uploaded artifact set.
- Fixed the CI handoff path contract after local proof showed that release-gate handoff paths are resolved from the DeSci app cwd: the handoff input must be `../../docs/reports/...`, while the root-level JSON artifact remains `var/...`.
- Extended workflow and quality-gate tests so the manual CI chain keeps the wrapper, product release-gate handoff validation, artifact upload, and final fail-closed step wired together.

### External Checks
- GitHub official workflow syntax docs support `workflow_dispatch` inputs and `jobs.<job_id>.if` conditions for explicit manual job gating: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- GitHub official workflow command docs state that job summaries support GitHub-flavored Markdown via `GITHUB_STEP_SUMMARY`: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands

### A/B Decision
- A: leave the manual workflow at release approval wrapper output only. This is simpler but does not prove the Markdown handoff can be consumed by DeSci release-gate parent JSON.
- B: continue the manual workflow into `release_gate.py --release-approval-handoff`, upload the product parent JSON, and fail closed only after all artifacts are collected.
- Selected B because the DeSci release gate is the product launch-readiness surface, and operator handoff artifacts should be validated where dashboards will consume them.

### Verification
- Initial local dry-run using `docs/reports/...` as the handoff path failed as expected because release gate resolved it under `apps/desci-platform/docs/...`; this caught the cwd contract mismatch before CI.
- Corrected local product release-gate proof: `python apps\desci-platform\scripts\release_gate.py --dry-run --skip-env --skip-compose --skip-backend --skip-frontend --skip-contracts --release-approval-handoff ..\..\docs\reports\2026-06\RELEASE_APPROVAL_OPERATOR_HANDOFF_MACHINE.md --json-out var\desci-release-gate-loop95-ci-handoff-dry-run.json` -> pass.
- Parsed `var\desci-release-gate-loop95-ci-handoff-dry-run.json`: `ok=true`, `failed=0`, `result=release-approval-handoff`, `handoff_exists=true`, `ready_for_job_summary=true`, `unsafe_marker_count=0`, `missing_sections=[]`.
- Scanned `docs\reports\2026-06\RELEASE_APPROVAL_OPERATOR_HANDOFF_MACHINE.md`, `var\release-approval-wrapper-loop95-step-summary.md`, and `var\desci-release-gate-loop95-ci-handoff-dry-run.json` for raw `postgres://`, `postgresql://`, `mcp.notion.com/authorize`, `Bearer `, `sbp_`, and `sb_secret_` markers -> none found.
- `python -m pytest tests\test_security_gate_contracts.py::test_github_workflows_are_valid_yaml tests\test_security_gate_contracts.py::test_desci_platform_quality_workflow_has_manual_release_approval_handoff -q` -> `2 passed`.
- `python -m pytest tests\test_security_gate_contracts.py -q --maxfail=1` -> `14 passed`.
- `python -m pytest tests\test_workspace_smoke.py::test_quality_gate_release_approval_machine_wrapper_exists -q` -> `1 passed`.
- `python -m pytest tests\test_workspace_smoke.py -q --maxfail=1` -> `44 passed`.
- `python -m pytest apps\desci-platform\backend\tests\test_deployment_docs.py::test_operations_docs_track_release_approval_handoff_summary -q` -> `1 passed`.

### Result
- The manual CI handoff path now carries release approval Markdown through the DeSci product release gate and archives the parent JSON that dashboards/operators can inspect.
- Routine PR/push quality gates remain unchanged; the manual handoff job still fails closed after artifact upload while current release approval blockers remain unresolved.

## 2026-06-10 (Release Approval Handoff Artifact Triage Order)

### Scope
- Inspected the manual release approval handoff workflow and product docs after Loop 95 and found the CI job uploaded the right bundle, but operators were not told which file to open first after a fail-closed manual run.
- Updated `README.md`, `DEPLOYMENT_GUIDE.md`, and `OPERATIONS_RUNBOOK.md` with an explicit artifact review order:
  1. `var/desci-release-gate-release-approval-handoff-machine.json` for the DeSci parent release-gate JSON and `release_approval_handoff_summary`.
  2. `docs/reports/2026-06/RELEASE_APPROVAL_OPERATOR_HANDOFF_MACHINE.md` for the operator-facing GitHub job summary text.
  3. `var/release-approval-check-machine.json` for raw approval failure analysis.
  4. `var/session-bootstrap-release-approval-machine.json` and `var/workspace-smoke-workspace-release-approval-machine.json` for environment context and smoke proof.
- Documented that artifact upload happens before the final fail-closed workflow step, so the bundle remains available when current release approval blockers fail the manual job.
- Extended deployment-doc and workflow-contract tests to keep that artifact set, viewing order, and upload-before-failure ordering pinned.

### External Checks
- GitHub official workflow artifact docs describe `actions/upload-artifact` as the workflow mechanism for uploading one or more files and retaining build/test output for debugging failed tests or production issues: https://docs.github.com/en/actions/tutorials/store-and-share-data

### A/B Decision
- A: leave artifact names only in the workflow upload block. This keeps CI compact but forces operators to infer the product parent JSON from raw artifact names after a failed manual run.
- B: document a fixed triage order and assert it in docs/workflow tests.
- Selected B because the release approval handoff is an operator path, and the first file should be the DeSci parent release-gate JSON that already validates/promotes `release_approval_handoff_summary`.

### Verification
- `python -m pytest apps\desci-platform\backend\tests\test_deployment_docs.py::test_operations_docs_track_release_approval_handoff_summary -q` -> `1 passed`.
- `python -m pytest tests\test_security_gate_contracts.py::test_desci_platform_quality_workflow_has_manual_release_approval_handoff -q` -> `1 passed`.
- `python -m pytest apps\desci-platform\backend\tests\test_deployment_docs.py -q --maxfail=1` -> `9 passed`.
- `python -m pytest tests\test_security_gate_contracts.py -q --maxfail=1` -> `14 passed`.
- `git diff --check -- apps/desci-platform/README.md apps/desci-platform/DEPLOYMENT_GUIDE.md apps/desci-platform/OPERATIONS_RUNBOOK.md apps/desci-platform/backend/tests/test_deployment_docs.py tests/test_security_gate_contracts.py apps/desci-platform/QC_LOG.md` -> pass, with only existing Git LF-to-CRLF working-copy warnings for tracked files.

### Result
- Manual release approval handoff artifacts now have a documented operator viewing order that starts with the product parent JSON, then the Markdown summary, then raw approval/session/smoke context.
- The workflow contract now asserts artifact upload precedes the final fail-closed step, preserving evidence even when approval blockers correctly fail the manual job.

## 2026-06-10 (Release Approval Handoff Artifact Index)

### Scope
- Inspected the manual release approval handoff workflow after Loop 96 and found the artifact bundle had a documented viewing order, but no machine-readable index inside the uploaded artifact set.
- Added a `Write release approval handoff artifact index` workflow step before artifact upload.
- The step writes `var/release-approval-handoff-artifact-index-machine.json` with:
  - `schema_version: 1` and UTC `generated_at`.
  - `first_decision_artifact` pointing at `var/desci-release-gate-release-approval-handoff-machine.json`.
  - `upload_before_fail_closed: true`.
  - wrapper and DeSci release-gate handoff exit codes from step outputs.
  - `review_order` plus per-artifact `exists` and `size_bytes` metadata.
- Added the index to the uploaded artifact set and changed the handoff upload policy to `if-no-files-found: error` with `retention-days: 30`.
- Updated product docs, `docs/QUALITY_GATE.md`, and contract tests so the artifact index, review order, upload-before-fail ordering, and retention policy remain discoverable.

### External Checks
- GitHub official workflow artifact docs describe `actions/upload-artifact` as the way to upload build/test output for later debugging and note that a workflow can upload multiple files or directories: https://docs.github.com/en/actions/tutorials/store-and-share-data
- The official `actions/upload-artifact` README documents `if-no-files-found`, `retention-days`, and compression/upload options for artifact policy control: https://github.com/actions/upload-artifact

### A/B Decision
- A: only add `retention-days: 30` to the existing upload step. This improves retention policy but leaves operators to infer bundle contents from filenames.
- B: add a machine-readable artifact index and pin upload retention/error policy.
- Selected B because the manual handoff path is an operator debugging path; the bundle should explain its own review order and show missing artifacts without requiring log parsing.

### Verification
- `python -m pytest tests\test_security_gate_contracts.py::test_github_workflows_are_valid_yaml tests\test_security_gate_contracts.py::test_desci_platform_quality_workflow_has_manual_release_approval_handoff -q` -> `2 passed`.
- `python -m pytest apps\desci-platform\backend\tests\test_deployment_docs.py::test_operations_docs_track_release_approval_handoff_summary -q` -> `1 passed`.
- `python -m pytest tests\test_workspace_smoke.py::test_quality_gate_release_approval_machine_wrapper_exists -q` -> `1 passed`.
- PowerShell parser check for `ops\scripts\run_release_approval_gate_machine.ps1` -> `parsed`.
- `python -m pytest tests\test_security_gate_contracts.py -q --maxfail=1` -> `14 passed`.
- `python -m pytest tests\test_workspace_smoke.py -q --maxfail=1` -> `44 passed`.
- `python -m pytest apps\desci-platform\backend\tests\test_deployment_docs.py -q --maxfail=1` -> `9 passed`.
- Local execution of the workflow index writer with sample exit-code env vars generated `var\release-approval-handoff-artifact-index-machine.json`.
- `python -m json.tool var\release-approval-handoff-artifact-index-machine.json` -> pass.
- Parsed local index proof: `schema_version=1`, `first_decision_artifact=var/desci-release-gate-release-approval-handoff-machine.json`, `upload_before_fail_closed=True`, exit codes `release_approval_wrapper=1` and `desci_release_gate_handoff=0`, and review order `product_release_gate_parent`, `operator_markdown_summary`, `raw_release_approval_analysis`, `session_bootstrap_context`, `workspace_smoke_context`.
- `git diff --check -- .github/workflows/desci-platform-quality.yml apps/desci-platform/README.md apps/desci-platform/DEPLOYMENT_GUIDE.md apps/desci-platform/OPERATIONS_RUNBOOK.md docs/QUALITY_GATE.md apps/desci-platform/backend/tests/test_deployment_docs.py tests/test_security_gate_contracts.py tests/test_workspace_smoke.py apps/desci-platform/QC_LOG.md` -> pass, with only existing Git LF-to-CRLF working-copy warnings for tracked files.

### Result
- The manual release approval handoff artifact bundle now includes a machine-readable index that records decision order, exit codes, and artifact existence/size metadata.
- Artifact upload is still before the final fail-closed step, but now has explicit `if-no-files-found: error` and 30-day retention policy for the manual handoff bundle.

## 2026-06-10 (Release Approval Handoff Artifact Index Script)

### Scope
- Inspected the Loop 97 artifact-index workflow step and found the logic was embedded as a long inline Python block inside `.github/workflows/desci-platform-quality.yml`.
- Moved that logic into `ops/scripts/write_release_approval_handoff_artifact_index.py` so the manual handoff bundle index is repo-owned, locally runnable, and directly unit-tested.
- The workflow now calls `uv run python ops/scripts/write_release_approval_handoff_artifact_index.py --json-out var/release-approval-handoff-artifact-index-machine.json`.
- Added `ops/scripts/write_release_approval_handoff_artifact_index.py` to the workflow path filters so changes to the index contract trigger the DeSci platform quality workflow.
- Extended the index payload with `all_required_artifacts_present`, `missing_artifact_count`, and `missing_artifacts` while preserving `schema_version`, `generated_at`, `first_decision_artifact`, `upload_before_fail_closed`, `exit_codes`, `review_order`, and per-artifact `exists`/`size_bytes`.
- Added `tests/test_release_approval_handoff_artifact_index.py` for complete bundle, missing bundle member, and CLI atomic-write coverage.
- Updated product docs, `docs/QUALITY_GATE.md`, and contract tests so the script path and expanded index fields stay discoverable.

### External Checks
- GitHub official workflow artifact docs describe workflow artifacts as retained workflow output that can be uploaded for later debugging, including multiple files or directories: https://docs.github.com/en/actions/tutorials/store-and-share-data
- The official `actions/upload-artifact` README documents `if-no-files-found` and `retention-days`, which remain the handoff bundle upload policy: https://github.com/actions/upload-artifact

### A/B Decision
- A: keep the inline Python block in the workflow. This keeps the YAML self-contained but makes the artifact-index contract harder to unit-test and reuse locally.
- B: move index writing into a repo-owned Python script and make the workflow call that script.
- Selected B because release approval handoff artifacts are part of the operator evidence contract, and that contract should be testable without editing or executing the whole GitHub Actions job.

### Verification
- `python -m pytest tests\test_release_approval_handoff_artifact_index.py -q` -> `3 passed`.
- `python -m pytest tests\test_security_gate_contracts.py::test_github_workflows_are_valid_yaml tests\test_security_gate_contracts.py::test_desci_platform_quality_workflow_covers_all_workspace_scopes tests\test_security_gate_contracts.py::test_desci_platform_quality_workflow_has_manual_release_approval_handoff -q` -> `3 passed`.
- `python -m pytest apps\desci-platform\backend\tests\test_deployment_docs.py::test_operations_docs_track_release_approval_handoff_summary -q` -> `1 passed`.
- `python -m pytest tests\test_workspace_smoke.py::test_quality_gate_release_approval_machine_wrapper_exists -q` -> `1 passed`.
- `$env:WRAPPER_EXIT_CODE='1'; $env:RELEASE_GATE_HANDOFF_EXIT_CODE='0'; uv run python ops\scripts\write_release_approval_handoff_artifact_index.py --json-out var\release-approval-handoff-artifact-index-machine.json` -> generated the local index proof.
- `python -m py_compile ops\scripts\write_release_approval_handoff_artifact_index.py` -> pass.
- `python -m pytest tests\test_security_gate_contracts.py -q --maxfail=1` -> `14 passed`.
- `python -m pytest tests\test_workspace_smoke.py -q --maxfail=1` -> `44 passed`.
- `python -m pytest apps\desci-platform\backend\tests\test_deployment_docs.py -q --maxfail=1` -> `9 passed`.
- `python -m json.tool var\release-approval-handoff-artifact-index-machine.json` -> pass.
- Parsed local index proof: `schema_version=1`, `first_decision_artifact=var/desci-release-gate-release-approval-handoff-machine.json`, `upload_before_fail_closed=True`, `all_required_artifacts_present=False`, `missing_artifact_count=4`, exit codes `release_approval_wrapper=1` and `desci_release_gate_handoff=0`, and review order `product_release_gate_parent`, `operator_markdown_summary`, `raw_release_approval_analysis`, `session_bootstrap_context`, `workspace_smoke_context`.
- Scanned `var\release-approval-handoff-artifact-index-machine.json`, `ops\scripts\write_release_approval_handoff_artifact_index.py`, and `tests\test_release_approval_handoff_artifact_index.py` for raw `postgres://`, `postgresql://`, `mcp.notion.com/authorize`, `Bearer `, `sbp_`, and `sb_secret_` markers -> none found.
- `git diff --check -- .github/workflows/desci-platform-quality.yml ops/scripts/write_release_approval_handoff_artifact_index.py tests/test_release_approval_handoff_artifact_index.py apps/desci-platform/README.md apps/desci-platform/DEPLOYMENT_GUIDE.md apps/desci-platform/OPERATIONS_RUNBOOK.md docs/QUALITY_GATE.md apps/desci-platform/backend/tests/test_deployment_docs.py tests/test_security_gate_contracts.py tests/test_workspace_smoke.py apps/desci-platform/QC_LOG.md` -> pass, with only existing Git LF-to-CRLF working-copy warnings for tracked files.

### Result
- The manual release approval handoff artifact index is no longer hidden in workflow YAML; it is a tested repo script with a stable JSON contract.
- Operators still get the same uploaded index artifact, now with explicit missing-artifact summary fields for faster incomplete-bundle triage.

## 2026-06-10 (Release Approval Handoff Artifact Index Job Summary)

### Scope
- Inspected the Loop 98 artifact-index script and workflow after moving the JSON writer out of YAML.
- Found that operators still needed to download the artifact bundle to see the index's missing count and first decision artifact.
- Extended `ops/scripts/write_release_approval_handoff_artifact_index.py` with:
  - `render_markdown_summary(payload)` for a compact job-summary Markdown table.
  - `--markdown-summary-out` for local/CI proof artifacts.
  - `--append-github-step-summary` for appending the compact summary to `GITHUB_STEP_SUMMARY`.
- Updated the manual `release_approval_handoff` workflow step to write `var/release-approval-handoff-artifact-index-summary.md`, append it to the GitHub job summary, and upload it with the JSON index.
- Updated product docs, `docs/QUALITY_GATE.md`, and contract tests so the job-summary append and Markdown summary artifact remain discoverable.

### External Checks
- GitHub official workflow-command docs state that custom Markdown can be added to a job summary through the `GITHUB_STEP_SUMMARY` environment file, and job summaries are shown on the workflow run summary page: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands
- GitHub official artifact docs still support preserving generated workflow output as artifacts, so the Markdown summary is uploaded alongside the JSON index: https://docs.github.com/en/actions/tutorials/store-and-share-data

### A/B Decision
- A: keep the artifact index available only as downloadable JSON/Markdown files.
- B: render a compact Markdown summary from the same script and append it to `GITHUB_STEP_SUMMARY`.
- Selected B because the operator path should show missing artifact count, wrapper/release-gate exit codes, and the first decision artifact before anyone downloads the bundle.

### Verification
- `python -m pytest tests\test_release_approval_handoff_artifact_index.py -q` -> `5 passed`.
- `python -m pytest tests\test_security_gate_contracts.py::test_github_workflows_are_valid_yaml tests\test_security_gate_contracts.py::test_desci_platform_quality_workflow_has_manual_release_approval_handoff -q` -> `2 passed`.
- `python -m pytest apps\desci-platform\backend\tests\test_deployment_docs.py::test_operations_docs_track_release_approval_handoff_summary -q` -> `1 passed`.
- `python -m pytest tests\test_workspace_smoke.py::test_quality_gate_release_approval_machine_wrapper_exists -q` -> `1 passed`.
- `$env:WRAPPER_EXIT_CODE='1'; $env:RELEASE_GATE_HANDOFF_EXIT_CODE='0'; $env:GITHUB_STEP_SUMMARY='var\release-approval-handoff-artifact-index-step-summary.md'; uv run python ops\scripts\write_release_approval_handoff_artifact_index.py --json-out var\release-approval-handoff-artifact-index-machine.json --markdown-summary-out var\release-approval-handoff-artifact-index-summary.md --append-github-step-summary` -> generated JSON, Markdown summary, and step-summary proof.
- `python -m json.tool var\release-approval-handoff-artifact-index-machine.json` -> pass.
- Parsed summary proof includes `Release Approval Handoff Artifact Index`, first decision artifact, complete-bundle status, missing artifact count, wrapper exit code, and DeSci release-gate handoff exit code.
- `python -m py_compile ops\scripts\write_release_approval_handoff_artifact_index.py` -> pass.
- `python -m pytest tests\test_security_gate_contracts.py -q --maxfail=1` -> `14 passed`.
- `python -m pytest apps\desci-platform\backend\tests\test_deployment_docs.py -q --maxfail=1` -> `9 passed`.
- `python -m pytest tests\test_workspace_smoke.py -q --maxfail=1` -> `44 passed`.
- Scanned `var\release-approval-handoff-artifact-index-machine.json`, `var\release-approval-handoff-artifact-index-summary.md`, `var\release-approval-handoff-artifact-index-step-summary.md`, `ops\scripts\write_release_approval_handoff_artifact_index.py`, and `tests\test_release_approval_handoff_artifact_index.py` for raw `postgres://`, `postgresql://`, `mcp.notion.com/authorize`, `Bearer `, `sbp_`, and `sb_secret_` markers -> none found.
- `git diff --check -- .github/workflows/desci-platform-quality.yml ops/scripts/write_release_approval_handoff_artifact_index.py tests/test_release_approval_handoff_artifact_index.py apps/desci-platform/README.md apps/desci-platform/DEPLOYMENT_GUIDE.md apps/desci-platform/OPERATIONS_RUNBOOK.md docs/QUALITY_GATE.md apps/desci-platform/backend/tests/test_deployment_docs.py tests/test_security_gate_contracts.py tests/test_workspace_smoke.py apps/desci-platform/QC_LOG.md` -> pass, with only existing Git LF-to-CRLF working-copy warnings for tracked files.

### Result
- Manual release approval handoff runs now expose the artifact-index essentials directly in the GitHub job summary and still upload both JSON and Markdown artifacts.
- The same repo script owns JSON generation, Markdown rendering, local proof output, and job-summary append behavior.

## 2026-06-10 (Release Approval Handoff Artifact SHA-256 Index)

### Scope
- Inspected the Loop 99 artifact-index JSON and Markdown summary path and found the index reported presence and size, but not a digest for confirming artifact identity.
- Added SHA-256 digest metadata for every existing artifact in `ops/scripts/write_release_approval_handoff_artifact_index.py`.
- The JSON index now includes `sha256` and `sha256_short` per artifact when a file exists, and `null` values when the artifact is missing.
- The Markdown summary table now includes a `SHA-256` column with short digest prefixes for compact operator review.
- Updated product docs, `docs/QUALITY_GATE.md`, and contract tests to document and enforce digest visibility.

### External Checks
- Python official `hashlib` docs document SHA-256 support and the `hashlib.file_digest(fileobj, "sha256")` helper for efficient file hashing: https://docs.python.org/3/library/hashlib.html
- GitHub official artifact docs describe workflow artifacts as retained workflow outputs, so digesting the files listed in the uploaded handoff bundle strengthens artifact identity/debug signals without changing the upload mechanism: https://docs.github.com/en/actions/tutorials/store-and-share-data

### A/B Decision
- A: keep index fields at `exists` and `size_bytes`. This is enough to see missing files but weak for artifact identity.
- B: add SHA-256 digests for existing artifacts and show short prefixes in the job-summary table.
- Selected B because SHA-256 is available in the Python standard library, requires no dependency, and gives operators a stable identity signal for downloaded handoff files.

### Verification
- Initial `python -m pytest tests\test_release_approval_handoff_artifact_index.py -q` failed because the expected digest was computed from LF text while Windows wrote CRLF bytes. Fixed the test to compute the expected digest from the actual file bytes.
- `python -m pytest tests\test_release_approval_handoff_artifact_index.py -q` -> `5 passed`.
- `python -m pytest tests\test_security_gate_contracts.py::test_desci_platform_quality_workflow_has_manual_release_approval_handoff apps\desci-platform\backend\tests\test_deployment_docs.py::test_operations_docs_track_release_approval_handoff_summary -q` -> `2 passed`.
- `$env:WRAPPER_EXIT_CODE='1'; $env:RELEASE_GATE_HANDOFF_EXIT_CODE='0'; $env:GITHUB_STEP_SUMMARY='var\release-approval-handoff-artifact-index-step-summary.md'; uv run python ops\scripts\write_release_approval_handoff_artifact_index.py --json-out var\release-approval-handoff-artifact-index-machine.json --markdown-summary-out var\release-approval-handoff-artifact-index-summary.md --append-github-step-summary` -> regenerated local JSON, Markdown summary, and step-summary proof.
- `python -m json.tool var\release-approval-handoff-artifact-index-machine.json` -> pass.
- Parsed local index proof: `schema_version=1`, `all_required_artifacts_present=False`, `missing_artifact_count=4`, and existing `operator_markdown_summary` artifact has `sha256_short=716a143726d6`.
- Parsed Markdown and step-summary proof include the `SHA-256` table column.
- `python -m pytest tests\test_security_gate_contracts.py -q --maxfail=1` -> `14 passed`.
- `python -m pytest apps\desci-platform\backend\tests\test_deployment_docs.py -q --maxfail=1` -> `9 passed`.
- `python -m pytest tests\test_workspace_smoke.py -q --maxfail=1` -> `44 passed`.
- Scanned `var\release-approval-handoff-artifact-index-machine.json`, `var\release-approval-handoff-artifact-index-summary.md`, `var\release-approval-handoff-artifact-index-step-summary.md`, `ops\scripts\write_release_approval_handoff_artifact_index.py`, and `tests\test_release_approval_handoff_artifact_index.py` for raw `postgres://`, `postgresql://`, `mcp.notion.com/authorize`, `Bearer `, `sbp_`, and `sb_secret_` markers -> none found.
- `git diff --check -- .github/workflows/desci-platform-quality.yml ops/scripts/write_release_approval_handoff_artifact_index.py tests/test_release_approval_handoff_artifact_index.py apps/desci-platform/README.md apps/desci-platform/DEPLOYMENT_GUIDE.md apps/desci-platform/OPERATIONS_RUNBOOK.md docs/QUALITY_GATE.md apps/desci-platform/backend/tests/test_deployment_docs.py tests/test_security_gate_contracts.py tests/test_workspace_smoke.py apps/desci-platform/QC_LOG.md` -> pass, with only existing Git LF-to-CRLF working-copy warnings for tracked files.

### Result
- Release approval handoff artifact indexes now carry file identity metadata for every present artifact without adding dependencies.
- The GitHub job-summary view remains compact by showing short SHA-256 prefixes while the JSON artifact preserves full digests.
