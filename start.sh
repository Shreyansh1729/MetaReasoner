#!/bin/bash

# MetaReasoner - Start script

echo "Starting MetaReasoner..."
echo ""

# Start backend
echo "Starting backend on http://localhost:8000..."
uv run python -m backend.main &
BACKEND_PID=$!

# Wait a bit for backend to start
sleep 2

# Start frontend
echo "Starting frontend on http://localhost:3000..."
cd frontend
npm run dev -- --port 3000 &
FRONTEND_PID=$!

echo ""
echo "✓ MetaReasoner is running!"
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM
wait
