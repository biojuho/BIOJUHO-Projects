# 핸드오프 0012 — review copy ready feedback helper 리팩터링

- **상태:** DONE
- **기획자:** Codex 기획
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-06-11

## 목표
`review-copy-actions.js`의 남은 copy action 중 repair payload와 ready-guarded copy의 성공/실패 feedback mapping을 기존 `copyFeedback` private helper로 통일하고, pending/warn guard 동작은 그대로 보존한다.

## 배경
0010/0011에서 configured path와 ready guard 없는 fixed copy action의 성공/실패 mapping을 helper로 분리했다. 아직 `copyReviewArtifactRepairPayload`, `copyReviewArtifactPostApplyReceipt`, `copyReviewPostRepairArtifactLink`에는 같은 state/status/toast/tone mapping이 남아 있다.

## 리서치 A/B
| 선택지 | 장점 | 단점 | 결정 |
| --- | --- | --- | --- |
| A. pending/warn guard까지 helper화 | copy action 전체 구조가 더 짧아진다 | ready 판정, text trim, warn 문구까지 섞여 blast radius가 커진다 | 보류 |
| B. 성공/실패 feedback만 `copyFeedback` 적용 | pending/warn branch를 건드리지 않아 동작 보존 검증이 명확하다 | guard 중복은 그대로 남는다 | 채택 |

## 범위
- **건드릴 것:** `review-copy-actions.js`, `handoffs/0012-review-copy-ready-feedback-refactor.md`, `WORKLOG.md`.
- **건드리지 말 것:** selector, dataset key, ready/pending guard 조건, warn status/toast 문구, export surface, 외부 전송.

## 단계
1. 직전 루프의 변경 후 `npm test` pass를 기준선으로 삼고, syntax baseline을 확인한다.
2. repair payload와 ready-guarded copy 성공/실패 branch에만 `copyFeedback`을 적용한다.
3. syntax/equality smoke/full test를 실행한다.
4. 반환 섹션과 WORKLOG에 결과를 기록한다.

## 수용 게이트
- `node --check review-copy-actions.js`
- HEAD 대비 VM equality smoke
- `npm test`
- `git diff --check`

## 금지사항
- pending/warn guard 조건과 문구는 이번 루프에서 바꾸지 않는다.
- 외부 push, 배포, remote workflow 설치는 하지 않는다.

---

## 반환 섹션 (실행자가 채운다)
- **결과:** `copyReviewArtifactRepairPayload`, `copyReviewArtifactPostApplyReceipt`, `copyReviewPostRepairArtifactLink`의 성공/실패 feedback mapping을 `copyFeedback` private helper로 통일했다. ready/pending guard 조건, warn status/toast 문구, selector, dataset key, export surface는 유지했다.
- **실행한 게이트:** 직전 변경 후 `npm test` pass를 기준선으로 확인, `node --check review-copy-actions.js` pass, HEAD 대비 VM equality smoke pass(repair body/receipt success/failure + ready/pending branches 12 cases), 변경 후 `npm test` pass, `git diff --check` pass.
- **남은 것 / 막힌 곳:** 공유 dirty tree와 외부 push/workflow 승인 경계 때문에 커밋·push는 보류. pending/warn guard 자체의 추가 공통화는 이번 범위 밖으로 남김.
