# 핸드오프 0014 — review result state copy config 리팩터링

- **상태:** DONE
- **기획자:** Codex 기획
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-06-11

## 목표
`review-result-state.js`의 `copyRepair`와 `copyRepairReceipt`에서 반복되는 `copyTextWithStatus` config 조립을 private helper로 분리해 repair copy action의 구조를 명확히 하고 동작은 보존한다.

## 배경
두 함수는 대상 panel, status selector, text selector, dataset key, status/toast 문구만 다르고 같은 형태의 `copyTextWithStatus` 호출을 직접 구성한다. config 조립 helper를 두면 DOM 조회와 copy 호출 의도가 분리된다.

## 리서치 A/B
| 선택지 | 장점 | 단점 | 결정 |
| --- | --- | --- | --- |
| A. copy 함수 전체를 하나의 generic 함수로 합치기 | 중복 제거 폭이 크다 | selector/문구/data key를 한 번에 모두 매개변수화해 가독성이 떨어질 수 있다 | 보류 |
| B. `copyTextWithStatus` config helper만 추출 | 함수별 DOM 흐름은 유지하면서 반복되는 config shape만 제거한다 | 함수 두 개의 wrapper는 남는다 | 채택 |

## 범위
- **건드릴 것:** `review-result-state.js`, `handoffs/0014-review-result-state-copy-config-refactor.md`, `WORKLOG.md`.
- **건드리지 말 것:** validator state, repair snapshot, persistence, receipt markdown, selector, dataset key, status/toast 문구, export surface, 외부 전송.

## 단계
1. 직전 루프의 변경 후 `npm test` pass를 기준선으로 삼고, syntax baseline을 확인한다.
2. repair copy config helper를 추가하고 `copyRepair`/`copyRepairReceipt`의 `copyTextWithStatus` 호출만 치환한다.
3. syntax/equality smoke/full test를 실행한다.
4. 반환 섹션과 WORKLOG에 결과를 기록한다.

## 수용 게이트
- `node --check review-result-state.js`
- HEAD 대비 VM equality smoke
- `npm test`
- `git diff --check`

## 금지사항
- validation/repair receipt 저장 로직은 이번 루프에서 건드리지 않는다.
- 외부 push, 배포, remote workflow 설치는 하지 않는다.

---

## 반환 섹션 (실행자가 채운다)
- **결과:** `repairCopyRequest` private helper를 추가하고 `copyRepair`/`copyRepairReceipt`의 `copyTextWithStatus` request shape 조립을 helper로 치환했다. validator state, repair snapshot, persistence, receipt markdown, selector, dataset key, status/toast 문구, export surface는 유지했다.
- **실행한 게이트:** 직전 변경 후 `npm test` pass를 기준선으로 확인, `node --check review-result-state.js` pass, HEAD 대비 VM equality smoke pass(`copyTextWithStatus` request 2 cases; raw VM prototype false-positive 후 plain JSON snapshot으로 재검증), 변경 후 `npm test` pass, `git diff --check` pass.
- **남은 것 / 막힌 곳:** 공유 dirty tree와 외부 push/workflow 승인 경계 때문에 커밋·push는 보류. copy 함수 전체 generic화는 이번 범위 밖으로 남김.
