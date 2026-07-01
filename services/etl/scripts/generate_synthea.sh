#!/usr/bin/env bash
# Downloads the official Synthea release jar (if not already cached) and
# generates a synthetic patient population as FHIR R4 bundles.
#
# Usage:
#   ./scripts/generate_synthea.sh [population_size] [state]
#
# Requires a Java 17+ runtime on PATH (or set $JAVA_BIN).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYNTHEA_DIR="${SCRIPT_DIR}/../synthea"
JAR_PATH="${SYNTHEA_DIR}/synthea-with-dependencies.jar"
JAR_URL="https://github.com/synthetichealth/synthea/releases/download/master-branch-latest/synthea-with-dependencies.jar"

POPULATION="${1:-15}"
STATE="${2:-Massachusetts}"
JAVA_BIN="${JAVA_BIN:-java}"

mkdir -p "${SYNTHEA_DIR}/output"

if [ ! -f "${JAR_PATH}" ]; then
    echo "Downloading Synthea (${JAR_URL})..."
    curl -sL -o "${JAR_PATH}" "${JAR_URL}"
fi

echo "Generating ${POPULATION} synthetic patients for ${STATE} via Synthea..."
"${JAVA_BIN}" -jar "${JAR_PATH}" \
    -p "${POPULATION}" \
    --exporter.baseDirectory="${SYNTHEA_DIR}/output" \
    --exporter.fhir.export=true \
    --exporter.hospital.fhir.export=false \
    --exporter.practitioner.fhir.export=false \
    --exporter.csv.export=false \
    "${STATE}"

echo "Done. FHIR bundles written to ${SYNTHEA_DIR}/output/fhir"
