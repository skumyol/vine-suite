# Vine API

Unified wine image analysis service — merging vine2 and vine-rec backends into a single FastAPI application.

## Architecture

```
app/
├── api/                    # FastAPI route handlers
│   ├── health.py          # Health and readiness endpoints
│   └── analyze.py         # Analyze and batch endpoints (Phase 3)
├── core/                   # Core utilities and configuration
│   ├── constants.py       # Enums and constants (Verdict, AnalyzerMode, etc.)
│   ├── registry.py        # Provider registry with DI
│   └── settings.py        # Configuration management
├── models/                 # Pydantic models
│   └── wine.py            # Request/response schemas
└── services/               # Service providers
    ├── base.py            # ABC interfaces for OCR/VLM/Search
    ├── ocr/               # OCR implementations (stubbed)
    ├── vlm/               # VLM implementations (stubbed)
    └── search/            # Search implementations (stubbed)

tests/
├── contract/              # Contract tests for golden fixtures
│   ├── test_fixtures.py   # Fixture compatibility tests
│   └── test_api.py        # API contract tests
└── fixtures/golden/       # Golden fixtures from legacy backends
    ├── vine2/             # vine2 response fixtures
    ├── vine-rec/          # vine-rec response fixtures
    └── shared/            # Unified request fixtures
```

## Phased Implementation

### Phase 1: Foundation ✅ COMPLETE
- Golden fixtures extracted from vine2 and vine-rec
- ABC interfaces defined for OCR, VLM, Search providers
- Provider stubs (NotImplementedError)
- Service registry with DI
- Minimal FastAPI skeleton with health endpoints
- 37 contract tests passing

### Phase 2: Core Providers (Next)
- Implement EasyOCR provider
- Implement Gemini VLM provider
- Implement Playwright search provider
- Wire up providers to analysis pipeline
- Single `/analyze` endpoint working

### Phase 3: Pipeline & API
- BasePipeline with StandardPipeline implementation
- Mode translation layer for backward compatibility
- Batch endpoint
- Error taxonomy (custom exceptions)

### Phase 4: Production Polish
- All 9 providers implemented
- SQLite persistence
- Concurrency controls (semaphores)
- Security hardening (SSRF protection)
- Observability (metrics)

### Phase 5: Migration
- Dual-run comparison with legacy backends
- Directory flattening
- Deprecate vine2 and vine-rec

## Quick Start

```bash
# Development server with auto-reload
./run_dev.sh

# Production server
./run_prod.sh

# Run tests
source .venv/bin/activate
python -m pytest tests/contract/ -v
```

## API Endpoints

| Method | Endpoint | Status | Description |
|--------|----------|--------|-------------|
| GET | `/health` | ✅ Ready | Basic health check |
| GET | `/health/ready` | ✅ Ready | Readiness probe |
| GET | `/health/providers` | ✅ Ready | Provider availability |
| POST | `/api/v1/analyze` | 🚧 Phase 2 | Single wine analysis |
| POST | `/api/v1/batch` | 🚧 Phase 2 | Batch analysis |
| GET | `/api/v1/modes` | ✅ Ready | List analyzer modes |

## Provider Registry

The `ProviderRegistry` provides lazy initialization and configuration-based provider selection:

```python
from app.core.registry import get_registry

registry = get_registry()
ocr = registry.get_ocr()      # Returns configured OCR provider
vlm = registry.get_vlm()      # Returns configured VLM provider
search = registry.get_search()  # Returns configured search provider
```

Currently all providers return `is_available() == False` (Phase 1 stubs).

## Environment Variables

```bash
# Provider selection (Phase 2+)
VINE_API_OCR_PROVIDER=easyocr
VINE_API_VLM_PROVIDER=gemini
VINE_API_SEARCH_PROVIDER=playwright

# API keys (Phase 2-4)
VINE_API_GEMINI_API_KEY=...
VINE_API_SERPAPI_API_KEY=...
VINE_API_GOOGLE_API_KEY=...

# Server
VINE_API_PORT=8000
VINE_API_DEBUG=false
```

## Legacy Mode Mapping

| Legacy Mode | Unified Mode | Backend |
|-------------|--------------|---------|
| `strict` | `strict` | vine2 |
| `balanced` | `balanced` | vine2 |
| `hybrid_fast` | `hybrid_fast` | vine-rec |
| `hybrid_strict` | `hybrid_strict` | vine-rec |
| `voter` | `voter` | vine-rec |
| `paddle_qwen` | `paddle_qwen` | vine-rec |
| `vine2` | `hybrid_fast` | legacy alias |

## Contract Tests

Contract tests verify that our models and API can handle requests/responses from both legacy backends:

```python
# tests/contract/test_fixtures.py
test_vine2_analyze_response_fixture_exists()
test_vine_rec_verify_response_fixture_exists()
test_vine2_request_format_compatible()
test_vine_rec_request_format_compatible()
test_legacy_mode_mapping()
```

All 37 tests pass, confirming backward compatibility at the data layer.
