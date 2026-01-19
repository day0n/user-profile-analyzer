#!/bin/bash

# Function to kill processes on exit
cleanup() {
  echo "Stopping servers..."
  kill $BACKEND_PID
  kill $FRONTEND_PID
  exit
}

trap cleanup SIGINT

echo "Starting Backend..."
cd react-dashboard/backend
uv run uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!

echo "Waiting for backend to start..."
sleep 5

echo "Starting Frontend..."
cd ../frontend
# Ensure deps are installed
if [ ! -d "node_modules" ]; then
    echo "First time setup: Installing dependencies..."
    npm install
fi

npm run dev

# Wait for both processes
wait
