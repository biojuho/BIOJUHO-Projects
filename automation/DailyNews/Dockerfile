FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ src/
COPY scripts/ scripts/
COPY config/ config/
COPY pyproject.toml .

# Install the package in editable mode
RUN pip install --no-cache-dir -e .

# Create data/logs/output directories
RUN mkdir -p data logs output

# Expose port for MCP server (if using HTTP transport)
EXPOSE 8080

# Default command: run MCP server
CMD ["antigravity-mcp", "serve"]
