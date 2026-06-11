# 핸드오프 0006 — 지식 자료 위키 통합 2차: 남은 4편을 "프로젝트 운영" 카테고리에 등록

- **상태:** DONE
- **기획자:** Claude Code
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-06-11

## 목표
앱 위키 "프로젝트 운영"(`project-ops`) 카테고리에서 `docs/knowledge/` 6편 전부를 읽을 수 있다 (현재 2편만 등록됨).

## 배경
핸드오프 0004 실행 시점에는 `docs/knowledge/`에 2편만 존재해 2편만 등록하고 반환했다(0004 반환 섹션 참조). 이후 조사 워크플로가 완료되어 나머지 4편이 생성됐다:
- `docs/knowledge/github-pages-actions-deploy.md`
- `docs/knowledge/pwa-offline-operations.md`
- `docs/knowledge/static-site-data-sync.md`
- `docs/knowledge/llm-agent-loop-guardrails.md`
(목차 `docs/knowledge/00-index.md`는 등록 대상 아님 — 저장소용 목차다.)

0004에서 만든 등록 패턴을 그대로 따른다: `llm-wiki-view.js`의 `project-ops` 카테고리에 원문 exact-match 본문으로 추가, `WIKI.sources`의 project docs 출처 패널 연결.

## 범위
- **건드릴 것:** `llm-wiki-view.js`(4편 등록), 필요 시 `scripts/smoke-llm-wiki.mjs`(검증 대상 확장), WORKLOG.md.
- **건드리지 말 것:** `docs/knowledge/*.md` 원본(내용 수정 금지), 기존 등록 2편과 기존 카테고리, 렌더 파이프라인.

## 단계
1. 0004에서 등록한 2편(`local-first-data-safety`, `vanilla-spa-quality-gates`)의 등록 방식을 확인한다.
2. 같은 방식으로 4편을 `project-ops` 카테고리에 추가한다 (원문 exact-match).
3. 문서 수 카운트·Fuse 검색 인덱스에 4편이 포함되는지 확인하고, `smoke-llm-wiki.mjs`가 6편 모두를 검증하도록 확장한다.
4. WORKLOG.md 기록.

## 수용 게이트
- `node --check llm-wiki-view.js` 및 `npm run lint && npm run check:structure && npm run check:docs` 통과
- `node scripts/run-local-smoke.mjs scripts/smoke-llm-wiki.mjs` 통과 (6편 본문 exact-match 단언 포함)
- 위키 검색에서 4편 제목 검색 가능

## 금지사항
- 원본 md 수정 금지(등록만). DOMPurify 정제 우회 금지 (audit:xss 게이트 유지).
- AGENTS.md 가드레일 준수: 이 핸드오프 완료 시 즉시 논리 단위 커밋(미커밋 20파일 한도 규칙). 단, 현재 워크트리에 이미 121개 미커밋 변경이 누적된 것은 0001(커밋·푸시) 소관이므로, 이 핸드오프 분량만 커밋이 어렵다면 커밋하지 않고 반환 섹션에 사유를 적는다.

---

## 반환 섹션 (실행자가 채운다)
- **결과:** `llm-wiki-view.js`의 `project-ops` 카테고리에 `docs/knowledge/` 6편 전체를 등록했다. 기존 2편(`local-first-data-safety`, `vanilla-spa-quality-gates`)은 유지하고, `github-pages-actions-deploy`, `pwa-offline-operations`, `static-site-data-sync`, `llm-agent-loop-guardrails` 4편을 원문 exact-match 본문과 `WIKI.sources` project docs 출처 패널로 추가했다. `scripts/smoke-llm-wiki.mjs`는 6편 exact-match 정적 검사, 6편 카드/본문 marker/source panel 검사, 새 4편 제목 검색 검사를 포함하도록 확장했다.
- **실행한 게이트:** `node --check llm-wiki-view.js` 통과, `node --check scripts/smoke-llm-wiki.mjs` 통과, 별도 Node exact-match 검사로 6편 모두 원본 md와 일치 확인, `npm run lint` 통과, `npm run check:structure` 통과, `npm run check:docs` 통과, `node scripts/run-local-smoke.mjs scripts/smoke-llm-wiki.mjs` 통과(`projectOpsCardCount=6`, 6편 `opened/markers/sourcePanel=true`, `projectOpsSearchOk=true`).
- **남은 것 / 막힌 곳:** 원본 `docs/knowledge/*.md`는 수정하지 않았다. 현재 워크트리는 이 핸드오프 이전부터 다수 미커밋 변경이 누적된 공유 dirty 상태라 0006 단독 커밋은 보류한다.
