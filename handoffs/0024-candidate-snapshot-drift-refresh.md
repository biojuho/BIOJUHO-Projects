# 핸드오프 0024 — candidate snapshot live drift refresh

- **상태:** DONE
- **기획자:** 사용자 (/goal)
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-06-11

## 목표

`node scripts/check-candidate-freshness-drift.mjs --live --fail-on-drift`에서 재현된 actionable candidate snapshot drift를 추측 없이 재현, 원인 규명, 수정, 검증한다.

## 배경

0022/0023 이후 로컬 release audit의 코드 fail은 해소됐고, product smoke 계열은 병렬 실행의 product smoke lock 때문에 중복 실행하지 않았다. 외부 쓰기 없이 실행 가능한 live freshness check에서 `data/adoption-candidates.json`의 GitHub 후보 메타데이터 drift가 재현됐다.

## 범위

- **건드릴 것:** `data/adoption-candidates.json`, `handoffs/0024-candidate-snapshot-drift-refresh.md`, `WORKLOG.md`.
- **건드리지 말 것:** 원격 GitHub 파일 수정, workflow dispatch, push, unrelated generated evidence 되돌리기.

## 단계

1. live candidate freshness drift를 `--fail-on-drift`로 재현한다.
2. drift 종류가 advisory인지 actionable/blocking인지 구분한다.
3. 공식 refresh 경로인 `refresh-candidate-snapshot.mjs --from-live-drift --actionable-only` dry-run으로 갱신 대상을 확인한다.
4. `--write`로 actionable drift 대상만 로컬 snapshot에 반영한다.
5. 같은 live drift check, snapshot-only check, unit test, release summary를 재실행한다.

## 수용 게이트

- `node scripts/check-candidate-freshness-drift.mjs --live --fail-on-drift`가 수정 전 `status=drift`/`actionableDriftCount=19`를 재현해야 한다.
- 수정 후 같은 명령이 `status=pass`/`blockingDriftCount=0`/`actionableDriftCount=0`이어야 한다.
- `node scripts/check-candidate-freshness-drift.mjs --snapshot-only`와 `npm run test:unit`이 통과해야 한다.
- `node scripts/audit-release-readiness.mjs --format=summary`가 packaged browser gate cache를 pass로 보고해야 한다.

## 금지사항

- 외부 쓰기, workflow dispatch, push 금지.
- advisory-only star/fork drift를 blocking처럼 고치지 않는다.
- 사용자/다른 세션의 dirty change 되돌리기 금지.

---

## 반환 섹션 (실행자가 채운다)

- **결과:** `data/adoption-candidates.json`이 2026-06-09 snapshot이라 live GitHub 후보 메타데이터와 달라졌고, `lastCommit`/`pushedAt`/issue/PR/disk size 계열 actionable drift 19건이 `--fail-on-drift`를 실패시켰다. `refresh-candidate-snapshot.mjs --from-live-drift --actionable-only --write`로 19개 repo의 로컬 snapshot을 최신 live 값으로 갱신했다.
- **실행한 게이트:** `node scripts/check-candidate-freshness-drift.mjs --live --fail-on-drift` 재현 fail (`status=drift`, `actionableDriftCount=19`), dry-run `node scripts/refresh-candidate-snapshot.mjs --from-live-drift --actionable-only --fail-on-change` drift, write refresh pass, 재실행 live drift check pass (`driftCount=9`, `blockingDriftCount=0`, `actionableDriftCount=0`, advisory만 남음), `node scripts/check-candidate-freshness-drift.mjs --snapshot-only` pass, `npm run test:unit` pass, `node scripts/audit-release-readiness.mjs --format=summary` blocked with `283 pass, 0 fail, 0 not_run, 1 blocked` and packaged browser gates pass.
- **사용자 가시 변화 한 줄:** 포트폴리오 참고 후보 데이터가 stale actionable GitHub 메타데이터 대신 최신 live snapshot을 반영한다.
- **남은 것 / 막힌 곳:** advisory-only stars/forks 및 commit-stable metadata-advisory drift는 정책상 nonblocking으로 남아 있고, launch completion은 `remoteWorkflowFilesReady=false` 및 branch sync 승인 대기로 계속 blocked다.
