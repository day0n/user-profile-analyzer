#!/bin/bash

# Configuration
BACKEND_PORT=8000
FRONTEND_PORT=5173

# Check for Bash
if [ -z "$BASH_VERSION" ]; then
    echo "This script requires Bash. Please run with: bash restart_dashboard.sh"
    exit 1
fi

kill_port() {
    local port=$1
    local pid=$(lsof -ti :$port)
    if [ -n "$pid" ]; then
        echo "Killing process on port $port (PID: $pid)..."
        kill -9 $pid
    else
        echo "No process found on port $port."
    fi
}

echo "=== Restarting Dashboard (Background Mode) ==="

# Check for clean install flag
if [ "$1" == "--clean" ]; then
    echo "🧹 Clean install mode detected."
    rm -rf react-dashboard/frontend/node_modules
    rm -f react-dashboard/frontend/package-lock.json
fi

# 1. Kill existing
kill_port $BACKEND_PORT
kill_port $FRONTEND_PORT

# 2. Start Backend
echo "Starting Backend (nohup)..."
cd react-dashboard/backend
if command -v uv &> /dev/null; then
    nohup uv run uvicorn main:app --reload --host 0.0.0.0 --port $BACKEND_PORT > ../../backend.log 2>&1 &
else
    nohup python3 -m uvicorn main:app --reload --host 0.0.0.0 --port $BACKEND_PORT > ../../backend.log 2>&1 &
fi
cd ../..

# 3. Start Frontend
echo "Starting Frontend (nohup)..."
cd react-dashboard/frontend
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

nohup npm run dev -- --host --port $FRONTEND_PORT > ../../frontend.log 2>&1 &
cd ../..

echo "=================================================="
echo "✅ Dashboard started in BACKGROUND."
echo "Backend Port: $BACKEND_PORT"
echo "Frontend Port: $FRONTEND_PORT"
echo "Logs are being written to: backend.log and frontend.log"
echo "You can close this terminal now."
echo "=================================================="
