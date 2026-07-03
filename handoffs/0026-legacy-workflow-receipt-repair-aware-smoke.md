# 핸드오프 0026 — legacy workflow receipt repair-aware smoke

- **상태:** DONE
- **기획자:** 사용자 (/goal)
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-06-11

## 목표

`SMOKE_LEGACY_LAUNCH_META=1 node scripts/run-local-smoke.mjs scripts/smoke-interactions.mjs`에서 0025 이후 남은 `workflow UI install receipt was not copy-ready` failure를 재현, 원인 규명, 최소 수정, 검증한다.

## 배경

현재 workflow UI install plan은 repair-aware 상태다. Pages workflow는 원격 파일이 존재하지만 template과 달라 edit-file 교체가 필요하고, Drift Watch workflow는 이미 원격 template과 일치해 no-op이다. legacy smoke assertion은 여전히 Pages new-file open command와 Drift Watch pbcopy command를 필수로 기대해 현재 receipt를 false fail 처리한다.

## 범위

- **건드릴 것:** `scripts/smoke-interactions.mjs`, `scripts/test-pure-helpers.mjs`, `handoffs/0026-legacy-workflow-receipt-repair-aware-smoke.md`, `WORKLOG.md`.
- **건드리지 말 것:** workflow template, 원격 GitHub 파일, dispatch/push, generated evidence 되돌리기.

## 단계

1. receipt copy-ready failure의 누락 문자열을 current receipt와 비교한다.
2. smoke assertion을 create-only 기대에서 repair-aware create/edit/verified state 기대로 바꾼다.
3. 순수 테스트에 stale create-only assertion 회귀 방지를 추가한다.
4. legacy smoke와 관련 unit/release gate를 재실행한다.

## 수용 게이트

- 수정 전 missing terms가 Pages new-file open command와 Drift Watch pbcopy command임을 확인해야 한다.
- 수정 후 legacy smoke가 `workflow UI install receipt was not copy-ready`를 내지 않아야 한다.
- `npm run test:unit`이 통과해야 한다.

## 금지사항

- 외부 쓰기, workflow dispatch, push 금지.
- remote workflow mismatch 자체를 우회하거나 ready로 바꾸지 않는다.
- 사용자/다른 세션의 dirty change 되돌리기 금지.

---

## 반환 섹션 (실행자가 채운다)

- **결과:** legacy smoke가 workflow receipt를 create-only 기준으로 검증하고 있어 현재 repair-aware plan(Pages `replace_existing_remote_file`, Drift Watch `verified_remote_matches_template`)을 false fail 처리했다. `scripts/smoke-interactions.mjs`의 receipt/copy assertion을 workflow install card의 `data-workflow-ui-install-action`과 `data-workflow-ui-install-open-command` 기준으로 바꿨고, `scripts/test-pure-helpers.mjs`에 create-only Pages URL 회귀 방지 검사를 추가했다.
- **실행한 게이트:** 수정 전 missing terms가 Pages new-file open command와 Drift Watch pbcopy command임을 확인, `node --check scripts/smoke-interactions.mjs` pass, `node --check scripts/test-pure-helpers.mjs` pass, `npm run test:unit` pass, 재실행 `SMOKE_LEGACY_LAUNCH_META=1 node scripts/run-local-smoke.mjs scripts/smoke-interactions.mjs`에서 `workflow UI install receipt was not copy-ready`와 관련 workflow/publish/launch/provenance persisted false가 회복됨을 확인.
- **사용자 가시 변화 한 줄:** legacy launch meta smoke가 현재 GitHub UI repair plan의 edit/no-op install 경로를 올바르게 검증한다.
- **남은 것 / 막힌 곳:** 같은 legacy smoke는 다음 잔여 failure인 `output quality audit state was not surfaced`에서 계속 fail한다. release audit packaged gate cache는 코드 변경으로 invalid/not_run 상태라 최종 변경 후 product gate 재실행이 필요하다.
