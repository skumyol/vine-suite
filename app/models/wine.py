"""
Wine SKU and analysis models.

Unified from vine2 and vine-rec models.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from app.core.constants import Verdict, FieldStatus, FailReason, AnalyzerMode


# ============== Request Models ==============

class WineSKUInput(BaseModel):
    """Input wine SKU specification."""
    wine_name: str = Field(..., description="Full wine name")
    vintage: Optional[str] = Field(None, description="Vintage year")
    format: Optional[str] = Field(None, description="Bottle format (e.g., 750ml)")
    region: Optional[str] = Field(None, description="Wine region")


class AnalyzeRequest(BaseModel):
    """Unified analyze request (vine2 compatible)."""
    wine_name: str = Field(..., min_length=1, description="Full wine name")
    vintage: str = Field(default="", min_length=0, description="Vintage year")
    format: str = Field(default="750ml", min_length=1, description="Bottle format")
    region: str = Field(default="", min_length=0, description="Wine region")
    analyzer_mode: AnalyzerMode = Field(default=AnalyzerMode.HYBRID_FAST, description="Analysis mode")


class BatchAnalyzeRequest(BaseModel):
    """Unified batch analyze request."""
    items: List[AnalyzeRequest] = Field(default_factory=list, description="Items to analyze")


# ============== Parsed Identity Models ==============

class ParsedIdentity(BaseModel):
    """
    Parsed wine identity from wine_name.
    
    Combines vine2 ParsedIdentity and vine-rec ParsedSKU.
    """
    # Core identity fields
    producer: Optional[str] = Field(None, description="Wine producer/domain")
    producer_normalized: Optional[str] = Field(None, description="Normalized producer name")
    appellation: Optional[str] = Field(None, description="Wine appellation/AOC")
    appellation_normalized: Optional[str] = Field(None, description="Normalized appellation")
    vineyard_or_cuvee: Optional[str] = Field(None, description="Vineyard or cuvee name")
    vineyard_normalized: Optional[str] = Field(None, description="Normalized vineyard")
    cuvee: Optional[str] = Field(None, description="Cuvee name (alternative to vineyard)")
    cuvee_normalized: Optional[str] = Field(None, description="Normalized cuvee")
    classification: Optional[str] = Field(None, description="Classification (Grand Cru, 1er Cru, etc.)")
    classification_normalized: Optional[str] = Field(None, description="Normalized classification")
    vintage: Optional[str] = Field(None, description="Vintage year")
    format: Optional[str] = Field(None, description="Bottle format")
    format_ml: Optional[int] = Field(None, description="Format in milliliters")
    region: Optional[str] = Field(None, description="Wine region")
    
    # Source tracking
    raw_wine_name: str = Field(..., description="Original input name")
    normalized_wine_name: str = Field(..., description="Normalized full name")
    normalized_tokens: List[str] = Field(default_factory=list, description="Tokenized name")


# ============== Result Models ==============

class FieldMatch(BaseModel):
    """Field-level match result."""
    target: Optional[str] = Field(None, description="Expected value")
    extracted: Optional[str] = Field(None, description="Extracted/OCR value")
    status: FieldStatus = Field(default=FieldStatus.UNVERIFIED)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ScoreBreakdown(BaseModel):
    """Detailed scoring breakdown."""
    producer: float = Field(default=0.0)
    appellation: float = Field(default=0.0)
    vineyard_or_cuvee: float = Field(default=0.0)
    classification: float = Field(default=0.0)
    vintage: float = Field(default=0.0)
    ocr_clarity: float = Field(default=0.0)
    image_quality: float = Field(default=0.0)
    source_trust: float = Field(default=0.0)


class ModuleVote(BaseModel):
    """Vote from a verification module (voter mode)."""
    module: str = Field(..., description="Module name (ocr, vlm, search, etc.)")
    available: bool = Field(default=True)
    passed: bool = Field(default=False)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    weight: float = Field(default=0.0)
    reason: str = Field(default="")
    field_matches: Dict[str, FieldMatch] = Field(default_factory=dict)
    raw_payload: Dict[str, Any] = Field(default_factory=dict)


class CandidateSummary(BaseModel):
    """Summary of a candidate image."""
    url: str
    source: str
    confidence: float = 0.0
    thumbnail_url: Optional[str] = None


class DebugPayload(BaseModel):
    """Debug information for analysis."""
    queries: List[str] = Field(default_factory=list)
    candidates_considered: int = Field(default=0)
    hard_fail_reasons: List[str] = Field(default_factory=list)
    ocr_snippets: List[str] = Field(default_factory=list)
    score_breakdown: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    notes: List[str] = Field(default_factory=list)
    candidate_summaries: List[CandidateSummary] = Field(default_factory=list)
    module_votes: List[ModuleVote] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    """Unified analyze response."""
    input: AnalyzeRequest
    parsed_identity: ParsedIdentity
    verdict: Verdict
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    selected_image_url: Optional[str] = Field(None, description="Best verified image URL")
    selected_source_page: Optional[str] = Field(None, description="Source page for selected image")
    reason: str = Field(..., description="Human-readable result explanation")
    fail_reason: Optional[FailReason] = Field(None, description="Failure classification")
    field_matches: Dict[str, FieldMatch] = Field(default_factory=dict)
    debug: DebugPayload = Field(default_factory=DebugPayload)
    
    # vine-rec compatibility fields
    top_candidates: List[CandidateSummary] = Field(default_factory=list)
    processing_time_ms: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class VLMVerification(BaseModel):
    """VLM verification result for pipeline tracking."""
    verdict: str = Field(default="unverified", description="VLM verdict: match, partial, no_match")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning: Optional[str] = Field(None, description="VLM explanation")


class BatchAnalyzeResponse(BaseModel):
    """Batch analysis response."""
    results: List[AnalyzeResponse] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)
