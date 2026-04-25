"""
Application constants and enums.

Unified from vine2 and vine-rec constants.
"""

from enum import Enum


class Verdict(str, Enum):
    """Analysis verdict outcomes."""
    PASS = "PASS"
    NO_IMAGE = "NO_IMAGE"
    ERROR = "ERROR"
    FAIL = "FAIL"

    def __str__(self) -> str:
        return self.value


class FieldStatus(str, Enum):
    """Field matching status."""
    MATCH = "match"
    NO_SIGNAL = "no_signal"
    CONFLICT = "conflict"
    UNVERIFIED = "unverified"

    def __str__(self) -> str:
        return self.value


class FailReason(str, Enum):
    """Reasons for analysis failure."""
    NO_CANDIDATES = "no_candidates"
    QUALITY_FAILED = "quality_failed"
    IDENTITY_UNVERIFIED = "identity_unverified"
    CONFLICTING_FIELDS = "conflicting_fields"
    PRODUCER_MISMATCH = "producer_mismatch"
    APPELLATION_MISMATCH = "appellation_mismatch"
    VINEYARD_OR_CUVEE_MISMATCH = "vineyard_or_cuvee_mismatch"
    CLASSIFICATION_CONFLICT = "classification_conflict"
    VINTAGE_MISMATCH = "vintage_mismatch"
    UNREADABLE_CORE_IDENTITY = "unreadable_core_identity"
    PIPELINE_NOT_IMPLEMENTED = "pipeline_not_implemented"

    def __str__(self) -> str:
        return self.value


class AnalyzerMode(str, Enum):
    """
    Unified analyzer modes.
    
    Maps from legacy vine2 and vine-rec modes:
    - strict, balanced (vine2)
    - hybrid_fast, hybrid_strict, voter, paddle_qwen (vine-rec)
    """
    STRICT = "strict"
    BALANCED = "balanced"
    HYBRID_FAST = "hybrid_fast"
    HYBRID_STRICT = "hybrid_strict"
    VOTER = "voter"
    PADDLE_QWEN = "paddle_qwen"

    def __str__(self) -> str:
        return self.value


# Legacy mode mapping for backward compatibility
LEGACY_MODE_MAP = {
    # vine2 legacy
    "vine2": AnalyzerMode.HYBRID_FAST,
    # Direct mappings
    "strict": AnalyzerMode.STRICT,
    "balanced": AnalyzerMode.BALANCED,
    "hybrid_fast": AnalyzerMode.HYBRID_FAST,
    "hybrid_strict": AnalyzerMode.HYBRID_STRICT,
    "voter": AnalyzerMode.VOTER,
    "paddle_qwen": AnalyzerMode.PADDLE_QWEN,
}


def normalize_mode(mode: str | None) -> AnalyzerMode:
    """
    Normalize legacy mode string to unified AnalyzerMode.
    
    Args:
        mode: Legacy mode string or None
        
    Returns:
        Unified AnalyzerMode enum
    """
    if mode is None:
        return AnalyzerMode.HYBRID_FAST
    
    normalized = LEGACY_MODE_MAP.get(mode.lower())
    if normalized:
        return normalized
    
    # Try direct enum match
    try:
        return AnalyzerMode(mode.lower())
    except ValueError:
        # Default to hybrid_fast for unknown modes
        return AnalyzerMode.HYBRID_FAST
