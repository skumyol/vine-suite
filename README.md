# Vine Suite 🍷

Meta-repository orchestrating three wine photo verification systems, each exploring different architectural approaches to the same problem: **accurately match wine bottle photos to SKU specifications using AI/ML pipelines**.

All three projects target the VinoBuzz internship assignment: achieving **≥90% accuracy** on 10 challenging test SKUs (Burgundy Grand/1er Cru, Bordeaux, Champagne, Northern Rhône, Piedmont, Alsace, Sonoma).

---

## System Comparison Overview

| Dimension | **vine2** | **vine-studio** | **vine-rec** |
|-----------|-----------|-----------------|--------------|
| **Primary Language** | Python + TypeScript | Full TypeScript | Python + TypeScript |
| **Backend** | FastAPI | Express (in server.ts) | FastAPI |
| **Frontend** | Vite + React 19 | Vite + React 19 | Next.js 14 |
| **Architecture** | Multi-container microservices | Single-container monolith | Backend-frontend split with nginx |
| **Container Strategy** | 3 services: backend + Playwright + nginx | 1 service: unified Express/Vite | 3 services: backend + frontend + nginx |
| **OCR Engine** | Tesseract / PaddleOCR | Tesseract (eng+fra+ita+deu) | EasyOCR |
| **VLM Strategy** | Voting ensemble (OCR + VLM consensus) | Qwen 3.5 VL primary, Gemini fallback | Gemini + Qwen-VL hybrid modes |
| **Visual Filtering** | OpenCV-based | Sharp (pure Node.js) | OpenCV-based |
| **Search** | Playwright service via HTTP | Playwright in-process | Playwright WebKit |
| **Scoring** | Source-trust weighted voting | Composite: VLM×0.9 + quality + authority | Weighted: Image 20% + OCR 40% + VLM 40% |
| **Key Innovation** | Playwright service isolation, pluggable pipelines | Semantic VLM matching, vintage-aware rescoring | Async batch jobs, SQLite persistence |

---

## Methodological Differences

### vine2: Service-Oriented Pipeline Architecture

**Philosophy**: Decouple heavy browser automation into a dedicated service for resource isolation and horizontal scaling.

```
┌─────────────┐     HTTP      ┌─────────────────┐
│   Backend   │◄─────────────►│ Playwright Svc  │
│  (FastAPI)  │               │ (isolated deps) │
└──────┬──────┘               └─────────────────┘
       │
       ▼
┌─────────────┐
│   Voter     │◄── OCR + VLM consensus
│   Pipeline  │    (pluggable: voter, paddle_qwen)
└─────────────┘
```

**Pipeline Variants**:
- `voter`: Multi-model voting with confidence aggregation
- `paddle_qwen`: OpenCV prefilter → PaddleOCR → Qwen multimodal verification

**Why it matters**: Playwright's heavy browser dependencies (Chromium, WebKit) run in their own container with separate resource limits. The backend stays lightweight and can scale independently.

---

### vine-studio: VLM-Centric Semantic Verification

**Philosophy**: Let the Vision Language Model be the **final decision maker**, not just a scorer. OCR provides hints, not gates.

```
SKU Input → Multi-query Search → Vintage-Aware Ranking
                                     ↓
                         ┌─────────────────────┐
                         │  Visual Pre-filter  │ (sharp: resolution/aspect/blur)
                         │   Classical CV      │
                         └──────────┬──────────┘
                                    ↓
                         ┌─────────────────────┐
                         │  Tesseract OCR      │──┐
                         │  (hint, not gate)   │  │
                         └─────────────────────┘  │
                                                    ▼
                                          ┌──────────────────┐
                                          │ Qwen 3.5 VL      │
                                          │ Semantic Match?  │
                                          │ MATCH/PARTIAL/   │
                                          │ NO_MATCH         │
                                          └────────┬─────────┘
                                                   ↓
                                          Composite Score
```

**Key Techniques**:
- **Semantic matching**: VLM handles producer/owner variants (e.g., "Stéphane Robert" ↔ "Domaine du Tunnel")
- **Vintage-aware rescoring**: +8 points for correct vintage in URL/title, −6 for wrong vintage
- **4-corner background cleanness**: Detects studio packshots vs. lifestyle photos
- **Laplacian blur detection**: Rejects soft-focus images via edge variance

**Language Strategy**: 4-language Tesseract (eng+fra+ita+deu) for European wine labels.

---

### vine-rec: Structured Pipeline with Persistence

**Philosophy**: Modular service architecture with explicit pipeline stages and result persistence for auditing.

```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│   Parser    │──►│   Search    │──►│  Download   │──►│  OpenCV     │──►│   OCR       │
│ (SKU→fields)│   │(Playwright) │   │  (async)    │   │  (filter)   │   │ (EasyOCR)   │
└─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘   └──────┬──────┘
                                                                                  │
                                                                    ┌─────────────┴─────────────┐
                                                                    ▼                           ▼
                                                           ┌───────────────┐            ┌───────────────┐
                                                           │   Gemini      │            │   Qwen-VL     │
                                                           │  (optional)   │            │  (optional)   │
                                                           └───────┬───────┘            └───────────────┘
                                                                   │
                                                                   ▼
                                                           ┌───────────────┐
                                                           │ ScoringEngine │
                                                           │ (weighted)    │
                                                           └───────┬───────┘
                                                                   │
                                                                   ▼
                                                           ┌───────────────┐
                                                           │   Verdict     │
                                                           │ PASS/REVIEW/  │
                                                           │ FAIL/NO_IMAGE │
                                                           └───────────────┘
```

**Analyzer Modes**:
| Mode | Description |
|------|-------------|
| `hybrid_fast` | OpenCV → OCR → Gemini only |
| `hybrid_strict` | OpenCV → OCR → Both Gemini + Qwen |
| `gemini` | Gemini-only verification |
| `qwen_vl` | Qwen-VL only |
| `opencv_only` | Debug mode, image quality only |

**Infrastructure Features**:
- **Async job API**: `POST /api/jobs/batch` for long-running batches with progress polling
- **SQLite persistence**: Run history with CSV export
- **Result storage**: JSON artifacts + downloaded images cached per SKU

---

## Technical Architecture Comparison

### Container Topology

| Project | Services | Resource Limits | Key Feature |
|---------|----------|-----------------|-------------|
| **vine2** | 3 (backend, playwright, frontend) | backend: 2CPU/2GB, playwright: 1CPU/1GB | Isolated Playwright service |
| **vine-studio** | 1 (unified) | 2GB memory | Simpler deployment, unified logging |
| **vine-rec** | 3 (backend, frontend, nginx) | backend: 4GB/1GB shm | Health-check dependencies, SSL-ready |

### OCR Strategy Matrix

| Project | Engine | Languages | Upscale | Preprocessing | Role in Pipeline |
|---------|--------|-----------|---------|---------------|------------------|
| **vine2** | Tesseract/PaddleOCR | Configurable | 2× | Threshold | Evidence for voter |
| **vine-studio** | Tesseract | eng+fra+ita+deu | 2–3× | Lanczos + contrast stretch | Hint to VLM |
| **vine-rec** | EasyOCR | Auto-detect | Thumbnail→800×1000 | MPS GPU when available | Text verification input |

### VLM Integration Patterns

| Project | Primary VLM | Secondary | Routing Strategy | Output Format |
|---------|-------------|-----------|------------------|---------------|
| **vine2** | Qwen (ensemble) | PaddleOCR-VL | Pipeline-selected | Verdict + confidence |
| **vine-studio** | Qwen 3.5 VL | Gemini Vision | Fallback on OpenRouter failure | MATCH/PARTIAL/NO_MATCH JSON |
| **vine-rec** | Gemini / Qwen | Both in hybrid_strict | Mode-selected via config | Score + verdict enum |

---

## Quick Start

```bash
# Install all dependencies
make install

# Start all projects in development mode
make dev

# Check what's running
make status
```

## Individual Projects

```bash
make vine2-dev       # vine2 only (ports 5173/8000/8043)
make vine-studio-dev # vine-studio only (port 3000)
make vine-rec-dev    # vine-rec only (ports 3001/8001)
```

Or use native scripts:

```bash
cd vine2 && ./run_dev.sh       # Docker-based dev (Playwright in container)
cd vine-studio && ./run_dev.sh # tsx server.ts (hot reload)
cd vine-rec && ./run_dev.sh    # Backend + frontend concurrently
```

## Docker (Production)

```bash
# Start all services with nginx gateway
docker-compose --profile proxy up --build

# Services exposed:
# - http://localhost        → nginx proxy (vine2 default)
# - http://localhost:8000   → vine2 backend
# - http://localhost:5173   → vine2 frontend
# - http://localhost:3000   → vine-studio
# - http://localhost:3001   → vine-rec frontend
# - http://localhost:8001   → vine-rec backend
```

---

## Submodule Management

### Cloning

```bash
# Clone with all submodules
git clone --recurse-submodules https://github.com/skumyol/vine-suite.git

# Or initialize after clone
git submodule update --init --recursive
```

### Updating Submodules on Remote

```bash
# On the remote server (pull updates without re-cloning)
git pull origin main && git submodule update --init --recursive
```

### Pushing Changes from Submodules

```bash
# 1. Push from submodule first
cd vine2 && git checkout main && git push origin main && cd ..

# 2. Stage and commit pointer update in parent
git add vine2 && git commit -m "Update vine2 submodule"
git push origin main
```

---

## Project URLs and Repositories

| Project | Local URL | GitHub Repository |
|---------|-----------|-------------------|
| vine2 | http://localhost:5173 | https://github.com/skumyol/vine2 |
| vine-studio | http://localhost:3000 | https://github.com/skumyol/vine_studio |
| vine-rec | http://localhost:3001 | https://github.com/skumyol/vine_rec |
| **vine-suite** (meta) | http://localhost (via nginx) | https://github.com/skumyol/vine-suite |

---

## Common Commands

| Command | Description |
|---------|-------------|
| `make dev` | Start all projects (dev mode) |
| `make prod` | Start all projects (Docker) |
| `make stop` | Stop all services |
| `make status` | Check running services |
| `make clean` | Clean build artifacts |
| `make install` | Install all dependencies |

---

## Design Notes

### When to use each approach

| Scenario | Recommended Project | Reason |
|----------|---------------------|--------|
| High-volume production | vine2 | Playwright isolation prevents memory leaks |
| Rapid prototyping / demos | vine-studio | Single container, fastest iteration |
| Audit/regulatory requirements | vine-rec | SQLite persistence, result exports |
| Burgundy-heavy catalogs | vine-studio | Semantic matching handles climat variants |
| Budget-conscious deployment | vine2 | Resource-targeted scaling per service |

### Shared Components

All three projects share the VinoBuzz test SKU set (see `assignment.md` in each repo):

1. Domaine Rossignol-Trapet Latricieres-Chambertin Grand Cru (2017)
2. Domaine Arlaud Morey-St-Denis 'Monts Luisants' 1er Cru (2019)
3. Domaine Taupenot-Merme Charmes-Chambertin Grand Cru (2018)
4. Château Fonroque Saint-Émilion Grand Cru Classé (2016)
5. Eric Rodez Cuvée des Crayeres Blanc de Noirs (NV)
6. Domaine du Tunnel Cornas 'Vin Noir' (2018)
7. Poderi Colla Barolo 'Bussia Dardi Le Rose' (2016)
8. Arnot-Roberts Trousseau Gris Watson Ranch (2020)
9. Brokenwood Graveyard Vineyard Shiraz (2015)
10. Domaine Weinbach Riesling 'Clos des Capucins' Vendanges Tardives (2017)

Each system targets **≥90% accuracy** (PASS or REVIEW verdicts) on this benchmark set.
