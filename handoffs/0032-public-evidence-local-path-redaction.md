# 핸드오프 0032 — public evidence local path redaction

- **상태:** DONE
- **기획자:** 사용자 (/goal)
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-06-11

## 목표
공개 release package에 포함되는 workflow/publish evidence JSON이 로컬 절대 경로(`/Users/...`)를 노출하지 않는다.

## 배경
`node scripts/plan-workflow-ui-install.mjs`와 `node scripts/plan-publish-dispatch.mjs --repo biojuho/BIOJUHO-Projects` dry-run 출력 및 저장된 `data/*.json`, `dist/release/data/*.json`에서 `repositoryRoot`가 `/Users/ju-hopark/Desktop/JooPark Project`로 노출된다. 두 data 파일은 package release에 포함되는 공개 산출물이므로 privacy leak이다.

## 범위
- **건드릴 것:** `scripts/plan-workflow-ui-install.mjs`, `scripts/plan-publish-dispatch.mjs`, 관련 unit regression, 갱신되는 evidence/package 산출물.
- **건드리지 말 것:** 원격 GitHub workflow 설치, dispatch, push, public claim, 관련 없는 UI 리팩터.

## 단계
1. planner payload의 공개 필드에서 로컬 절대 경로를 상대/라벨 값으로 redaction한다.
2. regression test로 두 planner가 `/Users/` 절대 경로를 출력하지 않음을 고정한다.
3. write 모드로 evidence를 갱신하고 package release를 재생성해 `dist/release/data/*.json`에도 절대 경로가 남지 않게 한다.
4. unit/lint/release/package/readiness smoke를 돌려 회귀가 없음을 확인한다.

## 수용 게이트
- `node scripts/plan-workflow-ui-install.mjs --write`
- `node scripts/plan-publish-dispatch.mjs --repo biojuho/BIOJUHO-Projects --write`
- `rg -n "/Users/ju-hopark|/Users/" data/workflow-ui-install-plan.json data/publish-dispatch-plan.json dist/release/data/workflow-ui-install-plan.json dist/release/data/publish-dispatch-plan.json`가 수정 후 hit 0
- `npm run test:unit`
- `npm run lint`
- `npm run build`
- `node scripts/verify-release.mjs`
- `node scripts/audit-release-readiness.mjs --format=summary`
- `git diff --check`

## 금지사항
- 외부 원격 쓰기, dispatch, push, 배포, 공개 claim 금지.
- secret/token 출력 금지.
- 범위 밖 파일을 임의로 되돌리지 말 것.

---

## 반환 섹션 (실행자가 채운다)
- **결과:** `workflow-ui-install` 및 `publish-dispatch` planner payload의 공개 `repositoryRoot`를 `project-root` 라벨로 redaction하고 `repositoryRootRedacted=true`를 추가했다. 저장된 `data/*.json`과 재생성된 `dist/release/data/*.json` 모두 `/Users/...` 절대 경로 hit 0을 확인했다. `scripts/test-pure-helpers.mjs`에 두 planner dry-run stdout 및 저장/package evidence의 `/Users/` 비노출 회귀 테스트를 연결했다.
- **실행한 게이트:** `node scripts/plan-workflow-ui-install.mjs --write` pass; `node scripts/plan-publish-dispatch.mjs --repo biojuho/BIOJUHO-Projects --write` pass; 기존 release-readiness live evidence 계약 유지를 위해 `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write` 추가 실행 pass; `npm run build` pass; `rg -n "/Users/ju-hopark|/Users/" data/workflow-ui-install-plan.json data/publish-dispatch-plan.json dist/release/data/workflow-ui-install-plan.json dist/release/data/publish-dispatch-plan.json` hit 0 (`rg_exit=1`); `npm run test:unit` pass; `npm run lint` pass; `node scripts/verify-release.mjs` pass; 최초 `node scripts/audit-release-readiness.mjs --format=summary`는 script hash 변경으로 packaged browser gate cache `not_run`을 재현했고, `node scripts/audit-release-readiness.mjs --run-gates --format=summary`로 fresh cache를 갱신한 뒤 최종 `node scripts/audit-release-readiness.mjs --format=summary`는 `283 pass, 0 fail, 0 not_run, 1 blocked` 및 packaged browser gates pass(cached) 확인; `git diff --check` pass.
- **남은 것 / 막힌 곳:** 로컬 redaction 범위는 완료. 남은 blocked는 기존 외부 승인 대상인 `remoteWorkflowFilesReady=false`, `launchPacketReadyForExternalClaim=false`, `readyForExternalClaim=false` 및 publish branch sync이며, 이 handoff 금지사항에 따라 원격 workflow 설치, dispatch, push, public claim은 수행하지 않았다.
- **사용자 가시 변화 한 줄:** 공개 release package의 workflow/publish evidence JSON이 로컬 사용자 홈 경로를 노출하지 않는다.
