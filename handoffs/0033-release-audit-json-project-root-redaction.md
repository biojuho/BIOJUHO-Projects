# 핸드오프 0033 — release audit JSON project root redaction

- **상태:** DONE
- **기획자:** 사용자 (/goal)
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-06-11

## 목표
`scripts/audit-release-readiness.mjs --format=json` 및 markdown 출력이 로컬 절대 경로(`/Users/...`)를 공개 증거로 내보내지 않고, 긴 JSON payload도 잘리지 않은 완전한 JSON으로 출력한다.

## 배경
0032에서 공개 package evidence의 로컬 경로 노출을 제거했지만, release readiness audit의 직접 JSON 출력은 여전히 `projectRoot`를 `/Users/ju-hopark/Desktop/JooPark Project`로 노출한다. 이 출력은 운영 자동화와 외부 handoff에 붙일 수 있는 machine-readable evidence라 같은 redaction 계약이 필요하다. 또한 검증 중 `console.log(JSON.stringify(payload))` 직후 `process.exit(exitCode)`가 호출되어 pipe stdout이 65536바이트 근처에서 잘리고 JSON이 파싱 불가능해지는 현상도 확인됐다.

## 범위
- **건드릴 것:** `scripts/audit-release-readiness.mjs`, 관련 unit regression, 필요한 generated release readiness cache/package 산출물.
- **건드리지 말 것:** 원격 GitHub workflow 설치, dispatch, push, 배포, public claim, 관련 없는 UI 리팩터.

## 단계
1. audit payload의 공개 `projectRoot` 값을 로컬 절대 경로가 아닌 `project-root` 라벨로 redaction한다.
2. redaction 여부를 명시하는 boolean 필드를 추가한다.
3. blocked 상태에서도 stdout이 flush되도록 직접 `process.exit()` 호출을 제거한다.
4. unit regression으로 audit source가 로컬 root를 payload에 직접 넣지 않고 stdout flush를 끊지 않음을 고정한다.
5. JSON/markdown 출력에서 `/Users/` hit 0 및 JSON 파싱 가능성을 확인한다.
6. unit/lint/release readiness smoke를 돌려 회귀가 없음을 확인한다.

## 수용 게이트
- `node scripts/audit-release-readiness.mjs --format=json | rg -n "/Users/ju-hopark|/Users/"`
- `node scripts/audit-release-readiness.mjs --format=json | node -e '<parse projectRoot/projectRootRedacted>'`
- `node scripts/audit-release-readiness.mjs --format=markdown | rg -n "/Users/ju-hopark|/Users/"`
- `node --check scripts/audit-release-readiness.mjs`
- `node --check scripts/test-pure-helpers.mjs`
- `npm run test:unit`
- `npm run lint`
- `node scripts/audit-release-readiness.mjs --format=summary`
- `git diff --check`

## 금지사항
- 외부 원격 쓰기, dispatch, push, 배포, 공개 claim 금지.
- secret/token 출력 금지.
- 범위 밖 파일을 임의로 되돌리지 말 것.

---

## 반환 섹션 (실행자가 채운다)
- **결과:** `audit-release-readiness` payload의 공개 `projectRoot`를 `project-root`로 redaction하고 `projectRootRedacted=true`를 추가했다. 긴 JSON 출력이 blocked exit에서도 잘리지 않도록 마지막 `process.exit(exitCode)`를 `process.exitCode = exitCode`로 바꿨다. `scripts/test-pure-helpers.mjs`에는 audit source가 `projectRoot: root`와 `process.exit(exitCode)`로 회귀하지 않도록 source regression을 추가했다.
- **실행한 게이트:** `node --check scripts/audit-release-readiness.mjs` pass; `node --check scripts/test-pure-helpers.mjs` pass; `node scripts/audit-release-readiness.mjs --format=json` 임시 파일 파싱 pass (`byteLength=633832`, `projectRoot=project-root`, `projectRootRedacted=true`, `localPathExposure=false`, audit exit은 기존 blocked 때문에 1); `node scripts/audit-release-readiness.mjs --format=json | rg -n "/Users/ju-hopark|/Users/"` hit 0; `node scripts/audit-release-readiness.mjs --format=markdown | rg -n "/Users/ju-hopark|/Users/"` hit 0; `npm run test:unit` pass; `npm run lint` pass; `node scripts/audit-release-readiness.mjs --format=summary`는 `283 pass, 0 fail, 0 not_run, 1 blocked`; `npm run build` pass; `node scripts/verify-release.mjs` pass; `rg -n "/Users/ju-hopark|/Users/" data dist/release autoresearch-results/release-readiness-summary.json` hit 0; `git diff --check` pass.
- **남은 것 / 막힌 곳:** 로컬 audit JSON/markdown evidence redaction 및 stdout truncation은 완료. 남은 blocked는 기존 외부 승인 대상인 `publish_branch_sync`, `remoteWorkflowFilesReady=false`, `launchPacketReadyForExternalClaim=false`, `readyForExternalClaim=false`이며 원격 workflow 설치, dispatch, push, public claim은 수행하지 않았다.
- **사용자 가시 변화 한 줄:** release readiness JSON 증거를 복사해도 로컬 홈 경로가 새지 않고, 긴 JSON이 중간에서 잘리지 않는다.
