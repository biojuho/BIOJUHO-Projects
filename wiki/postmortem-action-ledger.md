---
updated: 2026-06-08T15:49:53+09:00
confidence: medium
source_types:
  - web
  - paper
  - standard
  - book
sources:
  - id: google_sre_postmortem_culture
    type: web
    title: Google SRE postmortem culture
    url: https://sre.google/sre-book/postmortem-culture/
    checked: 2026-06-08
  - id: google_sre_workbook_postmortem
    type: web
    title: Google SRE workbook postmortem practices
    url: https://sre.google/workbook/postmortem-culture/
    checked: 2026-06-08
  - id: nist_sp_800_61r3
    type: standard
    title: NIST SP 800-61 Rev. 3
    url: https://csrc.nist.gov/pubs/sp/800/61/r3/final
    checked: 2026-06-08
  - id: pagerduty_postmortems
    type: web
    title: PagerDuty post-incident reviews and postmortems
    url: https://support.pagerduty.com/main/docs/post-incident-reviews-and-postmortems
    checked: 2026-06-08
  - id: failures_and_fixes
    type: paper
    title: "Failures and Fixes: A Study of Software System Incident Response"
    url: https://arxiv.org/abs/2008.11192
    checked: 2026-06-08
  - id: dekker_human_error
    type: book
    title: "The Field Guide to Understanding 'Human Error'"
    url: https://openlibrary.org/books/OL27171642M/The_field_guide_to_understanding_%27human_error%27
    checked: 2026-06-08
tags:
  - llm-wiki
  - autoresearch
  - postmortem
  - incidents
  - action-items
  - evals
---

# Postmortem Action Ledger

The postmortem action ledger tracks whether an incident actually changed the system. For LLM features, action items should close only when the recurrence hypothesis is tested by an eval, a trace replay, a rollout guard, or a runtime control.

## Ledger Contract

```js
const postmortemAction = {
  action_id: "pal-20260608-007",
  incident_id: "inc-20260608-llm-eval-002",
  failure_cluster_id: "fc-support-20260608-014",
  postmortem_url: "obsidian://wiki/postmortem-...",
  recurrence_hypothesis: "retrieval index omitted the new refund policy page",
  owner: "search-platform",
  due_at: "2026-06-15",
  priority: "p0|p1|p2|p3",
  action_type: "code|prompt|retrieval|tool-permission|policy|process|dataset|observability",
  closure_gate: "acceptance_eval|trace_replay|canary_metric|manual_review|doc_update",
  closure_evidence_id: "evalrun_...",
  status: "open|blocked|ready_for_verification|closed|accepted_risk",
  reviewer: "release_owner",
  closed_at: null,
};
```

If there is no closure gate, the item is not an action; it is a note.

## Postmortem Action Contract Extension

The app-level compatibility marker is `postmortem_action_ledger`, and the durable schema is `postmortem_action_contract`. A complete action row includes `action_item_id`, `postmortem_id`, `incident_id`, `failure_cluster_id`, `eval_run_id`, `dataset_run_id`, `trace_id`, `judge_id`, `score_config_id`, `calibration_set_id`, `action_type`, `prevent_action`, `detect_action`, `mitigate_action`, `owner_team`, `action_owner_id`, `tracking_ticket`, `priority`, `due_at`, `verifiable_end_state`, `acceptance_eval_id`, `acceptance_eval_run_id`, `regression_eval_suite`, `closure_evidence_uri`, `closure_reviewer_id`, `postmortem_reviewed_at`, `blameless`, `root_cause`, `trigger`, `lessons_learned`, `recurrence_linked_incident_id`, `stale_action_escalation`, `action_status=closed`, and `risk_acceptance`.

NIST SP 800-61 Rev. 3 maps incident response into CSF 2.0 functions: `Govern`, `Identify`, `Protect`, `Detect`, `Respond`, and `Recover`. JooPark should use that mapping to separate prevention work from detection and recovery work, while Google SRE postmortems keep the review blameless and action-oriented. Langfuse `Annotation Queues`, `score config`, and score analytics are useful when action closure depends on human review plus eval evidence.

## Action Types

| Type | Example | Closure evidence |
| --- | --- | --- |
| `code` | Fix schema validation for a tool call. | Unit/integration test plus trace replay. |
| `prompt` | Add citation-before-answer instruction. | Prompt regression eval and judge calibration check. |
| `retrieval` | Rebuild index or change chunking. | [[rag-evals]] recall/nDCG and failed-row replay. |
| `tool-permission` | Require approval before side-effect tool. | Permission eval and approval audit record. |
| `policy` | Update safety or privacy rubric. | [[safety]] eval and human policy review. |
| `process` | Require canary for model route changes. | [[rollout-decision-log]] evidence on next rollout. |
| `dataset` | Add incident-derived counterexamples. | [[eval-dataset-governance]] row lineage and holdout check. |
| `observability` | Emit score and trace ids in release panel. | Dashboard screenshot or trace query link. |

## Closure Rules

- Every severe [[eval-failure-triage]] cluster needs at least one owner and one closure gate.
- Actions that change model behavior must rerun the same acceptance eval that would have caught the incident.
- Actions that change process must be exercised in the next relevant rollout decision, not only documented.
- Actions involving privacy, security, or excessive agency need reviewer signoff before `closed`.
- Reopened incidents should reference the old `action_id` so ineffective mitigations stay visible.

Google SRE frames postmortems as written records of impact, response, root causes, and follow-up actions. PagerDuty's post-incident review model similarly keeps timelines and action items tied to incident evidence. NIST SP 800-61 Rev. 3 keeps incident response in a broader risk-management loop, so the ledger should feed readiness and prevention, not only incident cleanup.

## Eval-Gated Closure

| Incident class | Minimum closure gate | Related wiki |
| --- | --- | --- |
| Grounding or citation regression | Failed rows replayed and pass with same grader version. | [[rag-evals]], [[evaluator-calibration]] |
| Tool side effect | Trace replay plus permission approval evidence. | [[agent-tool-permissions]] |
| Sensitive disclosure | Red-team/privacy eval plus retention review. | [[data-privacy-retention]], [[safety]] |
| Canary regression | Next rollout decision shows guardrail triggered or telemetry improved. | [[rollout-decision-log]], [[runtime-reliability]] |
| Judge drift | Human label agreement recovers above threshold. | [[evaluator-calibration]] |
| Dataset contamination | Row quarantined and replacement dataset version released. | [[eval-dataset-governance]] |

## A/B: Ticket Queue vs Ledger

| Choice | Strength | Weakness | Adoption |
| --- | --- | --- | --- |
| Ticket queue only | Fits engineering workflow and sprint planning. | Closure evidence gets detached from incident and eval context. | Keep for implementation tasks. |
| Postmortem action ledger | Preserves incident, cluster, owner, gate, and closure proof in one place. | Needs discipline to keep current. | Use as release evidence source of truth. |

## A/B 비교: free-form postmortem vs action ledger

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. Free-form postmortem | 맥락과 narrative를 빠르게 기록하기 좋음 | owner, due date, eval closure evidence가 흩어지기 쉬움 | incident explanation과 learning record |
| B. Action ledger | owner, closure gate, recurrence evidence, `action_status=closed`를 구조화 | schema 유지와 stale action 관리가 필요 | production LLM incident 기본값 |

## A/B 비교: manual closure vs eval-gated closure

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. Manual closure | 빠르고 예외 상황 설명이 쉬움 | 실제 regression 재발 방지를 보장하지 않음 | low-risk docs/process action |
| B. Eval-gated closure | 같은 failure_cluster_id 재현 여부를 수치로 확인 | eval suite와 artifact 관리 필요 | judge/retrieval/tool/safety action 기본값 |

## A/B 비교: prevent vs detect/mitigate action

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. Prevent action | 원인을 제거해 recurrence 가능성을 낮춤 | 구현 비용이 크고 시간이 오래 걸릴 수 있음 | P0/P1 user-impacting failure |
| B. Detect/Mitigate action | alert, rollback, fallback으로 blast_radius를 줄임 | 근본 원인이 남을 수 있음 | 단기 containment와 recovery 보조 |

## JooPark Product Hook

The app should expose a small postmortem action table:

- open severe actions by owner and due date;
- actions waiting for eval verification;
- actions reopened after recurrence;
- incidents with no closure gate;
- last release decision affected by each action.

This lets the wiki become an operational memory for future model, prompt, retrieval, and tool-permission changes.

## Open Questions

- Should `accepted_risk` require a separate approval role from release owner?
- What is the SLA for `sev1` and `sev2` LLM action closure?
- Should incident-derived eval rows enter holdout sets or visible regression suites?

## Backlinks

- [[index]]
- [[eval-failure-triage]]
- [[rollout-decision-log]]
- [[rag-evals]]
- [[evaluator-calibration]]
- [[agent-tool-permissions]]
- [[safety]]
- [[data-privacy-retention]]
- [[source-governance]]

## References

### Web

- Google SRE. "Postmortem Culture: Learning from Failure." https://sre.google/sre-book/postmortem-culture/
- Google SRE Workbook. "Postmortem Practices for Incident Management." https://sre.google/workbook/postmortem-culture/
- PagerDuty. "Post-Incident Reviews and Postmortems." https://support.pagerduty.com/main/docs/post-incident-reviews-and-postmortems

### Standard

- NIST. "SP 800-61 Rev. 3: Incident Response Recommendations and Considerations for Cybersecurity Risk Management." https://csrc.nist.gov/pubs/sp/800/61/r3/final

### Paper

- Nygard et al. "Failures and Fixes: A Study of Software System Incident Response." arXiv:2008.11192. https://arxiv.org/abs/2008.11192

### Book

- Dekker. "The Field Guide to Understanding 'Human Error'." CRC Press, 2014. ISBN 9781472439048. https://openlibrary.org/books/OL27171642M/The_field_guide_to_understanding_%27human_error%27
