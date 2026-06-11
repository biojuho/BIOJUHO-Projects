# 핸드오프 0022 — verify summary freshness mismatch repair

- **상태:** DONE
- **기획자:** 사용자 (/goal)
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-06-11

## 목표

`node scripts/audit-release-readiness.mjs --format=summary`에서 재현된 `verify_command_gate_only` fail을 추측 없이 재현, 원인 규명, 수정, 검증한다.

## 배경

사용자 `/goal` 자율 디버깅 루프의 다음 한 건이다. 0021에서 버그 인벤토리는 완료됐고, 이후 로컬 evidence artifact가 다시 갱신되면서 release readiness summary가 `282 pass, 1 fail, 0 not_run, 1 blocked`로 떨어졌다. `npm run verify:full` 재동기화 뒤에도 generatedAt-only refresh가 같은 fail을 재발시킬 수 있어 audit semantic sync guard가 필요하다.

## 범위

- **건드릴 것:** `scripts/audit-release-readiness.mjs`, `scripts/test-pure-helpers.mjs`, `handoffs/0022-verify-summary-sync-repair.md`, `WORKLOG.md`, 재현된 evidence artifact freshness mismatch를 고치는 데 필요한 generated artifact.
- **건드리지 말 것:** push, dispatch, workflow 설치, public launch claim, unrelated `pwa-runtime.js` 변경 되돌리기.

## 단계

1. release readiness summary 실패를 재현한다.
2. fail id와 evidence mismatch를 JSON audit로 격리한다.
3. 근본 원인이 코드 결함인지 stale generated artifact인지 판별한다.
4. 공식 repair 경로인 `npm run verify:full`로 evidence artifacts를 재동기화한다.
5. generatedAt-only refresh가 재발 fail을 만들면 audit 비교를 semantic guard로 보강하고 회귀 테스트를 추가한다.
6. 같은 재현 명령을 다시 실행해 `verify_command_gate_only` fail이 사라졌는지 확인한다.

## 수용 게이트

- `node scripts/audit-release-readiness.mjs --format=summary`가 `verify_command_gate_only` fail 없이 `blocked` 상태만 보고해야 한다.
- `npm run verify:full`이 release evidence sync를 갱신하고 최종 `evidenceSync: pass`를 보여야 한다.
- `npm run test:unit`이 generatedAt-only drift 회귀 테스트를 포함해 통과해야 한다.
- 남은 blocked 항목이 외부 workflow/branch sync 경계임을 명시해야 한다.

## 금지사항

- 재현되지 않은 코드 변경 금지.
- push, workflow dispatch, workflow file remote install 금지.
- 사용자/다른 세션의 dirty change 되돌리기 금지.

---

## 반환 섹션 (실행자가 채운다)

- **결과:** `verify_command_gate_only` fail은 stale `autoresearch-results/verify-workspace-summary.json`이 최신 `data/launch-readiness-refresh.json`/`data/output-quality-audit.json` generatedAt을 따라가지 못해 발생한 generated evidence mismatch로 확인했다. `npm run verify:full`로 artifacts를 재동기화했고, 같은 상태값을 가진 timestamp-only refresh가 반복 fail을 만들지 않도록 `scripts/audit-release-readiness.mjs`가 verify summary의 semantic sync 상태를 비교하게 보강하고 source-contract 테스트를 갱신했다.
- **실행한 게이트:** `node --check pwa-runtime.js` pass, `node --check scripts/audit-release-readiness.mjs` pass, `npm run test:unit` pass, 최초 `node scripts/audit-release-readiness.mjs --format=summary` 재현 fail (`282 pass, 1 fail, 0 not_run, 1 blocked`), `node scripts/audit-release-readiness.mjs --format=json-pretty`로 `verify_command_gate_only` mismatch 확인, `npm run verify:full` 최종 `blocked` (`release_readiness_gates=blocked`, `launch_readiness_refresh=pass`, `product_loop_summary_sync=pass`, `evidenceSync=pass`), 재실행 `node scripts/audit-release-readiness.mjs --format=summary`는 `283 pass, 0 fail, 0 not_run, 1 blocked`로 fail 해소.
- **사용자 가시 변화 한 줄:** 사용자 화면 변화는 없고, release readiness가 로컬 evidence fail이 아닌 외부 승인 대기 blocked 상태로 정리됐다.
- **남은 것 / 막힌 곳:** `publish_branch_sync`와 `remoteWorkflowFilesReady=false`는 원격 workflow 파일 설치/브랜치 sync 승인 없이는 로컬 코드로 해결할 수 없다. 다음 루프 후보는 remote workflow mismatch 재현 및 승인 필요 상태 정리다.
