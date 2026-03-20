FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

# Build context is repo root
COPY hybridstream-common/ /app/hybridstream-common/
COPY aode/ /app/aode/

# Install packages (with compatible gRPC versions from pyproject.toml)
RUN pip install --no-cache-dir /app/hybridstream-common && \
    pip install --no-cache-dir /app/aode

WORKDIR /app/aode

# Use pure Python protobuf implementation for compatibility with generated stubs
ENV PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

EXPOSE 50055

ENTRYPOINT ["python", "-m", "aode.main"]