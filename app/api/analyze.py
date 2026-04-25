"""
Analysis endpoints.

Phase 1: Stub endpoints returning NotImplementedError.
Phase 2: Implement single analysis with core providers.
Phase 3: Add mode translation and backward compatibility.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List

from app.models.wine import (
    AnalyzeRequest,
    AnalyzeResponse,
    BatchAnalyzeRequest,
    BatchAnalyzeResponse,
    ParsedIdentity,
)
from app.core.registry import get_registry, ProviderRegistry
from app.core.constants import Verdict, FailReason

router = APIRouter(tags=["analyze"])


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_sku(
    payload: AnalyzeRequest,
    mode: Optional[str] = Query(None, description="Legacy mode override (deprecated, use analyzer_mode in body)"),
    pipeline: Optional[str] = Query(None, description="Legacy pipeline parameter (deprecated)"),
    registry: ProviderRegistry = Depends(get_registry)
) -> AnalyzeResponse:
    """
    Analyze a single wine SKU and find the best matching image.
    """
    from datetime import datetime
    import time

    from app.core.constants import normalize_mode, AnalyzerMode
    from app.services.pipeline import StandardPipeline, VoterPipeline, PaddleQwenPipeline
    from app.models.wine import ParsedIdentity, DebugPayload, CandidateSummary

    start_time = time.time()

    # Normalize analyzer mode
    analyzer_mode = normalize_mode(mode or payload.analyzer_mode)

    # Get providers from registry
    search_provider = registry.get_search()
    ocr_provider = registry.get_ocr()
    vlm_provider = registry.get_vlm()

    # Select and run appropriate pipeline
    try:
        if analyzer_mode in (AnalyzerMode.VOTER, AnalyzerMode.STRICT, AnalyzerMode.BALANCED):
            pipeline = VoterPipeline(
                search_provider=search_provider,
                ocr_providers=[ocr_provider],
                vlm_providers=[vlm_provider],
            )
        elif analyzer_mode == AnalyzerMode.PADDLE_QWEN:
            # Requires paddle OCR and qwen VLM specifically
            from app.services.ocr import PaddleOCRProvider
            from app.services.vlm import QwenVLMProvider
            pipeline = PaddleQwenPipeline(
                search_provider=search_provider,
                paddle_ocr=PaddleOCRProvider(),
                qwen_vlm=QwenVLMProvider(),
                gemini_vlm=vlm_provider,
            )
        else:
            # Default: HYBRID_FAST, HYBRID_STRICT
            pipeline = StandardPipeline(
                search_provider=search_provider,
                ocr_provider=ocr_provider,
                vlm_provider=vlm_provider,
            )

        result = await pipeline.analyze(payload)

        # Calculate processing time
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Map pipeline result to API response format
        debug = DebugPayload(
            queries=getattr(result, 'queries', []),
            candidates_considered=getattr(result, 'candidates_considered', len(result.candidates) if hasattr(result, 'candidates') else 0),
        )

        top_candidates = [
            CandidateSummary(
                url=c.image_url,
                source=c.source,
                confidence=c.score,
            )
            for c in (result.candidates[:5] if hasattr(result, 'candidates') else [])
        ]

        # Determine verdict
        best_candidate = result.best_candidate if hasattr(result, 'best_candidate') else None
        if best_candidate and best_candidate.score > 0.5:
            verdict = Verdict.PASS
            reason = f"Verified match with {best_candidate.score:.0%} confidence"
            fail_reason = None
        elif best_candidate:
            verdict = Verdict.FAIL
            reason = "Low confidence match"
            fail_reason = FailReason.IDENTITY_UNVERIFIED
        else:
            verdict = Verdict.NO_IMAGE
            reason = result.fail_reason if hasattr(result, 'fail_reason') else "No suitable candidate found"
            fail_reason = FailReason.NO_CANDIDATES

        # Build parsed_identity from result or parse fresh
        if hasattr(result, 'parsed_identity') and result.parsed_identity:
            parsed = result.parsed_identity
        else:
            from app.services.parser import WineParser
            parser = WineParser()
            parsed = parser.parse(payload)

        return AnalyzeResponse(
            input=payload,
            parsed_identity=ParsedIdentity(
                raw_wine_name=parsed.wine_name,
                normalized_wine_name=parsed.normalized_wine_name,
                producer=parsed.producer,
                appellation=parsed.appellation,
                vineyard_or_cuvee=parsed.vineyard_or_cuvee,
                classification=parsed.classification,
                vintage=parsed.vintage,
                region=parsed.region,
            ),
            verdict=verdict,
            confidence=best_candidate.score if best_candidate else 0.0,
            selected_image_url=best_candidate.image_url if best_candidate else None,
            reason=reason,
            fail_reason=fail_reason,
            debug=debug,
            top_candidates=top_candidates,
            processing_time_ms=processing_time_ms,
            created_at=datetime.utcnow(),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )


@router.post("/batch", response_model=BatchAnalyzeResponse)
async def analyze_batch(
    payload: BatchAnalyzeRequest,
    registry: ProviderRegistry = Depends(get_registry)
) -> BatchAnalyzeResponse:
    """Analyze multiple wine SKUs in batch."""
    import asyncio

    semaphore = asyncio.Semaphore(3)  # Limit concurrent analyses

    async def analyze_one(req: AnalyzeRequest) -> AnalyzeResponse:
        async with semaphore:
            return await analyze_sku(req, registry=registry)

    results = await asyncio.gather(
        *[analyze_one(item) for item in payload.items],
        return_exceptions=True
    )

    # Handle any exceptions
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed_results.append(
                AnalyzeResponse(
                    input=payload.items[i],
                    parsed_identity=ParsedIdentity(raw_wine_name=payload.items[i].wine_name),
                    verdict=Verdict.ERROR,
                    confidence=0.0,
                    reason=f"Batch item {i} failed: {str(result)}",
                    fail_reason=FailReason.PIPELINE_NOT_IMPLEMENTED,
                )
            )
        else:
            processed_results.append(result)

    success_count = sum(1 for r in processed_results if r.verdict == Verdict.PASS)

    return BatchAnalyzeResponse(
        results=processed_results,
        summary={
            "total": len(processed_results),
            "success": success_count,
            "failed": len(processed_results) - success_count,
        }
    )


@router.get("/modes")
async def list_modes() -> dict:
    """
    List available analyzer modes.
    
    Returns supported modes with descriptions.
    """
    from app.core.constants import AnalyzerMode
    
    return {
        "modes": [
            {
                "id": AnalyzerMode.STRICT,
                "name": "Strict",
                "description": "High precision, may reject borderline matches"
            },
            {
                "id": AnalyzerMode.BALANCED,
                "name": "Balanced",
                "description": "Balance between precision and recall"
            },
            {
                "id": AnalyzerMode.HYBRID_FAST,
                "name": "Hybrid Fast",
                "description": "Fast hybrid analysis (default)"
            },
            {
                "id": AnalyzerMode.HYBRID_STRICT,
                "name": "Hybrid Strict",
                "description": "Strict hybrid analysis"
            },
            {
                "id": AnalyzerMode.VOTER,
                "name": "Voter",
                "description": "Multi-module voting consensus"
            },
            {
                "id": AnalyzerMode.PADDLE_QWEN,
                "name": "Paddle + Qwen",
                "description": "PaddleOCR + Qwen VLM specialized pipeline"
            },
        ],
        "default": AnalyzerMode.HYBRID_FAST
    }
