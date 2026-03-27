# getdaytrends v3.0 / v8.0 - Pipeline Workflow

## System Overview

X(Twitter) 트렌드를 자동 수집 -> 분석 -> 콘텐츠 생성 -> 저장하는 end-to-end 파이프라인.

```
[Entry Point]
main.py → parse_args() → AppConfig.from_env() → run_pipeline()
                                                      │
                              ┌────────────────────────┘
                              ▼
                    _async_run_pipeline()
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
    Pre-checks          Pipeline Steps        Post-steps
    (예산/limit)        (1→2→3→4→5)         (스케줄/비용)
```

---

## Module Map

| File | Role | LLM Tier |
|------|------|----------|
| `config.py` | 환경변수 로드, 설정 관리, 유효성 검사 | - |
| `models.py` | Pydantic 데이터 모델 (RawTrend, ScoredTrend, TweetBatch 등) | - |
| `scraper.py` | 멀티소스 트렌드 수집 (getdaytrends.com, X API, Reddit, Google News, YouTube) | - |
| `analyzer.py` | 바이럴 스코어링 + 클러스터링 + 히스토리 보정 | LIGHTWEIGHT |
| `generator.py` | 트윗/장문/쓰레드 생성 + QA 검수 | LIGHTWEIGHT / HEAVY |
| `main.py` | 파이프라인 오케스트레이터 + 스케줄러 | - |
| `db.py` | SQLite/PostgreSQL 비동기 DB 레이어 | - |
| `storage.py` | Notion / Google Sheets 외부 저장 | - |
| `alerts.py` | Telegram / Discord 알림 + 비용 리포트 | - |
| `dashboard.py` | FastAPI 대시보드 (`:8080`) | - |
| `utils.py` | run_async, sanitize_keyword 등 유틸 | - |
| `shared/llm/` | 티어 기반 LLM 라우팅 + 비용 추적 | - |

---

## Pipeline Flow (Step by Step)

### Pre: Budget & Adaptive Limit

```
_check_budget_and_adjust_limit(config, conn)
    │
    ├─ [C2] shared/llm/stats.py에서 오늘 누적 비용 조회
    │   └─ 누적 >= daily_budget_usd ($2.00)
    │       → enable_long_form=False, thread_min_score=999 (Sonnet 비활성화)
    │
    ├─ [C2] 시간대별 예산: 22~07시 → daily_budget * 0.5 (off-peak)
    │
    └─ [C4] 직전 3시간 평균 바이럴 점수 기반 limit 조정
        ├─ 평균 < 60점 → limit 절반 (저품질 절약)
        └─ 평균 >= 80점 → limit +2 (고품질 확장)
```

**Output**: `pipeline_config` (불변 복사본)

---

### Step 1: Collect (수집)

```
_step_collect(config, conn)
    │
    └─ scraper.collect_trends(config, conn)
        │
        ├─ [Primary] getdaytrends.com HTML 스크래핑
        │   └─ 1시간 메모리 캐시 (_FETCH_CACHE)
        │
        ├─ [Secondary] 병렬 컨텍스트 수집 (collect_contexts)
        │   ├─ X API (twitter_bearer_token)
        │   ├─ Reddit (httpx GET)
        │   ├─ Google News RSS
        │   └─ YouTube Trending RSS [v5.0]
        │
        └─ [v6.1] RSS pubDate 파싱 → content_age_hours 계산
```

**Input**: `AppConfig`
**Output**: `raw_trends: list[RawTrend]`, `contexts: dict[str, MultiSourceContext]`

---

### Step 2-3: Score & Alert (분석)

```
_step_score_and_alert(raw_trends, contexts, config, conn, run)
    │
    ├─ analyzer.analyze_trends()
    │   │
    │   ├─ [Clustering] cluster_trends() — LIGHTWEIGHT 1회 호출
    │   │   └─ 유사 키워드 그루핑 → 대표 키워드만 남김
    │   │
    │   ├─ [Batch Scoring] _batch_score_async() — 5개/LLM 호출
    │   │   │
    │   │   ├─ 캐시 조회 (fingerprint 기반, TTL 18h)
    │   │   │
    │   │   ├─ BATCH_SCORING_PROMPT_TEMPLATE ──────────────────────┐
    │   │   │   [v8.0 프롬프트 (1)] 분석 항목:                       │
    │   │   │   1. volume_last_24h, trend_acceleration              │
    │   │   │   2. viral_potential (0~100)                          │
    │   │   │   3. top_insight, suggested_angles (3개)              │
    │   │   │   4. sentiment, safety_flag                           │
    │   │   │   5. why_trending (원인 추론)         ← NEW           │
    │   │   │   6. peak_status (상승중|정점|하락중)   ← NEW           │
    │   │   │   7. relevance_score (1~10)           ← NEW           │
    │   │   │   8. joongyeon_kick, joongyeon_angle                  │
    │   │   │   9. category, best_hook_starter                     │
    │   │   └──────────────────────────────────────────────────────┘
    │   │
    │   ├─ _parse_scored_trend_from_dict()
    │   │   ├─ [Phase 1] cross_source_confidence (0~4)
    │   │   │   └─ confidence < 2 → viral_potential * 0.65
    │   │   │
    │   │   └─ [Phase 2] Hybrid Scoring
    │   │       hybrid = LLM점수 * 0.6 + signal점수 * 0.4
    │   │       signal = volume(30) + acceleration(25) + sources(25) + freshness(20)
    │   │
    │   ├─ [Phase 3] 히스토리 패턴 보정 (detect_trend_patterns)
    │   │   ├─ new    → x1.10
    │   │   ├─ rising → x1.15
    │   │   ├─ stable → x0.90
    │   │   ├─ falling → x0.75
    │   │   └─ 5회 이상 반복 → 추가 x0.80
    │   │
    │   └─ [Phase 4] 중연 킥 기반 장문 조건 우회
    │       └─ joongyeon_kick >= 75 → viral_potential = long_form_min_score
    │
    ├─ _ensure_quality_and_diversity()
    │   ├─ safety_flag=True 제거
    │   ├─ exclude_categories 제거 (정치, 연예)
    │   ├─ [v6.1] 최신성 패널티 (stale x0.85, expired x0.7)
    │   ├─ Pass 1: 카테고리별 최고 점수 1개 시드 (다양성)
    │   ├─ Pass 2: 나머지 슬롯 바이럴 순 (max_same_category=2)
    │   └─ Pass 3: 최소 기사 수(5) 미달 시 기준 60% 하향
    │
    └─ check_and_alert() — Telegram/Discord 알림 전송
```

**Input**: `raw_trends`, `contexts`
**Output**: `scored_trends`, `quality_trends` (필터링 완료)

---

### Step 3.5: Deep Research (심층 컨텍스트)

```
quality_trends에 대해 추가 컨텍스트 수집
    │
    └─ scraper.collect_contexts()
        ├─ twitter_insight 보강
        ├─ reddit_insight 보강
        └─ news_insight 병합
```

---

### Step 4: Generate (생성)

```
_step_generate(quality_trends, config, conn)
    │
    └─ 각 트렌드 병렬: asyncio.gather(*[_get_or_generate(t) ...])
        │
        ├─ [C2 Cache] compute_fingerprint → get_cached_content
        │   └─ 가속도 기반 TTL: 하락/정체=48h, 상승=24h
        │
        ├─ generate_for_trend_async(trend, config, client) ─────────────┐
        │   │                                                           │
        │   ├─ _select_generation_tier()                                │
        │   │   └─ heavy_categories (정치/경제/테크 등) → HEAVY (Sonnet)  │
        │   │   └─ 그 외 → LIGHTWEIGHT (Gemini Flash)                   │
        │   │                                                           │
        │   ├─ [Always] generate_tweets_async() — 단문 5종              │
        │   │   │   LIGHTWEIGHT, max_tokens=1500                        │
        │   │   │                                                       │
        │   │   │   [v8.0 프롬프트 (2)] 생성 컨텍스트:                    │
        │   │   │   ├─ _build_account_identity_section()  ← NEW         │
        │   │   │   │   ├─ 분야: AI/테크/트렌드                          │
        │   │   │   │   ├─ 톤앤매너: (joongyeon or 커스텀)               │
        │   │   │   │   └─ 타겟: IT 종사자, 스타트업 관계자              │
        │   │   │   ├─ _build_context_section()                         │
        │   │   │   └─ _build_scoring_section()                         │
        │   │   │                                                       │
        │   │   │   Output JSON per tweet:                              │
        │   │   │   ├─ type, content                                    │
        │   │   │   ├─ best_posting_time      ← NEW                    │
        │   │   │   ├─ expected_engagement    ← NEW                    │
        │   │   │   └─ reasoning              ← NEW                    │
        │   │   │                                                       │
        │   │   │   트윗 5종 유형:                                       │
        │   │   │   ├─ 공감 유도형                                      │
        │   │   │   ├─ 꿀팁형                                           │
        │   │   │   ├─ 찬반 질문형                                      │
        │   │   │   ├─ 시크한 관찰형 (joongyeon) / 동기부여형 (generic)  │
        │   │   │   └─ 핫테이크형 (joongyeon) / 유머밈형 (generic)      │
        │   │   │                                                       │
        │   │   └─ 280자 초과 시 자동 트리밍                              │
        │   │                                                           │
        │   ├─ [Conditional] generate_long_form_async()                 │
        │   │   └─ viral_potential >= 95 (long_form_min_score)          │
        │   │       HEAVY (Sonnet), max_tokens=4000                    │
        │   │       딥다이브 (1500~2500자) + 핫테이크 (1000~2000자)      │
        │   │                                                           │
        │   └─ [Disabled] generate_thread_async()                      │
        │       └─ thread_min_score=999 → 사실상 비활성화               │
        │                                                               │
        └───────────────────────────────────────────────────────────────┘
        │
        ├─ [v8.0 프롬프트 (3)] QA Feedback Loop ──────────────────────┐
        │   │                                                          │
        │   ├─ audit_generated_content()                               │
        │   │   LIGHTWEIGHT, max_tokens=600                            │
        │   │                                                          │
        │   │   5-Point Checklist:                                     │
        │   │   1. 사실 오류 없는가?                                    │
        │   │   2. 논란 유발 표현 없는가?                               │
        │   │   3. 자연스러운 사람의 글인가? (AI 냄새 제거)             │
        │   │   4. 타겟 오디언스에게 가치 제공하는가?                    │
        │   │   5. X 커뮤니티 가이드라인 준수하는가?                     │
        │   │                                                          │
        │   │   Output: {avg_score, worst_tweet_type,                  │
        │   │            reason, corrected_tweets[]}                   │
        │   │                                                          │
        │   └─ avg_score < 50 (quality_feedback_min_score)             │
        │       ├─ corrected_tweets 있음                               │
        │       │   → 교정본 직접 적용 (LLM 재호출 절약)  ← v8.0 NEW  │
        │       └─ corrected_tweets 없음                               │
        │           → 전체 재생성 1회                                   │
        └──────────────────────────────────────────────────────────────┘
        │
        ├─ [Optional] A/B Variant B (enable_ab_variants=False)
        │   └─ 직설적 논쟁적 톤으로 단문 5종 추가 생성
        │
        └─ [Optional] Multilang (enable_multilang=False)
            └─ target_languages별 단문 5종 추가 생성
```

**Input**: `quality_trends`
**Output**: `batch_results: list[TweetBatch]`

---

### Step 5: Save (저장)

```
_step_save(quality_trends, batch_results, config, conn, run, run_row_id)
    │
    ├─ safety_flag=True 스킵
    │
    ├─ [Atomic] db_transaction(conn)
    │   ├─ save_trend() → trend_id
    │   └─ save_tweets_batch() (short + long + threads + thread)
    │
    └─ [Parallel] 외부 저장 (Semaphore=10)
        ├─ Notion API (notion_sem_limit 동시 요청 보호)
        └─ Google Sheets API
```

**Input**: `quality_trends`, `batch_results`
**Output**: DB + Notion/Sheets 저장 완료

---

### Post: Adaptive Schedule & Cost Alert

```
_adjust_schedule(scored_trends, config)
    │
    ├─ 핫 트렌드 감지 (90점+ & 급상승) → 간격 1/4 (최소 15분)
    ├─ 평균 75점+ → 간격 x0.85 (최소 30분)
    ├─ 평균 55점 미만 → 간격 x1.25 (최대 180분)
    └─ 기본 → schedule_minutes (360분)

send_daily_cost_alert()
    └─ 일일 예산 70%+ 도달 시 Telegram/Discord 경고
```

---

## LLM Call Summary (per trend)

| Step | Call | Tier | Est. Cost | Condition |
|------|------|------|-----------|-----------|
| Scoring | batch (5개/1call) | LIGHTWEIGHT | ~$0 | Always |
| Clustering | 1 call | LIGHTWEIGHT | ~$0 | enable_clustering=True |
| Tweet 5종 | 1 call | LIGHTWEIGHT | ~$0 | Always |
| Long-form 2종 | 1 call | HEAVY | ~$0.02 | viral >= 95 |
| X Thread | 1 call | HEAVY | - | **Disabled** (999) |
| QA Audit | 1 call | LIGHTWEIGHT | ~$0 | enable_quality_feedback=True |
| **Total** | **~3-4 calls** | | **~$0.02** | |

**Monthly Estimate** (1회/6h, 5 trends/run):
- LIGHTWEIGHT only: ~$0/month (Gemini 2.0 Flash free tier)
- With HEAVY (long-form): ~$1.20/month

---

## Data Flow Diagram

```
                    ┌──────────────┐
                    │  .env (keys) │
                    └──────┬───────┘
                           ▼
┌─────────────┐     ┌─────────────┐     ┌──────────────┐
│ getdaytrends│     │   X API     │     │ Google News  │
│   .com      │     │  (Bearer)   │     │  RSS Feed    │
└──────┬──────┘     └──────┬──────┘     └──────┬───────┘
       │                   │                    │
       └───────────┬───────┘────────────────────┘
                   ▼
           ┌───────────────┐
           │  RawTrend[]   │ + MultiSourceContext{}
           └───────┬───────┘
                   ▼
           ┌───────────────┐    ┌─────────────────┐
           │  analyzer.py  │───▶│  Score Cache     │
           │  (LIGHTWEIGHT)│    │  (SQLite 18h)    │
           └───────┬───────┘    └─────────────────┘
                   ▼
           ┌───────────────┐
           │ ScoredTrend[] │  + why_trending, peak_status,
           │ (filtered)    │    relevance_score, joongyeon_kick
           └───────┬───────┘
                   ▼
           ┌───────────────┐    ┌─────────────────┐
           │ generator.py  │───▶│ Content Cache    │
           │ (LIGHT+HEAVY) │    │ (SQLite 24~48h)  │
           └───────┬───────┘    └─────────────────┘
                   ▼
           ┌───────────────┐
           │  TweetBatch   │  + best_posting_time,
           │               │    expected_engagement,
           │               │    reasoning
           └───────┬───────┘
                   ▼
           ┌───────────────┐    (avg_score < 50)
           │  QA Audit     │───▶ corrected_tweets 적용
           │ (LIGHTWEIGHT)  │    or 전체 재생성
           └───────┬───────┘
                   ▼
        ┌──────────┼──────────┐
        ▼          ▼          ▼
   ┌────────┐ ┌────────┐ ┌────────────┐
   │ SQLite │ │ Notion │ │ GSheets    │
   │ (local)│ │ (API)  │ │ (API)      │
   └────────┘ └────────┘ └────────────┘
```

---

## Key Configuration (config.py)

### Cost Control
| Param | Default | Description |
|-------|---------|-------------|
| `daily_budget_usd` | 2.00 | 일 예산 상한. 초과 시 Sonnet 비활성화 |
| `peak_budget_multiplier` | 0.5 | 비피크(22~07시) 예산 배율 |
| `cost_alert_pct` | 70.0 | 예산 70% 도달 시 알림 |
| `long_form_min_score` | 95 | 이 이상만 장문 생성 (Sonnet 사용) |
| `thread_min_score` | 999 | **Disabled** (쓰레드 비활성화) |

### Quality Control
| Param | Default | Description |
|-------|---------|-------------|
| `min_viral_score` | 60 | 이하 트렌드 생성 건너뜀 |
| `enable_quality_feedback` | True | QA 피드백 루프 활성화 |
| `quality_feedback_min_score` | 50 | QA 이하 시 교정/재생성 |
| `min_article_count` | 5 | 파이프라인 최소 기사 수 보장 |
| `max_same_category` | 2 | 동일 카테고리 최대 기사 수 |
| `exclude_categories` | [정치, 연예] | 자동 제외 카테고리 |

### Identity (v8.0)
| Param | Default | Description |
|-------|---------|-------------|
| `account_niche` | AI/테크/트렌드 | 계정 분야 |
| `target_audience` | IT 종사자, 스타트업 관계자 | 타겟 오디언스 |
| `tone` | 친근하고 위트 있는 동네 친구 | 톤앤매너 (또는 "joongyeon") |

---

## Execution Modes

```bash
# 1회 실행 (기본)
python main.py --one-shot

# 한국 + 미국 순차 실행
python main.py --countries korea,us --one-shot

# 분석만 (저장 안 함)
python main.py --dry-run --verbose

# 스케줄 모드 (6시간마다, 야간 슬립 02~07시)
python main.py

# 대시보드 서버
python main.py --serve

# 통계 확인
python main.py --stats
```

---

## v8.0 Prompt Architecture Summary

### Prompt 1: Trend Analysis (analyzer.py)
- **Where**: `BATCH_SCORING_PROMPT_TEMPLATE` / `SCORING_PROMPT_TEMPLATE`
- **Added**: `why_trending`, `peak_status`, `relevance_score`
- **Rules**: 하락 트렌드 표시, 가십보다 인사이트 우선, X 논의 적합도 평가

### Prompt 2: Content Generation (generator.py)
- **Where**: `_system_tweets()`, `_system_tweets_joongyeon()`, `_system_tweets_and_threads()`
- **Added**: `_build_account_identity_section()` (niche/audience/tone 주입)
- **Output**: `best_posting_time`, `expected_engagement`, `reasoning` per tweet

### Prompt 3: Quality Audit (generator.py)
- **Where**: `_CONTENT_QA_PROMPT` / `audit_generated_content()`
- **Checklist**: 사실 오류 / 논란 위험 / AI 자연스러움 / 오디언스 가치 / 가이드라인
- **Key**: `corrected_tweets` 직접 적용 → LLM 재호출 1회 절약
