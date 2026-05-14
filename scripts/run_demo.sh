#!/usr/bin/env bash
# scripts/run_demo.sh — boot API + dashboard and replay the dataset against them.
#
# The legacy hand-crafted "synthetic" scenario seeder was removed when the
# dataset switched to the Isaac-Sim 19-channel telemetry schema. Use the
# replay path (which streams real rows from the held-out chronological tail
# of services/ai/dtx_ai_master_dataset.csv) or wire your own Isaac Sim
# adapter directly to POST /events/.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_URL="http://localhost:8000"
DASHBOARD_URL="http://localhost:5173"
SPLIT="holdout"
COUNT="100"
DELAY="0.5"
MODEL=""
DO_SETUP=0
DO_SEED=1
STRICT_REPLAY=0

usage() {
  cat <<'EOF'
Usage: bash scripts/run_demo.sh [options]
  --setup                 Run scripts/setup.sh first
  --split <name>          holdout|all (default: holdout — rows no model has seen)
  --count <n>             Number of rows to replay (default: 100)
  --delay <seconds>       Delay between events (default: 0.5)
  --model <model_key>     Override active model (lightgbm|random_forest|xgboost|lstm_ae)
  --strict-replay         Enable strict model validation in replay mode
  --no-seed               Start API + dashboard only, skip replay
  -h, --help              Show help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --setup) DO_SETUP=1; shift ;;
    --split) SPLIT="${2:-}"; shift 2 ;;
    --count) COUNT="${2:-}"; shift 2 ;;
    --delay) DELAY="${2:-}"; shift 2 ;;
    --model) MODEL="${2:-}"; shift 2 ;;
    --strict-replay) STRICT_REPLAY=1; shift ;;
    --no-seed) DO_SEED=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1"; usage; exit 1 ;;
  esac
done

if [[ "$SPLIT" != "holdout" && "$SPLIT" != "all" ]]; then
  echo "Invalid --split value: $SPLIT (use holdout|all)" >&2
  exit 1
fi

pkill -f "uvicorn main:app" 2>/dev/null || true
pkill -f "npm run dev" 2>/dev/null || true
lsof -ti :8000 | xargs kill -9 2>/dev/null || true
lsof -ti :5173 | xargs kill -9 2>/dev/null || true
lsof -ti :5174 | xargs kill -9 2>/dev/null || true

for required in \
  "$REPO_ROOT/scripts/run_dev.sh" \
  "$REPO_ROOT/scripts/replay_dataset_demo.py" \
  "$REPO_ROOT/services/ai/ai/models/shared/model_registry.json"
do
  if [[ ! -f "$required" ]]; then
    echo "Missing required file: $required" >&2
    exit 1
  fi
done

if [[ -z "${MODEL:-}" && -z "${DTX_ACTIVE_MODEL:-}" ]]; then
  export DTX_ACTIVE_MODEL="lightgbm"
elif [[ -n "${MODEL:-}" ]]; then
  export DTX_ACTIVE_MODEL="$MODEL"
fi

if [[ "$DO_SETUP" -eq 1 ]]; then
  bash "$REPO_ROOT/scripts/setup.sh"
fi

if [[ -f "$REPO_ROOT/.venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "$REPO_ROOT/.venv/bin/activate"
fi

echo "Starting demo services..."
echo "API:       $API_URL/docs"
echo "Dashboard: $DASHBOARD_URL"
echo "Model:     ${DTX_ACTIVE_MODEL:-registry active model}"

(
  cd "$REPO_ROOT"
  PYTHONPATH="$REPO_ROOT/packages:$REPO_ROOT/services:$REPO_ROOT/services/ai${PYTHONPATH:+:$PYTHONPATH}" \
    bash scripts/run_dev.sh
) &
RUN_DEV_PID=$!

cleanup() { kill "$RUN_DEV_PID" 2>/dev/null || true; }
trap cleanup INT TERM EXIT

python - <<'PY'
import time, urllib.request
url = "http://localhost:8000/health"
deadline = time.time() + 60
while time.time() < deadline:
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:
            if resp.status == 200:
                print("API is ready.")
                break
    except Exception:
        pass
    time.sleep(1)
else:
    raise SystemExit("API did not become ready within 60 seconds.")
PY

if [[ "$DO_SEED" -eq 1 ]]; then
  echo "Replaying split=$SPLIT limit=$COUNT delay=$DELAY strict=$STRICT_REPLAY"
  cmd=(
    python "$REPO_ROOT/scripts/replay_dataset_demo.py"
    --url "$API_URL"
    --model "${DTX_ACTIVE_MODEL:-lightgbm}"
    --split "$SPLIT"
    --limit "$COUNT"
    --delay "$DELAY"
  )
  if [[ "$STRICT_REPLAY" -eq 1 ]]; then
    cmd+=(--strict)
  fi
  "${cmd[@]}"
else
  echo "Replay skipped (--no-seed)."
fi

echo "Demo is running. Press Ctrl+C to stop."
wait "$RUN_DEV_PID"
