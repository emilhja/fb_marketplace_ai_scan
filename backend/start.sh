#!/usr/bin/env bash
# Start the dashboard API on http://127.0.0.1:8000
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load .env from repo root so AIMM_DATABASE_URL / DATABASE_URL is set
if [ -f "$REPO_ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.env"
  set +a
fi

export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"

cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
  echo "Creating backend venv..."
  python3 -m venv .venv
fi

.venv/bin/pip install -q -r requirements.txt

.venv/bin/python "$REPO_ROOT/scripts/process_rerun_queue.py" --loop &
QUEUE_WORKER_PID=$!

.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload &
UVICORN_PID=$!

cleanup() {
  kill "$UVICORN_PID" "$QUEUE_WORKER_PID" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

wait "$UVICORN_PID"
