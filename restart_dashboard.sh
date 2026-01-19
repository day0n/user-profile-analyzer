#!/bin/bash

# Configuration - Change ports here
BACKEND_PORT=8000
FRONTEND_PORT=5173

# Check if running with bash
if [ -z "$BASH_VERSION" ]; then
    echo "This script requires Bash. Please run with: ./restart_dashboard.sh or bash restart_dashboard.sh"
    exit 1
fi

# Function to kill process on a specific port
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

# Function to cleanup on exit
cleanup() {
    echo "Stopping servers..."
    if [ -n "$BACKEND_PID" ]; then kill $BACKEND_PID 2>/dev/null; fi
    if [ -n "$FRONTEND_PID" ]; then kill $FRONTEND_PID 2>/dev/null; fi
    exit
}

# Trap INT and TERM signals
trap cleanup INT TERM

echo "=== Restarting Dashboard ==="

# Check for clean install flag
if [ "$1" == "--clean" ]; then
    echo "🧹 Clean install mode detected."
    echo "Removing existing node_modules (fixes cross-platform copy issues)..."
    rm -rf react-dashboard/frontend/node_modules
    rm -f react-dashboard/frontend/package-lock.json
fi

# 1. Kill existing processes
echo "[1/4] Cleaning up ports..."
kill_port $BACKEND_PORT
kill_port $FRONTEND_PORT

# 2. Start Backend
echo "[2/4] Starting Backend on port $BACKEND_PORT..."
cd react-dashboard/backend
if command -v uv &> /dev/null; then
    uv run uvicorn main:app --reload --port $BACKEND_PORT &
else
    # Fallback to python/pip if uv not found (common on servers)
    python3 -m uvicorn main:app --reload --port $BACKEND_PORT &
fi
BACKEND_PID=$!
cd ../..

# 3. Start Frontend
echo "[3/4] Starting Frontend on port $FRONTEND_PORT..."
cd react-dashboard/frontend

# Ensure node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

# Start Vite
npm run dev -- --port $FRONTEND_PORT &
FRONTEND_PID=$!
cd ../..

echo "[4/4] Dashboard started!"
echo "Backend: http://localhost:$BACKEND_PORT"
echo "Frontend: http://localhost:$FRONTEND_PORT"
echo "Press Ctrl+C to stop both."

wait
