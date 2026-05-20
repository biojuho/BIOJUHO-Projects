# Handoff Document

**Last Updated**: 2026-05-20 (GHA security hardening & Workspace hygiene consolidation)
**Session Status**: GitHub Actions security vulnerabilities 100% resolved; Notion single-DB consolidated; Workspace hygiene refined
**Next Agent**: Claude Code / Gemini / Codex

---

## Current State (2026-05-20)

### GitHub Actions Security Hardening
**Status**: COMPLETED & VERIFIED
- **Permissions & Concurrency**: 24개 GHA 워크플로우에 `concurrency` 제한 및 `permissions: contents: read` 보안 블록을 전역 주입하여 동시성 한계 위반 경고(19 -> 0건) 및 무단 과다 권한 위험(51 -> 6건, 봇 용도 외 완전 해소)을 성공적으로 격리하였습니다.
- **Template Injection**: 사용자 입력 변수가 `run` 셸 블록 내에서 확장되는 보안 위협을 방지하기 위해 step 레벨 `env` 매핑 방식으로 7개 주요 워크플로우를 리팩토링하여 zizmor 감사의 High 등급 위협을 완전 제거(0개)하였습니다.
- **YAML 무결성**: 전체 YAML 파일의 파싱 검증을 마쳤으며, `run_workspace_smoke.py` 전역 검증 패스(25 / 25 PASS)를 확보하였습니다.

### Notion Single-DB Consolidation & Workspace Hygiene
**Status**: COMPLETED
- DailyNews 로컬 환경 변수 중 동일 DB를 중복 지정하던 `NOTION_TASKS_DATABASE_ID`를 주석 처리하여 Consolidated Single-DB 정합성을 지키고 `ops doctor` 검증 결과 **100% READY (Green)** 상태를 달성하였습니다.
- 임시 CLI 정보 및 대형 빌드/임시 폴더(`.antigravitycli/`, `apps/desci-platform/var/`)를 `.gitignore`에 추가 등록하여 워크스페이스 변경 잡음을 원천 차단하였습니다.

---

## Current State (2026-05-19)

### DailyNews morning-only publishing policy
**Status**: IMPLEMENTED / LOCAL SCHEDULER UPDATED

- DailyNews now publishes once per day at 07:00 KST.
- GitHub Actions already used `cron: "0 22 * * *"` (07:00 KST); the workflow now passes `--max-reports 6` so all six category parts can publish.
- Each part/category is constrained to one deep topic via `--max-items 1`.
- Local Windows Task Scheduler was re-registered:
  - Active: `DailyNews_Morning_Insights` (`Ready`, next run 2026-05-20 07:00 local time when checked)
  - Removed/stale: `DailyNews_Evening_Insights`
- `scripts/setup_scheduled_tasks.ps1` now creates only the morning task and removes any stale evening task.
- `scripts/run_scheduled_insights.ps1` now accepts only `-Window morning`, sets `PROMPT_VERSION=v2-deep`, uses UTF-8 log writes, and runs a runtime preflight before generation.
- `scripts/verify_first_run.ps1` now validates the morning-only policy and warns if an evening task exists.

### Operational blocker found
**Status**: INTENTIONAL FAIL-FAST UNTIL CONFIGURED

- Local config currently loads `NOTION_API_KEY`, but no LLM key:
  - `GOOGLE_API_KEY=False`
  - `ANTHROPIC_API_KEY=False`
  - `OPENAI_API_KEY=False`
  - `NOTION_API_KEY=True`
- Because deep DailyNews output depends on an LLM provider, the scheduled runner now fails preflight with:
  - `Missing required runtime configuration: one_of:GOOGLE_API_KEY|ANTHROPIC_API_KEY|OPENAI_API_KEY`
- Add at least one LLM API key to `automation/DailyNews/.env` or the scheduled task user environment before expecting the 07:00 job to generate deep reports.

### Verification performed

- `python -m pytest tests/test_run_daily_news.py tests/unit/test_cli_entrypoints.py -q` -> `19 passed`
- PowerShell parser check passed for:
  - `automation/DailyNews/scripts/run_scheduled_insights.ps1`
  - `automation/DailyNews/scripts/setup_scheduled_tasks.ps1`
  - `automation/DailyNews/scripts/verify_first_run.ps1`
- Manual scheduled runner check intentionally exited non-zero at preflight because no LLM key is configured.

### Files changed in this session

- `.github/workflows/dailynews-pipeline.yml`
- `automation/DailyNews/scripts/run_daily_news.py`
- `automation/DailyNews/scripts/run_scheduled_insights.ps1`
- `automation/DailyNews/scripts/setup_scheduled_tasks.ps1`
- `automation/DailyNews/scripts/verify_first_run.ps1`
- `automation/DailyNews/scripts/run_morning_insights.bat`
- `automation/DailyNews/tests/test_run_daily_news.py`
- `automation/DailyNews/docs/scheduling/SETUP-GUIDE.md`
- `automation/DailyNews/docs/QUICK-START-GUIDE.md`
- `automation/DailyNews/src/antigravity_mcp/templates/newsletter/welcome.html`

---

## Current State (2026-05-08)

### Infrastructure Stabilization — 인프라 실행 정합성 확보
**Status**: COMPLETED

- **진단 도구 안정화**: `healthcheck.py`의 `rglob` 행 현상 해결 및 임포트 프로세스 격리(timeout 도입) 완료
- **실행 타임아웃 강화**: `run_workspace_smoke.py` 및 CIE 파이프라인에 300초 타임아웃 적용하여 무한 대기 방지
- **터미널 인코딩 최적화**: Windows 환경에서 `sys.stdout.reconfigure`를 통한 한글 깨짐(mojibake) 방지 적용
- **CI 보안 게이트 검증**: `ruff`, `bandit` 로컬 검증을 통해 보안 품질 게이트 정합성 확인

### Workspace Health

| Item | Status |
|:-----|:-------|
| Branch | `main` @ `8cd3ed8` |
| Last Smoke | ✅ 21/21 PASS (2026-05-08) |
| getdaytrends | ✅ |
| DailyNews | ✅ |
| CIE | ✅ |
| AgriGuard | ✅ |
| DeSci | ✅ |
| Dashboard | ✅ |
| shared | ✅ |

### Active Policies

- **X 발행**: 수동 전용 (자동 업로드 금지 — 계정 리스크)
- **콘텐츠 승인**: `CONTENT_APPROVAL_MODE=manual`, `AUTO_PUSH_ENABLED=False`
- **Canva**: refresh token 만료 (`invalid_grant`) — `canva_auth_server.py` PKCE 재인증 필요

### Pending Manual Follow-ups

1. Canva token 브라우저 재인증 최종 확인 (서버 기동 확인됨)
2. CI 게이트 실기동 로그 모니터링 (PR comment 정상 출력 여부)

---

> **Archive**: 이전 핸드오프 기록
> - 2026-03-26 ~ 2026-04-10: [`archive/HANDOFF_archive_pre_2026-04-17.md`](archive/HANDOFF_archive_pre_2026-04-17.md)
> - 2026-04-17 ~ 2026-05-06: [`archive/HANDOFF_archive_pre_2026-05-07.md`](archive/HANDOFF_archive_pre_2026-05-07.md)
