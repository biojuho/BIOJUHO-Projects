# DailyNews 빠른 시작 가이드

**작성일**: 2026-03-21
**대상**: DailyNews 프로젝트 운영자
**소요시간**: 10분

---

## 🚀 즉시 실행 (오늘)

### Step 1: Task Scheduler 등록 (5분)

#### 방법 1: PowerShell 자동 설정 (권장)

1. **PowerShell 관리자 권한으로 실행**
   - 시작 메뉴 검색: "PowerShell"
   - 우클릭 → "관리자 권한으로 실행"

2. **스크립트 실행**
   ```powershell
   cd "d:\AI 프로젝트\DailyNews\scripts"
   .\setup_scheduled_tasks.ps1
   ```

3. **결과 확인**
   ```powershell
   Get-ScheduledTask -TaskName "DailyNews*" | Format-Table TaskName, State, NextRunTime
   ```

   **예상 출력**:
   ```
   TaskName                      State NextRunTime
   --------                      ----- -----------
   DailyNews_Morning_Insights    Ready 2026-03-22 07:00:00
   DailyNews_Evening_Insights    Ready 2026-03-21 18:00:00
   ```

#### 방법 2: Task Scheduler GUI 수동 설정

자세한 방법은 [SETUP-GUIDE.md](scheduling/SETUP-GUIDE.md) 참조

---

### Step 2: 수동 테스트 실행 (2분)

스케줄러 등록 후 즉시 테스트하려면:

```cmd
cd "d:\AI 프로젝트\DailyNews"
scripts\test_insight_generation.bat morning
```

**확인 사항**:
- [ ] 로그 파일 생성: `logs\insights\test_morning_*.log`
- [ ] 에러 없이 완료
- [ ] Notion 페이지 생성 (선택사항)

---

## 📅 단기 작업 (1주일)

### 1. 첫 자동 실행 검증

**일시**: 다음 07:00 또는 18:00

#### 사전 준비 (실행 10분 전)

```powershell
# 1. Task Scheduler 확인
Get-ScheduledTask -TaskName "DailyNews*" | Select-Object TaskName, State, NextRunTime

# 2. 로그 디렉토리 준비
cd "d:\AI 프로젝트\DailyNews\logs\insights"
ls  # 현재 파일 목록 확인
```

#### 실행 후 검증 (실행 10분 후)

```powershell
# 1. 최신 로그 파일 확인
cd "d:\AI 프로젝트\DailyNews\logs\insights"
ls | sort LastWriteTime -Descending | select -First 3

# 2. 로그 내용 확인
Get-Content (ls | sort LastWriteTime -Descending | select -First 1).FullName -Tail 20

# 3. 마지막 실행 상태 확인
Get-ScheduledTask -TaskName "DailyNews_Morning_Insights" | Get-ScheduledTaskInfo
```

#### 검증 체크리스트

- [ ] 로그 파일 생성됨 (`morning_*.log` 또는 `evening_*.log`)
- [ ] 로그에 `[SUCCESS]` 메시지 포함
- [ ] 에러 메시지 없음
- [ ] Notion 페이지 생성 확인 (선택)
- [ ] Task 상태 = "Ready" (다음 실행 대기 중)

---

### 2. 문서 업데이트 (Skill 경로)

#### 수정 대상 파일

**파일**: `PROJECT-STATUS.md` (Line 26)

**변경 전**:
```markdown
- ✅ `.agent/skills/daily-insight-generator/generator.py` (13 KB)
```

**변경 후**:
```markdown
- ✅ `d:/AI 프로젝트/.agent/skills/daily-insight-generator/generator.py` (13 KB)
```

**또는**:
```markdown
- ✅ `<workspace-root>/.agent/skills/daily-insight-generator/generator.py` (13 KB)
```

#### 추가 업데이트

**파일**: `docs/PROJECT-COMPLETION-REPORT.md` (Line 82)

동일하게 경로 수정

---

## 🎯 중기 작업 (1개월)

### 1. 모니터링 대시보드 구축

#### Option A: Streamlit 대시보드 (권장)

기존 파일 활용: `apps/streamlit_dashboard.py`

**실행**:
```bash
cd "d:\AI 프로젝트\DailyNews"
streamlit run apps/streamlit_dashboard.py
```

**추가 기능 구현**:
- [ ] Insight 생성 통계
- [ ] 일일/주간 성공률 차트
- [ ] 최근 10회 실행 로그
- [ ] 에러 알림

#### Option B: Notion 대시보드 페이지

**수동 작업**:
1. Notion에서 새 페이지 생성
2. 데이터베이스 연결 (NOTION_REPORTS_DATABASE_ID)
3. 필터 및 뷰 설정

---

### 2. 성능 최적화

#### A. LLM 캐시 분석

**스크립트 작성**: `scripts/analyze_llm_cache.py`

```python
import sqlite3
from pathlib import Path

db_path = Path("data/pipeline_state.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 캐시 히트율 계산
cursor.execute("""
    SELECT
        COUNT(*) as total_queries,
        SUM(CASE WHEN cache_hit = 1 THEN 1 ELSE 0 END) as cache_hits
    FROM llm_cache
""")

total, hits = cursor.fetchone()
hit_rate = (hits / total * 100) if total > 0 else 0

print(f"LLM Cache Statistics:")
print(f"  Total Queries: {total}")
print(f"  Cache Hits: {hits}")
print(f"  Hit Rate: {hit_rate:.1f}%")

conn.close()
```

**실행**:
```bash
python scripts/analyze_llm_cache.py
```

#### B. 병렬 처리 확대

**파일**: `src/antigravity_mcp/config.py` (Line 266)

**현재**:
```python
pipeline_max_concurrency=_env_int("PIPELINE_MAX_CONCURRENCY", 3),
```

**권장**:
```python
pipeline_max_concurrency=_env_int("PIPELINE_MAX_CONCURRENCY", 5),
```

**.env 파일 수정**:
```env
PIPELINE_MAX_CONCURRENCY=5
```

#### C. HTTP 타임아웃 최적화

**측정**:
```python
# scripts/measure_response_times.py
import httpx
import time

async def measure():
    async with httpx.AsyncClient() as client:
        start = time.time()
        response = await client.get("https://api.notion.com/v1/databases/{db_id}")
        duration = time.time() - start
        print(f"Notion API: {duration:.2f}s")

import asyncio
asyncio.run(measure())
```

**조정**: 평균 응답시간 + 50% 여유

---

## 📊 성과 모니터링

### 주간 체크리스트 (매주 월요일)

```powershell
# 1. 지난 주 실행 통계
cd "d:\AI 프로젝트\DailyNews"
python -c "
import sqlite3
conn = sqlite3.connect('data/pipeline_state.db')
cursor = conn.cursor()
cursor.execute('''
    SELECT status, COUNT(*)
    FROM job_runs
    WHERE started_at >= date('now', '-7 days')
    GROUP BY status
''')
print('Last 7 days statistics:')
for row in cursor.fetchall():
    print(f'  {row[0]}: {row[1]}')
"

# 2. 로그 에러 검색
cd logs\insights
findstr /s /i "ERROR" *.log
findstr /s /i "FAIL" *.log

# 3. 디스크 사용량
du -sh logs/
du -sh data/
```

### 월간 리뷰 항목

- [ ] 성공률 ≥ 80% 유지
- [ ] 평균 실행 시간 ≤ 5분
- [ ] Notion 페이지 생성 정상
- [ ] 에러 로그 0건 또는 해결됨
- [ ] 디스크 사용량 < 500MB

---

## 🔧 트러블슈팅

### Issue: Task가 실행되지 않음

**진단**:
```powershell
# 1. Task 상태 확인
Get-ScheduledTask -TaskName "DailyNews_Morning_Insights" | Format-List

# 2. 마지막 실행 결과
Get-ScheduledTaskInfo -TaskName "DailyNews_Morning_Insights" | Format-List

# 3. Task Scheduler 서비스 확인
Get-Service Schedule
```

**해결**:
```powershell
# 서비스 재시작
Restart-Service Schedule

# Task 수동 실행
Start-ScheduledTask -TaskName "DailyNews_Morning_Insights"
```

### Issue: Python 환경 에러

**증상**: `No module named antigravity_mcp`

**해결**:
```cmd
cd "d:\AI 프로젝트\DailyNews"
python -m pip install -e .
```

### Issue: Notion API 에러

**증상**: `APIResponseError: Description is not a property`

**진단**:
```python
# 데이터베이스 스키마 확인
python -c "
import os
from notion_client import Client

notion = Client(auth=os.getenv('NOTION_API_KEY'))
db_id = os.getenv('NOTION_REPORTS_DATABASE_ID')
db = notion.databases.retrieve(database_id=db_id)
print('Properties:')
for key in db['properties'].keys():
    print(f'  - {key}')
"
```

**해결**: 스키마와 코드 속성명 일치 확인

---

## 📞 지원 및 문의

### 문서 참조

1. **종합 점검 보고서**: [QC-COMPREHENSIVE-REPORT-2026-03-21.md](QC-COMPREHENSIVE-REPORT-2026-03-21.md)
2. **스케줄링 가이드**: [scheduling/SETUP-GUIDE.md](scheduling/SETUP-GUIDE.md)
3. **모니터링 가이드**: [scheduling/MONITORING-GUIDE.md](scheduling/MONITORING-GUIDE.md)
4. **Skill 문서**: `d:/AI 프로젝트/.agent/skills/daily-insight-generator/SKILL.md`

### 추가 지원

- QC 재점검 요청
- 커스텀 스크립트 작성
- 성능 튜닝 컨설팅

---

**작성**: Claude Code QC Agent
**최종 업데이트**: 2026-03-21
**버전**: 1.0
