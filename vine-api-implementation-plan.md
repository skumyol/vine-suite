# Vine-API Phased Implementation Plan

Based on engineering review and outside voice feedback. Addresses big-bang risk by splitting into 4 phases.

---

## Phase 1: Foundation (Week 1)
**Goal:** Establish contract tests, parity harnesses, and core interfaces without breaking existing systems.

### 1.1 Contract Tests & Fixtures
- Extract golden request/response fixtures from vine2 and vine-rec
- Create `tests/fixtures/golden/` with:
  - `vine2/analyze_response.json` — sample analyze output
  - `vine-rec/verify_response.json` — sample verify output
  - `shared/batch_request.json` — common batch format
- Write contract tests that assert new implementation matches golden fixtures

### 1.2 Core ABC Interfaces (No Implementations)
```python
# app/services/base.py
class OCRProvider(ABC): ...
class VLMProvider(ABC): ...
class SearchProvider(ABC): ...
```

### 1.3 Minimal FastAPI Skeleton
- Single endpoint: `POST /health` → `{"status": "ok"}`
- Pydantic models only (no business logic)
- No external dependencies beyond FastAPI + uvicorn

### 1.4 Project Structure (Pre-Flatten)
Keep nested for now to avoid import cycle risk during active development:
```
app/
├── api/
├── core/
├── services/
│   ├── ocr/
│   ├── vlm/
│   └── search/
└── models/
```

**Deliverable:** `pytest tests/contract/` passes against golden fixtures.

---

## Phase 2: Provider Adapters (Week 2)
**Goal:** Implement 3 core providers behind stable interfaces (not all 9).

### 2.1 Implement Core Providers Only
| Service | Provider |
|---------|----------|
| OCR | EasyOCR |
| VLM | Gemini |
| Search | Playwright |

### 2.2 Stub Interfaces for Others
```python
# app/services/ocr/tesseract.py
class TesseractProvider(OCRProvider):
    async def extract_text(self, image: bytes) -> str:
        raise NotImplementedError("Tesseract provider not yet implemented")
```

### 2.3 Service Registry with DI
```python
# app/core/registry.py
class ProviderRegistry:
    def get_ocr(self, name: str) -> OCRProvider: ...
    def get_vlm(self, name: str) -> VLMProvider: ...
```

### 2.4 Configuration (No Runtime Scaling Yet)
```yaml
# config.yaml
ocr_provider: easyocr  # or tesseract, paddle (stubbed)
vlm_provider: gemini   # or paddlevlm, qwen (stubbed)
search_provider: playwright  # or serpapi, google (stubbed)
```

**Deliverable:** `pytest tests/integration/providers/` passes for 3 core providers.

---

## Phase 3: Pipeline & API (Week 3)
**Goal:** Single working pipeline with backward-compatible API routes.

### 3.1 BasePipeline + One Subclass
```python
# app/services/pipeline.py
class BasePipeline(ABC): ...

class StandardPipeline(BasePipeline):
    """hybrid_fast equivalent — the default mode"""
```

Defer VoterPipeline and PaddleQwenPipeline to Phase 4.

### 3.2 Mode Translation Layer
```python
# app/api/compat.py
LEGACY_MODE_MAP = {
    "vine2": "hybrid_fast",
    "voter": "voter",  # will 400 until Phase 4
    "paddle_qwen": "paddle_qwen",  # will 400 until Phase 4
}

def normalize_mode(mode: str | None, pipeline: str | None) -> str:
    """Translate legacy params to unified mode"""
```

### 3.3 Core Endpoints
```python
# app/api/routes.py
@router.post("/analyze")
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse: ...

@router.post("/batch")
async def batch(request: BatchRequest) -> BatchResponse: ...

@router.get("/health/providers")
async def list_providers() -> dict: ...
```

### 3.4 Error Taxonomy (Not Just Pydantic)
```python
# app/core/exceptions.py
class ProviderError(Exception): ...
class OCRTimeoutError(ProviderError): ...
class VLMQuotaError(ProviderError): ...
class SearchSSRFBlocked(ProviderError): ...
```

**Deliverable:** API passes contract tests from Phase 1.

---

## Phase 4: Persistence & Polish (Week 4)
**Goal:** SQLite, concurrency controls, remaining providers, observability.

### 4.1 SQLite Schema (Now We Know What to Store)
```sql
-- jobs: request/response audit log
-- cache: VLM result caching (optional)
-- metrics: per-provider timing, success rates
```

### 4.2 Concurrency Controls (Replace Runtime Scaling)
```python
# app/core/concurrency.py
class ConcurrencyLimiter:
    """Explicit semaphores per operation type"""
    search_sem: asyncio.Semaphore(3)
    download_sem: asyncio.Semaphore(5)
    vlm_sem: asyncio.Semaphore(2)  # Rate limit sensitive
```

### 4.3 Remaining Providers (6 more)
- TesseractOCR, PaddleOCR
- PaddleVLM, QwenVLM
- SerpAPISearch, GoogleSearch

### 4.4 Observability
```python
# app/core/metrics.py
@dataclass
class PipelineMetrics:
    provider: str
    latency_ms: float
    success: bool
    retry_count: int
```

### 4.5 Security Hardening
- SSRF protection on image downloads
- Timeout/circuit-breaker per provider
- Input validation beyond pydantic (MIME checking, dimension limits)

**Deliverable:** Production-ready with monitoring dashboard.

---

## Phase 5: Migration & Cleanup (Week 5)
**Goal:** Deprecate old backends, finalize structure.

### 5.1 Dual-Run Comparison
- Run vine-api alongside vine2/vine-rec for 1 week
- Compare outputs using golden fixtures
- Fix discrepancies

### 5.2 Directory Flattening (Safe Now)
After behavior is stable, flatten structure:
```
app/services/ocr_easyocr.py
app/services/ocr_tesseract.py
...
```

### 5.3 Remove Legacy Backends
- Archive vine2 and vine-rec repositories
- Update deployment configs

### 5.4 Documentation
- API migration guide for clients
- Provider capability matrix
- Operational runbook

---

## Critical Path Dependencies

```
Phase 1 ──────┬──────> Phase 2 ──────┬──────> Phase 3 ──────┬──────> Phase 4 ──────> Phase 5
              │                      │                      │
       Golden fixtures         Provider stubs         Error taxonomy
       ABC interfaces          DI registry            Single pipeline
                              Core 3 working         Mode translation
```

**Cannot parallelize:** Each phase depends on previous phase's interfaces being stable.

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Big-bang failure | 4 separate deliverables, each testable independently |
| asyncio.to_thread() exhaustion | Phase 4: Replace with semaphores + explicit limits |
| Provider dependency conflicts | Phase 2: Only 3 providers, optional deps in pyproject.toml |
| Flattening causes cycles | Phase 5: Flatten only after stable, with tests passing |
| No error taxonomy | Phase 3: Custom exceptions before API routes |
| SQLite undefined | Phase 4: Schema designed with actual use cases |
| No observability | Phase 4: Metrics added with providers stable |

---

## Success Criteria by Phase

| Phase | Definition of Done |
|-------|-------------------|
| 1 | `pytest tests/contract/` passes; fixtures match both legacy backends |
| 2 | 3 core providers pass integration tests; stubs raise NotImplementedError |
| 3 | API routes return contract-compatible responses; error taxonomy covers 90% of failure modes |
| 4 | SQLite stores jobs/metrics; concurrency limits prevent thread exhaustion; all 9 providers work |
| 5 | Dual-run comparison <0.1% discrepancy; legacy backends archived |

---

## Estimated Effort

| Phase | Human Days | CC Hours | Critical Path |
|-------|-----------|----------|---------------|
| 1 | 3 | 0.5 | Yes |
| 2 | 4 | 1.0 | Yes |
| 3 | 5 | 1.5 | Yes |
| 4 | 5 | 2.0 | Yes |
| 5 | 3 | 1.0 | No |
| **Total** | **20** | **6** | **4 weeks** |

---

## Alternative: Fast Path (Higher Risk)

If timeline pressure exists, can collapse Phases 2-3:
- Week 1: Phase 1 (contracts + ABCs)
- Week 2-3: Phases 2+3 combined (3 providers + pipeline + API)
- Week 4: Phase 4 (remaining providers + persistence)

**Trade-off:** Less time to stabilize interfaces before building on them. Phase 3 API may need breaking changes to accommodate Phase 4 providers.

---

*Generated from engineering review with outside voice validation.*
