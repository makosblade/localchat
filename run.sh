#!/bin/bash

# Start the backend server
start_backend() {
  echo "Starting backend server..."
  cd backend
  if [ ! -d ".venv" ]; then
    echo "Setting up Python virtual environment..."
    python -m venv .venv
    source .venv/bin/activate
    pip install poetry
    poetry install
  else
    source .venv/bin/activate
  fi
  
  echo "Starting FastAPI server..."
  uvicorn localchat.main:app --reload --host 0.0.0.0 --port 8000 &
  BACKEND_PID=$!
  cd ..
  echo "Backend server running with PID: $BACKEND_PID"
}

# Start the frontend development server
start_frontend() {
  echo "Starting frontend server..."
  cd frontend
  if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    pnpm install
  fi
  
  echo "Starting Vite dev server..."
  pnpm dev &
  FRONTEND_PID=$!
  cd ..
  echo "Frontend server running with PID: $FRONTEND_PID"
}

# Handle cleanup on exit
cleanup() {
  echo "Shutting down servers..."
  if [ ! -z "$BACKEND_PID" ]; then
    kill $BACKEND_PID
  fi
  if [ ! -z "$FRONTEND_PID" ]; then
    kill $FRONTEND_PID
  fi
  exit 0
}

# Set up trap to handle cleanup on exit
trap cleanup INT TERM

# Start both servers
start_backend
start_frontend

echo "LocalChat is running!"
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo "Press Ctrl+C to stop all servers"

# Keep the script running
wait
