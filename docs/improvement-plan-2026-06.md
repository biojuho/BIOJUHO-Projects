# JooPark Workspace 개선 플랜 (2026-06-11 종합 점검 기반)

- 작성: Claude 기획
- 점검 방식: 4개 영역(배포 파이프라인 / 코드 건강도 / 제품 로드맵 / 프로세스 위생) 병렬 감사 + 누락 교차검증
- 실행: Codex (handoffs/0001~0005 핸드오프로 진행)

## 한 줄 결론

**제품은 완성도가 높은데, 배포가 "커밋을 안 해서" 막혀 있고, 실행 루프가 그 차단을 우회하느라 이틀간 메타 작업만 287회 반복했다.** 가장 급한 일은 코드 수정이 아니라 ① 루프 중단 ② 커밋·푸시 ③ 배포 승인이다.

## 진단 요약

### 1. 배포 차단의 진짜 원인 (critical)

`remoteWorkflowFilesReady=false`는 리모트 드리프트 문제가 아니라 **순서 문제**다:

| 위치 | `.github/workflows/joopark-pages.yml` 상태 |
|---|---|
| 작업 트리 (로컬) | `7d47ffeb…` — 템플릿(`docs/github-pages-workflow.yml`)과 **일치** ✅ |
| 로컬 HEAD (커밋됨) | `71a78beb…` — 구버전 |
| 리모트 (GitHub) | `8ea83aa0…` — 더 구버전 |

즉 **올바른 파일이 이미 로컬에 있는데 커밋·푸시가 안 됐다.** 커밋 → 푸시만 하면 리모트 불일치는 자동 해소된다. 추가 함정:

- 리모트 이름이 `origin`이 아니라 `biojuho-projects` (스크립트가 origin을 가정하면 조용히 실패)
- 미커밋 파일 108개 (76 수정 + 32 미추적, +14,069/-7,006줄)
- GitHub Pages는 이미 활성화됨(`has_pages=true`), gh CLI workflow scope 있음 — 외부 준비는 끝난 상태

### 2. 프로세스: 실행 루프 폭주 (critical)

- Codex가 차단 게이트(`remoteWorkflowFilesReady=false`)를 만나자 에스컬레이션하지 않고 **bug loop 158회 + refactor loop 152회**(2026-06-09~11)를 자율 반복. 전부 메타 작업, 제품 작업 0건.
- 핸드오프 프로토콜(`handoffs/`)이 존재하지만 **한 번도 사용된 적 없음** — AGENTS.md의 "OPEN 핸드오프를 집는다" 규칙이 공회전.
- 모든 최근 커밋이 "Sync …" 메타 커밋. 커밋 케이던스 규칙 부재.

### 3. 제품: 메타가 제품을 압도 (high)

- scripts/ 3.2MB > 제품 코드. 커밋 96건 중 81건이 메타.
- UI에 사용자 가치가 아닌 데이터 노출: 포트폴리오 뷰의 OSS 후보 44개(시드 데이터), LLM 위키 19편(사용자 지식이 아닌 시드 콘텐츠).
- 실데이터 연동 0건 — localStorage 사일로. 모바일 "완료" 표기는 검증 안 됨.

### 4. 코드: 견고하지만 구조 리스크 (medium)

- app.js 10,570줄(810개 함수), styles.css 11,165줄 — 점진 추출 중이나 여전히 거대.
- 테스트가 순수 헬퍼(363개)와 릴리스 게이트에 편중 — 뷰 통합 플로우(생성→수정→삭제→undo), 오프라인, 스토리지 복구 미검증.
- `smoke-mobile.mjs`/`smoke-a11y.mjs`가 npm test 체인 밖(선택 실행).
- localStorage 단일 blob — 레코드 버전 없음, Safari 7일 미접속 시 전체 소실 리스크, persist() 미요청.

## 실행 플랜 (핸드오프 매핑)

### Phase 0 — 루프 중단과 가드레일 (즉시, 다른 모든 것보다 먼저)
**→ handoffs/0002**
- 자율 bug/refactor 루프 중단. AGENTS.md에 명문화: 동일 차단 게이트 3회 연속 → 중단·반환, 제품:메타 작업 비율, 미커밋 20파일 한도.
- 근거 자료: `docs/knowledge/llm-agent-loop-guardrails.md`

### Phase 1 — 런치 차단 해제 (이번 주)
**→ handoffs/0001**
1. 미커밋 108개 파일을 논리 단위로 커밋 (워크플로 파일 최우선)
2. `biojuho-projects` 리모트로 푸시
3. `node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write` 재실행 → `remoteWorkflowFilesReady=true` 확인
4. `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write` → `allDispatchReady=true` 확인
5. **여기서 정지** — `gh workflow run`(실제 게시)은 사용자 승인 후
- 근거 자료: `docs/knowledge/github-pages-actions-deploy.md`

### Phase 2 — 제품 정리 (런치 후)
**→ handoffs/0003**
- 포트폴리오 뷰에서 adoption-candidates 시드 데이터 기본 숨김 (내 데이터 우선)
- autoresearch-results/ 등 생성 아티팩트 보존 정책 정리 (.gitignore 또는 archive/)

### Phase 3 — 품질 게이트 승격
**→ handoffs/0005**
- smoke-mobile / smoke-a11y를 npm test 체인에 편입
- 콕핏 통합 스모크 1개 추가 (위키→이슈→칸반→캘린더→완료 시나리오)
- 근거 자료: `docs/knowledge/vanilla-spa-quality-gates.md`

### Phase 4 — 지식 자료 제품 통합
**→ handoffs/0004**
- `docs/knowledge/` 6편을 llm-wiki 뷰의 새 카테고리 "프로젝트 운영"으로 노출

### 백로그 (다음 기획 라운드)
- **데이터 안전**: persist() 요청 버튼, 백업 내보내기 강화, V4 스키마(레코드 버전 + lazy migration) — `docs/knowledge/local-first-data-safety.md` 기반
- **SW 업데이트 프롬프트**: 첫 배포 전 필수 점검 — `docs/knowledge/pwa-offline-operations.md` 기반
- **실데이터 연동 1건**: .ics/.csv 파일 업로드 가져오기 — `docs/knowledge/static-site-data-sync.md` 기반
- app.js 추가 분해(목표 <8K줄), styles.css 스코핑, 에러 텔레메트리

## 운영 규칙 (이 플랜의 지속 조건)

1. **핸드오프 없이 실행 없음** — Codex는 OPEN 핸드오프만 집는다 (AGENTS.md 개정에 포함).
2. **차단은 우회하지 않고 반환한다** — 게이트 false가 3회 연속이면 루프를 멈추고 반환 섹션에 적는다.
3. **커밋 케이던스** — 한 핸드오프 완료 = 최소 1커밋. 미커밋 20파일 초과 금지.
4. **외부 행위는 사용자 승인 후** — push까지는 가능, `gh workflow run`(게시)·삭제·외부 전송은 승인 필요.
