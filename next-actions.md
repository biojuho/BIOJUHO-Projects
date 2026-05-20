# Next Actions

> 2026-05-20 기준 — getdaytrends 제품완성형 패스 완료 (commits 48109f1+e5585a2+6fe16ed, 764 tests green, docs aligned)
> 2026-05-15 기준 — zizmor 보안 자동 픽스 완료 (브랜치 ci/zizmor-safe-fixes, 77건 -63%)

## Backlog (미완료)

- [x] ~~QA Review S101 false positive 수정~~ — commit 244ea18 (PR #117에 통합, 별도 PR 대신). per-file-ignores 추가 + 두 test 파일 I001/F401 정리 + contract 테스트 갱신. GHA 재검증 진행 중.
- [ ] **Canva token 브라우저 재인증 최종 확인** (인증 서버 기동 테스트 완료됨)
- [ ] **X 수동 발행**: Economy_Global 최종 문안 게시
- [ ] **DeSci Platform**: DB Population (50 VCs) & Production Deployment (Railway/Vercel)
- [ ] **PR #120 머지 대기**: `ci/zizmor-safe-fixes` → main (commit 04dd45d, 25 workflows, +144/-37). https://github.com/biojuho/BIOJUHO-Projects/pull/120

## 시스템 고도화 후속 작업 (zizmor 잔여 findings)

- [x] ~~**artipacked 36건**~~ — commit 04dd45d, `persist-credentials: false` 일괄 추가, 36→0 (100%)
- [x] ~~**template-injection (Plan B) 부분**~~ — commit 04dd45d, env block 패턴으로 변환, 53→12 (77%, 단순 케이스 처리)
- [ ] [needs_approval] **template-injection 잔존 12건** — 복잡한 multi-line/nested 케이스. 수동 검토 필요
- [ ] [safe_auto] **secrets-outside-env 120건** — reusable workflow 호출 시 `with:` → `env:` 이동. 기계적 변환 가능
- [ ] [safe_auto] **excessive-permissions 33건** — 워크플로/잡 단위 `permissions: contents: read` 명시 추가 (zizmor 자동 픽스 안 함, 의도 파악 필요)
- [ ] [safe_auto] **concurrency-limits 19건** — `concurrency: group/cancel-in-progress` 추가 (pedantic persona)
- [ ] [needs_approval] **Plan P0-1 Langfuse self-host** — Supabase 옆 컨테이너로 LLM observability 도입
- [ ] [needs_approval] **Plan P0-2 LiteLLM proxy** — 7개 LLM 백엔드 통합 게이트웨이
- [ ] [needs_approval] **Plan P1-uv workspaces** — apps/automation/mcp/packages 단일 lockfile

## 다음 세션 복붙 메모

```text
GHA 공급망 보안 강화 완료 (2026-05-08):
- pinact: 26 workflows + 1 composite action SHA 핀 (commit 1437793)
- zizmor 게이트: workflow-audit job 추가, unpinned-uses 회귀 hard-fail (commit 0e3a006)
- zizmor HIGH 108 → 25 (-83), unpinned-uses 100% 제거
- 잔여 25 HIGH = template-injection 22 + excessive-permissions 3 → Plan B에서 처리
- var/zizmor.json (전), var/zizmor-after.json (후) 비교 가능
- pinact 도구는 ~/go/bin/pinact.exe (Windows), zizmor는 uvx로 ephemeral 실행
```
