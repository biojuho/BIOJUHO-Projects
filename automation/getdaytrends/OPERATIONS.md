# GetDayTrends 운영 규칙 (Operational Rules)

> 실시간 트렌드 파이프라인의 안정적 무인 운영을 위한 규칙.
> 최종 업데이트: 2026-03-21

---

## Scheduler Update (2026-03-23)

- Preferred runner: `run_scheduled_getdaytrends.ps1`
- Preferred setup entrypoint: `setup_scheduled_task.ps1`
- Legacy `run_getdaytrends.bat` and `register_scheduler.bat` now delegate to the PowerShell flow
- Non-admin setup falls back to `GetDayTrends_CurrentUser` if the legacy `GetDayTrends` task cannot be replaced
- Validation command:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\getdaytrends\run_scheduled_getdaytrends.ps1 -DryRun -Limit 1 -Country korea
```

- Successful validation writes UTF-8 detail logs to `getdaytrends\logs\scheduler\`
- Live verification on 2026-03-23: `GetDayTrends_CurrentUser` completed with `LastTaskResult=0`
- Latest confirmed metrics: `generated=7 saved=7 errors=0` from `logs\scheduler\run_2026-03-23_171527.log`

---

## 1. 스케줄링 (3시간 주기)

### 1-1. Windows Task Scheduler

**Batch Wrapper** (`run_getdaytrends.bat`):

```batch
@echo off
chcp 65001 > nul
cd /d "d:\AI 프로젝트\getdaytrends"
echo [%date% %time%] GetDayTrends 실행 시작 >> run_scheduled.log
"d:\AI 프로젝트\.venv\Scripts\python.exe" main.py --one-shot 2>&1 >> run_scheduled.log
echo [%date% %time%] GetDayTrends 실행 완료 >> run_scheduled.log
```

**등록 명령** (PowerShell Admin):

```powershell
Start-Process -FilePath "schtasks.exe" `
    -ArgumentList '/create /tn "GetDayTrends" /tr "C:\Users\bioju\run_getdaytrends.bat" /sc HOURLY /mo 3 /st 08:00 /rl HIGHEST /f' `
    -Verb RunAs -Wait
```

### 1-2. 배터리 모드 패치

기본적으로 배터리 전원 시 실행되지 않으므로 XML 패치 필요:

```powershell
$taskName = "GetDayTrends"
$xml = [xml](schtasks /query /tn $taskName /xml)
$ns = @{t="http://schemas.microsoft.com/windows/2004/02/mit/task"}
($xml | Select-Xml -XPath "//t:DisallowStartIfOnBatteries" -Namespace $ns).Node.InnerText = "false"
($xml | Select-Xml -XPath "//t:StopIfGoingOnBatteries" -Namespace $ns).Node.InnerText = "false"
$tmp = "$env:TEMP\task_fix.xml"
$xml.Save($tmp)
schtasks /create /tn $taskName /xml $tmp /f
Remove-Item $tmp
```

### 1-3. 적응형 스케줄 조정

| 조건 | 스케줄 변경 | 근거 |
|------|------------|------|
| 핫 트렌드 감지 (90점+, 급상승) | 간격 ÷ 4 (최소 15분) | 실시간 이슈 포착 |
| 평균 75점+ | 간격 × 0.85 (최소 30분) | 양질 트렌드 빈도 높음 |
| 평균 55점 미만 | 간격 × 1.25 (최대 180분) | 저품질 시 리소스 절약 |
| 야간 (02~07시) | 슬립 모드 | 트렌드 유입 감소 |

### 1-4. 상태 확인

```powershell
# 작업 상태 확인
schtasks /query /tn "GetDayTrends" /v /fo LIST

# 로그 확인 (최근 20줄)
Get-Content "d:\AI 프로젝트\getdaytrends\run_scheduled.log" -Tail 20
```

---

## 2. 키워드 히스토리 및 중복 방지

### 2-1. Deduplication 메커니즘

```
                 ┌──────────────────────┐
새 키워드 ──────→│ Fingerprint 생성      │
                 │ (keyword + vol_bucket)│
                 └──────────┬───────────┘
                            │
                   ┌────────▼────────┐
                   │ SQLite DB 조회   │
                   │ dedupe_window=6h │
                   └────────┬────────┘
                            │
                  ┌─────────┴──────────┐
                  │                    │
              히스토리에 있음       없음 (새 키워드)
                  │                    │
              제외 (skip)          파이프라인 진행
```

### 2-2. 의미적 클러스터링

동일/유사 키워드 중복 방지를 위한 2단계 클러스터링:

1. **Gemini Embedding 2** (기본): 코사인 유사도 ≥ 0.75 → 같은 클러스터
2. **Jaccard 유사도** (폴백): 토큰화 후 유사도 ≥ 0.35 → 같은 클러스터

클러스터 내 **최고 볼륨 키워드만** 대표로 선정, 나머지는 메타데이터에 병합.

### 2-3. 히스토리 보존

| 설정 | 기본값 | 설명 |
|------|--------|------|
| `dedupe_window_hours` | 6 | 중복 체크 윈도우 |
| `data_retention_days` | 90 | DB 데이터 보존 기간 |
| `cache_volume_bucket` | 5000 | 핑거프린트 볼륨 버킷 |

---

## 3. 품질 미달 자동 폐기

### 3-1. 키워드 수준 폐기 기준

| 기준 | 조건 | 동작 |
|------|------|------|
| **Safety Flag** | `safety_flag=True` (재난/혐오/사망) | 즉시 폐기, 로그 기록 |
| **Publishability** | `publishable=False` (문장 조각, 오타) | 폐기, `publishability_reason` 기록 |
| **최소 바이럴** | `viral_potential < 60` | 컨텐츠 생성 건너뜀 |
| **저신뢰 소스** | `cross_source_confidence < 2` | `viral_potential × 0.65` 패널티 |
| **진부한 트렌드** | 5회 이상 반복 | `× 0.80` 추가 패널티 |
| **만료된 뉴스** | `content_age_hours > 24` | `× 0.70` 패널티 |

### 3-2. 콘텐츠 수준 폐기/재생성

| 콘텐츠 그룹 | QA 최소 점수 | 미달 시 동작 |
|-------------|-------------|-------------|
| X 단문 | 50 | corrected_tweets 적용 또는 1회 재생성 |
| Threads | 65 | 1회 재생성 |
| X 장문 | 70 | 1회 재생성 |
| 블로그 | 75 | 1회 재생성 |

**Circuit Breaker**: 재생성은 **1회만** 허용 (무한 루프 + 비용 폭주 방지).

---

## 4. 에러 발생 시 재시도/알림 정책

### 4-1. 재시도 정책

| 에러 유형 | 재시도 | 최대 횟수 | 백오프 |
|-----------|--------|-----------|--------|
| LLM API 타임아웃 | Yes | 3 | 지수 (1s, 2s, 4s) |
| 스크래핑 403/429 | Yes | 2 | 30s 대기 |
| DB 연결 실패 | Yes | 3 | 1s 고정 |
| Notion API 제한 | Yes | 2 | 세마포어 대기 |
| LLM 예산 초과 | No | - | Sonnet 비활성화 |
| Safety Flag 감지 | No | - | 즉시 스킵 |

### 4-2. 알림 정책

| 이벤트 | 채널 | 조건 |
|--------|------|------|
| 고바이럴 트렌드 (70점+) | Telegram + Discord | `alert_threshold` 이상 |
| 일일 예산 70% 도달 | Telegram | `cost_alert_pct` 도달 |
| 파이프라인 완전 실패 | Telegram + Discord | 모든 소스 수집 실패 |
| 소스 품질 저하 | 로그 기록 | 성공률 < 80% |

### 4-3. 장애 복구

```
파이프라인 실패
    │
    ├─ 단일 소스 실패 → 나머지 소스로 계속
    ├─ 모든 소스 실패 → 알림 + 다음 사이클 대기
    ├─ LLM 실패 → 캐시된 결과 사용 시도
    └─ DB 실패 → 파이프라인 중단 + 알림
```

---

## 5. 비용 관리

### 5-1. 일일 예산 상한

| 설정 | 기본값 | 설명 |
|------|--------|------|
| `daily_budget_usd` | $3.00 | 일일 LLM 비용 상한 |
| `peak_budget_multiplier` | 0.5 | 비피크(22~07시) 예산 보율 |
| `cost_alert_pct` | 70% | 예산 경고 임계값 |

### 5-2. 예산 초과 시 동작

```
누적 비용 >= daily_budget_usd
    ├─ enable_long_form = False (Sonnet 비활성화)
    ├─ thread_min_score = 999 (쓰레드 비활성화)
    └─ LIGHTWEIGHT(Gemini Flash) 전용 모드 전환
```

### 5-3. 티어 기반 LLM 라우팅

| 티어 | 모델 | 용도 | 비용 |
|------|------|------|------|
| LIGHTWEIGHT | Gemini 2.0 Flash | 스코어링, 단문, QA | ~$0/월 (무료 티어) |
| HEAVY | Claude Sonnet | 장문, 심층 분석 | ~$0.02/트렌드 |

### 5-4. 월간 비용 추정

| 시나리오 | 실행 횟수 | 트렌드/회 | 월 비용 |
|----------|-----------|-----------|---------|
| LIGHTWEIGHT only | 8회/일 | 5 | ~$0 |
| LIGHT + HEAVY (1개/회) | 8회/일 | 5 | ~$4.80 |
| 전체 활성화 | 8회/일 | 10 | ~$12 |

---

## 6. 모니터링

### 6-1. 로그 체계

| 로그 | 경로 | 내용 |
|------|------|------|
| 실행 히스토리 | `run_history.log` | 실행 시작/종료 타임스탬프 |
| 봇 로그 | `tweet_bot.log` | 상세 파이프라인 로그 |
| 구조화 메트릭 | JSON stdout | 파이프라인 완료 후 메트릭 |

### 6-2. 소스 품질 모니터링 (SQT)

```sql
-- 최근 24시간 소스별 성공률
SELECT source,
       COUNT(*) as total,
       SUM(success) as ok,
       ROUND(100.0 * SUM(success) / COUNT(*), 1) as rate,
       ROUND(AVG(latency_ms)) as avg_ms
FROM source_quality
WHERE recorded_at > datetime('now', '-24 hours')
GROUP BY source;
```

### 6-3. 상태 확인 명령

```bash
# 파이프라인 통계
python main.py --stats

# 대시보드 (localhost:8080)
python main.py --serve
```
