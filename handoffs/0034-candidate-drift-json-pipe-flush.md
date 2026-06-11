# 핸드오프 0034 — candidate drift JSON pipe flush

- **상태:** DONE
- **기획자:** 사용자 (/goal)
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-06-11

## 목표
`scripts/check-candidate-freshness-drift.mjs --live`의 긴 JSON 출력이 pipe 환경에서도 65536바이트에서 잘리지 않고 완전한 JSON으로 전달된다.

## 배경
`node scripts/check-candidate-freshness-drift.mjs --live > file`은 약 69KB JSON을 정상 생성하지만, `node scripts/check-candidate-freshness-drift.mjs --live | wc -c`는 65536바이트만 받는다. `finish()`가 `console.log(JSON.stringify(...))` 직후 `process.exit()`를 호출해 pipe stdout flush를 끊는 것이 원인이다.

## 범위
- **건드릴 것:** `scripts/check-candidate-freshness-drift.mjs`, 관련 unit regression, 필요한 WORKLOG/핸드오프 기록.
- **건드리지 말 것:** 후보 snapshot 갱신 write, 원격 workflow 설치, dispatch, push, 배포, public claim, 관련 없는 refactor.

## 단계
1. `finish()`의 출력 후 즉시 `process.exit()` 패턴을 제거한다.
2. status에 따른 exit code는 `process.exitCode`로 설정한다.
3. stdout write callback으로 긴 JSON flush를 보장한다.
4. unit regression으로 source가 `process.exit()`로 회귀하지 않도록 고정한다.
5. live JSON pipe byte count와 JSON parse를 확인한다.

## 수용 게이트
- `node scripts/check-candidate-freshness-drift.mjs --live | wc -c`가 65536보다 큰 값
- `node scripts/check-candidate-freshness-drift.mjs --live | node -e '<parse JSON>'`
- `node --check scripts/check-candidate-freshness-drift.mjs`
- `node --check scripts/test-pure-helpers.mjs`
- `npm run test:unit`
- `npm run lint`
- `git diff --check`

## 금지사항
- 외부 원격 쓰기, dispatch, push, 배포, 공개 claim 금지.
- `refresh-candidate-snapshot --write` 금지.
- 범위 밖 파일을 임의로 되돌리지 말 것.

---

## 반환 섹션 (실행자가 채운다)

- **결과:** DONE
- **변경:** `scripts/check-candidate-freshness-drift.mjs`의 `finish()`가 JSON 출력 직후 `process.exit()`를 호출하던 구조를 제거하고, `process.exitCode` 설정 후 `process.stdout.write(..., callback)`이 flush될 때까지 기다리도록 정리했다. `scripts/test-pure-helpers.mjs`에는 `process.exit()` 회귀 방지와 stdout write callback 구조를 확인하는 source regression을 추가했다.
- **검증 명령:**
  - `node scripts/check-candidate-freshness-drift.mjs --live | wc -c` → `69771` bytes
  - `node scripts/check-candidate-freshness-drift.mjs --live | node -e '<parse JSON>'` → `{"bytes":69771,"status":"drift","mode":"live","monitored":35,"blockingDriftCount":3,"actionableDriftCount":3}`
  - `node --check scripts/check-candidate-freshness-drift.mjs`
  - `node --check scripts/test-pure-helpers.mjs`
  - `npm run test:unit`
  - `npm run lint`
  - `git diff --check`
- **사용자 가시 변화 한 줄:** candidate freshness drift live JSON을 pipe로 넘겨도 64KB에서 잘리지 않아 자동화가 완전한 JSON을 파싱할 수 있다.
- **남은 것:** live drift 3건은 현재 snapshot freshness 상태이지만, 본 핸드오프 범위와 금지사항에 따라 `refresh-candidate-snapshot --write`는 실행하지 않았다. 원격 workflow 설치, dispatch, push, public claim도 수행하지 않았다.
- **추가 검증:** 이후 release readiness cache mismatch가 감지되어 `node scripts/audit-release-readiness.mjs --run-gates --format=summary`를 실행했고 fresh packaged browser gates pass, `283 pass, 0 fail, 0 not_run, 1 blocked`로 회복했다. 이어 `npm run build`와 `node scripts/verify-release.mjs`도 pass로 source/dist package를 다시 동기화했다.
