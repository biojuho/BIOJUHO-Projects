# SQLite → Supabase PostgreSQL 마이그레이션 계획

**작성일**: 2026-03-30
**상태**: 📋 PLAN (미착수)
**우선순위**: P1 — getdaytrends + pipeline_state 먼저, llm_costs/cie는 후순위

---

## 현재 DB 인벤토리

| DB | 경로 | 크기 | 테이블 | 행수 | 용도 |
|:---|:---|:---|:---|:---|:---|
| **getdaytrends** | `automation/getdaytrends/data/getdaytrends.db` | 2.82MB | 15 | ~4,167 | 트렌드 수집/분석/발행 |
| **pipeline_state** | `automation/DailyNews/data/pipeline_state.db` | 4.31MB | 15 | ~2,857 | 뉴스 리포트/캐시/추론 |
| **llm_costs** | `packages/shared/llm/data/llm_costs.db` | 0.88MB | 2 | ~5,590 | LLM 비용 추적 |
| **cie** | `automation/content-intelligence/data/cie.db` | 0.06MB | 5 | ~32 | CIE 콘텐츠 저장 |

**총합**: 8.07MB, 37 테이블, ~12,646 행

---

## 대상 플랫폼: Supabase (PostgreSQL)

### 선택 근거

1. **AgriGuard 패턴 재사용**: 이미 SQLite → PostgreSQL + Alembic 이전을 성공한 패턴 보유
2. **Free Tier**: 500MB, 2 projects — 현재 총 DB가 8MB이므로 충분
3. **PostgreSQL 네이티브**: NULL 처리, 타입 안전성, JSONB 등 SQLite 한계 해소
4. **통합 가능**: Auth, Storage, Realtime 기능 활용 가능

### 아키텍처

```
Supabase Project (Free Tier: 500MB)
├── schema: getdaytrends     (runs, trends, tweets, ...)
├── schema: dailynews        (job_runs, content_reports, ...)
├── schema: llm_costs        (llm_calls)
└── schema: cie              (trend_reports, generated_contents, ...)
```

---

## 이전 단계

### Phase 1: getdaytrends + pipeline_state (2주)

#### Step 1: Supabase 프로젝트 생성

- Supabase 계정 생성 또는 기존 프로젝트 활용
- Connection string 확보: `postgresql://postgres:[password]@[host]:5432/postgres`
- `.env`에 `DATABASE_URL` 추가

#### Step 2: 스키마 변환

SQLite DDL → PostgreSQL DDL 변환 규칙:

| SQLite | PostgreSQL |
|:---|:---|
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL PRIMARY KEY` |
| `TEXT` | `TEXT` |
| `REAL` | `DOUBLE PRECISION` |
| `BLOB` | `BYTEA` |
| 날짜 `TEXT` | `TIMESTAMPTZ` |
| `""` (빈 문자열 기본값) | `NULL` (정규화 필수!) |

#### Step 3: 마이그레이션 스크립트

```python
# migrate_to_supabase.py (AgriGuard 패턴 재사용)
import sqlite3
import psycopg2

def migrate(sqlite_path, pg_url, schema_name):
    src = sqlite3.connect(sqlite_path)
    dst = psycopg2.connect(pg_url)

    # 1. CREATE SCHEMA IF NOT EXISTS
    # 2. CREATE TABLE (PostgreSQL DDL)
    # 3. INSERT INTO ... SELECT FROM sqlite
    # 4. Normalize empty strings → NULL
    # 5. Verify row counts
```

#### Step 4: Dual-write 기간 (1주)

- 코드에서 SQLite + PostgreSQL 양쪽에 기록
- 읽기는 SQLite (안전장치)
- 불일치 감지 시 alerts

#### Step 5: Switch-over

- 읽기를 PostgreSQL로 전환
- SQLite는 fallback으로 1주간 유지
- 문제없으면 SQLite 코드 제거

### Phase 2: llm_costs (1주)

- `shared/llm/stats.py`의 `CostTracker`만 수정
- 2개 테이블 (llm_calls, sqlite_sequence)이므로 단순

### Phase 3: cie (미래)

- 32행 수준이므로 급하지 않음
- CIE v2.0 실제 운영 안정화 후 진행

---

## 코드 변경 범위

### getdaytrends 변경 대상

| 파일 | 크기 | 변경 유형 |
|:---|:---|:---|
| `automation/getdaytrends/db.py` | 30KB | `sqlite3` → `psycopg2` |
| `automation/getdaytrends/db_schema.py` | 17KB | DDL 변환 |
| `automation/getdaytrends/storage.py` | 17KB | 쿼리 호환성 |

### DailyNews 변경 대상

| 파일 | 크기 | 변경 유형 |
|:---|:---|:---|
| `automation/DailyNews/src/.../state/store.py` | - | DB 연결 추상화 |
| `automation/DailyNews/src/.../state/mixins.py` | - | 쿼리 호환성 |

### 공통 변경

| 파일 | 변경 유형 |
|:---|:---|
| `.env` | `DATABASE_URL` 추가 |
| `requirements.txt` (각 프로젝트) | `psycopg2-binary` 추가 |

---

## 주의사항

### NULL vs 빈 문자열 정규화 (CRITICAL)

2026-03-30에 발견된 `notion_page_id` 장애:
- Python dataclass 기본값: `""` (빈 문자열)
- DB 쿼리: `WHERE notion_page_id IS NULL` → 빈 문자열 탐지 불가

PostgreSQL 이전 시 **반드시** 빈 문자열을 NULL로 정규화:

```sql
UPDATE content_reports SET notion_page_id = NULL WHERE notion_page_id = '';
UPDATE content_reports SET notion_url = NULL WHERE notion_url = '';
```

### SQLite 전용 기능 대체

- `sqlite3.Row` → `psycopg2.extras.RealDictCursor`
- `PRAGMA table_info` → `information_schema.columns`
- `sqlite_sequence` → PostgreSQL `SERIAL` 자동 관리
- `json_extract()` → PostgreSQL `->`, `->>` 연산자 또는 `JSONB`

---

## 예상 비용

| 항목 | 비용 |
|:---|:---|
| Supabase Free Tier | $0 (500MB, 50K reads/day, 20K writes/day) |
| 추가 비용 시나리오 | Pro $25/mo (8GB, unlimited reads — 현재 필요 없음) |

---

## 검증 계획

1. **마이그레이션 정합성**: 행 수 비교 (SQLite vs PostgreSQL)
2. **기존 테스트 통과**: getdaytrends 22개, DailyNews 32개
3. **Dual-write 기간**: 불일치 로그 모니터링
4. **성능 벤치마크**: 로컬 SQLite vs 원격 PostgreSQL 응답 시간 비교
