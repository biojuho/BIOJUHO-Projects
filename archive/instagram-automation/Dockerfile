FROM python:3.12-slim

WORKDIR /app

# System deps for Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo-dev \
    && rm -rf /var/lib/apt/lists/*

# Install shared module dependencies
COPY shared/ /app/shared/
COPY instagram-automation/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY instagram-automation/ .

# Create data dirs
RUN mkdir -p data/images

EXPOSE 8003

# Health check for Cloud Run
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import httpx; r=httpx.get('http://localhost:8003/'); assert r.status_code==200"

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
