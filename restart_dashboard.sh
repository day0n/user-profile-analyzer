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

# 2. Start Backend
echo "Starting Backend..."
cd "$SCRIPT_DIR/react-dashboard/backend"

if command -v uv &> /dev/null; then
    nohup uv run uvicorn main:app --reload --host 0.0.0.0 --port $BACKEND_PORT > "$SCRIPT_DIR/logs/backend.log" 2>&1 &
else
    echo "Warning: 'uv' not found, trying 'python3'..."
    nohup python3 -m uvicorn main:app --reload --host 0.0.0.0 --port $BACKEND_PORT > "$SCRIPT_DIR/logs/backend.log" 2>&1 &
fi
cd "$SCRIPT_DIR"

# 3. Start Frontend
echo "Starting Frontend..."
cd "$SCRIPT_DIR/react-dashboard/frontend"
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi
nohup npm run dev -- --host --port $FRONTEND_PORT > "$SCRIPT_DIR/logs/frontend.log" 2>&1 &
cd "$SCRIPT_DIR"

sleep 2
echo "=================================================="
echo "Dashboard started!"
echo "Backend Port: $BACKEND_PORT"
echo "Frontend Port: $FRONTEND_PORT"
echo "=================================================="
echo ""
echo "Showing logs for 60 seconds (Ctrl+C to exit earlier)..."
echo "--- Backend Log ---"
echo ""

# Show logs for 60 seconds
timeout 60 tail -f "$SCRIPT_DIR/logs/backend.log" "$SCRIPT_DIR/logs/frontend.log" 2>/dev/null || true

echo ""
echo "=================================================="
echo "Log preview finished. Services running in background."
echo "To view logs later: tail -f logs/backend.log logs/frontend.log"
echo "=================================================="
