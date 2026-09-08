# ==============================================================================
# SYNTROPION OS — Production Docker Container
# Lightweight, hardened microkernel container for autonomous micro-SaaS studio
# ==============================================================================

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    SYNTROPION_DB_PATH=/app/data/syntropion.db \
    SHM_IPC_PATH=/dev/shm/syntropion_treasury_ipc

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY syntropion_core/ ./syntropion_core/
COPY web/ ./web/
COPY syntropion ./syntropion
RUN chmod +x ./syntropion && ln -sfn syntropion synapse

RUN mkdir -p /app/data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

ENTRYPOINT ["./syntropion"]
CMD ["run-server", "--host", "0.0.0.0", "--port", "8000"]
