# 핸드오프 0031 — candidate freshness drift refresh

- **상태:** DONE
- **기획자:** 사용자 (/goal)
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-06-11

## 목표

`node scripts/check-candidate-freshness-drift.mjs --live --fail-on-drift`에서 재현된 live adoption candidate snapshot drift를 원인 확인 후 최소 데이터 갱신으로 해소한다.

## 배경

기본 로컬 게이트와 LLM wiki 보조 체크는 pass였지만, live candidate freshness drift check가 `blockingDriftCount=4`, `actionableDriftCount=4`로 실패했다. 차단 drift는 `HKUDS/nanobot`, `toeverything/AFFiNE`, `colanode/colanode`, `opf/openproject`의 최신 GitHub live metadata/source HEAD와 로컬 `data/adoption-candidates.json` snapshot 불일치다.

## 범위

- **건드릴 것:** `data/adoption-candidates.json`, 검증으로 갱신되는 release/product evidence, 이 핸드오프, `WORKLOG.md`.
- **건드리지 말 것:** 원격 GitHub workflow 파일, dispatch/push/deploy, 외부 claim 상태, unrelated dirty changes 되돌리기.

## 단계

1. live drift 실패를 재현하고 blocking/actionable drift 대상을 기록한다.
2. `refresh-candidate-snapshot.mjs --from-live-drift --actionable-only` dry-run으로 대상이 actionable drift에 한정되는지 확인한다.
3. `--write`로 `data/adoption-candidates.json`만 최신 live snapshot에 맞춰 갱신한다.
4. live drift 재검증과 unit/release summary 회귀 확인을 수행한다.

## 수용 게이트

- `node scripts/check-candidate-freshness-drift.mjs --live --fail-on-drift`가 `blockingDriftCount=0`, `actionableDriftCount=0`으로 통과해야 한다.
- `npm run test:unit`이 통과해야 한다.
- `node scripts/audit-release-readiness.mjs --format=summary`가 `0 fail`, `0 not_run`을 유지해야 한다.

## 금지사항

- advisory-only drift를 차단으로 승격하지 않는다.
- 외부 쓰기/dispatch/push/deploy 금지.
- 사용자/다른 세션의 dirty change 되돌리기 금지.

---

## 반환 섹션 (실행자가 채운다)

- **결과:** `node scripts/check-candidate-freshness-drift.mjs --live --fail-on-drift`에서 `blockingDriftCount=4`, `actionableDriftCount=4`를 재현했고, actionable drift 대상 4건(`HKUDS/nanobot`, `toeverything/AFFiNE`, `colanode/colanode`, `opf/openproject`)을 `node scripts/refresh-candidate-snapshot.mjs --from-live-drift --actionable-only --write`로 갱신했다. 검증 중 새로 발생한 `HKUDS/LightRAG` `openPRs` drift도 같은 루프에서 추가 갱신했다. 최종 live drift check는 `blockingDriftCount=0`, `actionableDriftCount=0`으로 통과했다. 남은 drift는 advisory/cadence/metadata advisory뿐이며 차단 drift로 승격하지 않았다.
- **근본 원인:** live GitHub 후보 저장소의 default-branch commit/metadata가 로컬 `data/adoption-candidates.json` snapshot 이후 갱신되어 freshness gate가 stale snapshot을 차단 drift로 판정했다.
- **수정:** `data/adoption-candidates.json`의 `generatedAt`과 `HKUDS/LightRAG`, `HKUDS/nanobot`, `toeverything/AFFiNE`, `colanode/colanode`, `opf/openproject` snapshot 필드를 최신 live 값으로 갱신했다.
- **실행한 명령:** `node scripts/check-candidate-freshness-drift.mjs --live --fail-on-drift`; `node scripts/refresh-candidate-snapshot.mjs --from-live-drift --actionable-only --repo HKUDS/nanobot`; `node scripts/refresh-candidate-snapshot.mjs --from-live-drift --actionable-only --write`; `node scripts/check-candidate-freshness-drift.mjs --snapshot-only`; `npm run test:unit`; `node scripts/run-local-smoke.mjs scripts/smoke-interactions.mjs`; `node scripts/audit-release-readiness.mjs --run-gates --format=summary`; `npm run refresh:launch-readiness`; `node scripts/audit-release-readiness.mjs --format=summary`; `git diff --check`.
- **검증:** live drift check는 최종 `blockingDriftCount=0`, `actionableDriftCount=0`; snapshot-only check는 pass; unit은 `PASS pure helper unit tests`; interaction smoke는 pass; release readiness는 fresh packaged browser gate cache 기준 `283 pass, 0 fail, 0 not_run, 1 blocked`.
- **남은 것 / 막힌 곳:** 제품/데이터 로컬 gate fail은 없다. 남은 blocked는 기존과 동일하게 외부 승인 필요한 Pages workflow 원격 파일 교체와 branch sync/dispatch guard다.
- **사용자 가시 변화 한 줄:** 포트폴리오 참고 후보 snapshot이 최신 actionable GitHub metadata를 반영해 candidate freshness 차단 drift 없이 유지된다.
