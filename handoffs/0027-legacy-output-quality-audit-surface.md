# 핸드오프 0027 — legacy output quality audit surface

- **상태:** DONE
- **기획자:** 사용자 (/goal)
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-06-11

## 목표

`SMOKE_LEGACY_LAUNCH_META=1 node scripts/run-local-smoke.mjs scripts/smoke-interactions.mjs`에서 0026 이후 남은 `output quality audit state was not surfaced` failure를 재현, 원인 규명, 최소 수정, 검증한다.

## 배경

0025/0026으로 workflow UI install loader와 repair-aware receipt assertion은 회복됐다. legacy smoke는 이제 output quality audit panel 관련 persisted checks만 false로 남는다.

## 범위

- **건드릴 것:** output quality audit loader/render/assertion 관련 최소 파일, `scripts/test-pure-helpers.mjs`, `handoffs/0027-legacy-output-quality-audit-surface.md`, `WORKLOG.md`.
- **건드리지 말 것:** output-quality evidence 내용을 외부 승인 없이 조작, 원격 GitHub 파일, dispatch/push, unrelated generated evidence 되돌리기.

## 단계

1. output quality audit failure assertion 부위를 찾는다.
2. `data/output-quality-audit.json`의 현재 shape와 앱 loader/render 조건을 비교한다.
3. stale 조건이면 현재 evidence 계약에 맞게 최소 수정한다.
4. unit/legacy smoke/release gate를 재실행한다.

## 수용 게이트

- 수정 전 failure가 output quality audit surface로 재현되어 있어야 한다.
- 수정 후 같은 failure와 관련 persisted checks가 사라져야 한다.
- `npm run test:unit`이 통과해야 한다.

## 금지사항

- 외부 쓰기, workflow dispatch, push 금지.
- readyForExternalClaim/remoteWorkflowFilesReady 등 외부 승인 차단 신호를 임의로 pass 처리하지 않는다.
- 사용자/다른 세션의 dirty change 되돌리기 금지.

---

## 반환 섹션 (실행자가 채운다)

- **결과:** `output quality audit state was not surfaced` 및 후속 `output quality audit receipt was not copy-ready` stale assertion을 현재 evidence 계약에 맞게 수정했다. 레거시 smoke 재실행에서 `outputQualityAuditReceipt`, `outputQualityExternalClaimGuard`, `outputQualityArtifactRubric` persisted check가 모두 true로 회복됐고, 다음 failure는 별도 영역인 `publish unblock handoff copy text is incomplete`로 이동했다.
- **변경 파일:** `scripts/smoke-interactions.mjs`, `scripts/test-pure-helpers.mjs`, `handoffs/0027-legacy-output-quality-audit-surface.md`, `WORKLOG.md`.
- **검증 명령:**
  - `node --check scripts/smoke-interactions.mjs`
  - `node --check scripts/test-pure-helpers.mjs`
  - `npm run test:unit`
  - `SMOKE_LEGACY_LAUNCH_META=1 node scripts/run-local-smoke.mjs scripts/smoke-interactions.mjs` (output-quality checks 회복 확인, 남은 failure: `publish unblock handoff copy text is incomplete`)
- **사용자 가시 변화 한 줄:** 시스템 상태의 output quality audit 패널/복사 영수증이 현재 launch guard 상태를 반영해 레거시 smoke에서 통과한다.
- **남은 것:** publish unblock handoff copy text assertion이 다음 버그 루프 후보이며, 외부 차단인 `remoteWorkflowFilesReady=false`/branch sync 승인은 그대로 유지한다.
