# Handoff 0018 — Review Creation Note Defaults Refactor

- **상태:** DONE
- **담당:** Codex 실행
- **시작일:** 2026-06-11

## 목표

`review-creation-actions.js`의 `publishReviewHandoffNote`에서 review note 종류별 기본 title prefix, source kind, color 선택 로직을 private helper로 추출한다. note 생성, 기존 note 열기, saved review result body, toast side effect는 변경하지 않는다.

## 범위

- 수정 가능:
  - `review-creation-actions.js`
  - `handoffs/0018-review-creation-note-defaults-refactor.md`
  - `WORKLOG.md`
- 수정 금지:
  - 공개 API/export surface
  - note title/sourceKind/color 문자열
  - target dataset override 우선순위
  - saved review result body 구성
  - 기존 note 재열기 동작
  - 외부 배포, push, workflow 변경

## A/B 선택

| 선택지 | 내용 | 장점 | 리스크 |
| --- | --- | --- | --- |
| A | `publishReviewHandoffNote` 전체를 note draft model builder로 분해 | 장기 구조 개선 폭 큼 | mutation/commit/toast 경로까지 흔들 수 있음 |
| B | note 종류별 기본 메타데이터 선택만 private helper로 추출 | 작고 검증 가능, override와 생성 side effect 유지가 명확함 | 개선 범위는 default 선택 로직으로 제한 |

채택: **B**. 이번 루프는 review note context 판정과 기본값 선택만 분리해 함수 본문 인지 부하를 줄인다.

## 실행 단계

1. 직전 loop 172 변경 후 `npm test` green을 기준선으로 사용한다.
2. private helper `reviewNoteDefaults`를 추가한다.
3. `publishReviewHandoffNote`의 inline benchmark/knowledge/workspace 기본값 분기를 helper 호출로 교체한다.
4. HEAD 대비 VM equality smoke로 existing note, benchmark default, knowledge override/saved 케이스의 note/commit/toast/open side effect 동일성을 확인한다.
5. `node --check review-creation-actions.js`, `npm test`, `git diff --check`를 통과시킨다.
6. 이 파일의 반환 섹션과 `WORKLOG.md`를 업데이트한다.

## 수용 게이트

- 직전 기준선 `npm test` pass
- `node --check review-creation-actions.js`
- HEAD 대비 `publishReviewHandoffNote` equality smoke 3 cases
- 변경 후 `npm test`
- `git diff --check`

## 반환

- 상태: DONE (반환 종료)
- 결과: `publishReviewHandoffNote`의 review note 종류별 title/sourceKind/color 기본값 선택을 private `reviewNoteDefaults` helper로 추출했다. target dataset override, saved review result body, existing note open, commit/toast side effect, export surface는 변경하지 않았다. 단, 현재 워크트리에는 내가 만들지 않은 `draftEstimate` 변경과 smoke verifier 변경이 함께 존재해 전체 변경 묶음은 handoff 0019 커밋 트레인에서 흡수한다.
- 실행한 명령:
  - 직전 기준선 `npm test`
  - `node --check review-creation-actions.js`
  - HEAD 대비 VM equality smoke (`publishReviewHandoffNote` existing/default/override+saved 3 cases)
  - 변경 후 `npm test` 2회 시도: 1차는 별도 `smoke:mobile`의 `Runtime.evaluate` 3초 timeout, 2차는 `verify:product` 내부 `smoke-a11y.mjs`가 stdout `status: pass` 출력 후 120초 timeout으로 실패
  - 재확인 `npm run smoke:mobile` pass
  - 재확인 `npm run smoke:a11y` pass
  - `git diff --check -- review-creation-actions.js handoffs/0018-review-creation-note-defaults-refactor.md WORKLOG.md` pass
- 사용자 가시 변화 한 줄: 없음 (동작 보존 리팩터; 기존 note 발행/재열기 흐름 유지)
- 남은 일: 전체 `npm test` green 확정은 진행 중인 다른 smoke verifier 경합과 별도 smoke script 변경 때문에 handoff 0019의 시작/마감 게이트에서 다시 확인해야 한다. 공유 dirty tree와 외부 push/workflow 승인 경계 때문에 커밋·push는 보류.
