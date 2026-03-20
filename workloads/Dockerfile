FROM python:3.12-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

# Copy dependencies
COPY ../hybridstream-common/ /app/hybridstream-common/
COPY ../hea/ /app/hea/
COPY . /app/workloads/

# Install Python dependencies
RUN pip install --no-cache-dir /app/hybridstream-common && \
    pip install --no-cache-dir /app/hea && \
    pip install --no-cache-dir /app/workloads

# Set Python path and working directory
ENV PYTHONPATH="/app/hea:/app:/app/workloads"
WORKDIR /app/workloads

# Default command (can be overridden)
ENTRYPOINT ["python", "-m"]