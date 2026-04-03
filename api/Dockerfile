# ============================================================================
# Swabrr API — Dockerfile
# ============================================================================
# Multi-stage build: Python 3.13, /opt/venv, tini, PUID/PGID
#
# FILE VERSION: v1.0.0
# LAST MODIFIED: 2026-04-01
# COMPONENT: swabrr-api
# ============================================================================

# --------------------------------------------------------------------------
# Stage 1: Builder — install dependencies into a virtual env
# --------------------------------------------------------------------------
FROM python:3.13-slim AS builder

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# --------------------------------------------------------------------------
# Stage 2: Runtime — slim image with venv copied in
# --------------------------------------------------------------------------
FROM python:3.13-slim AS runtime

ARG DEFAULT_UID=1000
ARG DEFAULT_GID=1000

# Install tini for PID 1 signal handling and zombie reaping
RUN apt-get update && \
    apt-get install -y --no-install-recommends tini && \
    rm -rf /var/lib/apt/lists/*

# Create application user
RUN groupadd -g ${DEFAULT_GID} appgroup && \
    useradd -m -u ${DEFAULT_UID} -g ${DEFAULT_GID} appuser

# Copy virtual env from builder
ENV PATH="/opt/venv/bin:$PATH"
COPY --from=builder /opt/venv /opt/venv

# Set working directory
WORKDIR /app

# Copy entrypoint and application code
COPY docker-entrypoint.py /app/docker-entrypoint.py
COPY src/ /app/src/

# NOTE: Do NOT use USER directive — entrypoint handles privilege dropping
ENTRYPOINT ["/usr/bin/tini", "--", "python", "/app/docker-entrypoint.py"]
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8484"]
