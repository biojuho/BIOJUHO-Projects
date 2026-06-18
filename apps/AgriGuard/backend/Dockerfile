FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for web3 and other compiled packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libffi-dev && \
    rm -rf /var/lib/apt/lists/*

COPY . .

# Install from pyproject.toml (the dependency source of truth). The old
# Dockerfile referenced a requirements.txt that no longer exists after the
# migration to pyproject, which broke `docker build`.
RUN pip install --no-cache-dir .

# Run as a non-root user (container-escape hardening); appuser owns /app.
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8002

CMD ["sh", "-c", "python scripts/run_migrations.py && uvicorn main:app --host 0.0.0.0 --port 8002"]
