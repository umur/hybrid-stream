#!/usr/bin/env bash
set -euo pipefail

PROTO_DIR="$(cd "$(dirname "$0")/.." && pwd)/proto"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "→ Generating Python stubs..."

# HEA stubs
python -m grpc_tools.protoc \
  -I "$PROTO_DIR" \
  --python_out="$ROOT/hea/hea/grpc" \
  --grpc_python_out="$ROOT/hea/hea/grpc" \
  "$PROTO_DIR/hybridstream.proto"

# AODE stubs (same proto, different output dir)
python -m grpc_tools.protoc \
  -I "$PROTO_DIR" \
  --python_out="$ROOT/aode/aode/grpc" \
  --grpc_python_out="$ROOT/aode/aode/grpc" \
  "$PROTO_DIR/hybridstream.proto"

# Common package stubs (for shared deserialization helpers)
python -m grpc_tools.protoc \
  -I "$PROTO_DIR" \
  --python_out="$ROOT/hybridstream-common/hybridstream/common/proto" \
  --grpc_python_out="$ROOT/hybridstream-common/hybridstream/common/proto" \
  "$PROTO_DIR/hybridstream.proto"

echo "→ Generating Java stubs..."
protoc \
  -I "$PROTO_DIR" \
  --java_out="$ROOT/flink-connector/src/main/java" \
  --grpc-java_out="$ROOT/flink-connector/src/main/java" \
  "$PROTO_DIR/hybridstream.proto"

echo "✓ Proto generation complete."
