# DailyNews 성능 최적화 가이드

**작성일**: 2026-03-21
**대상**: 시스템 관리자, 개발자
**목표**: 파이프라인 성능 3배 향상

---

## 📊 현재 성능 기준 (Baseline)

### 측정 결과 (2026-03-21 기준)

| 메트릭 | 현재 값 | 목표 | 상태 |
|--------|---------|------|------|
| **평균 실행 시간** | ~4분 | 2분 | ⚠️ 개선 필요 |
| **성공률** | 84% | 95% | ⚠️ 개선 필요 |
| **LLM 캐시 히트율** | 미측정 | 60% | 📊 측정 필요 |
| **병렬 처리** | 3 concurrent | 5 concurrent | ⚠️ 조정 가능 |
| **HTTP 타임아웃** | 15s | 10s | ⚠️ 조정 가능 |

---

## 🎯 최적화 전략 (우선순위별)

### Priority 1: LLM 캐시 최적화 (예상 개선: 40%)

#### 문제
- LLM API 호출이 전체 실행 시간의 60% 차지
- 동일 카테고리 반복 분석 시 캐시 미사용

#### 해결책

**1. 캐시 히트율 측정 스크립트**

파일: `scripts/analyze_llm_cache.py`

```python
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).resolve().parents[1]
db_path = PROJECT_ROOT / "data" / "pipeline_state.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 전체 통계
cursor.execute("SELECT COUNT(*) FROM llm_cache")
total = cursor.fetchone()[0]

# 7일 내 재사용된 캐시
cutoff = (datetime.now() - timedelta(days=7)).isoformat()
cursor.execute("""
    SELECT
        COUNT(DISTINCT prompt_hash) as unique_prompts,
        COUNT(*) as total_queries
    FROM llm_cache
    WHERE created_at >= ?
""", (cutoff,))

unique, queries = cursor.fetchone()
hit_rate = ((queries - unique) / queries * 100) if queries > 0 else 0

print(f"LLM Cache Statistics (Last 7 Days)")
print(f"  Total Cache Entries: {total:,}")
print(f"  Unique Prompts: {unique:,}")
print(f"  Total Queries: {queries:,}")
print(f"  Cache Hit Rate: {hit_rate:.1f}%")
print(f"  Estimated API Calls Saved: {queries - unique:,}")

conn.close()
```

**실행**:
```bash
cd "d:\AI 프로젝트\DailyNews"
python scripts\analyze_llm_cache.py
```

**2. 캐시 TTL 최적화**

파일: `src/antigravity_mcp/integrations/llm_adapter.py`

**현재 설정 확인**:
```python
# LLM 캐시 만료 시간 확인
# 기본값: 7일 (604800초)
```

**권장 설정**:
- 뉴스 요약: 1일 (빠르게 변하는 콘텐츠)
- 트렌드 분석: 7일 (패턴은 천천히 변함)
- 인사이트 생성: 3일 (중간)

**3. 캐시 웜업 스크립트**

매일 아침 자주 사용하는 프롬프트를 미리 캐싱:

```bash
# scripts/warmup_cache.bat
python -m antigravity_mcp jobs generate-brief --window morning --max-items 1 --categories Tech
```

---

### Priority 2: 병렬 처리 확대 (예상 개선: 30%)

#### 문제
- 현재 3개 concurrent 작업만 실행
- CPU/네트워크 자원 미활용

#### 해결책

**1. 동시성 증가**

파일: `.env`

**변경 전**:
```env
PIPELINE_MAX_CONCURRENCY=3
```

**변경 후** (단계적 적용):
```env
# Step 1: 5 concurrent (1주일 테스트)
PIPELINE_MAX_CONCURRENCY=5

# Step 2: 성공 시 7로 증가
# PIPELINE_MAX_CONCURRENCY=7
```

**2. 모니터링 스크립트**

```python
# scripts/monitor_concurrency.py
import sqlite3
from datetime import datetime, timedelta

db_path = "data/pipeline_state.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 동시 실행 수 분석
cutoff = (datetime.now() - timedelta(days=1)).isoformat()
cursor.execute("""
    SELECT
        COUNT(*) as concurrent_jobs,
        MIN(started_at) as batch_start,
        MAX(finished_at) as batch_end
    FROM job_runs
    WHERE started_at >= ?
    GROUP BY DATE(started_at), HOUR(started_at)
    HAVING COUNT(*) > 1
    ORDER BY concurrent_jobs DESC
    LIMIT 10
""", (cutoff,))

print("Concurrent Job Analysis:")
for row in cursor.fetchall():
    print(f"  {row[0]} jobs | {row[1]} ~ {row[2]}")

conn.close()
```

**3. 테스트 계획**

| 동시성 | 테스트 기간 | 성공률 목표 | 평균 시간 목표 |
|--------|------------|------------|--------------|
| 3 (현재) | - | 84% | 4분 |
| 5 | 1주일 | ≥80% | 3분 |
| 7 | 1주일 | ≥80% | 2.5분 |

---

### Priority 3: HTTP 타임아웃 튜닝 (예상 개선: 15%)

#### 문제
- 타임아웃 15초는 과도하게 길 수 있음
- 느린 API 호출이 전체 파이프라인 지연

#### 해결책

**1. API 응답 시간 측정**

```python
# scripts/measure_api_response_times.py
import asyncio
import httpx
import time
from statistics import mean, median

async def measure_notion_api():
    """Notion API 응답 시간 측정"""
    import os
    api_key = os.getenv('NOTION_API_KEY')

    times = []
    async with httpx.AsyncClient() as client:
        for _ in range(10):
            start = time.time()
            try:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Notion-Version": "2022-06-28"
                }
                response = await client.get(
                    "https://api.notion.com/v1/users/me",
                    headers=headers,
                    timeout=15.0
                )
                duration = time.time() - start
                times.append(duration)
            except Exception as e:
                print(f"Error: {e}")

    if times:
        print(f"Notion API Response Times (n={len(times)}):")
        print(f"  Mean: {mean(times):.2f}s")
        print(f"  Median: {median(times):.2f}s")
        print(f"  Min: {min(times):.2f}s")
        print(f"  Max: {max(times):.2f}s")
        print(f"  Recommended timeout: {max(times) * 1.5:.1f}s")

asyncio.run(measure_notion_api())
```

**실행**:
```bash
python scripts\measure_api_response_times.py
```

**2. 타임아웃 조정**

파일: `.env`

**권장 설정** (측정 후):
```env
# Notion API 평균 응답: ~2s
# Recommended: 평균 * 3 = 6s
PIPELINE_HTTP_TIMEOUT_SEC=10

# 재시도 횟수도 조정
PIPELINE_MAX_RETRIES=2
```

---

### Priority 4: 데이터베이스 최적화 (예상 개선: 10%)

#### 문제
- SQLite 쿼리 최적화 부족
- 인덱스 미사용

#### 해결책

**1. 인덱스 추가**

```sql
-- scripts/optimize_database.sql
CREATE INDEX IF NOT EXISTS idx_job_runs_started_at
ON job_runs(started_at DESC);

CREATE INDEX IF NOT EXISTS idx_job_runs_status
ON job_runs(status);

CREATE INDEX IF NOT EXISTS idx_article_cache_link
ON article_cache(link);

CREATE INDEX IF NOT EXISTS idx_llm_cache_prompt_hash
ON llm_cache(prompt_hash);
```

**실행**:
```bash
sqlite3 data\pipeline_state.db < scripts\optimize_database.sql
```

**2. VACUUM 실행 (월간)**

```bash
# scripts/vacuum_database.bat
@echo off
echo Optimizing database...
sqlite3 "d:\AI 프로젝트\DailyNews\data\pipeline_state.db" "VACUUM;"
echo Done.
```

**3. 쿼리 성능 분석**

```python
# scripts/analyze_query_performance.py
import sqlite3
import time

db_path = "data/pipeline_state.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# EXPLAIN QUERY PLAN
queries = [
    "SELECT * FROM job_runs WHERE status = 'success' ORDER BY started_at DESC LIMIT 10",
    "SELECT * FROM llm_cache WHERE prompt_hash = 'test'",
    "SELECT * FROM article_cache WHERE link = 'https://example.com'"
]

for query in queries:
    start = time.time()
    cursor.execute(f"EXPLAIN QUERY PLAN {query}")
    plan = cursor.fetchall()
    duration = time.time() - start

    print(f"Query: {query[:60]}...")
    print(f"  Plan: {plan}")
    print(f"  Time: {duration*1000:.2f}ms\n")

conn.close()
```

---

### Priority 5: 콘텐츠 수집 최적화 (예상 개선: 5%)

#### 문제
- RSS 피드 순차 처리
- 중복 기사 필터링 비효율적

#### 해결책

**1. 피드 병렬 수집**

파일: `src/antigravity_mcp/pipelines/collect.py`

현재 구조 확인 및 병렬화 적용 여부 검토

**2. 중복 체크 최적화**

```python
# 현재: O(n) 리스트 검색
if article_link in seen_links:
    continue

# 개선: O(1) 해시 셋
seen_links = set()  # 리스트 대신 셋 사용
```

---

## 📈 성능 측정 및 추적

### 벤치마크 스크립트

파일: `scripts/benchmark_pipeline.py`

```python
import subprocess
import time
from datetime import datetime

def benchmark(window: str, iterations: int = 3):
    """파이프라인 성능 벤치마크"""
    times = []

    for i in range(iterations):
        print(f"Run {i+1}/{iterations}...")
        start = time.time()

        result = subprocess.run(
            ["python", "-m", "antigravity_mcp.cli", "jobs", "generate-brief",
             "--window", window, "--max-items", "3"],
            capture_output=True,
            text=True,
            cwd="d:\\AI 프로젝트\\DailyNews"
        )

        duration = time.time() - start
        times.append(duration)

        print(f"  Duration: {duration:.2f}s")
        print(f"  Status: {'✓' if result.returncode == 0 else '✗'}")

    print(f"\nBenchmark Results ({window}):")
    print(f"  Average: {sum(times)/len(times):.2f}s")
    print(f"  Min: {min(times):.2f}s")
    print(f"  Max: {max(times):.2f}s")

if __name__ == "__main__":
    benchmark("morning", iterations=3)
```

**실행**:
```bash
python scripts\benchmark_pipeline.py
```

---

## 🎯 성능 개선 로드맵

### Week 1: 측정 및 기준 설정
- [ ] LLM 캐시 히트율 측정
- [ ] API 응답 시간 측정
- [ ] 벤치마크 실행 (baseline)

### Week 2: Quick Wins
- [ ] 병렬 처리 3 → 5로 증가
- [ ] HTTP 타임아웃 15s → 10s로 조정
- [ ] 데이터베이스 인덱스 추가

### Week 3: 측정 및 검증
- [ ] 새 벤치마크 실행
- [ ] 성공률 모니터링
- [ ] 에러 로그 분석

### Week 4: 추가 최적화
- [ ] LLM 캐시 TTL 최적화
- [ ] 병렬 처리 5 → 7로 증가 (선택)
- [ ] RSS 피드 병렬 수집 (선택)

---

## 📊 예상 결과

### 최적화 전 vs 후

| 메트릭 | Before | After (목표) | 개선율 |
|--------|--------|------------|-------|
| **평균 실행 시간** | 4분 | 2분 | **-50%** |
| **LLM API 호출** | 100% | 40% (60% 캐시) | **-60%** |
| **병렬 작업** | 3 | 5~7 | **+67%~133%** |
| **성공률** | 84% | 95% | **+11%** |
| **월간 비용** | 추정 $50 | $30 | **-40%** |

---

## 🔧 모니터링 도구

### 1. 실시간 대시보드

```bash
python scripts\monitoring_dashboard.py
```

### 2. 주간 성능 리포트

```bash
# scripts/weekly_performance_report.ps1
$StartDate = (Get-Date).AddDays(-7).ToString("yyyy-MM-dd")

python -c "
import sqlite3
from datetime import datetime, timedelta

db = sqlite3.connect('data/pipeline_state.db')
cursor = db.cursor()

cutoff = '$StartDate'

# 실행 통계
cursor.execute('''
    SELECT
        COUNT(*) as total,
        AVG(JULIANDAY(finished_at) - JULIANDAY(started_at)) * 24 * 60 as avg_minutes,
        SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as success_count
    FROM job_runs
    WHERE started_at >= ?
''', (cutoff,))

total, avg_min, success = cursor.fetchone()
success_rate = (success / total * 100) if total > 0 else 0

print(f'Weekly Performance Report ({cutoff} ~ today)')
print(f'  Total Runs: {total}')
print(f'  Success Rate: {success_rate:.1f}%')
print(f'  Average Duration: {avg_min:.1f} minutes')
"
```

---

## 📚 참고 문서

1. **현재 성능 기준**: [QC-COMPREHENSIVE-REPORT-2026-03-21.md](QC-COMPREHENSIVE-REPORT-2026-03-21.md)
2. **파이프라인 구조**: `src/antigravity_mcp/pipelines/`
3. **설정 파일**: `.env`, `src/antigravity_mcp/config.py`

---

**작성**: Claude Code QC Agent
**최종 업데이트**: 2026-03-21
**버전**: 1.0
