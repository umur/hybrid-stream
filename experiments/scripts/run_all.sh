#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== HybridStream Experiment Suite ==="
echo "Total runs: 270 (27 configs × 10 reps)"
echo "Estimated time: ~70 hours"

command -v docker  >/dev/null || { echo "ERROR: Docker not found"; exit 1; }
command -v tc      >/dev/null || { echo "ERROR: iproute2 not found"; exit 1; }
command -v python3 >/dev/null || { echo "ERROR: Python 3 not found"; exit 1; }

mkdir -p "$PROJECT_ROOT/results/figures" "$PROJECT_ROOT/results/tables"

cd "$PROJECT_ROOT"
python3 -m harness.runner --results-dir results/ --log-level INFO "$@"

echo ""
echo "=== Running analysis ==="
python3 -m analysis.run_analysis --results-dir results/ --output-dir results/
echo "=== Done. Figures: results/figures/ | Tables: results/tables/ ==="
