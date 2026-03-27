# getdaytrends v9.0 고도화 기획안
> 현재 버전: v8.0 | 목표 버전: v9.0 | 작성일: 2026-03-06

---

## 1. 현황 분석 (As-Is)

### 1.1 파이프라인 구조

```
수집(Step1) → 스코어링(Step2-3) → Deep Research(Step3.5) → 생성(Step4) → 저장(Step5)
```

### 1.2 현재 LLM 호출 비용 (트렌드 1개 기준)

| 호출 | 티어 | 빈도 | 비고 |
|------|------|------|------|
| 클러스터링 | LIGHTWEIGHT | 런 당 1회 | 동기 단일 호출 |
| 배치 스코어링 | LIGHTWEIGHT | 5개/1호출 | 캐시 TTL 18h |
| Deep Research | - | 품질 트렌드 재수집 | **Step1 중복 문제** |
| 단문 트윗 생성 | LIGHTWEIGHT | 1호출/트렌드 | Threads 포함 시 통합 |
| 장문 생성 | HEAVY(Sonnet) | viral >= 95 | 호출당 ~$0.02 |
| QA Audit | LIGHTWEIGHT | 1호출/트렌드 | avg_score 검증 |

### 1.3 발견된 주요 문제점

#### [P1] 크리티컬 - Deep Research 중복 수집
- Step 1에서 이미 contexts 수집 완료 (Twitter/Reddit/News 3소스 × 트렌드 수)
- Step 3.5에서 quality_trends 대상으로 **동일 소스를 재수집**
- 10개 트렌드 기준: 30회 HTTP 요청 중복 발생

#### [P2] 하이 - QA Audit 무조건 실행
- 캐시 재사용 콘텐츠에도 QA 실행 (불필요)
- 바이럴 점수 85점 이상 고품질 트렌드도 동일하게 심사
- 트렌드당 1회 추가 LLM 호출 고정

#### [P3] 미디엄 - 클러스터링 LLM 의존
- 의미적 유사도 판단에 LLM 사용 (LIGHTWEIGHT지만 런 당 1회 추가)
- 간단한 문자열 유사도(자카드/편집거리)로 대체 가능한 케이스 多

#### [P4] 미디엄 - 다국가 순차 실행
- `--countries korea,us,japan` 옵션이 **순차** 실행
- 각 국가 파이프라인이 독립적임에도 병렬화 미적용

#### [P5] 로우 - 히스토리 보정 N+1 패턴
- `_analyze_trends_async` 내부 for loop에서 `detect_trend_patterns`를 트렌드 수만큼 개별 호출
- 이미 `get_trend_history_batch`가 존재하나 스코어링 단계에 미적용

#### [P6] 로우 - X 실제 포스팅 미연동
- `scraper.py`에 `post_to_x_async` 구현 완료
- `main.py` 파이프라인에 포스팅 스텝 부재
- 생성된 콘텐츠가 Notion/Sheets에만 저장됨

---

## 2. 고도화 목표 (To-Be)

### 핵심 KPI
| 지표 | 현재 | 목표 |
|------|------|------|
| 런 당 LLM 호출 수 (10트렌드) | ~35회 | ~18회 (-49%) |
| 월 추정 비용 (장문 포함) | ~$1.20 | ~$0.60 (-50%) |
| 파이프라인 소요 시간 (10트렌드) | ~90초 | ~50초 (-44%) |
| 콘텐츠 품질 avg_score | 현재 미추적 | 75점 이상 목표 |
| X 실제 게시 자동화 | 0% | 옵션 활성 시 100% |

---

## 3. 개선 항목 상세

### Phase A: 비용 최적화 (Cost Optimization)

#### A-1. Deep Research 중복 수집 제거 [P1 해결]
**현재:**
```python
# Step 1: 전체 트렌드 컨텍스트 수집
raw_trends, contexts = collect_trends(config, conn)

# Step 3.5: quality_trends 재수집 (중복!)
deep_contexts = collect_contexts(dummy_raws, pipeline_config)
```

**개선안:**
```python
# Step 1에서 수집한 contexts를 quality_trends 필터 후 그대로 전달
# Step 3.5 완전 제거 OR 캐시된 contexts에서 선별만 수행

# 보강 필요 시: context 품질 점수 < 0.3인 항목만 선택적 재수집
low_quality = [t for t in quality_trends
               if context_quality_score(contexts[t.keyword]) < 0.3]
if low_quality:
    supplemental = await _async_collect_contexts(low_quality, config)
```

**절감 효과:** 런 당 HTTP 요청 ~30회 제거, 평균 15~20초 단축

---

#### A-2. QA Audit 선택적 실행 [P2 해결]
**조건부 스킵 로직:**

```python
def _should_skip_qa(trend: ScoredTrend, batch: TweetBatch, is_cached: bool) -> bool:
    """QA를 생략할 수 있는 조건."""
    if is_cached:
        return True                          # 캐시 재사용은 이미 검증됨
    if trend.viral_potential >= 85:
        return True                          # 고품질 트렌드는 스킵
    if trend.category in ["날씨", "음식", "스포츠"]:
        return True                          # 저위험 카테고리 스킵
    return False
```

**절감 효과:** QA 호출 ~60% 감소 (캐시 히트 + 고점수 트렌드 합산)

---

#### A-3. 로컬 클러스터링으로 LLM 대체 [P3 해결]
**현재:** 클러스터링 LLM 1회 호출/런

**개선안:** 자카드 유사도 기반 로컬 클러스터링
```python
def _jaccard_similarity(a: str, b: str) -> float:
    """형태소 단위 자카드 유사도 (0.0~1.0)."""
    set_a = set(a.lower().split())
    set_b = set(b.lower().split())
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)

def cluster_trends_local(raw_trends, threshold=0.4) -> ...:
    """LLM 없이 로컬 유사도 기반 클러스터링."""
    # 유사도 >= threshold면 같은 클러스터로 묶음
    # 10~15개 트렌드 기준 O(n²)이므로 성능 문제 없음
```

**LLM 클러스터링 유지 조건:** `ENABLE_LLM_CLUSTERING=true` 환경변수로 선택 가능

**절감 효과:** 런 당 1회 LLM 호출 제거 (~$0 이지만 latency 절감)

---

#### A-4. 히스토리 보정 배치 조회 [P5 해결]
**현재:** N+1 개별 쿼리
```python
for result in scored:
    pattern = await detect_trend_patterns(conn, result.keyword, days=7)
```

**개선안:** 단일 배치 조회
```python
# db.py에 추가할 함수
async def get_trend_history_patterns_batch(conn, keywords, days=7) -> dict[str, dict]:
    """여러 키워드의 히스토리 패턴을 1회 쿼리로 일괄 조회."""
    placeholders = ",".join("?" * len(keywords))
    since = datetime.now() - timedelta(days=days)
    rows = await conn.execute(
        f"SELECT keyword, viral_potential, scored_at FROM trends "
        f"WHERE keyword IN ({placeholders}) AND scored_at >= ? "
        f"ORDER BY scored_at DESC",
        (*keywords, since.isoformat())
    )
    # keywords별로 그룹핑 후 패턴 계산
```

**절감 효과:** DB 라운드트립 N → 1회 (10트렌드 기준 9회 절감)

---

#### A-5. 시간대별 생성 품질 차등화
**개념:** 피크 시간(오전 7~9시, 오후 12~1시, 저녁 7~9시)에만 고비용 생성 수행

```python
def _get_generation_mode() -> str:
    hour = datetime.now().hour
    if hour in [7, 8, 12, 19, 20]:
        return "full"      # 장문 포함
    elif 2 <= hour < 7:
        return "skip"      # 야간 → 생성 건너뜀 (스케줄 조정)
    else:
        return "lite"      # 단문만

# config에 추가
generation_mode_override: str = ""  # "full" | "lite" | "" (auto)
```

---

### Phase B: 품질 최적화 (Quality Optimization)

#### B-1. 트렌드 벨로시티 지표 추가
**현재:** 수집 시점 볼륨만 비교

**개선안:** 런 간 볼륨 델타를 추적해 실시간 상승 속도(velocity) 계산
```python
# db.py 추가
async def get_volume_velocity(conn, keyword, lookback_runs=3) -> float:
    """직전 N런의 볼륨 델타 평균 (상승률/런)."""
    # 데이터 부족 시 0.0 반환

# analyzer.py 시그널 스코어 반영
velocity_bonus = min(velocity * 5, 15)  # 최대 15점 추가 보너스
```

---

#### B-2. 콘텐츠 다양성 추적 (반복 표현 패널티)
**문제:** 동일 키워드가 6시간마다 재처리될 때 유사한 트윗이 생성됨

**개선안:** 생성된 콘텐츠의 TF-IDF 유사도 체크
```python
# db.py
async def get_recent_tweet_fingerprints(conn, keyword, hours=24) -> list[str]:
    """최근 N시간 내 생성된 트윗의 핑거프린트 목록."""

# generator.py - 생성 프롬프트에 이전 생성 내용 주입
if recent_tweets:
    avoid_section = f"\n[이미 생성된 표현 — 반드시 다른 각도로 작성]\n{recent_tweets}\n"
```

---

#### B-3. 소스 품질 피드백 루프 강화
**현재:** `enable_source_quality_tracking=True` 로 기록하나 수집 전략 미반영

**개선안:** 소스 품질 점수를 다음 런의 수집 전략에 반영
```python
# 소스별 최근 7일 평균 품질 조회
quality = await get_source_quality_avg(conn, ["twitter", "reddit", "news"], days=7)

# 품질 낮은 소스 타임아웃 단축 (리소스 절약)
timeout_map = {
    src: _SHORT_TIMEOUT if quality[src] < 0.3 else _DEFAULT_TIMEOUT
    for src in quality
}
```

---

#### B-4. 카테고리별 최적 게시 시간 학습
**개념:** 과거 트윗 데이터의 expected_engagement와 게시 시간을 매핑해 카테고리별 최적 시간 추천

```python
# db.py - 추가할 테이블
CREATE TABLE posting_time_stats (
    category TEXT,
    hour INTEGER,          -- 0~23
    avg_engagement REAL,   -- "높음"=1.0, "보통"=0.5, "낮음"=0.2
    sample_count INTEGER,
    updated_at TEXT
)

# 대시보드에서 시각화, 스케줄 자동 조정에 활용
```

---

#### B-5. 지정 키워드 Watchlist
**개념:** 특정 키워드(경쟁사명, 관심 주제 등)를 watchlist에 등록해 등장 시 즉시 알림

```python
# config.py 추가
watchlist_keywords: list[str] = field(default_factory=list)
# .env: WATCHLIST_KEYWORDS=OpenAI,Claude,삼성전자

# alerts.py - watchlist 매칭 시 별도 알림
def check_watchlist(trends, config) -> int:
    matches = [t for t in trends
               if any(kw.lower() in t.keyword.lower()
                      for kw in config.watchlist_keywords)]
    if matches:
        _send_alert(f"[WATCHLIST] {[m.keyword for m in matches]} 등장!", config)
    return len(matches)
```

---

### Phase C: 고도화 (Enhancement)

#### ~~C-1. X 실제 포스팅 파이프라인~~ [제외]

> **제외 사유:** X(Twitter) 자동화 정책(TOS) 위반 리스크. 자동 포스팅은 계정 정지 사유가 될 수 있어 구현하지 않음.

---

#### C-2. 다국가 병렬 실행 [P4 해결]
**현재:**
```python
for country in config.countries:
    run_pipeline(country_config, ...)  # 순차
```

**개선안:**
```python
async def _run_all_countries_parallel(config):
    """다국가를 asyncio.gather로 병렬 실행."""
    country_configs = [config.for_country(c) for c in config.countries]
    results = await asyncio.gather(
        *[_async_run_pipeline(cc) for cc in country_configs],
        return_exceptions=True,
    )
    # 각 국가 결과 집계 후 통합 리포트
```

**주의:** Notion API rate limit 고려 → per-country 세마포어 유지

**속도 개선:** 3개국 순차 90초 → 병렬 35초 (최대 국가)

---

#### C-3. 대시보드 고도화 (dashboard.py)
**현재 엔드포인트:** 기본 상태 조회 수준

**추가할 엔드포인트:**
```
GET  /api/trends/today          # 오늘 생성된 트렌드 + 트윗 목록
GET  /api/trends/{id}/tweets    # 특정 트렌드의 생성 트윗 전체
POST /api/tweets/{id}/post      # 수동 X 포스팅 트리거
GET  /api/cost/today            # 오늘 LLM 비용 상세
GET  /api/source/quality        # 소스별 품질 통계
GET  /api/stats/categories      # 카테고리별 바이럴 점수 분포
GET  /api/watchlist             # Watchlist 키워드 등장 히스토리
```

**프론트엔드 추가 (선택):** 경량 Alpine.js + TailwindCSS CDN 정적 HTML
```
dashboard.html → 실시간 파이프라인 상태 + 트윗 미리보기 + 원클릭 포스팅
```

---

#### C-4. Canva 비주얼 자동화 연동 (canva.py 활성화)
**현재:** `canva.py` 존재하나 파이프라인 미연동

**조건부 연동:**
```python
# config.py 추가
enable_canva_visuals: bool = False
canva_min_score: int = 90          # 이 점수 이상에만 비주얼 생성

# Step 4 이후: 고바이럴 트렌드 비주얼 자동 생성
if config.enable_canva_visuals and trend.viral_potential >= config.canva_min_score:
    visual_url = await generate_canva_visual(trend, batch, config)
    if visual_url:
        batch.visual_url = visual_url
```

---

#### C-5. 이메일 / Slack 알림 채널 추가
**현재:** Telegram + Discord만 지원

**개선안:**
```python
# alerts.py 추가
async def send_slack_alert(message: str, webhook_url: str) -> bool:
    """Slack Incoming Webhook 알림."""

async def send_email_alert(message: str, config: AppConfig) -> bool:
    """SMTP 기반 이메일 알림 (smtplib)."""

# config.py 추가
slack_webhook_url: str = ""
smtp_host: str = ""
smtp_port: int = 587
smtp_user: str = ""
smtp_password: str = ""
alert_email: str = ""
```

---

#### C-6. 트렌드 예측 모드 (Predictive Trending)
**개념:** 현재는 이미 뜨고 있는 트렌드만 수집. 볼륨이 낮지만 가속도가 급상승 중인 트렌드를 사전 포착.

```python
# scraper.py 개선
def _score_emerging_trend(trend: RawTrend, history: list) -> float:
    """볼륨이 낮아도 가속도가 높으면 이머징 트렌드 점수 부여."""
    if trend.volume_numeric < 5000 and trend.volume_numeric > 500:
        # 직전 런 대비 볼륨 증가율 계산
        velocity = compute_volume_velocity(history)
        if velocity > 2.0:  # 직전 런 대비 2배 이상 증가
            return 30.0     # 이머징 보너스
    return 0.0

# config.py 추가
enable_emerging_detection: bool = True
emerging_velocity_threshold: float = 2.0
```

---

## 4. 구현 우선순위 로드맵

### Sprint 1 (즉시 실행, 1~2일): 비용 절감
| ID | 작업 | 예상 효과 | 파일 |
|----|------|-----------|------|
| A-1 | Deep Research 중복 제거 | HTTP 30회 절감, 15초 단축 | `main.py` |
| A-2 | QA Audit 조건부 스킵 | LLM 60% 절감 | `main.py`, `generator.py` |
| A-4 | 히스토리 배치 조회 | DB N+1 해소 | `db.py`, `analyzer.py` |

### Sprint 2 (단기, 3~5일): 품질 + 포스팅
| ID | 작업 | 예상 효과 | 파일 |
|----|------|-----------|------|
| A-3 | 로컬 클러스터링 | 런 당 1회 LLM 제거 | `analyzer.py` |
| ~~C-1~~ | ~~X 자동 포스팅~~ | **제외 (TOS 위반 리스크)** | - |
| B-5 | Watchlist 알림 | 관심 키워드 모니터링 | `alerts.py`, `config.py` |
| B-3 | 소스 품질 피드백 강화 | 수집 효율 향상 | `scraper.py`, `db.py` |

### Sprint 3 (중기, 1~2주): 고도화
| ID | 작업 | 예상 효과 | 파일 |
|----|------|-----------|------|
| C-2 | 다국가 병렬 실행 | 실행 시간 ~60% 단축 | `main.py` |
| C-3 | 대시보드 고도화 | 운영 가시성 향상 | `dashboard.py` |
| B-1 | 벨로시티 지표 | 이머징 트렌드 선점 | `db.py`, `analyzer.py` |
| A-5 | 시간대별 생성 차등화 | 피크 타임 집중 최적화 | `main.py`, `config.py` |

### Sprint 4 (장기, 2~4주): 확장
| ID | 작업 | 비고 | 파일 |
|----|------|------|------|
| C-4 | Canva 비주얼 자동화 | canva.py 이미 존재 | `main.py`, `canva.py` |
| C-5 | Slack/이메일 알림 | 채널 다양화 | `alerts.py` |
| B-2 | 콘텐츠 다양성 추적 | 반복 표현 방지 | `generator.py`, `db.py` |
| C-6 | 이머징 트렌드 예측 | 선점 기회 포착 | `scraper.py`, `analyzer.py` |

---

## 5. 비용 최적화 시뮬레이션

### 현재 비용 구조 (10트렌드, 1런 기준)
```
클러스터링:      1호출 × LIGHTWEIGHT = ~$0.000
배치 스코어링:   2호출 × LIGHTWEIGHT = ~$0.000  (10개/2배치)
Deep Research:  30 HTTP 요청 (무료지만 latency 비용)
트윗 생성:      10호출 × LIGHTWEIGHT = ~$0.000
장문 생성:       2호출 × HEAVY(Sonnet) = ~$0.040  (viral >= 95, 2개 가정)
QA Audit:       10호출 × LIGHTWEIGHT = ~$0.000
──────────────────────────────────────────────────
런 당 총 LLM:   ~25호출, 비용 ~$0.040
일 6런 기준:     ~$0.24 / 월 ~$7.20 (Sonnet 포함)
```

> **참고:** Gemini 2.0 Flash는 현재 무료 티어이므로 LIGHTWEIGHT 비용 = $0
> 실질 비용은 Sonnet(HEAVY) 호출 수에 비례

### 개선 후 비용 구조
```
클러스터링:      0호출 (로컬 자카드로 대체, A-3)
배치 스코어링:   2호출 × LIGHTWEIGHT = $0.000
Deep Research:  0 HTTP 추가 요청 (중복 제거, A-1)
트윗 생성:      10호출 × LIGHTWEIGHT = $0.000
장문 생성:       2호출 × HEAVY(Sonnet) = ~$0.040  (조건 동일)
QA Audit:        4호출 × LIGHTWEIGHT = $0.000  (60% 스킵, A-2)
──────────────────────────────────────────────────
런 당 총 LLM:   ~18호출 (-28%), 비용 ~$0.040 (Sonnet 유지)
latency 절감:    ~35초 단축 (Deep Research 제거 효과)
```

### 장문 생성 비용 추가 최적화 옵션
```python
# 예산 대비 효율 기준 모델 선택
if trend.viral_potential >= 98:
    tier = TaskTier.HEAVY        # Sonnet: 최고 바이럴만
elif trend.viral_potential >= 95:
    tier = TaskTier.MEDIUM       # Gemini 1.5 Pro (중간 비용)
else:
    tier = TaskTier.LIGHTWEIGHT  # Gemini Flash
```

---

## 6. DB 스키마 변경 사항

### 6.1 tweets 테이블 추가 컬럼
```sql
ALTER TABLE tweets ADD COLUMN posted_at TEXT;
ALTER TABLE tweets ADD COLUMN x_tweet_id TEXT;
ALTER TABLE tweets ADD COLUMN post_status TEXT DEFAULT 'pending';
ALTER TABLE tweets ADD COLUMN variant_group TEXT;  -- A/B 그룹 추적
```

### 6.2 신규 테이블
```sql
-- 소스 품질 통계 집계 (기존 source_quality에서 집계)
CREATE TABLE IF NOT EXISTS source_quality_daily (
    date TEXT,
    source TEXT,
    avg_quality REAL,
    success_rate REAL,
    avg_latency_ms REAL,
    sample_count INTEGER,
    PRIMARY KEY (date, source)
);

-- 게시 시간 최적화 학습
CREATE TABLE IF NOT EXISTS posting_time_stats (
    category TEXT,
    hour INTEGER,
    avg_engagement REAL,
    sample_count INTEGER,
    updated_at TEXT,
    PRIMARY KEY (category, hour)
);

-- Watchlist 등장 히스토리
CREATE TABLE IF NOT EXISTS watchlist_hits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT,
    watchlist_item TEXT,
    viral_potential INTEGER,
    detected_at TEXT
);
```

### 6.3 인덱스 추가
```sql
CREATE INDEX IF NOT EXISTS idx_tweets_post_status ON tweets(post_status);
CREATE INDEX IF NOT EXISTS idx_tweets_posted_at ON tweets(posted_at);
CREATE INDEX IF NOT EXISTS idx_trends_scored_at_country ON trends(scored_at, country);
```

---

## 7. 환경변수 추가 목록 (.env.example 업데이트)

```env
# === Phase A: 비용 최적화 ===
ENABLE_LLM_CLUSTERING=false          # true=LLM, false=로컬 자카드 (기본)
QA_SKIP_CACHED=true                  # 캐시 콘텐츠 QA 스킵
QA_SKIP_HIGH_SCORE=85                # 이 점수 이상 QA 스킵
GENERATION_MODE=auto                 # auto|full|lite

# === Phase B: 품질 ===
WATCHLIST_KEYWORDS=                  # 쉼표 구분 관심 키워드
ENABLE_EMERGING_DETECTION=true
EMERGING_VELOCITY_THRESHOLD=2.0

# === Phase C: 고도화 ===
ENABLE_AUTO_POST=false               # X 자동 포스팅
AUTO_POST_MIN_SCORE=80
AUTO_POST_TYPE=공감 유도형
AUTO_POST_DELAY_MINUTES=5
ENABLE_PARALLEL_COUNTRIES=true       # 다국가 병렬 실행
ENABLE_CANVA_VISUALS=false
CANVA_MIN_SCORE=90
SLACK_WEBHOOK_URL=
ALERT_EMAIL=
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
```

---

## 8. 테스트 계획

### 8.1 회귀 테스트
- `tests/test_analyzer.py`: 로컬 클러스터링 정확도 검증 (기존 LLM 결과 대비 80% 일치 목표)
- `tests/test_scraper.py`: Deep Research 제거 후 contexts 품질 동등성 검증
- `tests/test_generator.py`: QA 스킵 조건별 콘텐츠 품질 비교

### 8.2 비용 검증 테스트
```bash
# dry-run으로 LLM 호출 수 측정
python main.py --dry-run --one-shot --verbose --limit 10 2>&1 | grep "acreate"

# 개선 전후 호출 수 비교
# 기대: ~25회 → ~18회
```

### 8.3 E2E 테스트
```bash
# 다국가 병렬 실행 검증
python main.py --countries korea,us --one-shot --dry-run

# 자동 포스팅 검증 (X 샌드박스 계정)
ENABLE_AUTO_POST=true AUTO_POST_MIN_SCORE=1 python main.py --dry-run
```

---

## 9. 리스크 및 주의사항

| 리스크 | 영향도 | 대응 방안 |
|--------|--------|-----------|
| 로컬 클러스터링 정확도 저하 | 중 | 신뢰도 낮을 때 LLM 폴백 (ENABLE_LLM_CLUSTERING=auto) |
| X 자동 포스팅 오발송 | 높 | dry_run 모드 강제 테스트 → 수동 승인 후 활성화 |
| 다국가 병렬 실행 시 Notion rate limit | 중 | 국가별 Semaphore 분리 + 지수 백오프 |
| Deep Research 제거로 컨텍스트 품질 저하 | 중 | 품질 임계값 미달 시 선택적 재수집 로직 유지 |
| X API rate limit (15분/앱 제한) | 높 | 포스팅 간격 최소 5분 + rate limit 헤더 모니터링 |

---

## 10. 성공 지표 (Definition of Done)

### Sprint 1 완료 기준
- [ ] Deep Research Step 제거 후 런 소요 시간 15초 이상 단축
- [ ] QA Audit 조건부 스킵으로 LLM 호출 수 -40% 이상
- [ ] DB N+1 쿼리 → 배치 조회 전환 완료
- [ ] 기존 테스트 100% 통과

### Sprint 2 완료 기준
- [ ] 로컬 클러스터링 vs LLM 클러스터링 정확도 80% 이상 일치
- [ ] X 자동 포스팅 dry-run 성공
- [ ] Watchlist 알림 수신 확인 (Telegram)

### 전체 목표 달성 기준
- [ ] 런 당 LLM 호출 수 -30% 이상
- [ ] 파이프라인 소요 시간 -30% 이상
- [ ] 생성 콘텐츠 avg QA score 75점 이상
- [ ] X 자동 포스팅 1주 무장애 운영
