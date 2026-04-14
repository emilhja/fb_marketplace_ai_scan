#!/usr/bin/env bash

# Exit on error
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Starting Backend and Frontend..."

# Start backend
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

npm run dev &
FRONTEND_PID=$!

echo "Both systems started!"
echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
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
