FROM python:3.12-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

# Copy source code
COPY ../hybridstream-common/ /app/hybridstream-common/
COPY . /app/aode/

# Install Python dependencies
RUN pip install --no-cache-dir /app/hybridstream-common && \
    pip install --no-cache-dir /app/aode

# Copy generated proto stubs
COPY ../proto/ /app/proto/
RUN python -m grpc_tools.protoc \
    --proto_path=/app/proto \
    --python_out=/app/aode/aode \
    --grpc_python_out=/app/aode/aode \
    /app/proto/hybridstream.proto

EXPOSE 50055

ENTRYPOINT ["python", "-m", "aode.main"]