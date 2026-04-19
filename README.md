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

## GitHub Setup

### Step 1: Push Individual Repos

Push each project to its own GitHub repo:

```bash
# vine2
cd /Users/skumyol/Documents/GitHub/vine2
git remote add origin https://github.com/YOUR_USERNAME/vine2.git
git push -u origin main

# vine_studio
cd /Users/skumyol/Documents/GitHub/vine_studio
git remote add origin https://github.com/YOUR_USERNAME/vine_studio.git
git push -u origin main

# vine_rec
cd /Users/skumyol/Documents/GitHub/vine_rec
git remote add origin https://github.com/YOUR_USERNAME/vine_rec.git
git push -u origin main
```

### Step 2: Convert to Submodules

Run the setup script:

```bash
cd /Users/skumyol/Documents/GitHub/vine-suite
./github-setup.sh
```

Or manually:

```bash
cd /Users/skumyol/Documents/GitHub/vine-suite
rm -f vine2 vine-studio vine-rec
git submodule add https://github.com/YOUR_USERNAME/vine2.git vine2
git submodule add https://github.com/YOUR_USERNAME/vine_studio.git vine-studio
git submodule add https://github.com/YOUR_USERNAME/vine_rec.git vine-rec
git add .gitmodules
git commit -m "Add submodules"
```

### Step 3: Push Meta-Repo

```bash
git remote add origin https://github.com/YOUR_USERNAME/vine-suite.git
git push -u origin main
```

### Cloning from GitHub

```bash
# Clone with all submodules
git clone --recurse-submodules https://github.com/YOUR_USERNAME/vine-suite.git

# Or clone then init submodules
git clone https://github.com/YOUR_USERNAME/vine-suite.git
cd vine-suite
git submodule update --init --recursive
```

### Updating Submodules

When a submodule project is updated:

```bash
cd vine-suite

# Pull latest in all submodules
git submodule update --remote

# Or update specific submodule
git submodule update --remote vine2

# Commit the new submodule refs
git add vine2 vine-studio vine-rec
git commit -m "Update submodules"
git push
```
