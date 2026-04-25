# Vine API Deployment Guide

## OCR Service with Live Evaluation

### Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   vine-api      │────▶│   ocr-service    │────▶│  EasyOCR        │
│   (port 8000)   │     │   (port 8001)    │     │  Tesseract      │
└─────────────────┘     └──────────────────┘     │  PaddleOCR*     │
         │                                        └─────────────────┘
         │
         ▼
┌─────────────────┐
│   OpenSerp      │
│   (port 7000)   │
└─────────────────┘
```

*PaddleOCR: Works on x86_64 Linux, may crash on ARM64 (Apple Silicon)

### Quick Start

```bash
# Build and start all services
docker-compose up --build -d

# Wait for OCR service warmup (~5 minutes)
docker-compose logs -f ocr-service

# Test endpoints
curl http://localhost:8001/health
curl http://localhost:8000/api/v1/eval/pipelines/quick
```

### OCR Service Endpoints

#### Core OCR Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /` | - | Service info (name, version, engines) |
| `GET /health` | - | Engine health status |
| `GET /stats` | - | Memory, CPU, uptime metrics |
| `POST /ocr/easyocr` | Form: `file` | Extract with EasyOCR |
| `POST /ocr/tesseract` | Form: `file` | Extract with Tesseract |
| `POST /ocr/paddle` | Form: `file` | Extract with PaddleOCR* |
| `POST /ocr/best` | Form: `file` | Ensemble - picks best result |

#### Live Evaluation Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /eval/quick` | Summary stats for all enabled engines |
| `GET /eval/run` | Full per-sample results (10 synthetic tests) |

**Example:**
```bash
# Quick evaluation summary
curl http://localhost:8001/eval/quick

# Response:
{
  "status": "success",
  "summary": {
    "engines_tested": 2,
    "engines_available": 2,
    "overall_accuracy": 1.0,
    "best_engine": "tesseract",
    "best_accuracy": 1.0,
    "avg_time_ms": 142.3
  },
  "engine_scores": {
    "easyocr": {"available": true, "accuracy": 1.0, "avg_time_ms": 234.5},
    "tesseract": {"available": true, "accuracy": 1.0, "avg_time_ms": 85.1}
  }
}
```

### Pipeline Evaluation (Main API)

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/eval/pipelines` | Full pipeline test with VLM verification |
| `GET /api/v1/eval/pipelines/quick` | Summary only |
| `GET /api/v1/eval/ocr` | OCR provider check (delegates to OCR service) |

**Example:**
```bash
# Quick pipeline evaluation
curl http://localhost:8000/api/v1/eval/pipelines/quick

# Response:
{
  "status": "success",
  "pipelines_tested": ["hybrid_fast", "voter"],
  "summaries": [
    {
      "pipeline": "hybrid_fast",
      "pass_rate": 0.8,
      "avg_time_ms": 2345.0,
      "total": 5,
      "passed": 4,
      "failed": 1,
      "errors": 0
    }
  ]
}
```

### Configuration

#### Environment Variables

**OCR Service:**
| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLED_ENGINES` | `easyocr` | Comma-separated: `easyocr,tesseract,paddle` |
| `MAX_CONCURRENT_REQUESTS` | `3` | Limit parallel OCR operations |
| `GC_AFTER_REQUEST` | `true` | Run garbage collection after each request |
| `OCR_TIMEOUT` | `30` | OCR operation timeout (seconds) |

**Main API:**
| Variable | Required | Description |
|----------|----------|-------------|
| `OCR_SERVICE_URL` | Yes | `http://ocr-service:8000` |
| `OPENSERP_URL` | Yes | `http://openserp:7000` |
| `OPENROUTER_API_KEY` | Yes | For VLM (GPT-4V, etc.) |
| `NVIDIA_API_KEY` | Optional | For alternative VLM |

#### Platform-Specific Notes

**ARM64 (Apple Silicon / M1/M2/M3):**
- PaddleOCR crashes with segfault - do NOT enable
- Use: `ENABLED_ENGINES=easyocr,tesseract`
- Tesseract is ~6x faster than EasyOCR

**x86_64 (Production servers):**
- All 3 engines work correctly
- Use: `ENABLED_ENGINES=easyocr,tesseract,paddle`
- Ensemble voting provides best accuracy

### Testing

```bash
# Test OCR service directly
curl -X POST -F "file=@test_image.png" http://localhost:8001/ocr/best

# Run live evaluation
curl http://localhost:8001/eval/run | jq '.summary'

# Test full pipeline with VLM
curl http://localhost:8000/api/v1/eval/pipelines/quick
```

### Troubleshooting

**OCR service not starting:**
```bash
# Check logs
docker-compose logs ocr-service

# Check if models are downloading (first startup takes ~5 min)
docker-compose logs ocr-service | grep "WARMUP"
```

**PaddleOCR crashes:**
- You're on ARM64 - remove `paddle` from `ENABLED_ENGINES`
- Or deploy on x86_64 Linux server

**Pipeline tests fail (0% pass rate):**
- Check OpenSerp is running: `curl http://localhost:7000/health`
- Verify search provider is returning results
- Check VLM API keys are valid

### Performance Benchmarks

On x86_64 with 4GB RAM allocated:

| Engine | Avg Time | Accuracy | Memory |
|--------|----------|----------|--------|
| EasyOCR | ~1400ms | 100% | ~600MB |
| Tesseract | ~230ms | 100% | ~50MB |
| PaddleOCR | ~800ms | 100% | ~400MB |
| Ensemble (best) | ~230ms | 100% | Shared |

### Deployment Checklist

- [ ] Set correct `ENABLED_ENGINES` for your architecture
- [ ] Configure API keys in `.env` file
- [ ] Set memory limits (4GB recommended for all 3 engines)
- [ ] Test `/eval/quick` endpoint after deployment
- [ ] Verify `/api/v1/eval/pipelines` returns results
- [ ] Monitor `/stats` for memory usage
- [ ] Check health endpoints are responding

## Files Created for Evaluation

- `ocr-service/evaluation.py` - Live OCR evaluation endpoints
- `app/api/eval.py` - Pipeline evaluation with VLM
- `app/services/ocr/ensemble.py` - Ensemble OCR provider
- `app/core/registry.py` - Provider registry updates

---

## Production Deployment (Replaces vine-rec)

### Nginx Configuration

Your server nginx config should have:

```nginx
# vine-api backend (port 8002)
location /vine/api/ {
    proxy_pass http://127.0.0.1:8002/api/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 300s;
}

# vine-api health endpoint (backend root /health)
location /vine/health/ {
    proxy_pass http://127.0.0.1:8002/health/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

# vine-api frontend (port 3001)
location /vine {
    proxy_pass http://127.0.0.1:3001;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

### Docker Compose Production (Full)

Use `docker-compose.full.yml` for complete deployment with all OCR engines:

```bash
# On the server
cd /path/to/vine-api
docker-compose -f docker-compose.full.yml up -d --build
```

**Services:**
| Service | Port | Internal | Description |
|---------|------|----------|-------------|
| frontend | 3001 | :3000 | Next.js app (replaces vine-rec frontend) |
| api | 8002 | :8000 | Main vine-api backend |
| ocr-service | 8003 | :8000 | OCR microservice (EasyOCR, Tesseract, Paddle) |
| openserp | 7000 | :7000 | Image search microservice |

### Path Mapping

| Nginx Location | Proxies To | Backend Route |
|----------------|------------|---------------|
| `/vine/api/` | `localhost:8002/api/` | `/api/v1/*` |
| `/vine/health/` | `localhost:8002/health/` | `/health/*` |
| `/vine` | `localhost:3001/` | Next.js app |

### Environment Variables

Create `.env` file on server:

```bash
# Required
OPENROUTER_API_KEY=your_key_here

# Optional
NVIDIA_API_KEY=your_key_here
```

### Verify Deployment

```bash
# Test OCR service (wait ~5 min for warmup)
curl http://localhost:8003/health
curl http://localhost:8003/eval/quick

# Test backend
curl http://localhost:8002/health
curl http://localhost:8002/api/v1/modes
curl http://localhost:8002/api/v1/eval/ocr

# Test frontend
curl -I http://localhost:3001

# Test via nginx (after nginx config reload)
curl https://skumyol.com/vine/health/
curl https://skumyol.com/vine/api/v1/modes
```

### Migration from vine-rec

1. Stop vine-rec containers:
   ```bash
   cd /path/to/vine-rec
   docker-compose down
   ```

2. Start vine-api:
   ```bash
   cd /path/to/vine-api
   docker-compose -f docker-compose.full.yml up -d --build
   ```

3. Update nginx (if needed) and reload:
   ```bash
   sudo nginx -t
   sudo nginx -s reload
   ```

4. Verify at `https://skumyol.com/vine`
