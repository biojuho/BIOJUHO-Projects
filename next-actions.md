# Next Actions

> 2026-05-11 기준 — GHA 공급망 보안 강화 완료 (Plan A+D, PR #117 실기동 검증)

## Backlog (미완료)

- [x] ~~QA Review S101 false positive 수정~~ — commit 244ea18 (PR #117에 통합, 별도 PR 대신). per-file-ignores 추가 + 두 test 파일 I001/F401 정리 + contract 테스트 갱신. GHA 재검증 진행 중.
- [ ] **Canva token 브라우저 재인증 최종 확인** (인증 서버 기동 테스트 완료됨)
- [ ] **X 수동 발행**: Economy_Global 최종 문안 게시

## 시스템 고도화 후속 작업 (zizmor 잔여 findings)

- [needs_approval] **Plan B**: HIGH template-injection 22건 수동 패치 — `${{ github.event.* }}` → `env:` 분리. 영향 파일: collect-tweet-metrics, content-intelligence 등. 별도 PR 권장
- [safe_auto] **secrets-outside-env 120건** — reusable workflow 호출 시 `with:` → `env:` 이동. 기계적 변환 가능
- [safe_auto] **excessive-permissions 50건** — 워크플로/잡 단위 `permissions: contents: read` 명시 추가
- [safe_auto] **artipacked 36건** — checkout step에 `persist-credentials: false` 추가 (zizmor auto-fix 가능)
- [safe_auto] **concurrency-limits 19건** — `concurrency: group/cancel-in-progress` 추가
- [needs_approval] **Plan P0-1 Langfuse self-host** — Supabase 옆 컨테이너로 LLM observability 도입
- [needs_approval] **Plan P0-2 LiteLLM proxy** — 7개 LLM 백엔드 통합 게이트웨이
- [needs_approval] **Plan P1-uv workspaces** — apps/automation/mcp/packages 단일 lockfile

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
