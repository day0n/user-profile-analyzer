#!/bin/bash

# Configuration - Change ports here
BACKEND_PORT=8000
FRONTEND_PORT=5173

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

echo "=== Restarting Dashboard ==="

# 1. Kill existing processes
echo "[1/4] Cleaning up ports..."
kill_port $BACKEND_PORT
kill_port $FRONTEND_PORT

# 2. Start Backend
echo "[2/4] Starting Backend on port $BACKEND_PORT..."
cd react-dashboard/backend
# Check if uv is installed, otherwise use python directly or handle error
if command -v uv &> /dev/null; then
    uv run uvicorn main:app --reload --port $BACKEND_PORT &
else
    echo "Error: 'uv' not found. Please install uv or adjust script."
    exit 1
fi
BACKEND_PID=$!
cd ../..

# 3. Start Frontend
echo "[3/4] Starting Frontend on port $FRONTEND_PORT..."
echo "Note: Vite port is configured in vite.config.js, ensuring it matches..."
# We pass --port to vite to strictly enforce it
cd react-dashboard/frontend
# Ensure node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi
npm run dev -- --port $FRONTEND_PORT &
FRONTEND_PID=$!
cd ../..

echo "[4/4] Dashboard started!"
echo "Backend: http://localhost:$BACKEND_PORT"
echo "Frontend: http://localhost:$FRONTEND_PORT"
echo "Press Ctrl+C to stop both."

# Trap Ctrl+C to kill both
cleanup() {
    echo "Stopping servers..."
    kill $BACKEND_PID
    kill $FRONTEND_PID
    exit
}
trap cleanup SIGINT

# Wait just to keep script running
wait
