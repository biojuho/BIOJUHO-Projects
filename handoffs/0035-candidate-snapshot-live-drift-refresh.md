# 핸드오프 0035 — candidate snapshot live drift refresh

- **상태:** DONE
- **기획자:** 사용자 (/goal)
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-06-11

## 목표
`data/adoption-candidates.json`의 GitHub 후보 snapshot이 현재 live repository state와 다시 일치해 `check-candidate-freshness-drift --live --fail-on-drift`가 통과한다.

## 배경
0034 검증 후 `node scripts/check-candidate-freshness-drift.mjs --live`가 `status=drift`, `blockingDriftCount=3`, `actionableDriftCount=3`를 보고했다. drift repo는 `web-infra-dev/midscene`, `outline/outline`, `opf/openproject`이며, 이는 upstream GitHub 상태 변화로 로컬 snapshot이 stale해진 상태다.

## 범위
- **건드릴 것:** `data/adoption-candidates.json`, 필요한 WORKLOG/핸드오프 기록, 검증 중 갱신되는 release readiness cache.
- **건드리지 말 것:** 후보 목록 재랭킹/삭제, 원격 workflow 설치, dispatch, push, 배포, public claim, 관련 없는 refactor.

## 단계
1. live drift를 `--fail-on-drift`로 재현한다.
2. `refresh-candidate-snapshot.mjs --from-live-drift --actionable-only --write`로 actionable repo만 갱신한다.
3. snapshot-only와 live fail-on-drift가 모두 통과하는지 확인한다.
4. unit/lint/release readiness/diff check를 돌린다.

## 수용 게이트
- `node scripts/check-candidate-freshness-drift.mjs --live --fail-on-drift` 수정 전 fail, 수정 후 pass
- `node scripts/refresh-candidate-snapshot.mjs --from-live-drift --actionable-only --write`
- `node scripts/check-candidate-freshness-drift.mjs --snapshot-only`
- `npm run test:unit`
- `npm run lint`
- `node scripts/audit-release-readiness.mjs --format=summary`
- `git diff --check`

## 금지사항
- 외부 원격 쓰기, dispatch, push, 배포, 공개 claim 금지.
- snapshot refresh 범위 밖 파일을 임의로 되돌리지 말 것.

---

## 반환 섹션 (실행자가 채운다)

- 완료일: 2026-06-11
- 실행자: Codex
- 사용자 가시 변화 한 줄: 후보 portfolio/search smoke가 최신 GitHub candidate snapshot을 사용해 OpenProject stale commit false negative 없이 동작한다.

### 결과
- 수정 전 `node scripts/check-candidate-freshness-drift.mjs --live --fail-on-drift`에서 `status=drift`, `blockingDriftCount=2`, `actionableDriftCount=2`를 재현했다.
- blocking drift는 `HKUDS/LightRAG`의 `openPRs 26->27`, `opf/openproject`의 `lastCommit 61a078ad2a569301e37a9d655fefbb855ad15b2d->b698ef9eb65ad41e448a72267699f000de74ca78`, `pushedAt 2026-06-11T07:05:21Z->2026-06-11T07:13:51Z`, `openPRs 212->211`이었다.
- `node scripts/refresh-candidate-snapshot.mjs --from-live-drift --actionable-only --write`로 `HKUDS/LightRAG`, `opf/openproject`만 갱신했다.
- 수정 후 live drift는 `status=pass`, `blockingDriftCount=0`, `actionableDriftCount=0`으로 회복했다.
- release readiness는 `283 pass, 0 fail, 0 not_run, 1 blocked`이며 남은 blocked는 기존 외부 workflow 설치/branch sync 승인 대기다.

### 실행한 명령
- `node scripts/check-candidate-freshness-drift.mjs --live --fail-on-drift` (수정 전 fail 재현)
- `node scripts/refresh-candidate-snapshot.mjs --from-live-drift --actionable-only --write`
- `node scripts/check-candidate-freshness-drift.mjs --snapshot-only`
- `node scripts/check-candidate-freshness-drift.mjs --live --fail-on-drift`
- `npm run test:unit`
- `npm run lint`
- `node scripts/audit-release-readiness.mjs --format=summary`
- `git diff --check`

### 남은 것
- 원격 workflow write, dispatch, push, 배포, public claim은 수행하지 않았다.
- `remoteWorkflowFilesReady=false`, `launchPacketReadyForExternalClaim=false`, `readyForExternalClaim=false` 외부 승인 blocker는 그대로 남아 있다.
