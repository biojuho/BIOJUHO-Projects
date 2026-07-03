# 핸드오프 0013 — review submission copy feedback helper 리팩터링

- **상태:** DONE
- **기획자:** Codex 기획
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-06-11

## 목표
`review-submission-copy.js`의 `copyReviewPackageFilledText`에서 copy 성공/실패에 따른 dataset, status text, toast text/tone 결정을 private helper로 분리해 review submission copy path의 의도를 명확히 하고 동작은 보존한다.

## 배경
review copy 계열에서 `copied` boolean을 `"true"`/`"false"`, 성공/실패 status, 성공/실패 toast, `info`/`error` tone으로 매핑하는 중복을 0010~0012에서 정리했다. `review-submission-copy.js`에도 같은 형태의 매핑이 한 곳 남아 있다.

## 리서치 A/B
| 선택지 | 장점 | 단점 | 결정 |
| --- | --- | --- | --- |
| A. required/warn branch까지 helper화 | 전체 copy flow가 더 짧아진다 | 입력 필수 조건, fallback 문구, warn tone까지 섞여 리팩터링 범위가 커진다 | 보류 |
| B. 성공/실패 feedback mapping만 helper화 | behavior-preserving equality smoke가 명확하고 review-copy-actions 패턴과 일관된다 | required/warn branch는 그대로 남는다 | 채택 |

## 범위
- **건드릴 것:** `review-submission-copy.js`, `handoffs/0013-review-submission-copy-feedback-refactor.md`, `WORKLOG.md`.
- **건드리지 말 것:** external receipt 값 채우기 로직, required/warn guard 조건과 문구, selector, dataset key, export surface, 외부 전송.

## 단계
1. 직전 루프의 변경 후 `npm test` pass를 기준선으로 삼고, syntax baseline을 확인한다.
2. submission copy feedback helper를 추가하고 `copyReviewPackageFilledText`의 성공/실패 branch만 치환한다.
3. syntax/equality smoke/full test를 실행한다.
4. 반환 섹션과 WORKLOG에 결과를 기록한다.

## 수용 게이트
- `node --check review-submission-copy.js`
- HEAD 대비 VM equality smoke
- `npm test`
- `git diff --check`

## 금지사항
- required/warn guard와 external issue text fill 로직은 이번 루프에서 바꾸지 않는다.
- 외부 push, 배포, remote workflow 설치는 하지 않는다.

---

## 반환 섹션 (실행자가 채운다)
- **결과:** `copyFeedback` private helper를 추가하고 `copyReviewPackageFilledText`의 copy 성공/실패 feedback mapping을 해당 helper로 치환했다. external receipt 값 채우기, required/warn guard 조건과 문구, selector, dataset key, export surface는 유지했다.
- **실행한 게이트:** 직전 변경 후 `npm test` pass를 기준선으로 확인, `node --check review-submission-copy.js` pass, HEAD 대비 VM equality smoke pass(external receipt/update success/failure/required 6 cases), 변경 후 `npm test` pass, `git diff --check` pass.
- **남은 것 / 막힌 곳:** 공유 dirty tree와 외부 push/workflow 승인 경계 때문에 커밋·push는 보류. required/warn branch 공통화는 이번 범위 밖으로 남김.
