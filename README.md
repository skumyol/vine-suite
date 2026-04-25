# Vine API

Wine image analysis and verification platform. Search, OCR, and VLM-powered pipeline for finding and verifying wine bottle images from web sources.

**Tech stack:** FastAPI + Next.js 14 + TailwindCSS + Docker

---

## Overview

Vine API analyzes wine SKU identities and finds the best matching images from the web. It combines:

- **Search** — Google/Bing image search via OpenSerp
- **OCR** — Text extraction (EasyOCR, Tesseract, PaddleOCR)
- **VLM** — Visual verification (Gemini, Mistral, Qwen, PaddleVLM)
- **Scoring** — Multi-signal ranking pipeline

Deploys as Docker containers behind nginx.

---

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│   Nginx     │────▶│  Frontend   │────▶│   Next.js 14    │
│  (443/80)   │     │   :3001     │     │   /vine         │
└──────┬──────┘     └─────────────┘     └─────────────────┘
       │
       │ /vine/api/    ┌─────────────┐
       └──────────────▶│    API      │────▶│  OpenSerp    │
                       │   :8002     │     │   :7000      │
                       │   FastAPI   │     │  (search)    │
                       └──────┬──────┘     └─────────────────┘
                              │
                              │ OCR request   ┌─────────────┐
                              └──────────────▶│ OCR Service  │
                                              │   :8003      │
                                              │EasyOCR/Tess/ │
                                              │   Paddle     │
                                              └─────────────┘
```

---

## Project Structure

```
├── app/                        # FastAPI backend
│   ├── api/                    # Route handlers (health, analyze, eval)
│   ├── core/                   # Registry, settings, constants
│   ├── models/                 # Pydantic schemas
│   └── services/               # Provider implementations
│       ├── ocr/                # EasyOCR, Tesseract, PaddleOCR
│       ├── vlm/                # Gemini, Mistral, Qwen, PaddleVLM
│       ├── search/             # OpenSerp, Playwright, SerpAPI
│       ├── image/              # Downloader, OpenCV, cropper
│       ├── pipeline/           # Standard, Voter, Paddle+Qwen
│       ├── parser.py           # Wine SKU parser
│       └── scoring.py          # Candidate scoring
│
├── frontend/                   # Next.js 14 app
│   ├── app/                    # App router pages
│   ├── components/             # UI components (Shell, PageHeader)
│   └── lib/                    # API client, types, utilities
│
├── ocr-service/                # Standalone OCR microservice
│   ├── Dockerfile              # Multi-engine OCR container
│   └── main.py                 # FastAPI OCR endpoints
│
├── docker-compose.yml          # Local development
├── docker-compose.full.yml     # Production deployment
└── DEPLOY.md                   # Deployment guide
```

---

## Quick Start

### Local Development

```bash
# Backend
./run_dev.sh                    # FastAPI on :8000

# Frontend (separate terminal)
cd frontend && pnpm install && pnpm dev    # Next.js on :3000

# Run tests
python -m pytest tests/ -v
```

### Docker (Full Stack)

```bash
# Local development with all services
docker-compose up -d

# Production deployment
docker-compose -f docker-compose.full.yml up -d --build
```

---

## API Endpoints

### Analysis

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/analyze` | Single SKU analysis |
| POST | `/api/v1/batch` | Batch analysis (3 concurrent) |
| GET | `/api/v1/modes` | List analyzer modes |

### Evaluation

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/eval/pipelines` | Full pipeline evaluation |
| GET | `/api/v1/eval/pipelines/quick` | Quick pipeline check |
| GET | `/api/v1/eval/ocr` | OCR provider check |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | API health |
| GET | `/health/ready` | Readiness probe |
| GET | `/health/providers` | Provider status |

---

## Analyzer Modes

| Mode | Pipeline | Use Case |
|------|----------|----------|
| `hybrid_fast` | Standard | Fast balanced analysis (default) |
| `hybrid_strict` | Standard | Strict with higher thresholds |
| `strict` | Voter | High precision, rejects borderline |
| `balanced` | Voter | Precision/recall balance |
| `voter` | Voter | Multi-module consensus voting |
| `paddle_qwen` | Paddle+Qwen | Chinese/wine-specialized |

---

## Providers

### OCR

| Provider | Library | Languages | Notes |
|----------|---------|-----------|-------|
| EasyOCR | easyocr | Multi | Default, GPU-accelerated |
| Tesseract | pytesseract | 100+ | Fast, lightweight |
| PaddleOCR | paddleocr | en/ch/ko/ja | Best for Asian languages |

### VLM (Vision Language Models)

| Provider | Model | API |
|----------|-------|-----|
| Gemini | gemini-pro-vision | Google AI |
| Mistral | pixtral-12b | Direct / OpenRouter |
| Qwen | qwen2.5-vl | OpenRouter |
| PaddleVLM | paddleocr-vlm | Local |

### Search

| Provider | Engine | Type |
|----------|--------|------|
| OpenSerp | Google/Bing | Default microservice |
| Playwright | Browser | Direct scraping |
| SerpAPI | Google | API service |

---

## Configuration

Create `.env` from `.env.example`:

```bash
# Required
OPENROUTER_API_KEY=your_key_here        # For Qwen, Mistral VLM

# Optional
NVIDIA_API_KEY=your_key_here            # Alternative VLM
GOOGLE_API_KEY=your_key_here            # Gemini, Custom Search
SERPAPI_KEY=your_key_here               # SerpAPI search

# Provider selection
OCR_PROVIDER=easyocr                    # easyocr | tesseract | paddleocr
VLM_PROVIDER=gemini                       # gemini | mistral | qwen | paddlevlm
SEARCH_PROVIDER=openserp                # openserp | playwright | serpapi | google
```

---

## Frontend

Next.js 14 app with TailwindCSS, deployed at `/vine` via nginx.

| Page | Route | Description |
|------|-------|-------------|
| Dashboard | `/vine` | API status, quick links |
| Analyze | `/vine/analyze` | Single SKU analysis |
| Batch | `/vine/batch` | Multi-SKU batch job |
| Evaluate | `/vine/eval` | Pipeline comparison |
| Health | `/vine/health` | Provider status |

---

## Deployment

See [DEPLOY.md](DEPLOY.md) for full production deployment instructions.

Quick deploy:

```bash
# Server setup
echo "OPENROUTER_API_KEY=your_key" > .env
docker-compose -f docker-compose.full.yml up -d --build

# Nginx locations
location /vine/api/ { proxy_pass http://127.0.0.1:8002/api/; }
location /vine/health/ { proxy_pass http://127.0.0.1:8002/health/; }
location /vine { proxy_pass http://127.0.0.1:3001; }
```

---

## License

MIT
