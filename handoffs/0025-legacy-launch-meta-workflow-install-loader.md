# 핸드오프 0025 — legacy launch meta workflow install loader

- **상태:** DONE
- **기획자:** 사용자 (/goal)
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-06-11

## 목표

`SMOKE_LEGACY_LAUNCH_META=1 node scripts/run-local-smoke.mjs scripts/smoke-interactions.mjs`에서 재현된 workflow UI install evidence 로드 실패를 추측 없이 재현, 원인 규명, 수정, 검증한다.

## 배경

기본 `npm test`와 release audit은 pass/blocked 상태지만, legacy launch/proof meta smoke를 강제하면 `workflowUiInstallLoaded=false`가 되어 system evidence panel과 launch runbook 관련 persisted check가 연쇄 실패한다.

## 범위

- **건드릴 것:** `app.js`, `scripts/test-pure-helpers.mjs`, `handoffs/0025-legacy-launch-meta-workflow-install-loader.md`, `WORKLOG.md`.
- **건드리지 말 것:** 원격 GitHub 파일 수정, workflow dispatch, push, unrelated generated evidence 되돌리기.

## 단계

1. legacy meta smoke failure를 재현한다.
2. `data/workflow-ui-install-plan.json`의 실제 shape와 앱 loader 검증 조건을 비교한다.
3. stale threshold만 최소 수정한다.
4. 순수 helper 테스트에 회귀 확인을 추가한다.
5. 재현 명령과 관련 unit/release summary를 재실행한다.

## 수용 게이트

- 수정 전 legacy smoke가 `workflowUiInstallLoaded=false`로 실패해야 한다.
- 수정 후 legacy smoke가 같은 failure를 내지 않아야 한다.
- `npm run test:unit`과 `node scripts/audit-release-readiness.mjs --format=summary`가 기존 release 상태를 보존해야 한다.

## 금지사항

- 외부 쓰기, workflow dispatch, push 금지.
- 외부 approval이 필요한 `remoteWorkflowFilesReady=false` 자체를 우회하지 않는다.
- 사용자/다른 세션의 dirty change 되돌리기 금지.

---

## 반환 섹션 (실행자가 채운다)

- **결과:** `data/workflow-ui-install-plan.json`의 `installReceipt.commandCount`는 현재 generator/audit/smoke 계약상 6개인데, `app.js`의 `loadWorkflowUiInstallPlan()`만 stale 기준인 `>= 8`을 요구해 유효한 evidence를 `loaded=false`로 처리했다. 로더 기준을 `>= 6`으로 맞추고 순수 테스트에 회귀 확인을 추가했다.
- **실행한 게이트:** 수정 전 `SMOKE_LEGACY_LAUNCH_META=1 node scripts/run-local-smoke.mjs scripts/smoke-interactions.mjs` fail (`workflowUiInstallLoaded=false`, settings runbook/source snapshot/GitHub discovery 연쇄 false), `node --check app.js` pass, `node --check scripts/test-pure-helpers.mjs` pass, `npm run test:unit` pass, 수정 후 legacy smoke에서 최초 failure와 관련 persisted checks는 회복됐으나 다음 stale assertion인 `workflow UI install receipt was not copy-ready`로 fail.
- **사용자 가시 변화 한 줄:** System evidence panel이 현재 6-command workflow UI install receipt를 유효한 로드 상태로 인정한다.
- **남은 것 / 막힌 곳:** legacy smoke의 receipt copy-ready assertion이 현재 repair-aware install plan(edit existing Pages workflow, skip already-matching Drift Watch workflow)을 반영하지 못해 루프 5 후보로 남았다. release audit은 `app.js` 변경으로 packaged browser gate cache가 invalid/not_run이며, 최종 변경 후 product gate 재실행이 필요하다.
