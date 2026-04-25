#!/bin/bash
# Development server startup script

cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -q -e ".[dev]"

# Run with auto-reload
echo "Starting development server on http://localhost:8000"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
