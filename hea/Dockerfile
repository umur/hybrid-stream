FROM python:3.12-slim

WORKDIR /app

# System deps for RocksDB
RUN apt-get update && apt-get install -y --no-install-recommends \
    librocksdb-dev build-essential && \
    rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY hybridstream-common/ /app/hybridstream-common/
COPY hea/ /app/hea/
RUN pip install --no-cache-dir /app/hybridstream-common && \
    pip install --no-cache-dir /app/hea

# Copy generated proto stubs
COPY hea/hea/grpc/ /app/hea/hea/grpc/

# Data directory for RocksDB
RUN mkdir -p /data/rocksdb /data/checkpoints

EXPOSE 50051

ENTRYPOINT ["python", "-m", "hea.main"]
