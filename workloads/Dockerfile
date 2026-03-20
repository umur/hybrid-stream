FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

# Build context is repo root
COPY hybridstream-common/ /app/hybridstream-common/
COPY hea/ /app/hea/
COPY workloads/ /app/workloads/

RUN pip install --no-cache-dir /app/hybridstream-common && \
    pip install --no-cache-dir /app/hea && \
    pip install --no-cache-dir /app/workloads

ENV PYTHONPATH="/app/hea:/app:/app/workloads"
WORKDIR /app/workloads

ENTRYPOINT ["python", "-m"]
