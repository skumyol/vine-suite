#!/bin/bash
# Production server startup script

cd "$(dirname "$0")"

# Check command arguments
if [ "$1" == "--check" ]; then
    # Check if server is already running
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "Server is running"
        exit 0
    else
        echo "Server is not running"
        exit 1
    fi
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Please run run_dev.sh first."
    exit 1
fi

# Activate virtual environment
source .venv/bin/activate

# Run production server (no reload, more workers)
echo "Starting production server on http://localhost:8000"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
