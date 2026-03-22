# Docker Compose Multi-Service Setup

**Labels**: `devops`, `infrastructure`, `docker`
**Priority**: 📊 **Medium** - 1개월 내

---

## Description

전체 워크스페이스를 `docker compose up`으로 실행 가능하도록 통합 설정을 만듭니다.

---

## Services

- `biolinker` (FastAPI, port 8000)
- `agriguard-backend` (FastAPI, port 8002)
- `desci-frontend` (React + Vite, port 5173)
- `postgres` (AgriGuard DB, port 5432)
- `qdrant` (Vector DB, port 6333) - POC 후
- `redis` (캐싱, port 6379) - 향후

---

## Tasks

- [ ] 루트에 `docker-compose.yml` 생성
- [ ] 각 서비스별 `Dockerfile` 생성
- [ ] 환경 변수 통합 (`.env.docker`)
- [ ] 네트워크 설정 (서비스 간 통신)
- [ ] 볼륨 설정 (데이터 영속성)
- [ ] Health check 추가
- [ ] 로컬 테스트 (전체 스택 시작)
- [ ] README 업데이트 (Quick Start)

---

## Example `docker-compose.yml`

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: agriguard
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: agriguard
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "agriguard"]
      interval: 5s

  biolinker:
    build: ./desci-platform/biolinker
    ports:
      - "8000:8000"
    environment:
      GEMINI_API_KEY: ${GEMINI_API_KEY}
    depends_on:
      postgres:
        condition: service_healthy

  agriguard:
    build: ./AgriGuard/backend
    ports:
      - "8002:8002"
    environment:
      DATABASE_URL: postgresql://agriguard:${DB_PASSWORD}@postgres:5432/agriguard
    depends_on:
      postgres:
        condition: service_healthy

  frontend:
    build: ./desci-platform/frontend
    ports:
      - "5173:5173"
    environment:
      VITE_API_URL: http://localhost:8000

volumes:
  postgres-data:
```

---

## Acceptance Criteria

- ✅ `docker compose up`으로 전체 스택 시작 가능
- ✅ 모든 서비스 health check 통과
- ✅ 로컬 개발 환경 < 5분 셋업
- ✅ 팀원 3명 이상이 테스트 완료

---

**Estimated Time**: 3-4일
