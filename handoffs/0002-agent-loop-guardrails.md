# 핸드오프 0002 — 에이전트 루프 가드레일: AGENTS.md 개정과 자율 루프 정지 규칙

- **상태:** DONE
- **기획자:** Claude Code
- **추천 실행자:** Codex
- **실행자:** Codex
- **작성일:** 2026-06-11

## 목표
실행자(Codex 등)가 차단 게이트를 만나면 우회 반복 대신 **중단·반환**하도록 운영 규칙이 AGENTS.md에 명문화되고, 자율 bug/refactor 루프가 핸드오프 기반으로 전환된다.

## 배경
2026-06-09~11 사이 실행 루프가 `remoteWorkflowFilesReady=false` 차단을 만나자 에스컬레이션 없이 bug loop 158회 + refactor loop 152회(전부 메타 작업)를 반복했고, 미커밋 108파일이 쌓였으며 제품 작업은 0건이었다(WORKLOG.md 참조). 핸드오프 프로토콜은 존재했으나 사용된 적이 없다. 진단: `docs/improvement-plan-2026-06.md` §2, 근거 지식: `docs/knowledge/llm-agent-loop-guardrails.md`.

## 범위
- **건드릴 것:** `AGENTS.md`, `handoffs/README.md`(규칙 보강), `WORKLOG.md`(기록 추가).
- **건드리지 말 것:** 앱 소스, scripts/, 게이트 산출물(data/), 전역 `~/.claude/` 설정.

## 단계
1. `docs/knowledge/llm-agent-loop-guardrails.md`를 읽는다.
2. `AGENTS.md`에 "루프 가드레일" 섹션을 추가한다. 반드시 포함할 규칙:
   - **정지 조건:** 동일 차단 게이트(예: `remoteWorkflowFilesReady=false`)가 3회 연속 작업 종료 메시지에 등장하면, 루프를 멈추고 핸드오프 반환 섹션(또는 WORKLOG)에 차단 내용을 적고 기획자에게 반환한다. 차단을 우회하는 메타 작업(감사 스크립트 보정, 래퍼 제거 등)으로 루프를 계속하지 않는다.
   - **루프 예산:** 핸드오프 1건당 bug/refactor 류 메타 루프는 최대 10회. 제품(사용자 가시) 작업이 0건인 날이 이틀 연속이면 자동 중단.
   - **커밋 케이던스:** 미커밋 변경 20파일 초과 금지. 한 작업 단위 완료 시 즉시 커밋(논리 단위, 의도가 드러나는 메시지).
   - **핸드오프 우선:** OPEN 핸드오프가 없으면 새 작업을 시작하지 않고 기획자에게 요청한다(자율 루프 금지).
3. `handoffs/README.md`에 "루프 작업도 핸드오프로 발급한다"는 한 줄과 정지 조건 요약을 추가한다.
4. WORKLOG.md에 한 줄 기록한다.

## 수용 게이트
- `AGENTS.md`에 위 4개 규칙(정지 조건·루프 예산·커밋 케이던스·핸드오프 우선)이 모두 존재
- `node scripts/check-syntax.mjs` 통과 (md 수정이므로 영향 없음 확인용)
- 기존 AGENTS.md의 역할·금지 섹션이 삭제되지 않고 유지됨

## 금지사항
- 기존 경계(되돌릴 수 없는 외부 행위 금지 등) 완화 금지.
- 전역 템플릿(`~/.claude/templates/`) 수정 금지 — 이 프로젝트 파일만.

---

## 반환 섹션 (실행자가 채운다)
- **결과:** `AGENTS.md`에 루프 가드레일 섹션을 추가해 정지 조건, 루프 예산, 커밋 케이던스, 핸드오프 우선 규칙을 명문화했다. `handoffs/README.md`에도 루프 작업은 핸드오프로 발급하고 동일 차단 게이트 3회 연속 시 반환한다는 요약을 추가했다. 기존 역할·절대 금지 섹션은 유지했다.
- **실행한 게이트:** `rg -n "정지 조건|루프 예산|커밋 케이던스|핸드오프 우선|절대 금지|네 역할" AGENTS.md`; `rg -n "루프 작업도 반드시 핸드오프로 발급|동일 차단 게이트" handoffs/README.md`; `node scripts/check-syntax.mjs`
- **남은 것 / 막힌 곳:** 핸드오프가 지정한 `docs/knowledge/llm-agent-loop-guardrails.md`는 현재 워크트리에 없어 읽지 못했다. 대신 `docs/improvement-plan-2026-06.md`와 핸드오프 본문에 적힌 필수 규칙을 기준으로 반영했다.
