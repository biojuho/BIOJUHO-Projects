# DailyNews Gray Zone Meeting Memo

**Date**: 2026-03-31  
**Scope**: `automation/DailyNews` 중심, 워크스페이스 운영 경계 포함  
**Purpose**: 프로젝트에서 말하는 "그레이존"을 회의용 언어로 정의하고, 우선 결정해야 할 운영 기준을 정리한다.

---

## Executive Summary

코드베이스에서 `gray zone` 또는 `그레이존`이라는 명시 용어는 발견되지 않았다.

하지만 문서와 소스를 종합하면, DailyNews의 실제 그레이존은 다음과 같이 정의할 수 있다.

> 정식 구조와 호환 구조, Notion과 로컬 상태, auto와 manual 운영이 동시에 살아 있어서  
> 팀이 무엇을 "공식 상태"로 봐야 하는지 헷갈릴 수 있는 경계

즉, 현재의 그레이존은 "고장난 영역"이라기보다 "의도된 호환과 임시 운영이 겹치는 영역"에 가깝다.

---

## What Counts As Gray Zone Here

### 1. 경로와 구현의 그레이존

- 워크스페이스는 canonical top-level layout과 generated legacy-path layer를 함께 사용한다.
- DailyNews도 활성 구현은 `src/antigravity_mcp` 아래에 있지만, 기존 compatibility entrypoints를 계속 유지한다.
- 결과적으로 신규 수정은 정식 경로를 기준으로 해야 하지만, 실제 운영과 스크립트는 여전히 구경로를 통과할 수 있다.

회의 포인트:
- "정식 수정 경로"를 어디로 고정할 것인가?
- compatibility entrypoint 종료 시점을 언제로 잡을 것인가?

### 2. 상태 저장과 source of truth의 그레이존

- README는 Notion을 curated report output의 system of record라고 정의한다.
- 동시에 로컬 SQLite `data/pipeline_state.db`를 run tracking, deduplication, lifecycle 관리에 사용한다.
- 체크포인트는 Supabase 설정이나 드라이버가 없으면 로컬 SQLite로 폴백한다.
- 대시보드도 Notion이 없으면 local metrics only로 동작한다.

회의 포인트:
- 어떤 상태를 "공식 상태"로 볼 것인가?
- `draft`, `published`, `synced`, `reported`를 저장소별로 어떻게 구분할 것인가?

### 3. 발행 상태의 그레이존

- 외부 발행은 manual approval이 기본값이다.
- `approval_mode=auto`라도 품질 상태가 `ok`가 아니거나 fallback draft가 섞이면 다시 manual로 강등된다.
- 따라서 파이프라인 결과가 `ok` 또는 `partial`이라고 해서 외부 채널 발행 완료를 의미하지는 않는다.

회의 포인트:
- 팀이 말하는 "발행 완료"의 정의는 무엇인가?
- `local saved`, `Notion synced`, `external posted`를 별도 상태로 분리할 것인가?

### 4. API 및 호환성 migration의 그레이존

- canonical MCP tool 이름이 이미 존재한다.
- 그러나 legacy tool 이름도 deprecation warning과 함께 유지되고 있다.
- Notion 쪽도 database endpoint가 표준인데, legacy alias와 older call site를 일정 기간 허용하고 있다.

회의 포인트:
- 다음 릴리스에서 반드시 제거할 legacy surface는 무엇인가?
- warning-only 정책을 언제 hard fail로 올릴 것인가?

### 5. QC와 release readiness의 그레이존

- 워크스페이스 smoke는 통과했지만, handoff는 이를 `PASS WITH CAUTION`으로 기록한다.
- 같은 문서에서 `not release-clean`, `119 changed paths`, `current in-progress diffs review required`를 명시한다.
- 또 prompt migration과 일부 schema mismatch는 known issue로 남아 있다.

회의 포인트:
- `green QC`와 `release-ready`를 분리해서 정의할 것인가?
- 어떤 조건이 충족되어야 release approval로 볼 것인가?

---

## Evidence Snapshot

- `ONBOARDING.md`
  - canonical layout + legacy-path layer 병행
- `CONTEXT.md`
  - `workspace-map.json`을 source of truth로 사용
  - legacy root path는 bootstrap 이후에만 사용 권장
- `automation/DailyNews/README.md`
  - active implementation은 `src/antigravity_mcp`
  - legacy compatibility env/tooling 유지
  - Notion = system of record
  - local SQLite state 사용
  - external publishing = manual by default
- `automation/DailyNews/src/antigravity_mcp/state/db_client.py`
  - Supabase 미설정 또는 `psycopg2` 미설치 시 local SQLite 폴백
- `automation/DailyNews/src/antigravity_mcp/pipelines/publish.py`
  - auto publish가 manual로 downgrade될 수 있음
- `automation/DailyNews/src/antigravity_mcp/server.py`
  - legacy MCP tools 유지, deprecation warning 부착
- `automation/DailyNews/src/antigravity_mcp/integrations/notion_adapter.py`
  - older call site를 위해 legacy method name 유지
- `HANDOFF.md`
  - `PASS WITH CAUTION`
  - `not release-clean`
  - `119 changed paths`
  - DailyNews/GetDayTrends prompt migration remaining

---

## Decisions Needed In This Meeting

1. `published` 상태를 단일 용어로 계속 쓸지, 아니면 아래 3단계로 분리할지 결정
   - `local_saved`
   - `notion_synced`
   - `external_posted`
2. DailyNews의 정식 수정 경로를 `src/antigravity_mcp`로 못 박고, legacy entrypoint 종료 일정을 잡을지 결정
3. checkpoint / dashboard / report lifecycle의 source of truth를 한 문장으로 명시할지 결정
4. `QC pass`와 `release approval`을 별도 게이트로 관리할지 결정

---

## Recommended Direction

- 방향 1: 상태 용어를 저장소 기준으로 분리한다.
  - 운영 혼선을 줄이기 위해 "저장됨"과 "발행됨"을 분리하는 것이 가장 우선이다.
- 방향 2: legacy surface에 종료 날짜를 붙인다.
  - "한 릴리스 더 허용" 상태를 계속 끌면 그레이존이 구조로 굳어진다.
- 방향 3: release 기준을 문서화한다.
  - 현재는 QC green과 release-ready가 다르다는 점이 문서에만 암묵적으로 존재한다.

---

## Immediate Action Items

- README 또는 runbook에 `published` 상태 정의 표 추가
- legacy env/tool/tool name retirement checklist 작성
- release approval checklist에 `worktree clean`, `legacy warnings reviewed`, `source of truth confirmed` 추가
- 다음 세션에서 DailyNews prompt migration 잔여 범위 재평가

---

## One-Sentence Meeting Definition

> 우리 프로젝트의 그레이존은 버그가 아니라, 정식 체계와 호환 체계가 동시에 살아 있어서  
> 팀이 무엇을 공식 상태로 간주해야 하는지 헷갈릴 수 있는 경계다.
