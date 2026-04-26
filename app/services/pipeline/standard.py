"""Standard pipeline - vine-rec style hybrid approach."""

import asyncio
from typing import Dict, List, Optional

from app.models.wine import AnalyzeRequest, AnalyzeResponse
from app.services.image.downloader import ImageDownloader
from app.services.image.opencv import OpenCVAnalyzer
from app.services.image.cropper import LabelCropper
from app.services.parser import WineParser, QueryBuilder
from app.services.scoring import WeightedScorer, CandidateScore
from app.services.base import OCRProvider, VLMProvider, SearchProvider
from app.services.pipeline.types import PipelineResult, PipelineCandidate


class StandardPipeline:
    """
    Standard analysis pipeline combining search, OpenCV, OCR, and VLM.

    This is the vine-rec style approach:
    1. Parse wine name and build search queries
    2. Search for candidate images
    3. Download and prefilter with OpenCV
    4. Run OCR on promising candidates
    5. VLM verification on top candidates
    6. Score and rank candidates
    """

    def __init__(
        self,
        search_provider: SearchProvider,
        ocr_provider: OCRProvider,
        vlm_provider: VLMProvider,
        max_candidates: int = 15,
        max_vlm_checks: int = 5,
    ):
        self.search_provider = search_provider
        self.ocr_provider = ocr_provider
        self.vlm_provider = vlm_provider
        self.max_candidates = max_candidates
        self.max_vlm_checks = max_vlm_checks

        self.parser = WineParser()
        self.query_builder = QueryBuilder()
        self.downloader = ImageDownloader()
        self.opencv = OpenCVAnalyzer()
        self.cropper = LabelCropper()
        self.scorer = WeightedScorer()

    async def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        """Run the standard analysis pipeline."""
        # Step 1: Parse wine identity
        parsed = self.parser.parse(request)

        # Step 2: Build search queries
        queries = self.query_builder.build_queries(parsed)

        # Step 3: Search for candidate images
        all_candidates = []
        for query in queries[:3]:  # Limit queries
            result = await self.search_provider.search_by_text(
                query, max_results=10
            )
            all_candidates.extend(result.items)

        # Deduplicate by URL
        seen_urls = set()
        unique_candidates = []
        for c in all_candidates:
            if c.url not in seen_urls:
                seen_urls.add(c.url)
                unique_candidates.append(c)

        candidates = unique_candidates[: self.max_candidates]

        if not candidates:
            return PipelineResult(
                wine_name=request.wine_name,
                vintage=request.vintage,
                status="failed",
                fail_reason="No candidate images found",
            )

        # Step 4: Download and OpenCV filter
        analyzed_candidates = []
        for cand in candidates:
            download = await self.downloader.download(cand.url)
            if download["status"] not in ["downloaded", "cached"]:
                continue

            opencv_result = self.opencv.analyze(download["local_path"])

            analyzed_candidates.append({
                "url": cand.url,
                "local_path": download["local_path"],
                "opencv": opencv_result,
                "search_score": cand.score,
            })

        # Filter hard fails
        viable_candidates = [
            c for c in analyzed_candidates
            if c["opencv"].opencv_pass
        ]

        if not viable_candidates:
            # Try with relaxed filtering
            viable_candidates = analyzed_candidates[: self.max_vlm_checks]

        # Step 5: OCR on candidates
        for cand in viable_candidates:
            try:
                with open(cand["local_path"], "rb") as f:
                    image_bytes = f.read()
                ocr_result = await self.ocr_provider.extract_text(image_bytes)
                cand["ocr"] = ocr_result
            except Exception:
                cand["ocr"] = None

        # Step 6: Score and rank
        scored_candidates = []
        for cand in viable_candidates:
            score = self.scorer.score(
                candidate_url=cand["url"],
                parsed_identity=parsed.model_dump(),
                opencv_result=cand["opencv"].__dict__ if cand["opencv"] else None,
                ocr_result=cand["ocr"].model_dump() if cand.get("ocr") else None,
                search_result={"score": cand["search_score"]},
            )
            scored_candidates.append((cand, score))

        # Sort by score descending
        scored_candidates.sort(key=lambda x: x[1].overall_score, reverse=True)

        # Step 7: VLM verification on top candidates
        top_candidates = scored_candidates[: self.max_vlm_checks]
        final_candidates = []

        for cand, score in top_candidates:
            vlm_verification = None
            try:
                with open(cand["local_path"], "rb") as f:
                    image_bytes = f.read()

                vlm_result = await self.vlm_provider.verify_image(
                    image_bytes,
                    expected_identity=parsed.model_dump(),
                )
                vlm_verification = VLMVerification(
                    verdict=vlm_result.verdict,
                    confidence=vlm_result.confidence,
                    reasoning=vlm_result.reasoning,
                )

                # Update score with VLM result
                score.vlm_score = vlm_result.confidence if vlm_result.verdict == "YES" else 0.0

            except Exception:
                vlm_verification = None

            candidate = PipelineCandidate(
                image_url=cand["url"],
                source="web",
                score=score.overall_score,
                vlm_verification=vlm_verification,
            )
            final_candidates.append(candidate)

        # Select best candidate
        best = max(final_candidates, key=lambda c: c.score) if final_candidates else None

        if not best or best.score < 0.3:
            return PipelineResult(
                wine_name=request.wine_name,
                vintage=request.vintage,
                status="failed",
                fail_reason="No suitable candidate found",
                parsed_identity=parsed,
                candidates_considered=len(candidates),
                queries=queries,
            )

        return PipelineResult(
            wine_name=request.wine_name,
            vintage=request.vintage,
            status="success",
            best_candidate=best,
            candidates=final_candidates,
            parsed_identity=parsed,
            candidates_considered=len(candidates),
            queries=queries,
        )
