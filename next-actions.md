# Next Actions

> 세션 종료 시 `/session-workflow`가 이 파일의 갱신을 제안합니다.
> 2026-04-17 10:47 기준 — 기술 부채 3건 전부 해소. news_bot.py 완전 삭제, 431 테스트 GREEN, QC 승인.

## 완료 항목

- [x] DailyNews smoke 게이트 `pytest` → `uv run` 수정 (S1-2)
- [x] `run_daily_news.py` JSON manifest 출력 (S2-1)
- [x] Telegram `[PRE-FAIL]/[PARTIAL]/[TOTAL-FAIL]` prefix 분류 (S2-2)
- [x] workflow bare command 금지 lint (S1-2)
- [x] `test_env_loader.py` warning 캐시 leak 수정 (S2-3)
- [x] `run_workspace_smoke` shared/tests/ 커버리지 (이미 존재)
- [x] 독립 감시자 워크플로 배포 (S1-5)
- [x] Notion DB 단일화: config.py에서 `NOTION_TASKS_DATABASE_ID` 미설정 시 `NOTION_REPORTS_DATABASE_ID`로 자동 fallback
- [x] pytest capture crash 해결: dashboard `api.py`의 `sys.stdout` 교체가 pytest를 파괴하는 버그 수정
- [x] pytest 8.3.x 핀 고정: 4개 pyproject.toml에서 `>=8.3,<8.4` 범위로 고정
- [x] DailyNews `news_bot.py` 레거시 의존성 분리: `category_filter.py` 추출 + 3개 active 스크립트 마이그레이션
- [x] pytest-asyncio loop scope 경고 해결
- [x] DailyNews `report-economy_global` 수동 보강 + Notion 재동기화
- [x] **pipeline_state.db stale running job 정리** — `refresh_dashboard` 좀비 → `failed` 전환 (2026-04-17)
- [x] **biolinker pytest → `[project.optional-dependencies].dev` 이동** (2026-04-17)
- [x] **news_bot.py 완전 제거** — 1,222줄 삭제 + test_category_filter_migration.py 7개 테스트 재작성 (2026-04-17)

## Backlog (향후 진행 가능)

- [x] Economy_Global 갱신본 X 초안 검토 후 실제 발행 여부 결정
- [x] Economy_Global Canva 카드 생성/디자인 검수 후 게시 자산 확정
- [x] DailyNews 수동 큐레이션 경로에 "기존 Notion 페이지 overwrite + channel_publications refresh" 자동화 추가
- [x] Dashboard CI 워크플로 리뷰 및 머지 (GHA workflow 파일 대기 중)
- [x] `category_filter.py` docstring "deprecated 2026-03-04" 문구를 "Originally extracted from…" 으로 업데이트 (LOW, ~2분)
- [x] `proofreader.py`, `sentiment_analyzer.py` 주석의 news_bot.py 참조 정리 (LOW, ~5분)
- [ ] DeSci Platform Frontend 컴포넌트 배포 및 리뷰
- [ ] `.smoke-tmp/` 및 `.test-tmp/` 내 permission-denied 잔류 디렉토리 정리

## 다음 세션 복붙 메모

```text
DailyNews Economy_Global 후속 진행:
- Canva 카드 수정본 저장 완료. 편집 링크: https://www.canva.com/d/boGsMspzVS9l_5B
- 수동 큐레이션 재동기화 자동화 추가 완료.
- 재실행 커맨드: uv run python -m antigravity_mcp ops resync-report --report-id report-economy_global-20260416T220508Z
- 최신 Notion 백업: automation/DailyNews/data/notion_backups/report-economy_global-20260416T220508Z.before-notion-resync-20260417T020633Z.json
- 권장 다음 액션:
  1. X 최종 문안 확정 후 수동 발행
  2. Canva 카드 export/posting asset 확정
  3. HANDOFF.md에 실제 X 발행 URL과 최종 게시 시각 기록
```
