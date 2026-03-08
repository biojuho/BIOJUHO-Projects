---
description: "배포 워크플로. 커밋→테스트→배포 자동화 파이프라인. '/deploy'로 실행"
---

// turbo-all

# 🚀 Deploy 워크플로우 (v3.0 - Continuous Delivery)

> 사용법: `/deploy` 또는 "배포", "커밋", "deploy" 키워드로 트리거
> 워크플로우 순서: STEP 1 → STEP 2 → STEP 3 → STEP 4 (선택)

---

## 프로젝트 자동 감지

변경된 파일 경로에서 프로젝트를 자동 감지한다:

| 경로 패턴 | 프로젝트 | 테스트 명령 |
|-----------|---------|------------|
| `getdaytrends/` | GetDayTrends | `pytest getdaytrends/tests/ -v --tb=short` |
| `desci-platform/biolinker/` | DeSci Backend | `pytest desci-platform/biolinker/tests/ -v` |
| `desci-platform/frontend/` | DeSci Frontend | `cd desci-platform/frontend && npm run build` |
| `desci-platform/contracts/` | DeSci Contracts | `cd desci-platform/contracts && npx hardhat test` |
| `AgriGuard/backend/` | AgriGuard Backend | `pytest AgriGuard/backend/tests/ -v` |
| `AgriGuard/frontend/` | AgriGuard Frontend | `cd AgriGuard/frontend && npm run build` |
| `DailyNews/` | DailyNews | `python DailyNews/server.py --help` |
| `canva-mcp/` | Canva MCP | `cd canva-mcp && npm run build` |
| `shared/` | Shared Modules | `pytest tests/ -v --tb=short` |
| `scripts/` | Scripts | `python scripts/healthcheck.py` |

---

## STEP 1 — 변경 사항 확인

```bash
git -C "d:\AI 프로젝트" status --short
```

```bash
git -C "d:\AI 프로젝트" diff --stat HEAD
```

변경된 파일 목록을 분석하여:
1. 영향받는 프로젝트를 식별한다
2. 변경 규모를 요약한다 (파일 수, 라인 추가/삭제)
3. `.env` 등 민감 파일이 staging에 포함되지 않았는지 확인한다

---

## STEP 2 — 테스트 및 사전 검증(Pre-commit) 실행

먼저 Git Pre-commit Hook을 수동으로 트리거하여 기초 품질을 확인한다:
```bash
pre-commit run --all-files
```

통과 시, 감지된 프로젝트의 테스트를 자동 실행한다.

### 실행 규칙
- 변경된 프로젝트의 테스트만 실행 (전체 실행 X)
- 테스트가 없는 프로젝트는 lint 또는 build 검증으로 대체
- 실패 시 사용자에게 알리고 STEP 3 진행 여부를 확인

### 출력 형식
```
## 🧪 테스트 결과
| 프로젝트 | 결과 | 상세 |
|---------|------|------|
| GetDayTrends | ✅ 89 passed, 6 failed | 기존 실패 (known issues) |
| Shared | ✅ All passed | - |
```

---

## STEP 3 — 커밋

### 커밋 메시지 생성 규칙

프로젝트 규칙에 따라 `[Project] 변경 내용 요약` 형식으로 자동 생성한다.

**단일 프로젝트 변경:**
```
[GetDayTrends] feat: 벨로시티 스코어링 추가
```

**다수 프로젝트 변경:**
```
[Workspace] refactor: healthcheck v2 + DORA metrics 업그레이드
```

### 실행 흐름
1. 커밋 메시지를 제안하고 사용자 확인을 받는다
2. `.env`, `credentials.json` 등이 staging에 없는지 최종 확인한다
3. 사용자 승인 후 커밋을 실행한다:

```bash
git -C "d:\AI 프로젝트" add -A
git -C "d:\AI 프로젝트" commit -m "[Project] 메시지"
```

> ⚠️ 사용자에게 커밋 여부를 확인한 후에만 실행한다.

---

## STEP 4 — 릴리즈/배포 (선택)

릴리즈 버전을 생성하고(tag) 배포 가능한 프로젝트에 대해 배포 명령을 제안한다.

배포 전 태그 생성을 제안한다:
```bash
git tag -a v1.0.X -m "Release v1.0.X"
git push origin v1.0.X
```

| 프로젝트 유형 | 배포 방식 | 명령 |
|-------------|---------|------|
| Python 자동화 | 로컬 데몬 재시작 | `python main.py --one-shot --dry-run` |
| React 프론트엔드 | 빌드 확인 | `npm run build` |
| Docker 프로젝트 | 컨테이너 재빌드 | `docker compose -f docker-compose.dev.yml up --build` |
| Git push | 원격 동기화 | `git push origin main` |

> 이 단계는 **사용자 명시적 요청 시에만** 실행한다. 기본값은 STEP 3 (커밋)까지.

---

## 📌 노드 구성 요약

| 노드명 | 역할 | 조건 |
|--------|------|------|
| STEP 1 확인 | 변경 분석 | 항상 |
| STEP 2 테스트 | 자동 테스트 | 코드 변경 시 |
| STEP 3 커밋 | 커밋 생성 | 사용자 승인 후 |
| STEP 4 배포 | 배포 실행 | 사용자 요청 시만 |
