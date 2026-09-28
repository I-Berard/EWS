#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "==========================================="
echo " Starting Sentinel Deformation Monitor MVP "
echo "==========================================="

# Function to clean up background processes on exit
cleanup() {
    echo ""
    echo "Shutting down servers..."
    kill $BACKEND_PID
    kill $FRONTEND_PID
    wait $BACKEND_PID 2>/dev/null
    wait $FRONTEND_PID 2>/dev/null
    echo "Shutdown complete."
    exit 0
}

# Trap SIGINT (Ctrl+C) and SIGTERM to run the cleanup function
trap cleanup SIGINT SIGTERM

# 1. Start the FastAPI backend
echo "[1/2] Starting FastAPI backend on http://127.0.0.1:8000..."
source venv/bin/activate
cd apps/api
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ../..

# Wait a brief moment for the backend to initialize
sleep 2

# 2. Start the React frontend
echo "[2/2] Starting React frontend..."
cd apps/web
npm run dev &
FRONTEND_PID=$!
cd ../..

echo "==========================================="
echo " Dashboard is running!"
echo " Both servers are now active in the background."
echo " Press Ctrl+C to stop both servers."
echo "==========================================="

# Wait indefinitely so the script doesn't exit until interrupted
wait
