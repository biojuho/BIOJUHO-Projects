# 핸드오프 0028 — legacy publish unblock handoff copy

- **상태:** DONE
- **기획자:** 사용자 (/goal)
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-06-11

## 목표

`SMOKE_LEGACY_LAUNCH_META=1 node scripts/run-local-smoke.mjs scripts/smoke-interactions.mjs`에서 0027 이후 남은 `publish unblock handoff copy text is incomplete` failure를 재현, 원인 규명, 최소 수정, 검증한다.

## 배경

0024~0027로 candidate snapshot, workflow UI install, output-quality audit 관련 stale smoke failures는 회복됐다. legacy smoke는 이제 publish readiness 영역의 unblock handoff copy assertion만 false로 남는다.

## 범위

- **건드릴 것:** publish readiness/unblock handoff copy 렌더링 또는 smoke assertion 관련 최소 파일, `scripts/test-pure-helpers.mjs`, `handoffs/0028-legacy-publish-unblock-handoff-copy.md`, `WORKLOG.md`.
- **건드리지 말 것:** 원격 GitHub workflow 파일, dispatch/push/deploy, external approval 차단 신호 조작, unrelated generated evidence 되돌리기.

## 단계

1. `publish unblock handoff copy text is incomplete` assertion 부위를 찾는다.
2. 현재 publish/launch/workflow evidence의 handoff copy text와 smoke 기대 조건을 비교한다.
3. stale assertion이면 현재 repair-aware evidence 계약에 맞게 최소 수정하고, 실제 렌더링 누락이면 UI copy 생성부를 수정한다.
4. unit/legacy smoke/release summary를 재실행한다.

## 수용 게이트

- 수정 전 failure가 publish unblock handoff copy text로 재현되어 있어야 한다.
- 수정 후 같은 failure와 `systemPublishReadiness` persisted check가 회복되거나, 다음 독립 failure로 이동해야 한다.
- `npm run test:unit`이 통과해야 한다.

## 금지사항

- 외부 쓰기, workflow dispatch, push 금지.
- `remoteWorkflowFilesReady`, `allDispatchReady`, `readyForExternalClaim` 같은 외부 승인 차단 신호를 임의로 pass 처리하지 않는다.
- 사용자/다른 세션의 dirty change 되돌리기 금지.

---

## 반환 섹션 (실행자가 채운다)

- **결과:** `publish unblock handoff copy text is incomplete`는 publish unblock handoff가 Drift Watch workflow target을 전체 경로(`.github/workflows/joopark-drift-watch.yml`)로 명시하지 않아 smoke의 operator handoff completeness gate를 통과하지 못한 문제였다. `release-status.js`의 handoff 텍스트에 Pages/Drift Watch 전체 workflow target path를 추가했고 회귀 테스트를 붙였다.
- **변경 파일:** `release-status.js`, `scripts/test-pure-helpers.mjs`, `handoffs/0028-legacy-publish-unblock-handoff-copy.md`, `WORKLOG.md`.
- **검증 명령:**
  - `node --check release-status.js`
  - `node --check scripts/test-pure-helpers.mjs`
  - `npm run test:unit`
  - `SMOKE_LEGACY_LAUNCH_META=1 node scripts/run-local-smoke.mjs scripts/smoke-interactions.mjs`
- **사용자 가시 변화 한 줄:** System Status의 publish unblock handoff 복사본이 Pages와 Drift Watch workflow target 전체 경로를 모두 포함하고 레거시 smoke의 `systemPublishReadiness`가 pass한다.
- **남은 것:** 외부 승인 차단(`remoteWorkflowFilesReady=false`, branch sync/원격 workflow 교체)은 그대로이며, 코드 변경 뒤 release gate cache 재검증이 필요하다.
