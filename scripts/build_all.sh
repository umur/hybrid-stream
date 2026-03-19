#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "→ Generating proto stubs..."
"$ROOT/scripts/generate_proto.sh"

echo "→ Installing hybridstream-common..."
cd "$ROOT/hybridstream-common" && pip install -e .

echo "→ Installing hea..."
cd "$ROOT/hea" && pip install -e .

echo "→ Installing aode..."
cd "$ROOT/aode" && pip install -e .

echo "→ Building flink-connector..."
cd "$ROOT/flink-connector" && mvn clean package -q

echo "✓ All components built."
