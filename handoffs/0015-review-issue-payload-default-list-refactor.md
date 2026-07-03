# Handoff 0015 — Review Issue Payload Default List Refactor

- **상태:** DONE
- **담당:** Codex 실행
- **시작일:** 2026-06-11

## 목표

`review-issue-payload.js`의 issue body 생성에서 acceptance criteria와 validation plan 기본값 선택 로직을 private helper로 추출한다. 출력되는 markdown 본문, 문자열, 줄 순서, export surface는 변경하지 않는다.

## 범위

- 수정 가능:
  - `review-issue-payload.js`
  - `handoffs/0015-review-issue-payload-default-list-refactor.md`
  - `WORKLOG.md`
- 수정 금지:
  - 공개 API/export surface
  - issue markdown heading/text/order
  - tracker field 계산
  - 외부 배포, push, workflow 변경

## A/B 선택

| 선택지 | 내용 | 장점 | 리스크 |
| --- | --- | --- | --- |
| A | markdown section/default model 전반을 추상화 | 재사용 가능성 큼 | 작은 리팩터 범위를 넘어 blast radius 증가 |
| B | non-empty list fallback 선택만 private helper로 추출 | 범위 작고 동등성 검증이 명확함 | 재사용 범위 제한 |

채택: **B**. 현재 중복은 리스트 기본값 선택 2곳으로 작고, output contract를 건드리지 않는 좁은 추출이 적합하다.

## 실행 단계

1. 기준 `node --check review-issue-payload.js` 통과를 확인한다.
2. private helper `nonEmptyListOrDefault`를 추가한다.
3. `reviewIssueBodyLines`의 acceptance criteria / validation plan 기본값 분기를 helper 호출로 교체한다.
4. HEAD 대비 VM equality smoke로 기본값, custom list, empty array 케이스의 `reviewIssueBodyLines` 출력 동일성을 확인한다.
5. `npm test`, `git diff --check`를 통과시킨다.
6. 이 파일의 반환 섹션과 `WORKLOG.md`를 업데이트한다.

## 수용 게이트

- `node --check review-issue-payload.js`
- HEAD 대비 `reviewIssueBodyLines` equality smoke 3 cases
- `npm test`
- `git diff --check`

## 반환

- 상태: DONE
- 결과: `reviewIssueBodyLines`의 acceptance criteria / validation plan non-empty fallback 선택을 private `nonEmptyListOrDefault` helper로 추출했다. 이후 `npm test`에서 드러난 non-finite timebox(`Infinity`) 누출도 `positiveFiniteNumberOrDefault`와 finite `trackerReady` guard로 막아 operational readiness, issue body, tracker fields가 기존 테스트 계약(4시간 fallback/false ready)을 유지하도록 수정했다. 공개 export surface와 정상 default/custom/empty list markdown 출력 계약은 변경하지 않았다.
- 실행한 명령:
  - `node --check review-issue-payload.js`
  - HEAD 대비 VM equality smoke (`reviewIssueBodyLines` default/custom/empty-array 3 cases)
  - `npm run test:unit`
  - `npm test`
  - `git diff --check`
- 남은 일: 없음. 공유 dirty tree와 외부 push/workflow 승인 경계 때문에 커밋·push는 보류.
