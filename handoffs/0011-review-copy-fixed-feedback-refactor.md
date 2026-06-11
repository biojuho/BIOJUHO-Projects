# 핸드오프 0011 — review copy fixed feedback helper 리팩터링

- **상태:** DONE
- **기획자:** Codex 기획
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-06-11

## 목표
`review-copy-actions.js`의 고정 copy action 중 단순 성공/실패 feedback mapping을 private helper로 분리해 dataset state, status text, toast text/tone 결정을 한 곳에서 읽히게 만들고 동작은 보존한다.

## 배경
`copyReviewPackagePasteBody`, `copyReviewArtifactReceipt`, `copyIssueFreshReceipt`는 모두 `copied` boolean을 `"true"`/`"false"`, 성공/실패 status 문구, 성공/실패 toast 문구, `info`/`error` tone으로 매핑한다. configured path helper를 이미 분리했으므로, 이번 루프는 ready guard가 없는 고정 copy action만 작게 정리한다.

## 리서치 A/B
| 선택지 | 장점 | 단점 | 결정 |
| --- | --- | --- | --- |
| A. ready guard 포함 모든 fixed action을 한 번에 공통화 | 중복 제거 폭이 크다 | pending/warn 상태까지 섞여 equality 범위와 blast radius가 커진다 | 보류 |
| B. ready guard 없는 fixed action 3개만 helper 적용 | 성공/실패 mapping만 검증하면 되어 범위가 작다 | ready guard 함수 중복은 다음 루프로 남는다 | 채택 |

## 범위
- **건드릴 것:** `review-copy-actions.js`, `handoffs/0011-review-copy-fixed-feedback-refactor.md`, `WORKLOG.md`.
- **건드리지 말 것:** selector, dataset key, status/toast 문구, ready/pending guard 함수, export surface, 외부 전송.

## 단계
1. 직전 루프의 변경 후 `npm test` pass를 기준선으로 삼고, syntax baseline을 확인한다.
2. fixed copy feedback helper를 추가하고 ready guard가 없는 fixed action 3개에만 적용한다.
3. syntax/equality smoke/full test를 실행한다.
4. 반환 섹션과 WORKLOG에 결과를 기록한다.

## 수용 게이트
- `node --check review-copy-actions.js`
- HEAD 대비 VM equality smoke
- `npm test`
- `git diff --check`

## 금지사항
- ready/pending guard 함수는 이번 루프에서 건드리지 않는다.
- 외부 push, 배포, remote workflow 설치는 하지 않는다.

---

## 반환 섹션 (실행자가 채운다)
- **결과:** `copyFeedback` private helper를 추가하고 ready guard가 없는 `copyReviewPackagePasteBody`, `copyReviewArtifactReceipt`, `copyIssueFreshReceipt`의 copy 성공/실패 feedback mapping을 해당 helper로 치환했다. dataset key, status/toast 문구, toast tone, export surface는 유지했다.
- **실행한 게이트:** 직전 변경 후 `npm test` pass를 기준선으로 확인, `node --check review-copy-actions.js` pass, HEAD 대비 VM equality smoke pass(3 functions × success/failure 6 cases), 변경 후 `npm test` pass, `git diff --check` pass.
- **남은 것 / 막힌 곳:** 공유 dirty tree와 외부 push/workflow 승인 경계 때문에 커밋·push는 보류. ready/pending guard 함수 공통화는 이번 범위 밖으로 남김.
