"""
Contract tests for golden fixtures.

Verifies that our models can parse and validate the golden fixtures
from vine2 and vine-rec backends.
"""

import json
import pytest
from pathlib import Path

from app.models.wine import (
    AnalyzeRequest,
    AnalyzeResponse,
    ParsedIdentity,
    FieldMatch,
    DebugPayload,
)
from app.core.constants import Verdict, FieldStatus, AnalyzerMode


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "golden"


def load_fixture(name: str) -> dict:
    """Load a JSON fixture file."""
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


class TestVine2Compatibility:
    """Contract tests for vine2 backend compatibility."""
    
    def test_vine2_analyze_response_fixture_exists(self):
        """Verify vine2 analyze response fixture is present."""
        fixture = load_fixture("vine2/analyze_response.json")
        assert "sample_response" in fixture
        assert "expected_fields" in fixture
        assert "required_fields" in fixture
    
    def test_vine2_response_has_required_fields(self):
        """Verify vine2 response has all required fields."""
        fixture = load_fixture("vine2/analyze_response.json")
        sample = fixture["sample_response"]
        required = fixture["required_fields"]
        
        for field in required:
            assert field in sample, f"Missing required field: {field}"
    
    def test_vine2_response_parsed_identity_structure(self):
        """Verify vine2 parsed_identity structure matches our model."""
        fixture = load_fixture("vine2/analyze_response.json")
        identity_data = fixture["sample_response"]["parsed_identity"]
        
        # Check key fields that vine2 expects
        assert "producer" in identity_data
        assert "appellation" in identity_data
        assert "vintage" in identity_data
        assert "raw_wine_name" in identity_data
        assert "normalized_wine_name" in identity_data
    
    def test_vine2_verdict_values(self):
        """Verify vine2 verdict values match our enum."""
        fixture = load_fixture("vine2/analyze_response.json")
        verdict = fixture["sample_response"]["verdict"]
        
        # Should be a valid Verdict enum value
        assert verdict in [v.value for v in Verdict]
    
    def test_vine2_field_match_structure(self):
        """Verify vine2 field_matches structure matches our model."""
        fixture = load_fixture("vine2/analyze_response.json")
        field_matches = fixture["sample_response"]["field_matches"]
        
        for field_name, match_data in field_matches.items():
            assert "target" in match_data
            assert "extracted" in match_data
            assert "status" in match_data
            assert "confidence" in match_data
            # Status should be valid FieldStatus
            assert match_data["status"] in [s.value for s in FieldStatus]
    
    def test_vine2_debug_payload_structure(self):
        """Verify vine2 debug payload structure."""
        fixture = load_fixture("vine2/analyze_response.json")
        debug = fixture["sample_response"]["debug"]
        
        expected_fields = [
            "queries",
            "candidates_considered",
            "hard_fail_reasons",
            "ocr_snippets",
            "score_breakdown",
            "notes",
            "candidate_summaries",
            "module_votes",
        ]
        
        for field in expected_fields:
            assert field in debug, f"Missing debug field: {field}"


class TestVineRecCompatibility:
    """Contract tests for vine-rec backend compatibility."""
    
    def test_vine_rec_verify_response_fixture_exists(self):
        """Verify vine-rec verify response fixture is present."""
        fixture = load_fixture("vine-rec/verify_response.json")
        assert "sample_response" in fixture
        assert "expected_fields" in fixture
        assert "required_fields" in fixture
    
    def test_vine_rec_response_has_required_fields(self):
        """Verify vine-rec response has all required fields."""
        fixture = load_fixture("vine-rec/verify_response.json")
        sample = fixture["sample_response"]
        required = fixture["required_fields"]
        
        for field in required:
            assert field in sample, f"Missing required field: {field}"
    
    def test_vine_rec_parsed_sku_structure(self):
        """Verify vine-rec parsed_sku structure matches our ParsedIdentity."""
        fixture = load_fixture("vine-rec/verify_response.json")
        parsed = fixture["sample_response"]["parsed_sku"]
        
        # Core fields vine-rec expects
        assert "raw_name" in parsed
        assert "producer" in parsed
        assert "producer_normalized" in parsed
        assert "appellation" in parsed
        assert "appellation_normalized" in parsed
        assert "vineyard" in parsed
        assert "classification" in parsed
        assert "normalized_tokens" in parsed
    
    def test_vine_rec_verdict_values(self):
        """Verify vine-rec verdict values match our enum."""
        fixture = load_fixture("vine-rec/verify_response.json")
        verdict = fixture["sample_response"]["verdict"]
        
        # vine-rec uses "PASS", "FAIL", etc.
        assert verdict in [v.value for v in Verdict]
    
    def test_vine_rec_analyzer_mode_compatibility(self):
        """Verify vine-rec analyzer modes are supported."""
        fixture = load_fixture("vine-rec/verify_response.json")
        mode = fixture["sample_response"]["analyzer_mode"]
        
        # Should be a valid AnalyzerMode or legacy mode
        from app.core.constants import LEGACY_MODE_MAP
        assert mode in LEGACY_MODE_MAP or mode in [m.value for m in AnalyzerMode]
    
    def test_vine_rec_top_candidates_structure(self):
        """Verify vine-rec top_candidates structure."""
        fixture = load_fixture("vine-rec/verify_response.json")
        candidates = fixture["sample_response"]["top_candidates"]
        
        assert isinstance(candidates, list)
        if candidates:
            for cand in candidates:
                assert "url" in cand
                assert "source" in cand
                assert "confidence" in cand


class TestSharedFormats:
    """Contract tests for unified request formats."""
    
    def test_analyze_request_fixture_exists(self):
        """Verify shared analyze request fixture is present."""
        fixture = load_fixture("shared/analyze_request.json")
        assert "vine2_compatible" in fixture
        assert "vine_rec_compatible" in fixture
        assert "unified_format" in fixture
        assert "legacy_mode_map" in fixture
    
    def test_vine2_request_format_compatible(self):
        """Verify vine2 request format can be parsed."""
        fixture = load_fixture("shared/analyze_request.json")
        vine2_data = fixture["vine2_compatible"]
        
        # Should be valid for our AnalyzeRequest
        request = AnalyzeRequest(**vine2_data)
        assert request.wine_name == vine2_data["wine_name"]
        assert request.vintage == vine2_data["vintage"]
    
    def test_vine_rec_request_format_compatible(self):
        """Verify vine-rec request format can be parsed."""
        fixture = load_fixture("shared/analyze_request.json")
        vine_rec_data = fixture["vine_rec_compatible"]
        
        # vine-rec uses same field names
        request = AnalyzeRequest(**vine_rec_data)
        assert request.wine_name == vine_rec_data["wine_name"]
        assert request.vintage == vine_rec_data["vintage"]
    
    def test_legacy_mode_mapping(self):
        """Verify all legacy modes map to valid analyzer modes."""
        from app.core.constants import LEGACY_MODE_MAP, normalize_mode
        
        for legacy_mode in LEGACY_MODE_MAP:
            normalized = normalize_mode(legacy_mode)
            assert isinstance(normalized, AnalyzerMode)
    
    def test_batch_request_fixture_exists(self):
        """Verify shared batch request fixture is present."""
        fixture = load_fixture("shared/batch_request.json")
        assert "vine2_format" in fixture
        assert "vine_rec_format" in fixture
        assert "unified_format" in fixture
        assert "field_mapping" in fixture
    
    def test_vine2_batch_format(self):
        """Verify vine2 batch format has expected structure."""
        fixture = load_fixture("shared/batch_request.json")
        vine2_format = fixture["vine2_format"]
        
        assert "items" in vine2_format
        assert isinstance(vine2_format["items"], list)
    
    def test_vine_rec_batch_format(self):
        """Verify vine-rec batch format has expected structure."""
        fixture = load_fixture("shared/batch_request.json")
        vine_rec_format = fixture["vine_rec_format"]
        
        assert "wines" in vine_rec_format
        assert "analyzer_mode" in vine_rec_format


class TestModelCompatibility:
    """Test that our Pydantic models match fixture structures."""
    
    def test_parsed_identity_from_vine2_data(self):
        """Verify ParsedIdentity can parse vine2 identity data."""
        fixture = load_fixture("vine2/analyze_response.json")
        identity_data = fixture["sample_response"]["parsed_identity"]
        
        # vine2 uses different field names than vine-rec
        # Our unified model should accept both
        identity = ParsedIdentity(
            producer=identity_data.get("producer"),
            appellation=identity_data.get("appellation"),
            vineyard_or_cuvee=identity_data.get("vineyard_or_cuvee"),
            classification=identity_data.get("classification"),
            vintage=identity_data.get("vintage"),
            format=identity_data.get("format"),
            region=identity_data.get("region"),
            raw_wine_name=identity_data["raw_wine_name"],
            normalized_wine_name=identity_data["normalized_wine_name"],
        )
        
        assert identity.raw_wine_name == identity_data["raw_wine_name"]
    
    def test_parsed_identity_from_vine_rec_data(self):
        """Verify ParsedIdentity can parse vine-rec sku data."""
        fixture = load_fixture("vine-rec/verify_response.json")
        sku_data = fixture["sample_response"]["parsed_sku"]
        
        # vine-rec uses vineyard/cuvee as separate fields
        identity = ParsedIdentity(
            producer=sku_data.get("producer"),
            producer_normalized=sku_data.get("producer_normalized"),
            appellation=sku_data.get("appellation"),
            appellation_normalized=sku_data.get("appellation_normalized"),
            vineyard=sku_data.get("vineyard"),
            vineyard_normalized=sku_data.get("vineyard_normalized"),
            cuvee=sku_data.get("cuvee"),
            cuvee_normalized=sku_data.get("cuvee_normalized"),
            classification=sku_data.get("classification"),
            vintage=sku_data.get("vintage"),
            region=sku_data.get("region"),
            raw_wine_name=sku_data["raw_name"],
            normalized_wine_name="",  # vine-rec doesn't have this
            normalized_tokens=sku_data.get("normalized_tokens", []),
        )
        
        assert identity.raw_wine_name == sku_data["raw_name"]
    
    def test_field_match_from_fixture(self):
        """Verify FieldMatch matches fixture structure."""
        fixture = load_fixture("vine2/analyze_response.json")
        field_matches = fixture["sample_response"]["field_matches"]
        
        for field_name, match_data in field_matches.items():
            match = FieldMatch(**match_data)
            assert match.status in FieldStatus
    
    def test_debug_payload_structure(self):
        """Verify DebugPayload can hold expected data."""
        fixture = load_fixture("vine2/analyze_response.json")
        debug_data = fixture["sample_response"]["debug"]
        
        # Parse score breakdown
        score_data = debug_data["score_breakdown"]
        from app.models.wine import ScoreBreakdown
        scores = ScoreBreakdown(**score_data)
        
        # Debug payload with scores
        debug = DebugPayload(
            queries=debug_data["queries"],
            candidates_considered=debug_data["candidates_considered"],
            hard_fail_reasons=debug_data["hard_fail_reasons"],
            ocr_snippets=debug_data["ocr_snippets"],
            score_breakdown=scores,
            notes=debug_data["notes"],
        )
        
        assert len(debug.queries) > 0
