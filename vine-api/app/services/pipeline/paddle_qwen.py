"""Paddle+Qwen pipeline - vine2 specialized approach."""

from typing import List, Optional

from app.models.wine import (
    AnalyzeRequest,
    VLMVerification,
)
from app.services.image.downloader import ImageDownloader
from app.services.image.opencv import OpenCVAnalyzer
from app.services.parser import WineParser, QueryBuilder
from app.services.scoring import ConsensusScorer
from app.services.base import OCRProvider, VLMProvider, SearchProvider
from app.services.pipeline.types import PipelineResult, PipelineCandidate


class PaddleQwenPipeline:
    """
    Specialized pipeline using PaddleOCR + Qwen VLM (vine2 style).

    This pipeline:
    1. Runs standard voter pipeline first
    2. Augments with PaddleOCR for text extraction
    3. Uses Qwen VLM for secondary verification
    4. Requires consensus between verifiers
    """

    def __init__(
        self,
        search_provider: SearchProvider,
        paddle_ocr: OCRProvider,
        qwen_vlm: VLMProvider,
        gemini_vlm: Optional[VLMProvider] = None,
        max_candidates: int = 15,
        max_vlm_checks: int = 5,
    ):
        self.search_provider = search_provider
        self.paddle_ocr = paddle_ocr
        self.qwen_vlm = qwen_vlm
        self.gemini_vlm = gemini_vlm
        self.max_candidates = max_candidates
        self.max_vlm_checks = max_vlm_checks

        self.parser = WineParser()
        self.query_builder = QueryBuilder()
        self.downloader = ImageDownloader()
        self.opencv = OpenCVAnalyzer()
        self.scorer = ConsensusScorer()

    async def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        """Run the Paddle+Qwen specialized pipeline."""
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

        # Step 3: Download + OpenCV
        viable = []
        for cand in candidates:
            download = await self.downloader.download(cand.url)
            if download["status"] not in ["downloaded", "cached"]:
                continue

            opencv_result = self.opencv.analyze(download["local_path"])
            viable.append({
                "url": cand.url,
                "local_path": download["local_path"],
                "opencv": opencv_result,
            })

        # Step 4: PaddleOCR text extraction
        for cand in viable:
            try:
                with open(cand["local_path"], "rb") as f:
                    image_bytes = f.read()
                ocr_result = await self.paddle_ocr.extract_text(image_bytes)
                cand["ocr_text"] = ocr_result.text
                cand["ocr_confidence"] = ocr_result.confidence
            except Exception:
                cand["ocr_text"] = ""
                cand["ocr_confidence"] = 0.0

        # Step 5: Qwen VLM verification (primary)
        # + optional Gemini for secondary opinion
        for cand in viable[: self.max_vlm_checks]:
            votes = []

            # Qwen vote
            try:
                with open(cand["local_path"], "rb") as f:
                    image_bytes = f.read()
                qwen_result = await self.qwen_vlm.verify_image(
                    image_bytes,
                    expected_identity=parsed.model_dump(),
                )
                votes.append({
                    "verdict": qwen_result.verdict,
                    "confidence": qwen_result.confidence,
                    "provider": "qwen",
                })
                cand["qwen_reasoning"] = qwen_result.reasoning
            except Exception as e:
                cand["qwen_reasoning"] = str(e)

            # Gemini secondary (if available)
            if self.gemini_vlm:
                try:
                    with open(cand["local_path"], "rb") as f:
                        image_bytes = f.read()
                    gemini_result = await self.gemini_vlm.verify_image(
                        image_bytes,
                        expected_identity=parsed.model_dump(),
                    )
                    votes.append({
                        "verdict": gemini_result.verdict,
                        "confidence": gemini_result.confidence,
                        "provider": "gemini",
                    })
                    cand["gemini_reasoning"] = gemini_result.reasoning
                except Exception:
                    pass

            # OCR as weak vote
            if cand.get("ocr_text"):
                from rapidfuzz import fuzz
                identity_text = " ".join([
                    parsed.wine_name,
                    parsed.vintage or "",
                    parsed.producer or "",
                ])
                match_score = fuzz.partial_ratio(
                    cand["ocr_text"].lower(), identity_text.lower()
                ) / 100.0
                votes.append({
                    "verdict": "YES" if match_score > 0.7 else "NO",
                    "confidence": match_score * 0.5,  # Lower weight for OCR
                    "provider": "paddle_ocr",
                })

            cand["votes"] = votes

        # Step 6: Score with consensus scorer
        scored = []
        for cand in viable[: self.max_vlm_checks]:
            score = self.scorer.score(
                candidate_url=cand["url"],
                parsed_identity=parsed.model_dump(),
                votes=cand.get("votes", []),
            )
            scored.append((cand, score))

        scored.sort(key=lambda x: x[1].overall_score, reverse=True)

        # Step 7: Build response
        final_candidates = []
        for cand, score in scored[: self.max_vlm_checks]:
            vlm_verification = None
            best_vote = None
            for vote in cand.get("votes", []):
                if vote.get("provider") == "qwen":
                    best_vote = vote
                    break
            if best_vote:
                vlm_verification = VLMVerification(
                    verdict=best_vote["verdict"],
                    confidence=best_vote["confidence"],
                    reasoning=cand.get("qwen_reasoning", ""),
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
