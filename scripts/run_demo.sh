#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_URL="http://localhost:8000"
DASHBOARD_URL="http://localhost:5173"
SCENARIO="mixed"
COUNT="10"
DELAY="0.8"
SEED=""
MODEL=""
DO_SETUP=0
DO_SEED=1

usage() {
  cat <<'EOF'
Usage: bash scripts/run_demo.sh [options]
  --setup                 Run scripts/setup.sh first
  --scenario <name>       normal|bearing_fault|overheating|combined|mixed|gradual_drift|intermittent_spike
  --count <n>             Number of events to seed (default: 10)
  --delay <seconds>       Delay between events (default: 0.8)
  --seed <n>              Seed jitter randomness for reproducible demo events
  --model <model_key>     Override active model (lightgbm|random_forest|xgboost|lstm_ae)
  --no-seed               Start services only
  -h, --help              Show help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --setup) DO_SETUP=1; shift ;;
    --scenario) SCENARIO="${2:-}"; shift 2 ;;
    --count) COUNT="${2:-}"; shift 2 ;;
    --delay) DELAY="${2:-}"; shift 2 ;;
    --seed) SEED="${2:-}"; shift 2 ;;
    --model) MODEL="${2:-}"; shift 2 ;;
    --no-seed) DO_SEED=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1"; usage; exit 1 ;;
  esac
done

for required in "$REPO_ROOT/scripts/run_dev.sh" "$REPO_ROOT/scripts/seed_demo_events.py" "$REPO_ROOT/services/ai/ai/models/shared/model_registry.json"; do
  if [[ ! -f "$required" ]]; then
    echo "Missing required file: $required" >&2
    exit 1
  fi
done

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
  echo "Seeding scenario: $SCENARIO (count=$COUNT delay=$DELAY)"
  seed_args=()
  if [[ -n "$SEED" ]]; then
    seed_args=(--seed "$SEED")
  fi
  python "$REPO_ROOT/scripts/seed_demo_events.py" \
    --url "$API_URL" \
    --scenario "$SCENARIO" \
    --count "$COUNT" \
    --delay "$DELAY" \
    "${seed_args[@]}"
else
  echo "Seeding skipped (--no-seed)."
fi

echo "Demo is running. Press Ctrl+C to stop."
wait "$RUN_DEV_PID"
