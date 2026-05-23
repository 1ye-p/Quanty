# syntax=docker/dockerfile:1.6
FROM python:3.12-slim

LABEL maintainer="cQuant Team"
LABEL description="cQuant quantitative research API server"

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency declaration first for layer caching
COPY pyproject.toml ./
COPY python/ ./python/
COPY sql/ ./sql/
COPY configs/ ./configs/
COPY schemas/ ./schemas/

# Install the package and its dependencies
RUN pip install --no-cache-dir -e . \
    && pip install --no-cache-dir "uvicorn[standard]"

# Create data directory
RUN mkdir -p /app/data

# Expose API port
EXPOSE 8000

# Non-root user for security
RUN useradd -m -u 1000 cquant && chown -R cquant:cquant /app
USER cquant

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "cquant.api_server.app:app", "--host", "0.0.0.0", "--port", "8000"]
