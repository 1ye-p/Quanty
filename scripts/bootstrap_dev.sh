#!/usr/bin/env bash
# bootstrap_dev.sh — Initialize the cQuanty conda environment and project scaffold.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

# ── 1. Conda environment ──────────────────────────────────────────────────────
if ! command -v conda &>/dev/null; then
  echo "ERROR: conda not found in PATH. Install Miniconda or Mambaforge first." >&2
  exit 1
fi

eval "$(conda shell.bash hook)"

if conda env list | awk '{print $1}' | grep -qx "cQuanty"; then
  echo "Updating existing cQuanty environment..."
  conda env update -n cQuanty -f environment.yml --prune
else
  echo "Creating cQuanty environment..."
  conda env create -f environment.yml
fi

conda activate cQuanty

# ── 2. Rust submodule ─────────────────────────────────────────────────────────
if grep -q "PLACEHOLDER" .gitmodules 2>/dev/null; then
  echo "Skipping Rust submodule: placeholder URL still configured."
  echo "  → Update .gitmodules with the real cquant-rust repo URL, then rerun."
else
  git submodule sync --recursive
  git submodule update --init --recursive rust
fi

# ── 3. Vibe-Trading submodule ─────────────────────────────────────────────────
if [ -d lib/vibe-trading/agent ] || [ -f lib/vibe-trading/.git ]; then
  echo "Vibe-Trading submodule found, updating..."
  git submodule update --remote lib/vibe-trading 2>/dev/null || true
else
  echo "Initializing Vibe-Trading submodule..."
  git submodule update --init lib/vibe-trading 2>/dev/null || \
    echo "  → Skipping: lib/vibe-trading submodule not configured."
fi
# Install Vibe-Trading minimal dependencies
conda run -n cQuanty pip install langgraph langchain-openai --quiet 2>/dev/null || true

# ── 4. Editable install ───────────────────────────────────────────────────────
if [ -f python/cquant/__init__.py ]; then
  python -m pip install --no-deps -e .
else
  echo "Skipping editable install: python/cquant/__init__.py not yet present."
fi

# ── 5. Rust wheel ─────────────────────────────────────────────────────────────
if [ -f rust/Cargo.toml ]; then
  bash scripts/build_rust.sh
else
  echo "Skipping Rust wheel build: rust/Cargo.toml not present."
fi

# ── 6. Pre-commit hooks ───────────────────────────────────────────────────────
if command -v pre-commit &>/dev/null && [ -f .pre-commit-config.yaml ]; then
  pre-commit install
fi

echo ""
echo "✅ Bootstrap complete. Activate the environment with:"
echo "   conda activate cQuanty"
