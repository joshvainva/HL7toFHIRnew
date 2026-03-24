# ============================================================
# HL7 & EHR → FHIR Converter — Dockerfile
# Innova Solutions  |  2026 AI Hackathon  |  CS06
# ============================================================
# Multi-stage build: lean production image (~200 MB)
#
# Quick start:
#   docker build -t hl7-fhir-converter .
#   docker run -p 8000:8000 --env-file .env hl7-fhir-converter
# ============================================================

# ---------- Stage 1: dependency builder ----------
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# ---------- Stage 2: runtime image ----------
FROM python:3.12-slim

LABEL org.opencontainers.image.title="HL7 & EHR to FHIR Converter"
LABEL org.opencontainers.image.description="Convert HL7 v2.x and raw EHR records to FHIR R4. Rule-based + AI-powered (Claude Sonnet 4.6 / Groq Llama 3.3)."
LABEL org.opencontainers.image.version="2.0.0"
LABEL org.opencontainers.image.vendor="Innova Solutions"

# Runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 \
    libxslt1.1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Install Python packages from builder wheels
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/* && \
    rm -rf /wheels

# Copy application code (owned by non-root user)
COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8000

# Health check using curl (installed above)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# 2 workers for production; override with WORKERS env var
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WORKERS:-2}"]
