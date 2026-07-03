# 핸드오프 0029 — release audit output quality receipt terms

- **상태:** DONE
- **기획자:** 사용자 (/goal)
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-06-11

## 목표

`node scripts/audit-release-readiness.mjs --format=summary`에서 0028 이후 남은 `output_quality_audit_receipt` fail을 재현, 원인 규명, 최소 수정, 검증한다.

## 배경

legacy launch meta smoke는 pass했고 `systemPublishReadiness`, `outputQualityAuditReceipt`, `outputQualityExternalClaimGuard`, `outputQualityArtifactRubric` persisted checks가 true로 회복됐다. 그러나 release audit summary는 현재 `data/output-quality-audit.json`의 pass/guarded evidence shape 대신 이전 blocked receipt terms를 요구해 false negative를 낸다.

## 범위

- **건드릴 것:** `scripts/audit-release-readiness.mjs`의 `output_quality_audit_receipt` evidence terms, 관련 pure regression test, `handoffs/0029-release-audit-output-quality-receipt-terms.md`, `WORKLOG.md`.
- **건드리지 말 것:** output-quality evidence를 임의로 조작, external claim/remote workflow 차단 신호 pass 처리, 원격 GitHub 파일/dispatch/push/deploy.

## 단계

1. `output_quality_audit_receipt` fail의 missing terms를 확인한다.
2. 현재 `data/output-quality-audit.json` receipt/status/rubric/proof-parser/auth-preflight shape와 audit terms를 비교한다.
3. stale audit terms만 현재 계약에 맞게 수정한다.
4. unit/release summary/legacy smoke 관련 게이트를 재실행한다.

## 수용 게이트

- 수정 전 `output_quality_audit_receipt` fail이 재현되어 있어야 한다.
- 수정 후 release summary가 해당 fail 없이 통과하고 남은 항목은 외부 승인 blocked만이어야 한다.
- `npm run test:unit`이 통과해야 한다.

## 금지사항

- `remoteWorkflowFilesReady`, `allDispatchReady`, `readyForExternalClaim` 같은 외부 승인 차단 신호를 임의로 pass 처리하지 않는다.
- 사용자/다른 세션의 dirty change 되돌리기 금지.

---

## 반환 섹션 (실행자가 채운다)

- **결과:** `output_quality_audit_receipt` fail은 release audit의 evidence term/alias가 현재 `data/output-quality-audit.json`의 pass/guarded shape를 충분히 인정하지 못한 false negative였다. pass/100점 artifact rubric, copy-ready completeness pass, guarded zero-parser/6-field parser 전환, workflow auth preflight pass 상태를 current evidence로 인정하도록 `scripts/audit-release-readiness.mjs`를 보정하고 pure regression test를 추가했다.
- **변경 파일:** `scripts/audit-release-readiness.mjs`, `scripts/test-pure-helpers.mjs`, `handoffs/0029-release-audit-output-quality-receipt-terms.md`, `WORKLOG.md`.
- **검증 명령:**
  - `node --check release-status.js`
  - `node --check scripts/audit-release-readiness.mjs`
  - `node --check scripts/smoke-interactions.mjs`
  - `node --check scripts/test-pure-helpers.mjs`
  - `node --check app.js`
  - `npm run test:unit`
  - `node scripts/audit-release-readiness.mjs --format=summary` (`output_quality_audit_receipt` fail 해소, packaged gate cache invalid만 남음)
  - `SMOKE_LEGACY_LAUNCH_META=1 node scripts/run-local-smoke.mjs scripts/smoke-interactions.mjs` (pass)
  - `node scripts/audit-release-readiness.mjs --run-gates --format=summary` (`283 pass, 0 fail, 0 not_run, 1 blocked`)
- **사용자 가시 변화 한 줄:** release readiness audit가 현재 output-quality receipt의 pass/guarded evidence를 false fail로 막지 않는다.
- **남은 것:** 외부 승인 차단(`remoteWorkflowFilesReady=false`, `launchPacketReadyForExternalClaim=false`, `readyForExternalClaim=false`)과 branch sync blocked는 그대로다. 원격 workflow 교체/dispatch/push/deploy는 수행하지 않았다.
