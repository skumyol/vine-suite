"""Pipeline evaluation endpoints."""

import time
from typing import List, Dict, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query

from app.core.registry import get_registry, ProviderRegistry
from app.models.wine import AnalyzeRequest, ParsedIdentity
from app.core.constants import Verdict, AnalyzerMode, normalize_mode

router = APIRouter(prefix="/eval", tags=["evaluation"])


# Test fixtures for pipeline evaluation
TEST_CASES = [
    {
        "name": "Château Margaux 2015",
        "request": AnalyzeRequest(
            wine_name="Château Margaux",
            vintage="2015",
            format="750ml",
            region="Bordeaux",
        ),
        "expected_producer": "Château Margaux",
        "expected_appellation": "Margaux",
    },
    {
        "name": "Opus One 2018",
        "request": AnalyzeRequest(
            wine_name="Opus One",
            vintage="2018",
            format="750ml",
            region="Napa Valley",
        ),
        "expected_producer": "Opus One",
        "expected_appellation": "Napa Valley",
    },
    {
        "name": "Dom Pérignon 2012",
        "request": AnalyzeRequest(
            wine_name="Dom Pérignon",
            vintage="2012",
            format="750ml",
            region="Champagne",
        ),
        "expected_producer": "Dom Pérignon",
        "expected_appellation": "Champagne",
    },
    {
        "name": "Penfolds Grange 2016",
        "request": AnalyzeRequest(
            wine_name="Penfolds Grange",
            vintage="2016",
            format="750ml",
            region="South Australia",
        ),
        "expected_producer": "Penfolds",
        "expected_appellation": "South Australia",
    },
    {
        "name": "Sassicaia 2019",
        "request": AnalyzeRequest(
            wine_name="Sassicaia",
            vintage="2019",
            format="750ml",
            region="Bolgheri",
        ),
        "expected_producer": "Tenuta San Guido",
        "expected_appellation": "Bolgheri Sassicaia",
    },
]


class PipelineEvalResult(BaseModel):
    """Result for a single pipeline on one test case."""
    test_name: str
    pipeline: str
    status: str  # "success", "failed", "error"
    verdict: str
    confidence: float
    processing_time_ms: int
    candidates_found: int
    error: Optional[str] = None


class PipelineSummary(BaseModel):
    """Summary for one pipeline across all tests."""
    pipeline: str
    total: int
    passed: int
    failed: int
    errors: int
    avg_time_ms: float
    avg_confidence: float
    pass_rate: float


class PipelineEvalResponse(BaseModel):
    """Full pipeline evaluation response."""
    status: str
    pipelines_tested: List[str]
    results: List[PipelineEvalResult]
    summaries: List[PipelineSummary]


@router.get("/pipelines", response_model=PipelineEvalResponse)
async def evaluate_pipelines(
    registry: ProviderRegistry = Depends(get_registry),
    modes: Optional[List[str]] = Query(None, description="Pipeline modes to test (default: all)"),
    max_cases: int = Query(5, description="Max test cases to run (1-5)"),
):
    """
    Evaluate all available pipelines against test fixtures.

    Tests each pipeline with known wine SKUs and measures:
    - Pass rate (verdict == PASS)
    - Average processing time
    - Candidate discovery rate
    - Error rate
    """
    from app.services.pipeline import StandardPipeline, VoterPipeline

    # Determine which pipelines to test
    available_modes = []
    if modes and isinstance(modes, list):
        available_modes = [normalize_mode(m) for m in modes]
    else:
        # Test all available pipelines
        available_modes = [
            AnalyzerMode.HYBRID_FAST,
            AnalyzerMode.VOTER,
        ]
        # Add BALANCED/HYBRID_STRICT if they differ
        if AnalyzerMode.BALANCED != AnalyzerMode.HYBRID_FAST:
            available_modes.append(AnalyzerMode.BALANCED)

    search_provider = registry.get_search()
    ocr_provider = registry.get_ocr()
    vlm_provider = registry.get_vlm()

    all_results: List[PipelineEvalResult] = []
    test_cases = TEST_CASES[:max_cases]

    for mode in available_modes:
        pipeline_name = mode

        # Build pipeline for this mode
        try:
            if mode == AnalyzerMode.VOTER:
                pipeline = VoterPipeline(
                    search_provider=search_provider,
                    ocr_providers=[ocr_provider],
                    vlm_providers=[vlm_provider],
                )
            else:
                pipeline = StandardPipeline(
                    search_provider=search_provider,
                    ocr_provider=ocr_provider,
                    vlm_provider=vlm_provider,
                )
        except Exception as e:
            # Pipeline init failed
            for test in test_cases:
                all_results.append(PipelineEvalResult(
                    test_name=test["name"],
                    pipeline=pipeline_name,
                    status="error",
                    verdict="ERROR",
                    confidence=0.0,
                    processing_time_ms=0,
                    candidates_found=0,
                    error=str(e)[:200],
                ))
            continue

        # Run each test case
        for test in test_cases:
            start = time.time()
            try:
                result = await pipeline.analyze(test["request"])
                elapsed_ms = int((time.time() - start) * 1000)

                # Map PipelineResult fields
                status = getattr(result, "status", "unknown")
                best = getattr(result, "best_candidate", None)
                candidates = getattr(result, "candidates", [])

                verdict = "PASS" if status == "success" and best else "FAIL"
                confidence = best.score if best else 0.0

                all_results.append(PipelineEvalResult(
                    test_name=test["name"],
                    pipeline=pipeline_name,
                    status=status,
                    verdict=verdict,
                    confidence=round(confidence, 3),
                    processing_time_ms=elapsed_ms,
                    candidates_found=len(candidates),
                ))

            except Exception as e:
                elapsed_ms = int((time.time() - start) * 1000)
                all_results.append(PipelineEvalResult(
                    test_name=test["name"],
                    pipeline=pipeline_name,
                    status="error",
                    verdict="ERROR",
                    confidence=0.0,
                    processing_time_ms=elapsed_ms,
                    candidates_found=0,
                    error=str(e)[:200],
                ))

    # Build summaries per pipeline
    pipeline_names = list(set(r.pipeline for r in all_results))
    summaries = []
    for name in pipeline_names:
        pipeline_results = [r for r in all_results if r.pipeline == name]
        total = len(pipeline_results)
        passed = sum(1 for r in pipeline_results if r.verdict == "PASS")
        failed = sum(1 for r in pipeline_results if r.verdict == "FAIL")
        errors = sum(1 for r in pipeline_results if r.verdict == "ERROR")

        times = [r.processing_time_ms for r in pipeline_results if r.status != "error"]
        confs = [r.confidence for r in pipeline_results if r.status != "error"]

        summaries.append(PipelineSummary(
            pipeline=name,
            total=total,
            passed=passed,
            failed=failed,
            errors=errors,
            avg_time_ms=round(sum(times) / len(times), 1) if times else 0.0,
            avg_confidence=round(sum(confs) / len(confs), 3) if confs else 0.0,
            pass_rate=round(passed / total, 2) if total > 0 else 0.0,
        ))

    return PipelineEvalResponse(
        status="success",
        pipelines_tested=pipeline_names,
        results=all_results,
        summaries=summaries,
    )


@router.get("/pipelines/quick")
async def evaluate_pipelines_quick(
    registry: ProviderRegistry = Depends(get_registry)
):
    """Quick pipeline evaluation - 1 pipeline, 2 wines, summary only."""
    response = await evaluate_pipelines(registry, modes=["hybrid_fast"], max_cases=2)
    return {
        "status": response.status,
        "pipelines_tested": response.pipelines_tested,
        "summaries": [
            {
                "pipeline": s.pipeline,
                "pass_rate": s.pass_rate,
                "avg_time_ms": s.avg_time_ms,
                "total": s.total,
                "passed": s.passed,
                "failed": s.failed,
                "errors": s.errors,
            }
            for s in response.summaries
        ],
    }


@router.get("/ocr")
async def evaluate_ocr(registry: ProviderRegistry = Depends(get_registry)):
    """Evaluate OCR providers - delegates to OCR service if available."""
    ocr = registry.get_ocr()

    # Check if OCR service client has evaluation endpoint
    from app.services.ocr.client import OCRServiceClient
    if isinstance(ocr, OCRServiceClient):
        try:
            import httpx
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.get(f"{ocr.base_url}/eval/quick")
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass

    # Fallback: run local evaluation
    from app.services.ocr import EasyOCRProvider, TesseractProvider, PaddleOCRProvider

    providers = {
        "easyocr": EasyOCRProvider(),
        "tesseract": TesseractProvider(),
        "paddleocr": PaddleOCRProvider(),
    }

    results = {}
    for name, provider in providers.items():
        try:
            avail = await provider.is_available()
            results[name] = {
                "available": avail,
                "name": name,
            }
        except Exception as e:
            results[name] = {
                "available": False,
                "error": str(e)[:100],
            }

    return {
        "status": "success",
        "providers": results,
        "note": "Install OCR service for detailed evaluation",
    }
