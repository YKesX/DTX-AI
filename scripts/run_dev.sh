#!/usr/bin/env bash
# scripts/run_dev.sh — start all local services in background processes
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

activate_venv() {
  if [ -f "$REPO_ROOT/.venv/bin/activate" ]; then
    # shellcheck source=/dev/null
    source "$REPO_ROOT/.venv/bin/activate"
  fi
}

echo "=== Starting DTX-AI dev environment ==="

activate_venv

# ---- API ----
echo "[1/2] Starting FastAPI backend on :8000…"
(
  cd "$REPO_ROOT/apps/api" && \
  PYTHONPATH="$REPO_ROOT/packages:$REPO_ROOT/services:$REPO_ROOT/services/ai${PYTHONPATH:+:$PYTHONPATH}" \
  uvicorn main:app --reload --port 8000
) &
API_PID=$!
echo "      API PID: $API_PID"

# ---- Dashboard ----
echo "[2/2] Starting Vite dashboard on :5173…"
(cd "$REPO_ROOT/apps/dashboard" && npm run dev) &
DASH_PID=$!
echo "      Dashboard PID: $DASH_PID"

echo ""
echo "✅  Services started."
echo "   API:       http://localhost:8000/docs"
echo "   Dashboard: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop all services."

# Wait for Ctrl+C
trap "kill $API_PID $DASH_PID 2>/dev/null; echo 'Stopped.'" INT TERM
wait
