# Unified Vine API Design

Merging vine2 + vine-rec Python backends into a single, clean, DRY system.

## Goals

1. **Eliminate duplication** - One implementation of each concept (OCR, VLM, search, scoring)
2. **Pluggable architecture** - Swap OCR engines, VLM providers, search backends via config
3. **Unified API surface** - Single endpoint supporting all analyzer modes
4. **Async throughout** - Modern Python with proper concurrency
5. **Backward compatibility** - Existing vine-studio proxy calls work unchanged

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         FastAPI Application                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │ /analyze    │  │ /batch      │  │ /jobs       │  │ /health          │ │
│  │   (unified) │  │   (async)   │  │   (persist) │  │                  │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────────────────┘ │
│         │                │                │                            │
│  ┌──────▼────────────────▼────────────────▼──────┐                      │
│  │         Pipeline Router (mode → pipeline)      │                      │
│  └──────┬────────────────────────────────────────┘                      │
│         │                                                                │
│  ┌──────▼──────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ Analyzer Modes  │  │  Pipelines   │  │  Scoring     │               │
│  │ ─────────────── │  │  ──────────  │  │  ─────────── │               │
│  │ hybrid_fast     │→ │  standard    │  │  weighted    │               │
│  │ hybrid_strict   │→ │  (opencv →   │  │  (vine-rec)  │               │
│  │ gemini_only     │→ │   ocr → vlm) │  │              │               │
│  │ qwen_only       │→ │              │  │  voting      │               │
│  │ voter           │→ │  voter       │  │  (vine2)     │               │
│  │ paddle_qwen     │→ │  (ensemble)  │  │              │               │
│  │                 │  │              │  │  consensus   │               │
│  │ opencv_only*    │→ │  paddle_qwen │  │  (combined)  │               │
│  └─────────────────┘  └──────────────┘  └──────────────┘               │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                     Service Registry (DI container)                │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │ │
│  │  │ Search   │ │ OCR      │ │ VLM      │ │ Storage  │           │ │
│  │  │ (pluggable)│ │(pluggable)│ │(pluggable)│ │(optional) │           │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

## Service Abstractions

### OCR Service (unified interface)

```python
class OCRProvider(ABC):
    @abstractmethod
    async def extract(self, image_path: str, crops: dict) -> OCRResult:
        """Extract text from image, optionally using label crops."""

class EasyOCRProvider(OCRProvider): ...      # vine-rec default
class TesseractProvider(OCRProvider): ...    # vine2 + studio
class PaddleOCRProvider(OCRProvider): ...    # vine2 paddle_qwen
```

### VLM Service (unified interface)

```python
class VLMProvider(ABC):
    @abstractmethod
    async def verify(self, image_path: str, parsed_sku: ParsedSKU, 
                     ocr_text: str) -> VLMVerification:
        """Verify image matches SKU using vision-language model."""

class GeminiProvider(VLMProvider): ...       # Native + OpenRouter fallback
class QwenProvider(VLMProvider): ...         # Native + OpenRouter fallback
class OpenRouterProvider(VLMProvider): ...  # Generic OpenRouter
```

### Search Service (unified interface)

```python
class SearchProvider(ABC):
    @abstractmethod
    async def search(self, queries: list[SearchQuery], 
                     parsed_sku: ParsedSKU) -> list[ImageCandidate]:
        """Search for candidate images."""

class PlaywrightProvider(SearchProvider): ...  # vine-rec (async)
class SerpAPIProvider(SearchProvider): ...   # vine2 + vine-rec
class BingProvider(SearchProvider): ...      # vine-rec
```

## Unified Request/Response Models

### Request

```python
class AnalyzeRequest(BaseModel):
    wine_name: str
    vintage: Optional[str] = None
    format: Optional[str] = "750ml"
    region: Optional[str] = None
    
    # Mode selection (vine-rec style)
    mode: AnalyzerMode = AnalyzerMode.HYBRID_FAST
    
    # Or pipeline selection (vine2 style) - mode takes precedence
    pipeline: Optional[str] = None  # "voter", "paddle_qwen"
    
    # Optional overrides
    ocr_engine: Optional[str] = None  # "easyocr", "tesseract", "paddle"
    search_backend: Optional[str] = None  # "playwright", "serpapi", "bing"
```

### Response (unified)

```python
class AnalysisResult(BaseModel):
    # Input echo
    input: WineSKUInput
    parsed_sku: ParsedSKU
    
    # Result
    verdict: Verdict  # PASS, REVIEW, FAIL, NO_IMAGE
    confidence: float  # 0.0 - 1.0
    selected_image_url: Optional[str] = None
    selected_source_page: Optional[str] = None
    reason: str
    
    # Provenance
    mode: str  # Which mode/pipeline was used
    processing_time_ms: int
    
    # Debug info (optional, controlled by ?debug=true)
    debug: Optional[DebugInfo] = None
    
    # Top candidates (for UI display)
    top_candidates: list[CandidateSummary] = []
```

## Pipeline Implementations

### Standard Pipeline (hybrid_fast, hybrid_strict, gemini, qwen_vl)

From vine-rec:
1. Parse SKU → structured fields
2. Build search queries
3. Search candidates (async, concurrent)
4. Download candidates (async, batch)
5. For each candidate:
   - OpenCV filter (thread pool)
   - Label crop (thread pool)
   - OCR (thread pool)
   - VLM verification (async API call)
   - Score (weighted)
6. Select best candidate
7. Return result

### Voter Pipeline (voter mode)

From vine2:
1. Parse SKU → structured fields
2. Build search queries
3. Retrieve candidates
4. Download/hydrate candidates
5. For each candidate:
   - Image quality check
   - OCR vote (deterministic matching)
   - VLM vote (Qwen via OpenRouter)
   - Joint vote (consensus)
   - Aggregate with source trust
6. Select best by confidence
7. Return result

### Paddle-Qwen Pipeline (paddle_qwen mode)

From vine2:
1. Run standard/voter pipeline first
2. OpenCV pre-filter on selected image
3. PaddleOCR on label crop
4. Qwen VLM verification (secondary)
5. Adjust verdict based on Qwen result

## Configuration (DRY)

```python
class Settings(BaseSettings):
    # API Keys (all optional, runtime availability checked)
    gemini_api_key: Optional[str] = None
    qwen_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    serpapi_key: Optional[str] = None
    
    # Defaults
    default_ocr_engine: str = "easyocr"  # or "tesseract"
    default_search_provider: str = "playwright"
    default_vlm_provider: str = "gemini"
    
    # Feature flags
    enable_persistence: bool = False  # SQLite jobs/results
    enable_short_circuit: bool = True  # Stop on first PASS
    
    # Concurrency
    search_concurrency: int = 3
    download_concurrency: int = 5
    analysis_concurrency: int = 3
```

## Directory Structure

```
vine-api/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app factory
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes_analyze.py   # POST /analyze, POST /batch
│   │   ├── routes_jobs.py      # POST /jobs, GET /jobs/{id}
│   │   └── routes_health.py    # GET /health
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py           # Settings (Pydantic)
│   │   ├── constants.py        # Enums, weights
│   │   └── exceptions.py       # Custom exceptions
│   ├── models/
│   │   ├── __init__.py
│   │   ├── sku.py              # WineSKUInput, ParsedSKU
│   │   ├── candidate.py        # ImageCandidate, CandidateAnalysis
│   │   └── result.py           # AnalysisResult, Verdict
│   ├── services/
│   │   ├── __init__.py
│   │   ├── pipeline/
│   │   │   ├── __init__.py
│   │   │   ├── router.py       # PipelineRouter
│   │   │   ├── standard.py     # StandardPipeline (vine-rec)
│   │   │   ├── voter.py        # VoterPipeline (vine2)
│   │   │   └── paddle_qwen.py  # PaddleQwenPipeline (vine2)
│   │   ├── search/
│   │   │   ├── __init__.py
│   │   │   ├── base.py         # SearchProvider ABC
│   │   │   ├── playwright.py   # PlaywrightProvider
│   │   │   ├── serpapi.py      # SerpAPIProvider
│   │   │   └── bing.py         # BingProvider
│   │   ├── ocr/
│   │   │   ├── __init__.py
│   │   │   ├── base.py         # OCRProvider ABC
│   │   │   ├── easyocr.py      # EasyOCRProvider
│   │   │   ├── tesseract.py    # TesseractProvider
│   │   │   └── paddle.py       # PaddleOCRProvider
│   │   ├── vlm/
│   │   │   ├── __init__.py
│   │   │   ├── base.py         # VLMProvider ABC
│   │   │   ├── gemini.py       # GeminiProvider
│   │   │   ├── qwen.py         # QwenProvider
│   │   │   └── openrouter.py   # OpenRouterProvider
│   │   ├── image/
│   │   │   ├── __init__.py
│   │   │   ├── downloader.py   # Async image download
│   │   │   ├── opencv.py       # OpenCV filters
│   │   │   └── cropper.py      # Label cropper
│   │   ├── parsing/
│   │   │   ├── __init__.py
│   │   │   ├── sku_parser.py   # Wine name parser
│   │   │   └── query_builder.py # Search query generator
│   │   ├── scoring/
│   │   │   ├── __init__.py
│   │   │   ├── weighted.py     # vine-rec scoring
│   │   │   ├── voting.py       # vine2 voting ensemble
│   │   │   └── consensus.py    # Combined approach
│   │   └── storage/
│   │       ├── __init__.py
│   │       └── sqlite.py       # Optional persistence
│   └── utils/
│       ├── __init__.py
│       ├── text.py             # Text normalization
│       └── timing.py           # Pipeline timing
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Migration Path

1. **Create vine-api repo** (new clean repo, no git history baggage)
2. **Port services systematically**:
   - Models first (unified schema)
   - Service abstractions (ABC base classes)
   - One provider at a time (EasyOCR → Tesseract → Paddle)
   - One pipeline at a time (standard → voter → paddle_qwen)
3. **Test against existing fixtures** - same 10 SKUs, compare outputs
4. **Update vine-suite docker-compose** - replace vine2 + vine-rec with vine-api
5. **Deprecate old repos** - archive vine2 and vine-rec

## API Compatibility Mapping

| Old Endpoint | New Endpoint | Notes |
|--------------|--------------|-------|
| vine2: POST /analyze | vine-api: POST /analyze?mode=voter | pipeline=voter |
| vine2: POST /analyze?pipeline=paddle_qwen | vine-api: POST /analyze?mode=paddle_qwen | |
| vine-rec: POST /analyze/ | vine-api: POST /analyze?mode=hybrid_fast | default mode |
| vine-rec: POST /analyze/batch | vine-api: POST /batch?mode=hybrid_fast | |
| vine-rec: GET /jobs/{id} | vine-api: GET /jobs/{id} | if persistence enabled |

## Key DRY Wins

1. **One OCR interface** - not 3 different OCR call patterns
2. **One VLM interface** - unified Gemini/Qwen/OpenRouter handling
3. **One search interface** - Playwright/SerpAPI/Bing all implement same ABC
4. **One scoring interface** - weighted, voting, or consensus selectable per-request
5. **One set of models** - single source of truth for SKU, Candidate, Result
6. **One config system** - Pydantic Settings, not scattered env vars
7. **One test suite** - comprehensive coverage, not split across repos
