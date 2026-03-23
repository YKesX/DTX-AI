#!/usr/bin/env bash
# scripts/setup.sh — one-time developer environment setup
set -euo pipefail

echo "=== DTX-AI Setup ==="

# ---- Python virtual environment ----
if [ ! -d ".venv" ]; then
  echo "[1/4] Creating Python virtual environment (.venv)…"
  python3 -m venv .venv
fi

source .venv/bin/activate

echo "[2/4] Installing shared package…"
pip install -q -e packages/shared

echo "[3/4] Installing API dependencies…"
pip install -q -r apps/api/requirements.txt

echo "[4/4] Installing AI service dependencies…"
pip install -q -r services/ai/requirements.txt

# ---- Node / frontend ----
echo "[5/5] Installing dashboard npm dependencies…"
(cd apps/dashboard && npm install --silent)

# ---- Copy example .env files if not present ----
for env_example in apps/api/.env.example apps/sim/.env.example apps/dashboard/.env.example; do
  target="${env_example%.example}"
  if [ ! -f "$target" ]; then
    cp "$env_example" "$target"
    echo "Copied $env_example → $target"
  fi
done

echo ""
echo "✅  Setup complete."
echo "   Activate the venv: source .venv/bin/activate"
echo "   Then start services: bash scripts/run_dev.sh"
