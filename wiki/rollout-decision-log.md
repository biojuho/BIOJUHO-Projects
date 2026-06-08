---
updated: 2026-06-08T15:46:50+09:00
confidence: medium
source_types:
  - web
  - paper
  - book
sources:
  - id: openai_eval_best_practices
    type: web
    title: OpenAI evaluation best practices
    url: https://developers.openai.com/api/docs/guides/evaluation-best-practices
    checked: 2026-06-08
  - id: langfuse_experiments_ci_cd
    type: web
    title: Langfuse experiments in CI/CD
    url: https://langfuse.com/docs/evaluation/experiments/experiments-ci-cd
    checked: 2026-06-08
  - id: openfeature_intro
    type: web
    title: OpenFeature introduction
    url: https://openfeature.dev/docs/reference/intro
    checked: 2026-06-08
  - id: openfeature_evaluation_context
    type: web
    title: OpenFeature Evaluation Context
    url: https://openfeature.dev/specification/sections/evaluation-context/
    checked: 2026-06-08
  - id: opentelemetry_feature_flag_semconv
    type: web
    title: OpenTelemetry feature flag semantic conventions
    url: https://opentelemetry.io/docs/specs/semconv/registry/attributes/feature-flag/
    checked: 2026-06-08
  - id: argo_rollouts_canary
    type: web
    title: Argo Rollouts canary deployment strategy
    url: https://argoproj.github.io/argo-rollouts/features/canary/
    checked: 2026-06-08
  - id: argo_rollouts_analysis
    type: web
    title: Argo Rollouts analysis
    url: https://argoproj.github.io/argo-rollouts/features/analysis/
    checked: 2026-06-08
  - id: google_sre_canarying
    type: web
    title: Google SRE workbook canarying releases
    url: https://sre.google/workbook/canarying-releases/
    checked: 2026-06-08
  - id: github_actions_environments
    type: web
    title: GitHub Actions deployment environments
    url: https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments
    checked: 2026-06-08
  - id: kubernetes_deployment_rollback
    type: web
    title: Kubernetes deployment rollbacks
    url: https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#rolling-back-a-deployment
    checked: 2026-06-08
  - id: ci_cd_slr
    type: paper
    title: "Continuous Integration, Delivery and Deployment: A Systematic Review on Approaches, Tools, Challenges and Practices"
    url: https://arxiv.org/abs/1703.07019
    checked: 2026-06-08
  - id: continuous_delivery_book
    type: book
    title: "Continuous Delivery: Reliable Software Releases through Build, Test, and Deployment Automation"
    url: https://openlibrary.org/works/OL16420058W/Continuous_Delivery
    checked: 2026-06-08
tags:
  - llm-wiki
  - autoresearch
  - rollout
  - feature-flags
  - canary
  - evals
---

# Rollout Decision Log

The rollout decision log is the release evidence record for LLM features. It explains whether a prompt, model, retrieval index, tool permission, or safety policy was promoted, paused, rolled back, or accepted with known risk.

## Decision Contract

```js
const rolloutDecision = {
  decision_id: "rdl-20260608-006",
  release_candidate_id: "prompt-support-v17+retrieval-index-20260608",
  feature_flag_key: "llm.support_triage.v17",
  exposure_stage: "shadow|internal|canary|partial|full|rollback",
  exposure_percent: 10,
  target_segment: "workspace_admins_kr",
  eval_run_ids: ["evalrun_..."],
  acceptance_eval_ids: ["rag-groundedness-v4", "tool-permission-v2"],
  blocker_failure_cluster_ids: [],
  human_approver: "release_owner",
  decision: "promote|pause|rollback|hold|accept_risk",
  decision_reason: "all acceptance evals pass; canary error budget impact below threshold",
  rollback_plan_id: "rollback-support-v16",
  previous_known_good: "prompt-support-v16+retrieval-index-20260601",
  telemetry_window: "2026-06-08T15:00:00+09:00/PT30M",
  evidence_urls: ["trace_dashboard_url", "eval_report_url", "flag_audit_url"],
  created_at: "2026-06-08T15:46:50+09:00",
};
```

The record should be append-only. Edit the current status only when the product needs a concise dashboard value; keep earlier decisions as historical evidence.

## Gate Matrix

| Gate | Promote | Pause | Rollback |
| --- | --- | --- | --- |
| Offline acceptance eval | Required pass on agreed dataset and grader version. | Ambiguous judge output or unstable run. | Critical regression against previous known good. |
| [[eval-failure-triage]] | No open `sev0`/`sev1`; `sev2` below release threshold. | New cluster without owner or root-cause layer. | Safety, privacy, excessive agency, or core workflow cluster. |
| Canary telemetry | Error, latency, cost, and user feedback inside budget. | Telemetry window too short or noisy. | Candidate burns more error budget than allowed. |
| Feature flag audit | Flag target, segment, and default are documented. | Flag is missing owner or expiry. | Flag cannot be disabled quickly. |
| Rollback readiness | Previous known good artifact exists and is tested. | Rollback path is unclear. | Rollback succeeds or kill switch is activated. |

## Evidence Types

- Eval evidence: [[rag-evals]], [[evaluator-calibration]], score distributions, failed rows, grader versions, and comparison to baseline.
- Trace evidence: representative trace ids, tool calls, retrieved documents, latency spans, and policy checks from [[eval-result-lineage]].
- Flag evidence: flag key, provider, targeting rule, default, audit trail, and expiry date.
- Canary evidence: exposure percentage, time window, traffic segment, SLO/error-budget impact, and promotion/abort events.
- Human evidence: release owner, reviewer comments, known risk acceptance, and rollback confirmation.

OpenFeature makes feature flags a vendor-neutral runtime control. Argo Rollouts shows the deployment-side pattern: canary steps, pause points, background analysis, and abort on failed analysis. Google SRE frames canarying as a way to learn from real traffic while limiting error-budget exposure.

## JooPark Rollout Modes

| Mode | Use when | Required decision fields |
| --- | --- | --- |
| `shadow` | Model/prompt/tool observes traffic but does not answer users. | `eval_run_ids`, trace sample, no user-visible side effect. |
| `internal` | Staff or QA users exercise the feature. | target segment, human reviewer, acceptance checklist. |
| `canary` | A small user segment receives output. | exposure percent, telemetry window, rollback plan, failure threshold. |
| `partial` | Feature is expanded but not global. | staged exposure plan, daily eval comparison, support feedback. |
| `full` | Default user path changes. | final acceptance eval, no critical clusters, rollback drill result. |
| `rollback` | Candidate is disabled or reverted. | root cause, previous known good, reopened clusters, postmortem link if required. |

## Anti-Patterns

- Treating an eval pass as a release decision without a flag, exposure, and rollback record.
- Promoting from internal testing to full rollout without a canary or shadow telemetry window.
- Rolling back by memory instead of linking the exact previous known good prompt/model/index/tool policy.
- Letting a feature flag live forever without owner, expiry, and audit trail.
- Combining unrelated changes in one decision record so that rollback causality becomes unclear.

## Product Hook

JooPark should expose a compact release panel:

- Current decision: `promote`, `pause`, `rollback`, `hold`, or `accept_risk`.
- Blocking clusters from [[eval-failure-triage]].
- Acceptance eval trend against previous known good.
- Feature flag key and current exposure percentage.
- Rollback button state: available, unavailable, already rolled back, or manual only.

The UI should show raw evidence links without turning every trace into a visible card. Operators need a scan-first decision surface and a deeper evidence drawer.

## Rollout Decision Contract Extension

The app-level verifier keeps these marker fields as the compatibility contract: `rollout_decision_log`, `rollout_decision_contract`, `decision_id`, `action_item_id`, `postmortem_id`, `release_candidate_id`, `eval_run_id`, `dataset_run_id`, `acceptance_eval_run_id`, `regression_eval_suite`, `rollout_stage`, `rollout_strategy`, `feature_flag_key`, `feature_flag_context`, `targeting_key`, `flag_variant`, `feature_flag.result.variant`, `feature_flag.result.reason`, `feature_flag.version`, `feature_flag.provider.name`, `canary_weight`, `canary_step_index`, `canary_analysis_run_id`, `analysis_status`, `abort_on_failed_analysis`, `guarded_promote`, `promote_criteria`, `rollback_target`, `rollback_trigger`, `rollback_runbook_id`, `rollback_window`, `stable_replica_set`, `deployment_environment`, `environment_protection_rule`, `required_reviewers`, `wait_timer`, `deployment_status_id`, `decision_owner_id`, `approver_id`, `blast_radius`, `observability_window`, `decision_status`, `go_decision`, `no_go_decision`, and `risk_acceptance`.

- Langfuse CI/CD can raise `RegressionError` when an experiment metric is below threshold; JooPark should store that as `no_go_decision` evidence, not only as a failed workflow.
- OpenFeature requires a `targeting key` in evaluation context for stable flag targeting. JooPark stores both `feature_flag_context` and `targeting_key`.
- OpenTelemetry feature flag attributes prefer `feature_flag.result.variant` over raw value when possible, and capture `feature_flag.result.reason`, `feature_flag.version`, and `feature_flag.provider.name`.
- Argo Rollouts canary steps such as `setWeight` and `pause` map to `canary_weight` and `canary_step_index`; the stable/canary ReplicaSet state maps to `stable_replica_set`.
- GitHub environments provide `required reviewers` and wait timers, while Kubernetes `Deployment rollback` provides the deployment-side previous revision path.

## A/B 비교: feature flag rollout vs deployment canary

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. Feature flag rollout | tenant/user cohort를 조절하고 기능 단위 rollback이 쉬움 | flag context, provider state, stale flag cleanup 필요 | prompt/RAG/tool behavior rollout 기본값 |
| B. Deployment canary | infra revision, pod/traffic/SLO를 일관되게 관측 | 사용자 cohort와 기능 단위 targeting이 약함 | runtime/library/container 변경 기본값 |

## A/B 비교: automatic abort vs human approval

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. Automatic abort | p95 latency, error rate, eval regression을 빠르게 차단 | false positive와 context 없는 rollback 가능 | low-ambiguity SLO/eval threshold |
| B. Human approval | product nuance와 risk_acceptance 판단 가능 | 대기 시간과 reviewer 병목 | safety, data, policy, customer-impacting release |

## A/B 비교: dashboard decision vs app-owned decision log

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. Dashboard decision | 공급자 UI에서 빠르게 approve/abort 가능 | eval, flag, canary, deployment evidence가 흩어짐 | 임시 실험과 manual review |
| B. App-owned decision log | `eval_run_id`부터 `deployment_status_id`까지 재현 가능 | schema와 workflow wiring 비용이 있음 | production LLM release 기본값 |

## Open Questions

- Which JooPark changes require canary mode: prompt-only, retrieval index, model route, tool permission, or all user-visible LLM changes?
- Should `accept_risk` be allowed for `sev2` clusters, and who can approve it?
- What telemetry window is long enough for Korean/US timezone traffic differences?

## Backlinks

- [[index]]
- [[eval-failure-triage]]
- [[eval-result-lineage]]
- [[rag-evals]]
- [[runtime-reliability]]
- [[cost-observability]]
- [[postmortem-action-ledger]]
- [[prompt-release-management]]
- [[source-governance]]

## References

### Web

- OpenAI. "Evaluation best practices." OpenAI API docs. https://developers.openai.com/api/docs/guides/evaluation-best-practices
- Langfuse. "Experiments in CI/CD." https://langfuse.com/docs/evaluation/experiments/experiments-ci-cd
- OpenFeature. "Welcome to OpenFeature." https://openfeature.dev/docs/reference/intro
- OpenFeature. "Evaluation Context." https://openfeature.dev/specification/sections/evaluation-context/
- OpenTelemetry. "Feature flag semantic conventions." https://opentelemetry.io/docs/specs/semconv/registry/attributes/feature-flag/
- Argo Rollouts. "Canary Deployment Strategy." https://argoproj.github.io/argo-rollouts/features/canary/
- Argo Rollouts. "Analysis." https://argoproj.github.io/argo-rollouts/features/analysis/
- Google SRE Workbook. "Canarying Releases." https://sre.google/workbook/canarying-releases/
- GitHub Docs. "Managing environments for deployment." https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments
- Kubernetes. "Rolling Back a Deployment." https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#rolling-back-a-deployment

### Paper

- Shahin et al. "Continuous Integration, Delivery and Deployment: A Systematic Review on Approaches, Tools, Challenges and Practices." arXiv:1703.07019. https://arxiv.org/abs/1703.07019

### Book

- Humble and Farley. "Continuous Delivery: Reliable Software Releases through Build, Test, and Deployment Automation." Addison-Wesley, 2010. ISBN 9780321601919. https://openlibrary.org/works/OL16420058W/Continuous_Delivery
