"""
Contract tests for API endpoints.

Verifies API structure and response contracts.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


class TestHealthEndpoints:
    """Contract tests for health endpoints."""
    
    def test_health_returns_ok(self):
        """Health endpoint should return status ok."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    
    def test_health_ready_returns_provider_info(self):
        """Ready endpoint should return provider configuration."""
        response = client.get("/health/ready")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ready"
        assert "version" in data
        assert "providers" in data
        assert "ocr" in data["providers"]
        assert "vlm" in data["providers"]
        assert "search" in data["providers"]
    
    def test_health_providers_returns_availability(self):
        """Providers endpoint should return availability status."""
        response = client.get("/health/providers")
        assert response.status_code == 200
        
        data = response.json()
        
        # OCR section
        assert "ocr" in data
        assert "configured" in data["ocr"]
        assert "available" in data["ocr"]
        
        # VLM section
        assert "vlm" in data
        assert "configured" in data["vlm"]
        assert "available" in data["vlm"]
        
        # Search section
        assert "search" in data
        assert "configured" in data["search"]
        assert "available" in data["search"]


class TestAnalyzeEndpoints:
    """Contract tests for analyze endpoints."""
    
    def test_analyze_requires_wine_name(self):
        """Analyze endpoint should require wine_name field."""
        payload = {"vintage": "2020"}  # Missing wine_name
        
        response = client.post("/api/v1/analyze", json=payload)
        # Will fail validation before hitting 501
        assert response.status_code == 422
    
    def test_batch_validates_request_structure(self):
        """Batch endpoint should validate request structure."""
        payload = {
            "items": [
                {"wine_name": "Wine 1"},
                {"vintage": "2020"},  # Missing wine_name
            ]
        }
        
        response = client.post("/api/v1/batch", json=payload)
        assert response.status_code == 422


class TestModesEndpoint:
    """Contract tests for modes endpoint."""
    
    def test_modes_returns_available_modes(self):
        """Modes endpoint should return list of available modes."""
        response = client.get("/api/v1/modes")
        assert response.status_code == 200
        
        data = response.json()
        assert "modes" in data
        assert "default" in data
        
        # Should have all analyzer modes
        mode_ids = [m["id"] for m in data["modes"]]
        assert "strict" in mode_ids
        assert "balanced" in mode_ids
        assert "hybrid_fast" in mode_ids
        assert "hybrid_strict" in mode_ids
        assert "voter" in mode_ids
        assert "paddle_qwen" in mode_ids
    
    def test_mode_descriptions_present(self):
        """Each mode should have name and description."""
        response = client.get("/api/v1/modes")
        data = response.json()
        
        for mode in data["modes"]:
            assert "id" in mode
            assert "name" in mode
            assert "description" in mode
            assert len(mode["name"]) > 0
            assert len(mode["description"]) > 0


class TestRootEndpoint:
    """Contract tests for root endpoint."""
    
    def test_root_returns_api_info(self):
        """Root endpoint should return API metadata."""
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data


class TestResponseContracts:
    """Test that API responses match expected contracts."""
    
    def test_error_response_structure(self):
        """Error responses should follow FastAPI structure."""
        response = client.post("/api/v1/analyze", json={"wine_name": ""})  # Empty name fails validation
        
        assert response.status_code == 422
        data = response.json()
        
        # FastAPI validation error format
        assert "detail" in data
        # Detail is usually a list of errors
        errors = data["detail"]
        assert isinstance(errors, list) or isinstance(errors, str)
    
    def test_analyze_endpoint_accepts_valid_request(self):
        """Analyze endpoint accepts valid request structure."""
        payload = {
            "wine_name": "Test Wine",
            "vintage": "2020",
            "analyzer_mode": "hybrid_fast"
        }
        response = client.post("/api/v1/analyze", json=payload)
        # Should not fail validation (may 500 if provider unavailable, but structure is ok)
        assert response.status_code != 422
