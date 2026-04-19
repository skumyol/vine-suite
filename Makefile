# Vine Suite - Meta-repo Orchestration
# Usage: make [target]

.PHONY: help dev prod stop clean status install

## Show all available commands
help:
	@echo "Vine Suite - Available commands:"
	@echo ""
	@echo "  make dev        - Start all projects in development mode"
	@echo "  make prod       - Start all projects in production mode (Docker)"
	@echo "  make stop       - Stop all running services"
	@echo "  make clean      - Clean all build artifacts and node_modules"
	@echo "  make status     - Check status of all projects"
	@echo "  make install    - Install dependencies for all projects"
	@echo ""
	@echo "  make vine2-dev      - Start vine2 only (dev mode)"
	@echo "  make vine-studio-dev - Start vine-studio only (dev mode)"
	@echo "  make vine-rec-dev   - Start vine-rec only (dev mode)"

## Development mode - start all projects
 dev:
	@echo "🚀 Starting all projects in development mode..."
	@echo ""
	@echo "vine2 (http://localhost:5173):"
	@cd vine2 && ./run_dev.sh &
	@echo ""
	@echo "vine-studio (http://localhost:3000):"
	@cd vine-studio && ./run_dev.sh &
	@echo ""
	@echo "vine-rec (http://localhost:3001):"
	@cd vine-rec && ./run_dev.sh &
	@echo ""
	@echo "All services starting... Use 'make status' to check ports"

## Production mode - Docker
prod:
	@echo "🐳 Starting all projects in production mode..."
	docker-compose up --build -d

## Stop all services
stop:
	@echo "🛑 Stopping all services..."
	@pkill -f "run_dev.sh" 2>/dev/null || true
	@pkill -f "next dev" 2>/dev/null || true
	@pkill -f "vite" 2>/dev/null || true
	docker-compose down 2>/dev/null || true
	@echo "All services stopped"

## Clean all build artifacts
clean:
	@echo "🧹 Cleaning build artifacts..."
	@cd vine2 && rm -rf frontend/dist frontend/node_modules backend/__pycache__ .venv
	@cd vine-studio && rm -rf dist node_modules
	@cd vine-rec && rm -rf frontend/.next frontend/node_modules backend/__pycache__
	@echo "Clean complete"

## Check status of all projects
status:
	@echo "📊 Vine Suite Status:"
	@echo ""
	@echo "vine2:"
	@lsof -i :5173 2>/dev/null | grep LISTEN && echo "  ✅ Frontend: http://localhost:5173" || echo "  ❌ Frontend (port 5173)"
	@lsof -i :8000 2>/dev/null | grep LISTEN && echo "  ✅ Backend: http://localhost:8000" || echo "  ❌ Backend (port 8000)"
	@echo ""
	@echo "vine-studio:"
	@lsof -i :3000 2>/dev/null | grep LISTEN && echo "  ✅ http://localhost:3000" || echo "  ❌ (port 3000)"
	@echo ""
	@echo "vine-rec:"
	@lsof -i :3001 2>/dev/null | grep LISTEN && echo "  ✅ Frontend: http://localhost:3001" || echo "  ❌ Frontend (port 3001)"
	@lsof -i :8001 2>/dev/null | grep LISTEN && echo "  ✅ Backend: http://localhost:8001" || echo "  ❌ Backend (port 8001)"

## Install dependencies for all projects
install:
	@echo "📦 Installing dependencies..."
	@cd vine2/frontend && pnpm install
	@cd vine-studio && npm install
	@cd vine-rec/frontend && pnpm install
	@echo "Dependencies installed"

# Individual project commands

vine2-dev:
	@echo "🍷 Starting vine2..."
	@cd vine2 && ./run_dev.sh

vine2-prod:
	@cd vine2 && ./run_prod.sh

vine-studio-dev:
	@echo "🎨 Starting vine-studio..."
	@cd vine-studio && ./run_dev.sh

vine-studio-prod:
	@cd vine-studio && ./run_prod.sh

vine-rec-dev:
	@echo "🍇 Starting vine-rec..."
	@cd vine-rec && ./run_dev.sh

vine-rec-prod:
	@cd vine-rec && ./run_prod.sh
