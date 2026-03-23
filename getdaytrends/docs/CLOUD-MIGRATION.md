# GetDayTrends 클라우드 이전 가이드

## 개요
로컬 Windows Task Scheduler(`schtasks`) → GitHub Actions 전환 절차.

## 현재 구성

| 환경 | 스케줄러 | 상태 |
|:---|:---|:---|
| GitHub Actions | `getdaytrends.yml` (cron 4h) | ✅ 활성 |
| GitHub Actions | `heartbeat-monitor.yml` (매일 10:00 KST) | ✅ 활성 |
| 로컬 Windows | `schtasks "GetDayTrends"` | ⚠️ 비활성화 대상 |

## 이전 절차

### Step 1: GitHub Secrets 등록 확인

Repository → Settings → Secrets and variables → Actions에서 다음 시크릿이 등록되어야 합니다:

```
ANTHROPIC_API_KEY
GOOGLE_API_KEY
OPENAI_API_KEY         # [NEW] 폴백 체인
XAI_API_KEY            # [NEW] Grok 폴백
NOTION_TOKEN
NOTION_DATABASE_ID
X_ACCESS_TOKEN         # [NEW] X 포스팅
X_CLIENT_ID            # [NEW]
X_CLIENT_SECRET        # [NEW]
TWITTER_BEARER_TOKEN
TELEGRAM_BOT_TOKEN     # 알림용
TELEGRAM_CHAT_ID       # 알림용
DISCORD_WEBHOOK_URL    # 알림용
```

### Step 2: Dry-Run 테스트

Actions 탭에서 `getdaytrends - Auto Tweet Generator` → `Run workflow`:
- `dry_run`: ✅ 체크
- `country`: korea
- `limit`: 3

성공 시 로그에 `[DRY-RUN]` 접두사와 함께 정상 파이프라인 실행 확인.

### Step 3: 로컬 스케줄러 비활성화

```powershell
# 비활성화 (삭제 아님 — 2주 모니터링 후 삭제)
schtasks /Change /TN "\GetDayTrends" /DISABLE
schtasks /Change /TN "\GetDayTrends_AutoStart" /DISABLE 2>$null

# 상태 확인
schtasks /Query /TN "\GetDayTrends" /FO LIST | Select-String "Status"
```

### Step 4: 2주 모니터링

Heartbeat Monitor(`heartbeat-monitor.yml`)가 매일 자동 실행되어:
- ✅ 24시간 내 성공 실행이 있으면 `healthy`
- ⚠️ 실행 기록이 없으면 `silent` → Discord/Telegram 알림
- 🔴 실패만 있으면 `failing` → 즉시 알림

### Step 5: 완전 삭제 (2주 후)

```powershell
schtasks /Delete /TN "\GetDayTrends" /F
schtasks /Delete /TN "\GetDayTrends_AutoStart" /F 2>$null
```

## 롤백

문제 발생 시 로컬 스케줄러 재활성화:
```powershell
schtasks /Change /TN "\GetDayTrends" /ENABLE
```
