#!/usr/bin/env bash
# seed_sample_data.sh — Seed minimal fixture market data for tests.
# Usage: bash scripts/seed_sample_data.sh [--force]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

FIXTURES_DIR="python/tests/fixtures/market"
FORCE="${1:-}"

if [ -d "${FIXTURES_DIR}" ] && [ -z "${FORCE}" ]; then
  echo "Fixtures already exist at ${FIXTURES_DIR}. Pass --force to regenerate."
  exit 0
fi

mkdir -p "${FIXTURES_DIR}"

echo "Fixture seeding is a placeholder — implement via python/cquant/datahub CLI."
echo "  python -m cquant.cli seed-fixtures --output ${FIXTURES_DIR}"
