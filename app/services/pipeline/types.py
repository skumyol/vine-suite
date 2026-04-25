"""Pipeline result types."""

from dataclasses import dataclass, field
from typing import List, Optional

from app.models.wine import ParsedIdentity
from app.services.base import VLMVerificationResult


@dataclass
class PipelineCandidate:
    """A candidate from pipeline analysis."""
    image_url: str
    source: str = "web"
    score: float = 0.0
    vlm_verification: Optional[VLMVerificationResult] = None


@dataclass
class PipelineResult:
    """Result from pipeline analysis."""
    wine_name: str
    vintage: str = ""
    status: str = "failed"  # "success" or "failed"
    fail_reason: str = ""
    best_candidate: Optional[PipelineCandidate] = None
    candidates: List[PipelineCandidate] = field(default_factory=list)
    queries: List[str] = field(default_factory=list)
    candidates_considered: int = 0
    parsed_identity: Optional[ParsedIdentity] = None
