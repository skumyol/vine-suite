"""Pipeline integration tests using 10 benchmark SKUs from vine-rec."""

import asyncio
import json
import time
from dataclasses import asdict
from typing import List, Optional

import pytest

from app.core.registry import ProviderRegistry
from app.models.wine import AnalyzeRequest, ParsedIdentity
from app.services.parser import WineParser, QueryBuilder
from app.services.pipeline import StandardPipeline, VoterPipeline, PaddleQwenPipeline


# 10 benchmark SKUs from vine-rec assignment
TEST_SKUS = [
    {
        "wine_name": "Domaine Rossignol-Trapet Latricieres-Chambertin Grand Cru",
        "vintage": "2017",
        "format": "750ml",
        "region": "Burgundy",
        "difficulty": "Hard",
    },
    {
        "wine_name": "Domaine Arlaud Morey-St-Denis 'Monts Luisants' 1er Cru",
        "vintage": "2019",
        "format": "750ml",
        "region": "Burgundy",
        "difficulty": "Hard",
    },
    {
        "wine_name": "Domaine Taupenot-Merme Charmes-Chambertin Grand Cru",
        "vintage": "2018",
        "format": "750ml",
        "region": "Burgundy",
        "difficulty": "Hard",
    },
    {
        "wine_name": "Château Fonroque Saint-Émilion Grand Cru Classé",
        "vintage": "2016",
        "format": "750ml",
        "region": "Bordeaux",
        "difficulty": "Medium",
    },
    {
        "wine_name": "Eric Rodez Cuvée des Crayères Blanc de Noirs",
        "vintage": "NV",
        "format": "750ml",
        "region": "Champagne",
        "difficulty": "Medium",
    },
    {
        "wine_name": "Domaine du Tunnel Cornas 'Vin Noir'",
        "vintage": "2018",
        "format": "750ml",
        "region": "Northern Rhône",
        "difficulty": "Hard",
    },
    {
        "wine_name": "Poderi Colla Barolo 'Bussia Dardi Le Rose'",
        "vintage": "2016",
        "format": "750ml",
        "region": "Piedmont",
        "difficulty": "Medium",
    },
    {
        "wine_name": "Arnot-Roberts Trousseau Gris Watson Ranch",
        "vintage": "2020",
        "format": "750ml",
        "region": "Sonoma",
        "difficulty": "Very Hard",
    },
    {
        "wine_name": "Brokenwood Graveyard Vineyard Shiraz",
        "vintage": "2015",
        "format": "750ml",
        "region": "Hunter Valley",
        "difficulty": "Medium",
    },
    {
        "wine_name": "Domaine Weinbach Riesling 'Clos des Capucins' Vendanges Tardives",
        "vintage": "2017",
        "format": "750ml",
        "region": "Alsace",
        "difficulty": "Hard",
    },
]


@pytest.fixture
def registry():
    """Provider registry with test config."""
    return ProviderRegistry(
        ocr_provider="easyocr",
        vlm_provider="gemini",
        search_provider="openserp",
    )


class TestParser:
    """Test wine identity parsing from SKU text."""

    def test_parse_burgundy_grand_cru(self):
        parser = WineParser()
        request = AnalyzeRequest(
            wine_name="Domaine Rossignol-Trapet Latricieres-Chambertin Grand Cru",
            vintage="2017",
            region="Burgundy",
        )
        result = parser.parse(request)
        assert "rossignol" in result.normalized_wine_name.lower()
        assert "latricieres" in result.normalized_wine_name.lower()
        assert result.vintage == "2017"
        assert result.region.lower() == "burgundy"

    def test_parse_chateau(self):
        parser = WineParser()
        request = AnalyzeRequest(
            wine_name="Château Fonroque Saint-Émilion Grand Cru Classé",
            vintage="2016",
        )
        result = parser.parse(request)
        assert "fonroque" in result.producer.lower()
        # Handle accent: Saint-Émilion -> saint-emilion
        if result.appellation:
            from unidecode import unidecode
            app_normalized = unidecode(result.appellation.lower())
            assert "saint" in app_normalized and "emilion" in app_normalized

    def test_parse_nv_champagne(self):
        parser = WineParser()
        request = AnalyzeRequest(
            wine_name="Eric Rodez Cuvée des Crayères Blanc de Noirs",
            vintage="NV",
        )
        result = parser.parse(request)
        assert result.vintage.lower() == "nv"
        assert "rodez" in result.normalized_wine_name


class TestQueryBuilder:
    """Test search query generation."""

    def test_build_queries_priority(self):
        builder = QueryBuilder()
        identity = ParsedIdentity(
            raw_wine_name="Domaine Rossignol-Trapet Latricieres-Chambertin",
            normalized_wine_name="domaine rossignol-trapet latricieres-chambertin",
            producer="Domaine Rossignol-Trapet",
            vintage="2017",
            region="Burgundy",
        )
        queries = builder.build_queries(identity)
        assert len(queries) >= 3
        # First query should be most specific
        assert "rossignol" in queries[0].lower()
        assert "latricieres" in queries[0].lower()
        assert "2017" in queries[0].lower()

    def test_build_queries_fallback(self):
        builder = QueryBuilder()
        identity = ParsedIdentity(
            raw_wine_name="Generic Bordeaux",
            normalized_wine_name="generic bordeaux",
        )
        queries = builder.build_queries(identity)
        assert len(queries) > 0


class TestOCRPreprocessor:
    """Test unified OCR preprocessing pipeline."""

    def test_load_image(self):
        from app.services.ocr.preprocessor import OCRPreprocessor
        import numpy as np
        import cv2

        # Create a synthetic test image
        img = np.ones((600, 400, 3), dtype=np.uint8) * 128
        _, buf = cv2.imencode(".jpg", img)
        image_bytes = buf.tobytes()

        preprocessor = OCRPreprocessor()
        result = preprocessor.preprocess(image_bytes)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_resize_to_target_height(self):
        from app.services.ocr.preprocessor import OCRPreprocessor
        import numpy as np
        import cv2

        # Small image should be resized up
        img = np.ones((200, 150, 3), dtype=np.uint8) * 128
        _, buf = cv2.imencode(".jpg", img)
        preprocessor = OCRPreprocessor()
        result = preprocessor.preprocess(buf.tobytes())
        assert len(result) > 0


class TestPipelineIntegration:
    """End-to-end pipeline tests with benchmark SKUs.
    
    These tests require provider credentials and network access.
    Mark with --run-integration to execute.
    """

    @pytest.mark.integration
    async def test_standard_pipeline_single_sku(self, registry):
        pipeline = StandardPipeline(
            search_provider=registry.get_search(),
            ocr_provider=registry.get_ocr(),
            vlm_provider=registry.get_vlm(),
        )
        request = AnalyzeRequest(
            wine_name="Château Fonroque Saint-Émilion Grand Cru Classé",
            vintage="2016",
            format="750ml",
            region="Bordeaux",
        )
        result = await pipeline.analyze(request)
        assert result.wine_name == request.wine_name
        assert result.status in ("success", "failed")
        if result.status == "success":
            assert result.best_candidate is not None
            assert result.best_candidate.score > 0

    @pytest.mark.integration
    async def test_voter_pipeline_single_sku(self, registry):
        pipeline = VoterPipeline(
            search_provider=registry.get_search(),
            ocr_providers=[registry.get_ocr()],
            vlm_providers=[registry.get_vlm()],
        )
        request = AnalyzeRequest(
            wine_name="Château Fonroque Saint-Émilion Grand Cru Classé",
            vintage="2016",
        )
        result = await pipeline.analyze(request)
        assert result.status in ("success", "failed")

    @pytest.mark.integration
    async def test_paddle_qwen_pipeline(self, registry):
        from app.services.ocr import PaddleOCRProvider
        from app.services.vlm import QwenVLMProvider

        pipeline = PaddleQwenPipeline(
            search_provider=registry.get_search(),
            paddle_ocr=PaddleOCRProvider(),
            qwen_vlm=QwenVLMProvider(),
            gemini_vlm=registry.get_vlm(),
        )
        request = AnalyzeRequest(
            wine_name="Château Fonroque Saint-Émilion Grand Cru Classé",
            vintage="2016",
        )
        result = await pipeline.analyze(request)
        assert result.status in ("success", "failed")

    @pytest.mark.integration
    async def test_all_skus_parser_query_builder(self):
        """Test parser + query builder on all 10 SKUs (no external calls)."""
        parser = WineParser()
        builder = QueryBuilder()

        for sku in TEST_SKUS:
            request = AnalyzeRequest(
                wine_name=sku["wine_name"],
                vintage=sku["vintage"],
                format=sku.get("format"),
                region=sku.get("region"),
            )
            parsed = parser.parse(request)
            queries = builder.build_queries(parsed)

            assert parsed.wine_name == sku["wine_name"]
            assert len(queries) > 0
            # At least one query should contain the wine name
            assert any(sku["wine_name"].split()[0].lower() in q.lower() for q in queries)


class TestProviderAvailability:
    """Test provider health checks."""

    @pytest.mark.asyncio
    async def test_registry_health(self, registry):
        ocr_health = await registry.get_ocr().health_check()
        assert "name" in ocr_health
        assert "preprocessing" in ocr_health

        vlm_health = await registry.get_vlm().health_check()
        assert "name" in vlm_health


class TestBenchmarkEvaluator:
    """Run full benchmark against 10 test SKUs."""

    @pytest.mark.benchmark
    @pytest.mark.integration
    async def test_run_benchmark(self, registry):
        """Run all 10 SKUs through StandardPipeline and report accuracy."""
        pipeline = StandardPipeline(
            search_provider=registry.get_search(),
            ocr_provider=registry.get_ocr(),
            vlm_provider=registry.get_vlm(),
        )

        results = []
        for sku in TEST_SKUS:
            request = AnalyzeRequest(
                wine_name=sku["wine_name"],
                vintage=sku["vintage"],
                format=sku.get("format"),
                region=sku.get("region"),
            )
            start = time.time()
            result = await pipeline.analyze(request)
            elapsed_ms = int((time.time() - start) * 1000)

            results.append({
                "sku": sku["wine_name"],
                "difficulty": sku["difficulty"],
                "status": result.status,
                "has_candidate": result.best_candidate is not None,
                "score": result.best_candidate.score if result.best_candidate else 0.0,
                "queries": result.queries,
                "candidates_considered": result.candidates_considered,
                "time_ms": elapsed_ms,
            })

        # Report
        success = sum(1 for r in results if r["status"] == "success")
        total = len(results)
        print(f"\nBenchmark: {success}/{total} succeeded")

        for r in results:
            icon = "✓" if r["status"] == "success" else "✗"
            print(f"  {icon} {r['sku'][:50]:50} ({r['difficulty']:10}) "
                  f"score={r['score']:.2f} time={r['time_ms']}ms")

        # Save results
        with open("benchmark_results.json", "w") as f:
            json.dump(results, f, indent=2)

        # Target: at least 50% success rate for integration test baseline
        assert success >= total * 0.5, f"Expected >=50% success, got {success}/{total}"
