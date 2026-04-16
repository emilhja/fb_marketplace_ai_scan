#!/usr/bin/env bash
#
# start_backend_and_frontend.sh
#
# Launches the local dashboard — FastAPI backend and React frontend — as
# background processes and waits for both to exit.
#
# What it starts:
#   backend/start.sh   — FastAPI API on http://127.0.0.1:8000
#                        (also runs the rerun-queue worker as a subprocess)
#   frontend/          — Vite dev server on http://127.0.0.1:5173
#
# Usage:
#   ./start_backend_and_frontend.sh
#
# Press Ctrl+C to stop both services cleanly.
#
# Prerequisites:
#   - .env must exist in the repo root with AIMM_DATABASE_URL set.
#   - backend/.venv is created automatically by backend/start.sh on first run.
#   - Node.js >=20.19 is required; npm install runs automatically if
#     frontend/node_modules is missing.

# Exit immediately on error
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load .env so port variables are available for echo messages
if [ -f "$SCRIPT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$SCRIPT_DIR/.env"
  set +a
fi

BACKEND_PORT="${DASHBOARD_BACKEND_PORT:-8000}"
FRONTEND_PORT="${DASHBOARD_FRONTEND_PORT:-5173}"

echo "Starting Backend and Frontend..."

# Start backend (backend/start.sh reads DASHBOARD_BACKEND_PORT itself)
cd "$SCRIPT_DIR/backend"
./start.sh &
BACKEND_PID=$!

# Start frontend
cd "$SCRIPT_DIR/frontend"
# Install dependencies if they don't exist
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

echo "Starting frontend dev server on http://127.0.0.1:${FRONTEND_PORT}"
npm run dev -- --port "${FRONTEND_PORT}" &
FRONTEND_PID=$!

echo ""
echo "Dashboard running:"
echo "  API:      http://127.0.0.1:${BACKEND_PORT}"
echo "  Docs:     http://127.0.0.1:${BACKEND_PORT}/docs"
echo "  Frontend: http://127.0.0.1:${FRONTEND_PORT}"
echo ""
echo "Backend PID: $BACKEND_PID  |  Frontend PID: $FRONTEND_PID"
echo "Press Ctrl+C to stop both."

# Trap SIGINT and SIGTERM to kill and clean up child processes
function cleanup() {
    echo "Shutting down..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
