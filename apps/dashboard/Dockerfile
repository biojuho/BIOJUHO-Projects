FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements-dashboard.txt .
RUN pip install --no-cache-dir -r requirements-dashboard.txt

# Copy application
COPY apps/dashboard/ ./apps/dashboard/
COPY shared/ ./shared/
COPY packages/ ./packages/
COPY automation/ ./automation/
COPY workspace-map.json .

# Build frontend (already in dist/)
# If rebuilding: COPY apps/dashboard/dist/ ./apps/dashboard/dist/

EXPOSE 8080

ENV PYTHONUNBUFFERED=1
ENV DASHBOARD_ALLOWED_ORIGINS="*"

CMD ["python", "apps/dashboard/api.py", "--host", "0.0.0.0", "--port", "8080"]
