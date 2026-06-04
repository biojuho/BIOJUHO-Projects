# 운영 Runbook

프로젝트 운영에 필요한 표준 절차를 정리합니다.

## 목차
1. [일상 점검](#일상-점검)
2. [장애 대응](#장애-대응)
3. [배포 절차](#배포-절차)
4. [데이터 백업](#데이터-백업)
5. [관찰성 게이트 (Observability)](#관찰성-게이트-observability)

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
# Docker 환경 (compose 서비스명은 'biolinker')
cd apps/desci-platform
docker compose restart biolinker

# 로컬 환경
cd apps/desci-platform/biolinker
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

---

## 관찰성 게이트 (Observability)

LiteLLM 프록시 + 셀프호스트 Langfuse 게이트(Phase 1–3)의 운영·검증 절차.
**100% opt-in** — 아래 env가 모두 미설정이면 모든 경로가 무비용 no-op이며 기존 동작과 100% 동일하다.

### 1. 오프라인 계약 검증 (인프라 불필요, CI/로컬용)

Docker/Langfuse를 띄우지 않고 정적 계약(프록시 config·compose 프로파일·env 키·tracing no-op)을 검증한다.

```bash
python ops/scripts/verify_observability.py
# 증거 JSON으로 남기려면:
python ops/scripts/verify_observability.py --json-out var/observability-verify-$(date +%F).json
```

- 6/6 통과 + exit 0 이어야 한다.
- 검사 항목: `ops/litellm/config.yaml` 모델 라우트·tier 별칭·langfuse 콜백, `docker-compose.dev.yml`의
  `observability` 프로파일 4개 서비스, `.env.example` opt-in 키, `shared.llm.tracing` no-op,
  `shared.llm.proxy_adapter` 표면, `healthcheck.py` 관찰성 프로브 정의.
- 회귀 테스트: `pytest tests/test_verify_observability.py -q`.

### 2. 라이브 운영 스모크 (실제 트레이스 확인)

실제로 스택을 띄우고 한 번의 LLM 호출이 Langfuse 트레이스로 도달하는지 확인한다(인프라 필요).

```bash
# 1) env 설정 (.env)  — 프록시 경로를 쓰려면 LITELLM_*, 네이티브 SDK 트레이스를 쓰려면 LANGFUSE_* 3종
#    LANGFUSE_HOST / LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY (+ 선택: LITELLM_PROXY_URL, LITELLM_MASTER_KEY)

# 2) 관찰성 스택 기동 (ClickHouse + Langfuse web/worker + LiteLLM proxy)
docker compose -f docker-compose.dev.yml --profile observability up -d

# 3) 헬스 확인 — 관찰성 엔드포인트 프로브 (env 미설정 시 자동 skip)
python ops/scripts/healthcheck.py

# 4) LLM 호출을 한 번 트리거 (예: getdaytrends one-shot dry-run 또는 임의 shared.llm 호출)
#    이후 Langfuse UI(LANGFUSE_HOST)에서 generation 트레이스 1건 도달 확인
```

트레이스 경로 요약:

| 설정된 env | 동작 |
| --- | --- |
| (없음) | 네이티브 체인만. 프록시·트레이스 없음. Phase 1 이전과 동일. |
| `LITELLM_PROXY_URL` | LiteLLM 프록시 경유, LiteLLM이 Langfuse 콜백 emit. 실패 시 네이티브 폴백. |
| `LANGFUSE_*` 3종 | 네이티브 체인이 SDK span 직접 emit. 프록시 없음. |
| 네 개 모두 | 프록시 경로 emit + 네이티브 폴백 경로 emit (프록시 short-circuit으로 이중 트레이스 없음). |

실패 시맨틱: Langfuse SDK 예외·import 실패·백엔드 장애는 `log.warning`으로 흡수되며 LLM 호출은 정상 진행된다(트레이싱이 운영 호출을 깨뜨릴 수 없음).

### 3. 롤백

1. **운영 롤백(가장 빠름)** — 실행 환경에서 `LITELLM_PROXY_URL` + `LANGFUSE_*` 키 unset. 즉시 전 단계 no-op 복귀, 코드 변경 없음.
2. **코드 롤백** — 관찰성 커밋 4개 revert 시 Phase 1 이전 베이스라인으로 복귀. 의존성·DB·API 계약 변경 없음.
