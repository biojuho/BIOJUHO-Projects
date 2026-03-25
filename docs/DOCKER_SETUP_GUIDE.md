# Docker 통합 개발 환경 설정 가이드

**작성일**: 2026-03-25
**대상**: 신규 팀원, 개발자
**난이도**: 초급-중급

---

## 목차

1. [개요](#개요)
2. [사전 요구사항](#사전-요구사항)
3. [빠른 시작 (Quick Start)](#빠른-시작-quick-start)
4. [서비스 구성](#서비스-구성)
5. [프로필별 실행](#프로필별-실행)
6. [유용한 명령어](#유용한-명령어)
7. [트러블슈팅](#트러블슈팅)
8. [FAQ](#faq)

---

## 개요

이 가이드는 **AI Projects Workspace**의 모든 프로젝트를 Docker Compose로 한 번에 실행하는 방법을 설명합니다.

### 통합 환경의 장점

- ✅ **원클릭 환경 구축**: 모든 서비스를 한 명령어로 실행
- ✅ **의존성 자동 관리**: PostgreSQL, ChromaDB, MQTT 등 자동 설정
- ✅ **일관된 개발 환경**: "내 PC에서는 되는데" 문제 해결
- ✅ **Hot Reload**: 코드 변경 시 자동 반영 (Frontend/Backend)
- ✅ **네트워크 격리**: 모든 서비스가 독립 네트워크에서 통신

---

## 사전 요구사항

### 1. 시스템 요구사항

| 항목 | 최소 | 권장 |
|------|------|------|
| **OS** | Windows 10/11, macOS, Linux | - |
| **RAM** | 8GB | 16GB 이상 |
| **디스크 여유 공간** | 20GB | 50GB 이상 |
| **Docker Desktop** | 최신 버전 | - |

### 2. 소프트웨어 설치

#### Docker Desktop 설치

**Windows:**
```powershell
# Chocolatey 사용 시
choco install docker-desktop

# 또는 공식 사이트에서 다운로드
# https://www.docker.com/products/docker-desktop
```

**macOS:**
```bash
# Homebrew 사용 시
brew install --cask docker

# 또는 공식 사이트에서 다운로드
```

**설치 확인:**
```bash
docker --version
# Docker version 24.0.0 이상

docker compose version
# Docker Compose version v2.20.0 이상
```

#### WSL 2 (Windows 전용)

Windows에서는 WSL 2가 필요합니다:

```powershell
# 관리자 권한 PowerShell에서 실행
wsl --install
wsl --set-default-version 2

# WSL 서비스 재시작
Restart-Service -Name "com.docker.service"
```

> 자세한 내용: [docs/DOCKER_WSL_SERVICE_FIX.md](DOCKER_WSL_SERVICE_FIX.md)

### 3. 환경 변수 설정

루트 디렉토리의 `.env` 파일을 설정해야 합니다:

```bash
# 1. .env.example 복사
cp .env.example .env

# 2. .env 파일 편집 (필수 API 키 입력)
nano .env
# 또는
code .env
```

**필수 환경 변수:**
```env
# LLM API Keys
GEMINI_API_KEY=your_gemini_api_key
GOOGLE_API_KEY=your_google_api_key
OPENAI_API_KEY=your_openai_api_key (선택)
ANTHROPIC_API_KEY=your_anthropic_api_key (선택)

# PostgreSQL
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_postgres_password
POSTGRES_PORT=5432

# Firebase (DeSci Platform)
VITE_FIREBASE_API_KEY=your_firebase_api_key
VITE_FIREBASE_PROJECT_ID=your_firebase_project_id

# Blockchain (AgriGuard)
WEB3_PROVIDER_URI=https://sepolia.infura.io/v3/your_infura_key
AGRIGUARD_PRIVATE_KEY=your_private_key
```

> ⚠️ **주의**: `.env` 파일은 Git에 커밋하지 마세요! (.gitignore에 이미 포함됨)

---

## 빠른 시작 (Quick Start)

### 1. 전체 서비스 실행 (기본 프로필)

```bash
cd "d:\AI 프로젝트"  # 또는 워크스페이스 경로

# 모든 기본 서비스 시작 (PostgreSQL, ChromaDB, Mosquitto, DeSci, AgriGuard)
docker compose -f docker-compose.dev.yml up -d

# 로그 확인 (실시간)
docker compose -f docker-compose.dev.yml logs -f

# 상태 확인
docker compose -f docker-compose.dev.yml ps
```

**실행되는 서비스:**
- PostgreSQL (5432)
- ChromaDB (8001)
- Mosquitto MQTT (1883)
- DeSci BioLinker API (8000)
- DeSci Frontend (5173)
- AgriGuard Backend API (8002)
- AgriGuard Frontend (5174)

### 2. 특정 프로젝트만 실행

**DeSci Platform만:**
```bash
docker compose -f docker-compose.dev.yml up postgres chromadb biolinker desci-frontend -d
```

**AgriGuard만:**
```bash
docker compose -f docker-compose.dev.yml up postgres mosquitto agriguard-backend agriguard-frontend -d
```

### 3. 서비스 접속

모든 서비스가 시작되면 브라우저에서 접속:

| 서비스 | URL | 설명 |
|--------|-----|------|
| **DeSci Frontend** | http://localhost:5173 | Research Matching UI |
| **DeSci API Docs** | http://localhost:8000/docs | Swagger UI |
| **AgriGuard Frontend** | http://localhost:5174 | Supply Chain Tracking UI |
| **AgriGuard API Docs** | http://localhost:8002/docs | Swagger UI |
| **ChromaDB** | http://localhost:8001 | Vector DB Dashboard |
| **pgAdmin** | http://localhost:5050 | PostgreSQL UI (--profile tools) |

### 4. 서비스 중지

```bash
# 모든 서비스 중지 (컨테이너 유지)
docker compose -f docker-compose.dev.yml stop

# 모든 서비스 중지 및 제거
docker compose -f docker-compose.dev.yml down

# 볼륨까지 완전히 제거 (주의! 데이터 삭제됨)
docker compose -f docker-compose.dev.yml down -v
```

---

## 서비스 구성

### 1. 공유 인프라

#### PostgreSQL (포트: 5432)
- **용도**: 메인 데이터베이스 (DeSci, AgriGuard)
- **데이터베이스**: `biolinker`, `agriguard`, `getdaytrends`, `dailynews`
- **Health Check**: `pg_isready`
- **볼륨**: `dev-postgres-data`

#### ChromaDB (포트: 8001)
- **용도**: Vector Database (Research Paper Embeddings)
- **API**: http://localhost:8001
- **볼륨**: `dev-chroma-data`

#### Mosquitto MQTT (포트: 1883, 9001)
- **용도**: IoT 센서 메시지 브로커 (AgriGuard)
- **MQTT**: 1883 (TCP)
- **WebSocket**: 9001
- **볼륨**: `dev-mosquitto-data`

#### Redis (포트: 6379) - 선택적
- **용도**: Caching & Session Store
- **프로필**: `--profile full`
- **볼륨**: `dev-redis-data`

### 2. DeSci Platform

#### BioLinker API (포트: 8000)
- **Framework**: FastAPI
- **Features**:
  - Research Paper Upload & Analysis
  - RFP Matching (Vector Search)
  - Web3 Rewards (DeSciToken)
- **Health Endpoint**: `/health`
- **Dependencies**: PostgreSQL, ChromaDB, GROBID (선택)

#### DeSci Frontend (포트: 5173)
- **Framework**: React 19 + Vite 7
- **Hot Reload**: ✅ (`src/` 디렉토리)
- **Features**: Paper Management, RFP Dashboard, Wallet Integration

### 3. AgriGuard Platform

#### AgriGuard Backend API (포트: 8002)
- **Framework**: FastAPI
- **Features**:
  - Supply Chain Tracking
  - IoT Sensor Integration (MQTT)
  - Blockchain Verification (Sepolia)
- **Dependencies**: PostgreSQL, Mosquitto

#### AgriGuard Frontend (포트: 5174)
- **Framework**: React (SPA)
- **Hot Reload**: ✅

### 4. Content Intelligence (선택적)

#### GetDayTrends
- **용도**: 트렌드 분석 & 콘텐츠 생성
- **실행 방식**: One-shot 또는 Scheduler
- **프로필**: `--profile tools`

#### DailyNews
- **용도**: 뉴스 수집 & Insight 생성
- **프로필**: `--profile tools`

---

## 프로필별 실행

Docker Compose 프로필을 사용하여 필요한 서비스만 선택적으로 실행할 수 있습니다.

### 기본 프로필 (프로필 지정 없음)
```bash
docker compose -f docker-compose.dev.yml up -d
```
- PostgreSQL, ChromaDB, Mosquitto
- DeSci (biolinker, frontend)
- AgriGuard (backend, frontend)

### desci 프로필
```bash
docker compose -f docker-compose.dev.yml --profile desci up -d
```
- PostgreSQL, ChromaDB, GROBID
- DeSci Stack (biolinker, frontend)

### agriguard 프로필
```bash
docker compose -f docker-compose.dev.yml --profile agriguard up -d
```
- PostgreSQL, Mosquitto
- AgriGuard Stack (backend, frontend)

### tools 프로필
```bash
docker compose -f docker-compose.dev.yml --profile tools up -d
```
- GetDayTrends, DailyNews, pgAdmin

### monitoring 프로필
```bash
docker compose -f docker-compose.dev.yml --profile monitoring up -d
```
- Prometheus (9090)
- Grafana (3000)

### full 프로필 (모든 서비스)
```bash
docker compose -f docker-compose.dev.yml --profile full up -d
```
- 위 모든 서비스 + Redis, Qdrant

---

## 유용한 명령어

### 로그 확인

```bash
# 모든 서비스 로그 (실시간)
docker compose -f docker-compose.dev.yml logs -f

# 특정 서비스만
docker compose -f docker-compose.dev.yml logs -f biolinker

# 마지막 100줄만
docker compose -f docker-compose.dev.yml logs --tail=100 biolinker

# 타임스탬프 포함
docker compose -f docker-compose.dev.yml logs -f -t biolinker
```

### 컨테이너 상태 확인

```bash
# 간단한 상태
docker compose -f docker-compose.dev.yml ps

# 상세 정보 (CPU, Memory 사용량)
docker stats

# 특정 컨테이너 상태
docker inspect dev-biolinker
```

### 컨테이너 내부 접속

```bash
# Biolinker 컨테이너에 bash로 접속
docker exec -it dev-biolinker bash

# PostgreSQL 컨테이너에 psql 접속
docker exec -it dev-postgres psql -U postgres -d biolinker

# Redis CLI 접속 (full 프로필일 때)
docker exec -it dev-redis redis-cli
```

### 데이터베이스 작업

```bash
# PostgreSQL 백업
docker exec dev-postgres pg_dump -U postgres biolinker > backup_biolinker.sql

# PostgreSQL 복원
cat backup_biolinker.sql | docker exec -i dev-postgres psql -U postgres -d biolinker

# Alembic 마이그레이션 (AgriGuard 예시)
docker exec dev-agriguard-backend alembic upgrade head
```

### 서비스 재시작

```bash
# 특정 서비스만 재시작
docker compose -f docker-compose.dev.yml restart biolinker

# 빌드 캐시 무시하고 재시작
docker compose -f docker-compose.dev.yml up --build -d biolinker

# 코드 변경 후 즉시 반영 (rebuild)
docker compose -f docker-compose.dev.yml up --build --force-recreate -d biolinker
```

### 볼륨 관리

```bash
# 볼륨 목록 확인
docker volume ls | grep dev-

# 특정 볼륨 상세 정보
docker volume inspect dev-postgres-data

# 사용하지 않는 볼륨 정리 (주의!)
docker volume prune
```

### 이미지 관리

```bash
# 로컬 이미지 목록
docker images | grep dev-

# 사용하지 않는 이미지 제거
docker image prune -a

# 특정 이미지 삭제
docker rmi dev-biolinker
```

### 리소스 정리

```bash
# 중지된 컨테이너, 사용하지 않는 이미지, 네트워크, 빌드 캐시 제거
docker system prune

# 볼륨까지 모두 제거 (주의!)
docker system prune -a --volumes
```

---

## 트러블슈팅

### 1. Docker Desktop이 시작되지 않음 (Windows)

**증상:**
```
Error: Cannot start Docker Desktop
Wsl/0x80070422
```

**해결 방법:**
```powershell
# 관리자 PowerShell에서 실행
# 1. WSL 서비스 활성화
Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux

# 2. 필수 서비스 시작
Start-Service -Name "WslService"
Start-Service -Name "vmcompute"
Restart-Service -Name "com.docker.service"

# 3. Docker Desktop 재시작
```

> 자세한 내용: [docs/DOCKER_WSL_SERVICE_FIX.md](DOCKER_WSL_SERVICE_FIX.md)

### 2. 포트 충돌 에러

**증상:**
```
Error: Bind for 0.0.0.0:5432 failed: port is already allocated
```

**해결 방법:**

**Option A: 실행 중인 프로세스 종료**
```powershell
# Windows
netstat -ano | findstr :5432
taskkill /PID <PID> /F

# macOS/Linux
lsof -i :5432
kill -9 <PID>
```

**Option B: .env에서 포트 변경**
```env
# .env 파일에서 포트 변경
POSTGRES_PORT=5433
```

### 3. 볼륨 권한 문제 (Linux/macOS)

**증상:**
```
Error: permission denied while trying to connect to the Docker daemon socket
```

**해결 방법:**
```bash
# 현재 사용자를 docker 그룹에 추가
sudo usermod -aG docker $USER

# 로그아웃 후 재로그인 또는
newgrp docker

# 권한 확인
docker ps
```

### 4. Health Check 실패

**증상:**
```
biolinker is unhealthy
```

**확인 방법:**
```bash
# 컨테이너 로그 확인
docker compose -f docker-compose.dev.yml logs biolinker

# Health check 상태 확인
docker inspect dev-biolinker | grep -A 10 Health

# 수동으로 health endpoint 호출
curl http://localhost:8000/health
```

**일반적인 원인:**
- 환경 변수 누락 (`.env` 확인)
- 의존 서비스 미실행 (PostgreSQL, ChromaDB)
- 방화벽 차단

### 5. 빌드 실패

**증상:**
```
Error: failed to solve: process "/bin/sh -c pip install -r requirements.txt" did not complete successfully
```

**해결 방법:**

**Option A: 캐시 무시하고 재빌드**
```bash
docker compose -f docker-compose.dev.yml build --no-cache biolinker
docker compose -f docker-compose.dev.yml up -d biolinker
```

**Option B: BuildKit 사용**
```bash
# .env 파일에 추가
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# 또는 명령어 앞에 추가
DOCKER_BUILDKIT=1 docker compose -f docker-compose.dev.yml build
```

### 6. 메모리 부족

**증상:**
```
Error: OOMKilled
```

**해결 방법:**

**Docker Desktop 설정 변경:**
1. Docker Desktop → Settings → Resources
2. Memory: 8GB 이상으로 증가
3. Swap: 2GB 이상
4. Apply & Restart

**불필요한 서비스 중지:**
```bash
# 필요한 서비스만 실행
docker compose -f docker-compose.dev.yml up postgres biolinker -d
```

### 7. 네트워크 연결 실패

**증상:**
```
Error: could not connect to server: Connection refused
```

**해결 방법:**

**네트워크 재생성:**
```bash
# 모든 서비스 중지
docker compose -f docker-compose.dev.yml down

# 네트워크 삭제
docker network rm ai-projects-dev-network

# 재시작
docker compose -f docker-compose.dev.yml up -d
```

### 8. Hot Reload 작동 안 함

**증상:**
- 코드 변경이 반영되지 않음

**해결 방법:**

**볼륨 마운트 확인:**
```bash
# docker-compose.dev.yml에서 볼륨 설정 확인
# volumes:
#   - ./desci-platform/frontend/src:/app/src:cached

# 컨테이너 재시작
docker compose -f docker-compose.dev.yml restart desci-frontend
```

**Windows 파일 시스템 성능:**
```bash
# WSL 2 내부로 프로젝트 이동 (성능 향상)
# \\wsl$\Ubuntu\home\username\projects\
```

---

## FAQ

### Q1. 모든 서비스를 한 번에 실행해야 하나요?

A1. 아니요. 필요한 서비스만 선택하여 실행할 수 있습니다:

```bash
# DeSci만 개발할 경우
docker compose -f docker-compose.dev.yml up postgres chromadb biolinker desci-frontend -d

# AgriGuard만 개발할 경우
docker compose -f docker-compose.dev.yml up postgres mosquitto agriguard-backend -d
```

### Q2. 프로덕션 환경에도 이 파일을 사용하나요?

A2. 아니요. `docker-compose.dev.yml`은 개발 환경 전용입니다. 프로덕션에는 루트의 `docker-compose.yml`을 사용하세요.

```bash
# Production
docker compose -f docker-compose.yml up -d
```

### Q3. 데이터베이스 데이터는 어디에 저장되나요?

A3. Docker 볼륨에 저장됩니다:

```bash
# 볼륨 위치 확인
docker volume inspect dev-postgres-data

# 백업 (권장)
docker exec dev-postgres pg_dumpall -U postgres > backup_all.sql
```

### Q4. API 키를 변경했는데 반영이 안 됩니다

A4. 컨테이너 재시작이 필요합니다:

```bash
# 1. .env 파일 수정
# 2. 컨테이너 재시작 (환경 변수 다시 로드)
docker compose -f docker-compose.dev.yml up --force-recreate -d biolinker
```

### Q5. 로컬 Python/Node 개발 환경과 충돌하나요?

A5. 충돌하지 않습니다. Docker는 격리된 환경에서 실행됩니다. 다만 포트 충돌은 발생할 수 있으니 `.env`에서 포트를 변경하세요.

### Q6. 초기 데이터는 어떻게 로드하나요?

A6. 각 프로젝트의 마이그레이션 및 시드 스크립트를 사용하세요:

```bash
# DeSci Biolinker 초기 데이터
docker exec dev-biolinker python scripts/seed_data.py

# AgriGuard Alembic 마이그레이션
docker exec dev-agriguard-backend alembic upgrade head
```

### Q7. 개발 중 코드 변경이 즉시 반영되나요?

A7. 네, Hot Reload가 활성화되어 있습니다:

- **Frontend**: Vite Hot Module Replacement (즉시)
- **Backend**: Uvicorn auto-reload (파일 저장 시)

단, 의존성 변경(`requirements.txt`, `package.json`)은 재빌드가 필요합니다:

```bash
docker compose -f docker-compose.dev.yml up --build -d biolinker
```

### Q8. 서비스 간 통신은 어떻게 하나요?

A8. Docker Compose 네트워크를 통해 서비스 이름으로 통신합니다:

```python
# biolinker에서 postgres에 연결
DATABASE_URL = "postgresql://postgres:password@postgres:5432/biolinker"
#                                            ^^^^^^^^
#                                            컨테이너 이름
```

### Q9. 프로필을 여러 개 동시에 사용할 수 있나요?

A9. 네, 가능합니다:

```bash
docker compose -f docker-compose.dev.yml --profile tools --profile monitoring up -d
```

### Q10. 윈도우 성능이 느린데 개선 방법이 있나요?

A10. WSL 2 + 파일 시스템 최적화를 권장합니다:

```powershell
# 1. WSL 2 내부로 프로젝트 이동
# \\wsl$\Ubuntu\home\username\projects\

# 2. Docker Desktop 설정
# Settings → General → "Use the WSL 2 based engine" 체크

# 3. 리소스 증가
# Settings → Resources → Memory: 8GB, Swap: 2GB
```

---

## 다음 단계

### 1. 신규 팀원 온보딩

- [ ] Docker Desktop 설치 및 WSL 2 설정
- [ ] 워크스페이스 클론 및 `.env` 파일 설정
- [ ] `docker compose -f docker-compose.dev.yml up -d` 실행
- [ ] http://localhost:5173, http://localhost:8000/docs 접속 확인

### 2. 개발 워크플로우

1. 특정 프로젝트 서비스 시작
2. 코드 변경 (Hot Reload 자동 반영)
3. 로그 모니터링: `docker compose logs -f`
4. 테스트: `docker exec <container> pytest`
5. 커밋 및 푸시

### 3. 추가 학습 자료

- [SYSTEM_ENHANCEMENT_PLAN.md](../SYSTEM_ENHANCEMENT_PLAN.md) - 시스템 고도화 계획
- [POSTGRESQL_MIGRATION_PLAN.md](POSTGRESQL_MIGRATION_PLAN.md) - AgriGuard DB 마이그레이션
- [CLAUDE.md](../CLAUDE.md) - 프로젝트 전체 아키텍처

---

**문서 작성**: Backend Team
**마지막 업데이트**: 2026-03-25
**다음 리뷰**: 2026-04-15
