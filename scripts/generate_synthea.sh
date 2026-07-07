#!/usr/bin/env bash
# Generate synthetic patients with Synthea (https://github.com/synthetichealth/synthea)
# Output: CSV files in data/synthea/  (zero real data, zero RGPD)
#
# Requirements: Java 11+ (Synthea is a Java tool). Check with: java -version
# Usage: bash scripts/generate_synthea.sh [POPULATION] [SEED]
set -euo pipefail

POP="${1:-100}"     # number of living patients
SEED="${2:-42}"     # deterministic seed -> reproducible cohort
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/data/synthea"
JAR="$ROOT/data/synthea-with-dependencies.jar"
JAR_URL="https://github.com/synthetichealth/synthea/releases/download/master-branch-latest/synthea-with-dependencies.jar"

mkdir -p "$OUT"

if [ ! -f "$JAR" ]; then
  echo "[synthea] downloading the runnable jar..."
  curl -L -o "$JAR" "$JAR_URL"
fi

echo "[synthea] generating $POP patients (seed=$SEED) -> $OUT"
java -jar "$JAR" \
  -p "$POP" -s "$SEED" \
  --exporter.csv.export true \
  --exporter.fhir.export false \
  --exporter.baseDirectory "$OUT" \
  Massachusetts

echo "[synthea] done. CSVs are in $OUT/csv/"
echo "Next: uv run python -m synthea_omop_fhir.load_bronze"
