# ── Stage 1: Install dependencies ─────────────────────
FROM python:3.13-slim AS builder

WORKDIR /build

# shared 모듈도 설치에 필요
COPY requirements.txt ./
RUN pip install --user --no-cache-dir -r requirements.txt

# ── Stage 2: Runtime ──────────────────────────────────
FROM python:3.13-slim

LABEL maintainer="biojuho"
LABEL description="GetDayTrends — automated trend analysis & content generation"

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH="/root/.local/bin:$PATH"

# 필요한 시스템 패키지 (lxml 파싱용)
RUN apt-get update && \
    apt-get install -y --no-install-recommends libxml2 libxslt1.1 && \
    rm -rf /var/lib/apt/lists/*

# 먼저 shared 모듈 복사 (부모 디렉토리에서 마운트/복사됨)
# docker-compose에서 context를 workspace root로 설정해야 함
COPY shared/ /app/shared/
COPY getdaytrends/ /app/getdaytrends/

WORKDIR /app/getdaytrends

# 데이터 디렉토리
RUN mkdir -p /app/getdaytrends/data

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app"

# Healthcheck: main.py --health로 상태 확인
HEALTHCHECK --interval=5m --timeout=10s --retries=2 \
    CMD python -c "import sys; sys.exit(0)"

# 기본: one-shot 실행 (cron/scheduler에서 호출)
CMD ["python", "main.py", "--one-shot", "--verbose"]
