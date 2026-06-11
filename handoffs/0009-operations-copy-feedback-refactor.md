# 핸드오프 0009 — operations copy feedback helper 리팩터링

- **상태:** DONE
- **기획자:** Codex 기획
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-06-11

## 목표
`operations-copy-actions.js`에서 copy 성공/실패에 따라 dataset, status text, toast text/tone을 고르는 결정을 private helper로 분리해 copy feedback 흐름을 읽기 쉽게 만들고 동작은 보존한다.

## 배경
`copyConfiguredText`는 clipboard write 결과를 받은 뒤 같은 `copied ? success : failure` 판단을 여러 UI side effect에 직접 섞어 쓴다. feedback decision helper로 묶으면 side effect 적용 순서는 유지하면서 성공/실패 mapping을 한 곳에서 검증할 수 있다.

## 리서치 A/B
| 선택지 | 장점 | 단점 | 결정 |
| --- | --- | --- | --- |
| A. 인라인 삼항 유지 | 코드 이동이 없고 짧다 | 상태 문자열, status text, toast text/tone 결정이 side effect와 섞인다 | 보류 |
| B. `copyFeedback(copied, config)` helper | 결정과 적용을 분리하고 equality smoke가 쉬워진다 | 아주 작은 helper가 추가된다 | 채택 |

## 범위
- **건드릴 것:** `operations-copy-actions.js`, `handoffs/0009-operations-copy-feedback-refactor.md`, `WORKLOG.md`.
- **건드리지 말 것:** copy action selector, dataset key, status/toast 문구, clipboard API 경로, export surface, 외부 전송.

## 단계
1. 기준선 `npm test` 통과를 확인한다.
2. copy feedback helper를 추가하고 기존 side effect 적용 순서를 유지해 치환한다.
3. syntax/equality smoke/full test를 실행한다.
4. 반환 섹션과 WORKLOG에 결과를 기록한다.

## 수용 게이트
- `node --check operations-copy-actions.js`
- HEAD 대비 VM equality smoke
- `npm test`
- `git diff --check`

## 금지사항
- 성공/실패 dataset 값, status text, toast text/tone, writeClipboardText 호출 순서를 바꾸지 않는다.
- 외부 push, 배포, remote workflow 설치는 하지 않는다.

---

## 반환 섹션 (실행자가 채운다)
- **결과:** `operations-copy-actions.js`의 copy 성공/실패 feedback 결정을 `copyFeedback` private helper로 추출했다. dataset state, status text, toast text/tone 적용 순서와 값은 HEAD 대비 VM equality smoke로 동일함을 확인했다.
- **실행한 게이트:** 기준선 `node --check operations-copy-actions.js` pass, 기준선 `npm test` pass, 변경 후 `node --check operations-copy-actions.js` pass, HEAD 대비 VM equality smoke pass(4 success/failure side-effect cases), 변경 후 `npm test` pass, `git diff --check` pass.
- **남은 것 / 막힌 곳:** 다른 핸드오프/세션의 공유 dirty tree가 남아 있어 커밋은 보류했다. 외부 push, 배포, remote workflow 설치는 명시 승인 전까지 수행하지 않았다.
