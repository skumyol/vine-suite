# Vine Suite 🍷

Meta-repository for orchestrating three wine-related projects:

| Project | Description | Stack | URL |
|---------|-------------|-------|-----|
| **vine2** | AI wine analysis with visual recognition | Python + Vite/React | http://localhost:5173 |
| **vine-studio** | OCR processing studio | Express + React | http://localhost:3000 |
| **vine-rec** | Wine recommendations | Python + Next.js | http://localhost:3001 |

## Quick Start

```bash
# Install all dependencies
make install

# Start all projects in development mode
make dev

# Check what's running
make status
```

## Project Structure

```
vine-suite/
├── vine2/          → AI wine analysis (submodule/symlink)
├── vine-studio/    → OCR studio (submodule/symlink)
├── vine-rec/       → Recommendations (submodule/symlink)
├── docker-compose.yml   # Orchestrate all services
├── Makefile             # Common commands
└── README.md
```

## Commands

| Command | Description |
|---------|-------------|
| `make dev` | Start all projects (dev mode) |
| `make prod` | Start all projects (Docker) |
| `make stop` | Stop all services |
| `make status` | Check running services |
| `make clean` | Clean build artifacts |
| `make install` | Install all dependencies |

## Individual Projects

Start a single project:

```bash
make vine2-dev       # vine2 only
make vine-studio-dev # vine-studio only
make vine-rec-dev    # vine-rec only
```

Or use each project's native scripts:

```bash
cd vine2 && ./run_dev.sh
cd vine-studio && ./run_dev.sh
cd vine-rec && ./run_dev.sh
```

## Docker (Production)

```bash
# Start all services
docker-compose up --build

# With nginx reverse proxy
docker-compose --profile proxy up --build
```

## Git Setup

These are **symlinks** to your existing repositories. Changes in `vine-suite/vine2` automatically reflect in `/Users/skumyol/Documents/GitHub/vine2`.

To convert to proper git submodules (for remote sharing):

```bash
git rm vine2 vine-studio vine-rec  # Remove symlinks
git submodule add https://github.com/user/vine2.git vine2
git submodule add https://github.com/user/vine_studio.git vine-studio
git submodule add https://github.com/user/vine_rec.git vine-rec
```
