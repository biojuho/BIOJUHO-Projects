# 운영 Runbook

프로젝트 운영에 필요한 표준 절차를 정리합니다.

## 목차
1. [일상 점검](#일상-점검)
2. [장애 대응](#장애-대응)
3. [배포 절차](#배포-절차)
4. [데이터 백업](#데이터-백업)

---

## 일상 점검

### 헬스체크 실행
```bash
python scripts/healthcheck.py
python scripts/healthcheck.py --webhook $DISCORD_WEBHOOK_URL
```

### DORA 메트릭 확인
```bash
python scripts/dora_metrics.py --days 30
```

### 스모크 테스트
```bash
python scripts/run_workspace_smoke.py --scope workspace
```

---

## 장애 대응

### 1. 즉시 조치 (5분 이내)

1. 현상 파악 — 어떤 서비스가 영향받는지
2. 영향 범위 확인 — 사용자, 데이터, 비용
3. 핫픽스 or 롤백 결정

### 2. 서비스별 복구

#### GetDayTrends 파이프라인 중단
```bash
# 1. 프로세스 확인
tasklist | findstr python

# 2. 행 프로세스 종료
taskkill /F /PID <PID>

# 3. 재시작
cd getdaytrends
python main.py --one-shot --verbose --dry-run
```

#### DeSci Backend 응답 없음
```bash
# Docker 환경
docker compose -f docker-compose.dev.yml restart desci-backend

# 로컬 환경
cd desci-platform/biolinker
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. 사후 처리

1. `docs/postmortem-template.md` 복사하여 포스트모템 작성
2. 저장 위치: `docs/postmortems/YYYY-MM-DD-제목.md`
3. 팀 공유 후 Action Items ADR에 기록

---

## 배포 절차

### 사전 점검
```bash
# 1. 테스트 통과 확인
pytest -v --tb=short

# 2. 린트 확인
ruff check .
ruff format --check .

# 3. 보안 스캔
gitleaks detect --source .
```

### 커밋 & 푸시
```bash
git add .
git commit -m "[Project] 변경 내용 요약"
git push origin dev  # main이 아닌 dev 브랜치로
# PR 생성 후 CI 통과 확인 → 머지
```

---

## 데이터 백업

### SQLite 데이터베이스
```bash
# getdaytrends
copy getdaytrends\data\getdaytrends.db getdaytrends\data\backup_%date%.db
```

### 환경변수
```bash
# .env 파일들은 Git에 포함되지 않으므로 별도 백업 필요
# Google Drive 동기화 사용 중:
python scripts/sync_gdrive.py
```
