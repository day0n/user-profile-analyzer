#!/bin/bash

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Configuration
BACKEND_PORT=8000
FRONTEND_PORT=5173

kill_port() {
    local port=$1
    local pid=$(lsof -ti :$port)
    if [ -n "$pid" ]; then
        echo "Killing process on port $port (PID: $pid)..."
        kill -9 $pid 2>/dev/null
    else
        echo "No process found on port $port."
    fi
}

echo "=== Restarting Dashboard ==="

# Check for clean install flag
if [ "$1" == "--clean" ]; then
    echo "Clean install mode detected."
    rm -rf "$SCRIPT_DIR/react-dashboard/frontend/node_modules"
    rm -f "$SCRIPT_DIR/react-dashboard/frontend/package-lock.json"
fi

# 1. Kill existing
kill_port $BACKEND_PORT
kill_port $FRONTEND_PORT

# 2. Start Backend (using .venv)
echo "Starting Backend..."
cd "$SCRIPT_DIR/react-dashboard/backend"
nohup "$SCRIPT_DIR/.venv/bin/uvicorn" main:app --reload --host 0.0.0.0 --port $BACKEND_PORT > "$SCRIPT_DIR/backend.log" 2>&1 &
cd "$SCRIPT_DIR"

# 3. Start Frontend
echo "Starting Frontend..."
cd "$SCRIPT_DIR/react-dashboard/frontend"
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi
nohup npm run dev -- --host --port $FRONTEND_PORT > "$SCRIPT_DIR/frontend.log" 2>&1 &
cd "$SCRIPT_DIR"

sleep 2
echo "=================================================="
echo "Dashboard started!"
echo "Backend Port: $BACKEND_PORT"
echo "Frontend Port: $FRONTEND_PORT"
echo "Logs: backend.log, frontend.log"
echo "=================================================="
