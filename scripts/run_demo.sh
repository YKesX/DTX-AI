#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_URL="http://localhost:8000"
DASHBOARD_URL="http://localhost:5173"
SCENARIO="mixed"
MODE="synthetic"
SPLIT="test"
SOURCE="ziya"
COUNT="10"
DELAY="0.8"
SEED=""
MODEL=""
DO_SETUP=0
DO_SEED=1
STRICT_REPLAY=0

usage() {
  cat <<'EOF'
Usage: bash scripts/run_demo.sh [options]
  --setup                 Run scripts/setup.sh first
  --mode <name>           synthetic|replay (default: synthetic)
  --scenario <name>       normal|bearing_fault|overheating|combined|mixed|gradual_drift|intermittent_spike
  --split <name>          train|test|all (replay mode only, default: test)
  --source <name>         dataset source id (replay mode only, default: ziya)
  --count <n>             Number of events to seed (default: 10)
  --delay <seconds>       Delay between events (default: 0.8)
  --seed <n>              Seed jitter randomness for reproducible demo events
  --model <model_key>     Override active model (lightgbm|random_forest|xgboost|lstm_ae)
  --strict-replay         Enable strict model validation in replay mode
  --no-seed               Start services only
  -h, --help              Show help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --setup) DO_SETUP=1; shift ;;
    --mode) MODE="${2:-}"; shift 2 ;;
    --scenario) SCENARIO="${2:-}"; shift 2 ;;
    --split) SPLIT="${2:-}"; shift 2 ;;
    --source) SOURCE="${2:-}"; shift 2 ;;
    --count) COUNT="${2:-}"; shift 2 ;;
    --delay) DELAY="${2:-}"; shift 2 ;;
    --seed) SEED="${2:-}"; shift 2 ;;
    --model) MODEL="${2:-}"; shift 2 ;;
    --strict-replay) STRICT_REPLAY=1; shift ;;
    --no-seed) DO_SEED=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1"; usage; exit 1 ;;
  esac
done

if [[ "$MODE" != "synthetic" && "$MODE" != "replay" ]]; then
  echo "Invalid --mode value: $MODE (use synthetic|replay)" >&2
  exit 1
fi

if [[ "$SPLIT" != "train" && "$SPLIT" != "test" && "$SPLIT" != "all" ]]; then
  echo "Invalid --split value: $SPLIT (use train|test|all)" >&2
  exit 1
fi

pkill -f "uvicorn main:app" 2>/dev/null || true
pkill -f "npm run dev" 2>/dev/null || true
lsof -ti :8000 | xargs kill -9 2>/dev/null || true
lsof -ti :5173 | xargs kill -9 2>/dev/null || true
lsof -ti :5174 | xargs kill -9 2>/dev/null || true

for required in "$REPO_ROOT/scripts/run_dev.sh" "$REPO_ROOT/scripts/seed_demo_events.py" "$REPO_ROOT/scripts/replay_dataset_demo.py" "$REPO_ROOT/services/ai/ai/models/shared/model_registry.json"; do
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

if [[ -n "$MODEL" ]]; then
  export DTX_ACTIVE_MODEL="$MODEL"
fi

echo "Starting demo services..."
echo "API: $API_URL/docs"
echo "Dashboard: $DASHBOARD_URL"
echo "Model: ${DTX_ACTIVE_MODEL:-registry active model}"

(
  cd "$REPO_ROOT"
  PYTHONPATH="$REPO_ROOT/packages:$REPO_ROOT/services:$REPO_ROOT/services/ai${PYTHONPATH:+:$PYTHONPATH}" \
    bash scripts/run_dev.sh
) &
RUN_DEV_PID=$!

cleanup() {
  kill "$RUN_DEV_PID" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

python - <<'PY'
import time
import urllib.request
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
  if [[ "$MODE" == "replay" ]]; then
    echo "Running dataset replay: source=$SOURCE split=$SPLIT limit=$COUNT delay=$DELAY strict=$STRICT_REPLAY"
    cmd=(
      python "$REPO_ROOT/scripts/replay_dataset_demo.py"
      --url "$API_URL"
      --model "${DTX_ACTIVE_MODEL:-lightgbm}"
      --split "$SPLIT"
      --limit "$COUNT"
      --delay "$DELAY"
      --source "$SOURCE"
    )
    if [[ "$STRICT_REPLAY" -eq 1 ]]; then
      cmd+=(--strict)
    fi
    "${cmd[@]}"
  else
    echo "Seeding scenario: $SCENARIO (count=$COUNT delay=$DELAY)"
    cmd=(
      python "$REPO_ROOT/scripts/seed_demo_events.py"
      --url "$API_URL"
      --scenario "$SCENARIO"
      --count "$COUNT"
      --delay "$DELAY"
    )
    if [[ -n "${SEED:-}" ]]; then
      cmd+=(--seed "$SEED")
    fi
    "${cmd[@]}"
  fi
else
  echo "Seeding skipped (--no-seed)."
fi

echo "Demo is running. Press Ctrl+C to stop."
wait "$RUN_DEV_PID"
