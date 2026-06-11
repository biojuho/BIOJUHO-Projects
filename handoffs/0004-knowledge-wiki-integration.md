# 핸드오프 0004 — 지식 자료 통합: docs/knowledge 6편을 앱 위키 "프로젝트 운영" 카테고리로

- **상태:** DONE
- **기획자:** Claude Code
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-06-11

## 목표
2026-06-11 조사로 만든 `docs/knowledge/*.md` 6편을 앱의 LLM 위키 뷰에서 "프로젝트 운영" 카테고리로 읽을 수 있다.

## 배경
사용자 요청("필요한 지식을 조사해 우리 자료로")으로 6편의 운영 지식 문서를 작성했다:
1. `docs/knowledge/github-pages-actions-deploy.md`
2. `docs/knowledge/local-first-data-safety.md`
3. `docs/knowledge/pwa-offline-operations.md`
4. `docs/knowledge/vanilla-spa-quality-gates.md`
5. `docs/knowledge/static-site-data-sync.md`
6. `docs/knowledge/llm-agent-loop-guardrails.md`
(목차: `docs/knowledge/00-index.md`)

현재 위키 뷰(`llm-wiki-view.js`, 3,528줄)는 `WIKI.categories` 객체에 문서를 인라인 포함하는 구조다(약 975행부터). 기존 카테고리·문서는 LLM 일반 지식이고, 이번 6편은 "이 프로젝트를 운영하는 데 필요한 지식"이라 별도 카테고리가 맞다.

## 범위
- **건드릴 것:** `llm-wiki-view.js`(카테고리·문서 등록), 필요 시 위키 뷰 관련 스타일, WORKLOG.md.
- **건드리지 말 것:** `docs/knowledge/*.md` 원본(내용 수정 금지 — 뷰 등록만), 기존 카테고리 문서들, marked/DOMPurify 렌더 파이프라인.

## 단계
1. `llm-wiki-view.js`의 `WIKI.categories` 구조를 파악한다(문서 객체 필드: 제목·요약·본문·출처 등 기존 관례 확인).
2. 새 카테고리 `프로젝트 운영`(id 예: `project-ops`)을 추가하고 6편을 기존 문서 객체 관례에 맞춰 등록한다. 본문은 마크다운 원문을 기존 방식(인라인 문자열 배열 등)대로 넣되, 원문과 내용이 달라지지 않게 한다.
3. 문서 수 카운트·검색(Fuse) 인덱스가 새 문서를 포함하는지 확인한다.
4. WORKLOG.md 기록 후 커밋한다.

## 수용 게이트
- `npm run lint && npm run check:structure && npm run check:docs` 통과
- 위키 뷰에서 "프로젝트 운영" 카테고리와 6편이 보이고 본문이 렌더링됨 (스모크 또는 수동 확인 결과 기록)
- 위키 검색에서 새 문서 제목 검색 가능

## 금지사항
- 기존 위키 문서 삭제·수정 금지. 렌더 파이프라인(DOMPurify 통과) 우회 금지.
- `innerHTML`에 정제 없이 삽입 금지 (audit:xss 게이트 유지).

---

## 반환 섹션 (실행자가 채운다)
- **결과:** `llm-wiki-view.js`에 새 `프로젝트 운영`(`project-ops`) 카테고리를 추가하고, 현재 워크트리에 실제 존재하는 `docs/knowledge/local-first-data-safety.md`, `docs/knowledge/vanilla-spa-quality-gates.md` 2편을 원문 exact-match 본문으로 등록했다. 두 문서는 `WIKI.sources`의 project docs 출처 패널을 가진다.
- **실행한 게이트:** `node --check llm-wiki-view.js` 통과, 프로젝트 운영 카테고리/제목 검색/본문 exact-match Node smoke 통과, `npm run lint && npm run check:structure && npm run check:docs && node scripts/run-local-smoke.mjs scripts/smoke-llm-wiki.mjs` 통과, `git diff --check` 통과.
- **남은 것 / 막힌 곳:** 핸드오프에는 6편이 명시돼 있지만 현재 `docs/knowledge/`에는 `local-first-data-safety.md`, `vanilla-spa-quality-gates.md` 2편만 존재한다. `github-pages-actions-deploy.md`, `pwa-offline-operations.md`, `static-site-data-sync.md`, `llm-agent-loop-guardrails.md`, `00-index.md`는 워크트리에 없어 생성하지 않고 남김.
