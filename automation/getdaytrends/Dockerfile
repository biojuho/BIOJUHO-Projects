FROM python:3.13-slim AS builder

WORKDIR /build/getdaytrends

COPY . ./
RUN pip install --user --no-cache-dir .

FROM python:3.13-slim

LABEL maintainer="biojuho"
LABEL description="GetDayTrends automated trend analysis and content generation"

WORKDIR /app/getdaytrends

RUN apt-get update && \
    apt-get install -y --no-install-recommends libxml2 libxslt1.1 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.local /root/.local
COPY . ./

ENV PATH="/root/.local/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app:/app/getdaytrends"

RUN mkdir -p /app/getdaytrends/data

HEALTHCHECK --interval=5m --timeout=10s --retries=2 \
    CMD python main.py --health-check || exit 1

CMD ["python", "main.py", "--one-shot", "--verbose"]
