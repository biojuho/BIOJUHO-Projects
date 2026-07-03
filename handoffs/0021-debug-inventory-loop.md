# 핸드오프 0021 — 사용자 요청 기반 버그 인벤토리와 첫 재현 루프

- **상태:** DONE
- **기획자:** 사용자 (/goal)
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-06-11

## 목표

프로젝트의 알려진 버그·이상 증상을 실제 증거 기반으로 목록화하고, 재현 가능한 최우선 1건이 있으면 재현 → 원인 규명 → 수정 → 검증 순서로 처리한다. 재현 가능한 버그가 없으면 추측으로 수정하지 않고 재현 불가/정보 필요 상태를 기록한다.

## 배경

사용자가 `/goal`로 자율 디버깅 루프를 요청했다. 다만 프로젝트 운영 계약상 루프 작업은 핸드오프로 발급되어야 하므로, 이 파일은 사용자 요청을 실행 가능한 단일 작업 단위로 제한한다.

## 범위

- **건드릴 것:** `handoffs/0021-debug-inventory-loop.md`, `WORKLOG.md`, 재현된 버그의 최소 수정 파일과 해당 회귀 테스트.
- **건드리지 말 것:** 배포·push·workflow dispatch·외부 전송, 비밀키/토큰, 재현되지 않은 증상에 대한 코드 변경, 범위 밖 리팩터.

## 단계

1. `WORKLOG.md`, `handoffs/`, 현재 git 상태, 기존 검증 산출물에서 알려진 버그·이상 증상을 수집한다.
2. 각 항목에 재현 절차·기대 동작·실제 동작·우선순위(심각도 x 빈도)를 붙인다.
3. 재현 가능한 최우선 1건이 있으면 한 루프만 수행한다: 재현 → 격리 → 원인 규명 → 수정 → 검증 → 기록.
4. 재현 가능한 버그가 없으면 코드 변경 없이 재현 불가/정보 필요를 반환 섹션에 기록한다.

## 수용 게이트

- 재현 가능한 버그가 있을 때: 해당 재현 절차 재실행 pass, 관련 회귀 테스트 pass, 필요한 최소 테스트 명령 pass.
- 재현 가능한 버그가 없을 때: 증상 목록과 정보 필요 항목이 반환 섹션에 기록되고 `git status`가 불필요한 변경 없이 설명 가능해야 한다.

## 금지사항

- 추측으로 코드를 고치지 않는다.
- 한 번에 버그 1건만 수정한다.
- push·dispatch·배포 금지.
- 막히면 반환 섹션에 적고 중단한다.

---

## 반환 섹션 (실행자가 채운다)

- **결과:** 0단계 인벤토리를 수행했다. 현재 코드 수정 대상으로 볼 수 있는 재현된 제품 버그는 확인되지 않았다. 확인된 이상 상태는 (1) `node scripts/audit-release-readiness.mjs --format=summary`가 `packaged_browser_gates` cache context mismatch로 `not_run`을 보고하는 상태, (2) `remoteWorkflowFilesReady=false`/`readyForExternalClaim=false` 외부 workflow 설치·푸시 승인 차단, (3) 별도 세션이 남긴 것으로 보이는 `scripts/test-pure-helpers.mjs`/`WORKLOG.md` 미커밋 리팩터 변경이다. (1)은 현재 dirty tree와 stale packaged gate cache의 불일치로 재현되며, 감사 출력이 제시한 repair는 `--run-gates` 재실행이지만 unrelated dirty change가 있어 이 핸드오프에서 산출물 갱신으로 덮지 않았다. (2)는 사용자 승인 U1/U2 없이는 코드로 해결할 수 없는 외부 상태다. (3)은 사용자/다른 세션 변경으로 취급해 되돌리지 않았다.
- **실행한 게이트:** `node --check scripts/test-pure-helpers.mjs` pass, `npm run test:unit` pass, `git diff --check -- WORKLOG.md scripts/test-pure-helpers.mjs handoffs/0021-debug-inventory-loop.md` pass, `node scripts/audit-release-readiness.mjs --format=summary` reproduced `blocked`/`not_run` state with 282 pass, 0 fail, 1 not_run, 1 blocked.
- **사용자 가시 변화 한 줄:** 사용자 화면 변화는 없다. 이번 작업은 재현 가능한 코드 버그가 있는지 판별하고 추측 수정을 막은 운영 점검이다.
- **남은 것 / 막힌 곳:** unrelated dirty tree(`scripts/test-pure-helpers.mjs`, `WORKLOG.md`)가 남아 있어 내가 단독 커밋하지 않았다. 해당 변경의 소유자가 정리한 뒤 `node scripts/audit-release-readiness.mjs --run-gates --format=summary`와 `npm run refresh:launch-readiness`를 실행하면 packaged gate cache mismatch를 해소할 수 있다. 외부 launch 차단은 U1/U2 승인 없이는 계속 남는다.
