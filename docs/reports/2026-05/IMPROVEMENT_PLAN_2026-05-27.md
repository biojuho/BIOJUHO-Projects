# 워크스페이스 개선안 — 2026-05-27

> 목표: 진행 중인 작업 스트림을 정리하고, 가장 레버리지가 높은 항목을 "완성품" 단위로 마감한다.
> 작성 시점 기준: branch `feat/observability-gateway-2026-05` (92 commits ahead of origin/main).

## 1. 현재 상태 스냅샷

| 영역 | 상태 | 근거 |
| --- | --- | --- |
| 워크스페이스 스모크 | 31/31 PASS | `var/workspace-smoke-all-2026-05-27-final-product-readiness-31.json` |
| Healthcheck | 6/6 healthy | `next-actions.md` baseline 2026-05-27 |
| Observability Phase 1 | ✅ 머지됨 | commit `eeb4bcc` — LiteLLM proxy + Langfuse self-host, opt-in, default OFF |
| Observability Phase 2 | ⏳ 미착수 | `next-actions.md` `[needs_approval]` |
| 브랜치 vs origin/main | +92 / -0 | PR 미생성, main의 Pipeline Watcher 잔존 |
| 워킹트리 | 493 modified | CRLF 정규화 + 일부 콘텐츠 (병렬 세션 가능) |

## 2. 개선 축 (Priority Matrix)

### 🔴 P0 — 즉시 수정 / 차단 해소
- **(없음)** — 현재 보고된 회귀 없음. Phase 1 머지 후 모든 게이트 그린.

### 🟡 P1 — 이번 세션에 마감 ("완성품")
1. **Observability Phase 2: Langfuse SDK 직접 trace 전파**
   - 현재 한계: LiteLLM proxy 경로(opt-in)에서만 trace 발생. native 백엔드 체인은 무계측.
   - 완성품 정의: `packages/shared/llm/tracing.py` (신규) + `client.py` 통합 + 회귀 테스트.
   - 안전성: env 미설정 시 zero-op → 기본 동작 불변. langfuse SDK는 lazy import.
   - 범위: 단일 모듈 신규 + `client.py`에 hook 2곳(sync/async) → diff 최소.

### 🟢 P2 — 다음 세션 후보 (승인 필요)
1. **Phase 3 — 호출 사이트 점진 마이그레이션** (apps/desci-platform/backend, DailyNews, getdaytrends, content-intelligence)
2. **Phase 4 — native BackendManager deprecation**
3. **Plan P1-uv workspaces** — apps/automation/mcp/packages 단일 lockfile
4. **DeSci Platform 외부 배포 실행** — Railway/Vercel/Polygon Amoy (계정/지갑 필요)
5. **PR 작업**
   - 현재 브랜치를 origin push + PR open (외부 액션, 사용자 승인 필요)

### 🔵 P3 — 운영/위생
- `next-actions.md` 길이 정리 (38줄 baseline 누적 → 마감된 항목 아카이브)
- 워킹트리 CRLF 정규화 일괄 처리 (병렬 세션 종료 후)

## 3. 이번 세션 완성품 — Observability Phase 2 상세 계획

### 3.1 동기 (Why)
Phase 1 MVP는 LiteLLM proxy 경로에 한해 Langfuse trace를 발행한다. 그러나 `LITELLM_PROXY_URL` 미설정 시(현재 모든 호출 사이트의 기본값) native 백엔드 체인이 직접 호출되어 trace가 사라진다. Phase 2는 proxy on/off와 무관하게 모든 LLM 호출이 동일한 관측 신호를 남기도록 한다.

### 3.2 설계
- 신규 모듈 `packages/shared/llm/tracing.py`:
  - `is_tracing_enabled()` → `LANGFUSE_SECRET_KEY` + `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_HOST` 셋 모두 있을 때만 True
  - `LLMTraceSpan(tier, system, messages)` 컨텍스트 매니저
    - 활성화 시 langfuse `trace()` + `generation()` span 생성, 비활성/SDK 미설치 시 no-op
    - `.record_response(LLMResponse)` 메서드 — 성공 종료 시 호출
    - `.record_error(Exception)` — 실패 종료 시 호출
- `client.py` 통합:
  - `_dispatch` 의 native chain 루프 진입 직전에 span 시작
  - 성공 응답 직전에 `record_response`, 모든 백엔드 실패 시 `record_error`
  - `_dispatch_async` 동일
- proxy 경로는 LiteLLM이 자체 Langfuse 콜백을 갖고 있으므로 손대지 않는다 (중복 trace 방지).

### 3.3 회귀 방어
- `LANGFUSE_*` 미설정 환경(기본값)에서 모든 기존 120 tests green
- langfuse 패키지 미설치 환경에서도 import 가능 (lazy)
- span 생성 실패가 LLM 호출 자체를 깨뜨리지 않음 (catch-all + log.warning)

### 3.4 검수 체크리스트 (완성품 정의)
- [ ] `packages/shared/llm/tracing.py` 작성 — 80~120 LoC 내
- [ ] `packages/shared/llm/client.py` — sync/async dispatch에 hook 2곳 (10 LoC 미만 변경)
- [ ] `packages/shared/llm/tests/test_tracing.py` — 8+ 테스트
- [ ] `uv run pytest packages/shared/llm/tests/ -q` 전부 green
- [ ] commit 시 pathspec 격리 (워킹트리 더트 흡수 금지)
- [ ] `next-actions.md` Phase 2 체크박스 갱신

## 4. 안전 가드 (CLAUDE.md 수정 모드 프로토콜)

| 항목 | 본 작업 |
| --- | --- |
| 직접 수정 파일 | `client.py` (hook 2곳), `next-actions.md` |
| 신규 파일 | `tracing.py`, `test_tracing.py`, 본 문서 |
| public API 변경 | 없음 (`tracing.py` 신규 모듈만 노출) |
| DB 스키마 변경 | 없음 |
| 의존성 추가 | langfuse는 옵셔널 (lazy import, requirements.txt 미변경) |
| GHA workflow 변경 | 없음 |
| 한 커밋 = 한 변경 | (1) doc + tracing 모듈, (2) client 통합 + tests로 분리 |

## 5. 명시적 비범위 (Out of Scope)

- Phase 3 호출 사이트 마이그레이션 — 별도 세션
- LiteLLM proxy 경로의 trace 검증 — Phase 1에서 이미 콜백으로 처리
- requirements.txt / pyproject.toml에 langfuse 강제 추가 — opt-in 유지
- main 머지 또는 PR open — 사용자 명시 승인 필요
