#!/usr/bin/env bash
# build_rust.sh — Build the Rust extension wheel with maturin.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

if ! command -v maturin &>/dev/null; then
  echo "ERROR: maturin not found in PATH. Activate the cQuanty conda environment first." >&2
  exit 1
fi

if [ ! -f rust/Cargo.toml ]; then
  echo "ERROR: rust/Cargo.toml not found. Initialize the Rust submodule first." >&2
  exit 1
fi

mkdir -p dist

maturin build \
  --manifest-path rust/Cargo.toml \
  --release \
  --out dist \
  "$@"

echo "✅ Rust wheel built. Install with:"
echo "   pip install --force-reinstall dist/cquant_py-*.whl"
