"""Voter pipeline - vine2 style ensemble voting approach."""

import asyncio
from typing import Dict, List, Optional

from app.models.wine import (
    AnalyzeRequest,
    AnalyzeResponse,
    VLMVerification,
)
from app.services.image.downloader import ImageDownloader
from app.services.image.opencv import OpenCVAnalyzer
from app.services.parser import WineParser, QueryBuilder
from app.services.scoring import VoterScorer
from app.services.base import OCRProvider, VLMProvider, SearchProvider
from app.services.pipeline.types import PipelineResult, PipelineCandidate


class VoterPipeline:
    """
    Voter pipeline using ensemble decision making (vine2 style).

    This pipeline uses multiple verification strategies:
    1. Search for candidate images
    2. OpenCV pre-filtering
    3. Multiple OCR reads (if available)
    4. Multiple VLM checks for consensus
    5. Ensemble voting for final decision
    """

    def __init__(
        self,
        search_provider: SearchProvider,
        ocr_providers: List[OCRProvider],
        vlm_providers: List[VLMProvider],
        max_candidates: int = 20,
        max_vlm_checks: int = 5,
    ):
        self.search_provider = search_provider
        self.ocr_providers = ocr_providers
        self.vlm_providers = vlm_providers
        self.max_candidates = max_candidates
        self.max_vlm_checks = max_vlm_checks

        self.parser = WineParser()
        self.query_builder = QueryBuilder()
        self.downloader = ImageDownloader()
        self.opencv = OpenCVAnalyzer()
        self.scorer = VoterScorer()

    async def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        """Run the voter pipeline with ensemble verification."""
        # Step 1: Parse
        parsed = self.parser.parse(request)
        queries = self.query_builder.build_queries(parsed)

        # Step 2: Search
        all_candidates = []
        for query in queries[:4]:
            result = await self.search_provider.search_by_text(query, max_results=8)
            all_candidates.extend(result.items)

        # Deduplicate
        seen_urls = set()
        unique = []
        for c in all_candidates:
            if c.url not in seen_urls:
                seen_urls.add(c.url)
                unique.append(c)

        candidates = unique[: self.max_candidates]
        if not candidates:
            return PipelineResult(
                wine_name=request.wine_name,
                vintage=request.vintage,
                status="failed",
                fail_reason="No candidates found",
                queries=queries,
            )

        # Step 3: Download + OpenCV filter
        viable = []
        for cand in candidates:
            download = await self.downloader.download(cand.url)
            if download["status"] not in ["downloaded", "cached"]:
                continue

            opencv_result = self.opencv.analyze(download["local_path"])
            if opencv_result.opencv_pass:
                viable.append({
                    "url": cand.url,
                    "local_path": download["local_path"],
                    "opencv": opencv_result,
                })

        if not viable:
            return PipelineResult(
                wine_name=request.wine_name,
                vintage=request.vintage,
                status="failed",
                fail_reason="No viable candidates after OpenCV filter",
                queries=queries,
                candidates_considered=len(candidates),
            )

        # Step 4: OCR votes from multiple engines
        for cand in viable:
            ocr_votes = []
            for ocr_provider in self.ocr_providers:
                try:
                    with open(cand["local_path"], "rb") as f:
                        image_bytes = f.read()
                    ocr_result = await ocr_provider.extract_text(image_bytes)

                    # OCR provides hints, not verdicts
                    text = ocr_result.text.lower()
                    identity_text = " ".join([
                        parsed.raw_wine_name.lower(),
                        (parsed.vintage or "").lower(),
                        (parsed.producer or "").lower(),
                    ])

                    from rapidfuzz import fuzz
                    match_score = fuzz.partial_ratio(text, identity_text) / 100.0
                    ocr_votes.append({
                        "verdict": "YES" if match_score > 0.7 else "NO",
                        "confidence": match_score,
                        "provider": ocr_provider.name,
                    })
                except Exception:
                    pass
            cand["ocr_votes"] = ocr_votes

        # Step 5: VLM votes from multiple providers
        for cand in viable:
            vlm_votes = []
            for vlm_provider in self.vlm_providers:
                try:
                    with open(cand["local_path"], "rb") as f:
                        image_bytes = f.read()
                    vlm_result = await vlm_provider.verify_image(
                        image_bytes,
                        expected_identity=parsed.model_dump(),
                    )
                    vlm_votes.append({
                        "verdict": vlm_result.verdict,
                        "confidence": vlm_result.confidence,
                        "provider": vlm_provider.name,
                    })
                except Exception:
                    pass
            cand["vlm_votes"] = vlm_votes

        # Step 6: Score with voter scorer
        scored = []
        for cand in viable:
            all_votes = cand.get("ocr_votes", []) + cand.get("vlm_votes", [])
            score = self.scorer.score(
                candidate_url=cand["url"],
                parsed_identity=parsed.model_dump(),
                votes=all_votes,
                opencv_result=cand["opencv"].__dict__ if cand["opencv"] else None,
            )
            scored.append((cand, score))

        scored.sort(key=lambda x: x[1].overall_score, reverse=True)

        # Step 7: Build response
        final_candidates = []
        for cand, score in scored[: self.max_vlm_checks]:
            vlm_votes = cand.get("vlm_votes", [])
            best_vlm = max(vlm_votes, key=lambda v: v["confidence"], default=None)

            vlm_verification = None
            if best_vlm:
                vlm_verification = VLMVerification(
                    verdict=best_vlm["verdict"],
                    confidence=best_vlm["confidence"],
                )

            candidate = PipelineCandidate(
                image_url=cand["url"],
                source="web",
                score=score.overall_score,
                vlm_verification=vlm_verification,
            )
            final_candidates.append(candidate)

        best = max(final_candidates, key=lambda c: c.score) if final_candidates else None

        if not best or best.score < 0.3:
            return PipelineResult(
                wine_name=request.wine_name,
                vintage=request.vintage,
                status="failed",
                fail_reason="No candidate reached consensus threshold",
                queries=queries,
                candidates_considered=len(candidates),
                parsed_identity=parsed,
            )

        return PipelineResult(
            wine_name=request.wine_name,
            vintage=request.vintage,
            status="success",
            best_candidate=best,
            candidates=final_candidates,
            queries=queries,
            candidates_considered=len(candidates),
            parsed_identity=parsed,
        )
