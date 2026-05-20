# Devlog: Notion MCP 서버

## 2026-01-01

### 프로젝트 시작
- **목표**: Python을 사용하여 Notion MCP 서버를 구축하고, AI(Antigravity)가 Notion 페이지를 검색하고 읽을 수 있도록 함.
- **결정 사항**:
    - 데이터 처리 능력과 AI 통합 잠재력을 고려하여 구현 언어로 **Python**을 선택함.
    - 소통 규칙 수립: 개념을 명확히 설명하고, 구현 전 논의하며, 진행 상황을 문서화함.
- **다음 단계**:
    - 프로젝트 구조 정의 및 Git 설정.
    - 개발 환경 설정.

## 2026-02-06

### Notion 뉴스 봇 고도화 (AI Agent)
- **뉴스 수집 및 요약**:
  - `news_bot.py` 신규 개발: RSS 피드를 수집하고 Gemini 2.0 Flash를 이용해 개별 기사를 3줄 요약.
  - `BrainModule` 연동: 기사들을 종합 분석하여 "인사이트"와 "X(트위터) 포스트 초안"을 생성하도록 업그레이드.
- **자동화**:
  - `run_daily_news.bat` 배치 파일 업데이트로 원클릭 실행 환경 구축.
- **성과**:
  - 단순 수집을 넘어, '분석'하는 인텔리전트 에이전트로 진화. Notion 페이지에 AI 인사이트 섹션 추가.

## 2026-05-19

### Local intelligence and analogy guard hardening
- **목표**: DailyNews를 단순 뉴스 요약 자동화에서 로컬 기사 추출, 의미 기반 클러스터링, 품질 관측 메타데이터를 갖춘 뉴스 인텔리전스 파이프라인으로 고도화.
- **구현**:
  - `JinaAdapter`에 `LocalArticleExtractor`를 추가해 Trafilatura 기반 로컬 기사 본문 추출을 먼저 수행하고 Jina Reader로 fallback하도록 개선.
  - `collect.py`의 기사 본문 수집도 같은 로컬 추출기를 재사용하도록 정리.
  - `EmbeddingAdapter`에 FastEmbed 로컬 fallback을 추가해 `GOOGLE_API_KEY`가 없어도 semantic clustering이 가능하도록 개선.
  - 리포트 `analysis_meta.source_intelligence`에 source count, full-text coverage, cluster count, multi-source topics, embedding provider를 저장.
  - 대시보드 최근 리포트에 source/cluster/multi-source topic 신호를 표시.
  - X longform/insight/brain prompts에서 비유, 은유, "마치 ~ 같다", "~처럼" 유도 문구를 제거하고 사실, 수치, 이해관계자 영향 중심 규칙으로 교체.
  - DailyNews QA와 getdaytrends QA에 prohibited analogy/metaphor detector를 추가해 금지 표현이 남으면 `needs_review` 또는 tone penalty로 잡히게 함.
- **문서화**:
  - `docs/GITHUB-ENHANCEMENT-ROADMAP-2026-05-19.md` 추가.
  - `docs/runbooks/local-intelligence.md` 추가.
  - README에 `article-extraction` 및 `semantic-local` optional extra 설치 경로 추가.
- **검증**:
  - DailyNews full suite: `477 passed`.
  - DailyNews analogy/local intelligence targeted suite: `49 passed`.
  - getdaytrends generation/content QA suite: `73 passed`.
  - `ruff check` 통과.
  - `uv pip check` 통과.

## 2026-05-20

### Product-ready morning operations alignment
- **목표**: DailyNews 운영 표면을 제품완성형에 가깝게 정리해 실제 운영자와 스케줄러가 같은 실행 경로, 같은 설정 요구사항, 같은 실패 신호를 보도록 함.
- **구현**:
  - `docs/QUICK-START-GUIDE.md`와 `docs/scheduling/SETUP-GUIDE.md`를 현재 정책에 맞춰 재작성: 하루 1회 07:00 KST, `DailyNews_Morning_Insights` 단일 작업, `run_scheduled_insights.ps1 -Window morning` 기준.
  - `run_morning_insights.bat`를 오래된 venv/직접 CLI 실행 대신 production PowerShell runner로 위임하는 compatibility wrapper로 축소.
  - `test_insight_generation.bat`도 morning-only smoke wrapper로 정리하고 legacy evening 인자를 명시적으로 거부.
  - `run_scheduled_insights.ps1` preflight에 `NOTION_REPORTS_DATABASE_ID`를 추가해 Notion 업로드 대상이 없는 실행을 generation 전에 차단.
  - `ops doctor` CLI를 추가해 morning runner 필수 설정, 스크립트 파일, 경로를 오프라인으로 점검할 수 있게 함.
  - `config.py`가 DailyNews 로컬 `.env`뿐 아니라 workspace root `.env`도 보조 로드하도록 보강해 CLI, scheduler, venv 간 설정 판정 불일치를 제거.
  - scheduled runner의 Python 선택 기준에 `dotenv`와 `sqlalchemy`를 추가해 `.env` 및 `shared.llm` 비용 추적 경로를 사용할 수 없는 로컬 venv를 피하도록 함.
  - scheduled runner가 report 0건 또는 `all_providers_failed` fallback-only 결과를 production 성공으로 처리하지 않도록 실패 게이트를 추가.
  - LLM fallback provider 체인에서 Gemini 403처럼 빈 응답이 돌아온 경우를 성공으로 오판하지 않고 Anthropic/OpenAI까지 계속 시도하도록 수정.
  - fallback provider 순서를 `Gemini -> Anthropic -> OpenAI -> Ollama`로 조정해 로컬 Ollama 미기동 상태가 원격 fallback을 지연시키지 않도록 함.
  - README의 환경변수 설명을 "필수 / 권장 / 선택"으로 분리하고 LLM 키는 셋 중 하나만 필수임을 명확히 함.
- **검증**:
  - `python -m pytest automation\DailyNews\tests\test_run_daily_news.py -q` -> `11 passed`.
  - `python -m pytest automation\DailyNews\tests\unit\test_config_aliases.py automation\DailyNews\tests\unit\test_tooling_content_ops.py::TestOpsTools::test_ops_doctor_reports_blockers_and_ready_state automation\DailyNews\tests\unit\test_cli_entrypoints.py::TestCliOpsModule::test_run_ops_doctor automation\DailyNews\tests\unit\test_cli_entrypoints.py::TestCliOpsModule::test_dispatch_ops_command_and_main_entrypoint -q` -> `6 passed`.
  - `python -m pytest automation\DailyNews\tests\unit\test_llm_client_wrapper.py` -> `1 passed`.
  - `run_scheduled_insights.ps1` PowerShell parser check 통과.
  - `test_insight_generation.bat evening --no-pause`는 exit `1`로 legacy evening 실행을 거부.
  - `test_insight_generation.bat morning --no-pause`는 네트워크 허용 상태에서 production runner로 진입해 workspace `.venv` 선택, preflight, 6개 report ID 생성, manual approval prep, dashboard refresh, NotebookLM markdown export까지 exit `0`로 완료.
  - 최종 runner는 Google/Gemini 키 403 이후 Anthropic fallback provider로 생성했으며, 일부 리포트는 `needs_review` 품질 경고를 남겼으나 auto-publish는 수동 승인 정책에 의해 차단됨.
- **Notion Single-DB & Workspace Hygiene**:
  - `NOTION_TASKS_DATABASE_ID`와 `NOTION_REPORTS_DATABASE_ID`가 동일 DB를 중복 설정하여 `ops doctor` 시 발생하던 Warning을 single-DB 모델 권장 정책에 의거 `NOTION_TASKS_DATABASE_ID` 주석 처리를 통해 해소 완료.
  - 재검증 실행 결과 `ready: true` 및 `blockers: []`, `warnings: []`에 준하는 깨끗한 운영 표면 정비 확보.
  - Antigravity CLI 상태 디렉토리(`.antigravitycli/`) 및 앱 캐시 디렉토리를 `.gitignore`에 등록하여 Git 추적 잡음 제거.
