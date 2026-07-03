# 핸드오프 0010 — review copy configured feedback helper 리팩터링

- **상태:** DONE
- **기획자:** Codex 기획
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-06-11

## 목표
`review-copy-actions.js`의 generic `copyReviewPackagePanelText`에서 copy 성공/실패에 따른 dataset, status text, toast text/tone 결정을 private helper로 분리해 configured copy path의 의도를 명확히 하고 동작은 보존한다.

## 배경
`copyReviewPackagePanelText`는 여러 review package copy action이 공유하는 configured path다. 현재 side effect 적용과 성공/실패 mapping이 한 블록에 섞여 있어, helper로 분리하면 config 기반 copy action의 검증 단위가 작아진다.

## 리서치 A/B
| 선택지 | 장점 | 단점 | 결정 |
| --- | --- | --- | --- |
| A. 전체 review copy 함수 한 번에 공통화 | 중복 제거 폭이 크다 | ready guard와 동적 status 문구까지 같이 건드려 blast radius가 커진다 | 보류 |
| B. configured path만 helper 추출 | 범위가 작고 equality smoke가 명확하다 | 고정 액션 중복은 다음 루프로 남는다 | 채택 |

## 범위
- **건드릴 것:** `review-copy-actions.js`, `handoffs/0010-review-copy-configured-feedback-refactor.md`, `WORKLOG.md`.
- **건드리지 말 것:** selector, dataset key, status/toast 문구, ready guard, fixed action copy 함수, export surface, 외부 전송.

## 단계
1. 기준선 `npm test` 통과를 확인한다.
2. configured copy feedback helper를 추가하고 `copyReviewPackagePanelText`만 치환한다.
3. syntax/equality smoke/full test를 실행한다.
4. 반환 섹션과 WORKLOG에 결과를 기록한다.

## 수용 게이트
- `node --check review-copy-actions.js`
- HEAD 대비 VM equality smoke
- `npm test`
- `git diff --check`

## 금지사항
- fixed action 함수나 ready/pending guard는 이번 루프에서 건드리지 않는다.
- 외부 push, 배포, remote workflow 설치는 하지 않는다.

---

## 반환 섹션 (실행자가 채운다)
- **결과:** `copyReviewPackagePanelText`의 configured copy 성공/실패 feedback 결정을 `configuredCopyFeedback` private helper로 분리했다. dataset state, status text, toast text/tone은 HEAD 대비 VM equality smoke에서 성공/실패 2 cases 모두 동일하게 유지됨을 확인했다.
- **실행한 게이트:** 기준선 `npm test` pass, `node --check review-copy-actions.js` pass, HEAD 대비 VM equality smoke pass(`copyReviewPackagePanelText` success/failure 2 cases), 변경 후 `npm test` pass, `git diff --check` pass.
- **남은 것 / 막힌 곳:** 공유 dirty tree와 외부 push/workflow 승인 경계 때문에 커밋·push는 보류. fixed action copy 함수 공통화는 이번 범위 밖으로 남김.
