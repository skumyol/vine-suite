"""Shared VLM utilities to eliminate code duplication across providers."""

import base64
import json
import re
from typing import Dict, Optional

from app.services.base import VLMProvider, VLMVerificationResult


def build_verification_prompt(expected_identity: Dict[str, Optional[str]]) -> str:
    """Build the standard wine verification prompt shared by all VLM providers."""
    wine_name = expected_identity.get("wine_name", "Unknown")
    vintage = expected_identity.get("vintage", "Unknown")
    producer = expected_identity.get("producer", "Unknown")
    region = expected_identity.get("region", "Unknown")
    country = expected_identity.get("country", "Unknown")

    return f"""Analyze this wine bottle image and verify if it matches the expected wine.

Expected Wine Identity:
- Wine Name: {wine_name}
- Vintage: {vintage}
- Producer: {producer}
- Region: {region}
- Country: {country}

You are a wine label verification expert. Examine the image carefully and determine:
1. Is this the correct wine? (yes/no/partially)
2. Confidence level (0.0 to 1.0)
3. What text is visible on the label?
4. What discrepancies do you see, if any?

Respond ONLY in valid JSON format:
{{
    "verdict": "YES|NO|PARTIAL",
    "confidence": 0.0,
    "reasoning": "detailed explanation",
    "detected_name": "name seen on label",
    "detected_vintage": "vintage seen on label",
    "discrepancies": ["list of any differences"]
}}
"""


def extract_json(text: str) -> Optional[str]:
    """Extract JSON block from markdown or raw response."""
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        return match.group(1)
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        return match.group(0)
    return None


def parse_fallback(text: str) -> Dict:
    """Fallback parsing when JSON extraction fails."""
    text_lower = text.lower()
    if "yes" in text_lower and "no" not in text_lower[:100]:
        verdict = "YES"
    elif "partial" in text_lower:
        verdict = "PARTIAL"
    else:
        verdict = "NO"

    conf_match = re.search(r'confidence[:\s]+(\d+\.?\d*)', text_lower)
    confidence = float(conf_match.group(1)) if conf_match else 0.5

    return {
        "verdict": verdict,
        "confidence": min(max(confidence, 0.0), 1.0),
        "reasoning": text[:500],
        "detected_name": None,
        "detected_vintage": None,
        "discrepancies": [],
    }


def parse_verification_result(text: str) -> VLMVerificationResult:
    """Parse a raw text response into a structured VLMVerificationResult."""
    json_str = extract_json(text)
    if json_str:
        try:
            result = json.loads(json_str)
            return VLMVerificationResult(
                matches=result.get("verdict", "NO").upper() == "YES",
                confidence=float(result.get("confidence", 0.0)),
                extracted_fields={
                    "name": result.get("detected_name"),
                    "vintage": result.get("detected_vintage"),
                },
                reasoning=result.get("reasoning", text[:500]),
                raw_metadata={"parsed_from_json": True},
            )
        except (json.JSONDecodeError, ValueError):
            pass

    # Fallback parsing
    fallback = parse_fallback(text)
    return VLMVerificationResult(
        matches=fallback["verdict"] == "YES",
        confidence=fallback["confidence"],
        extracted_fields={
            "name": fallback.get("detected_name"),
            "vintage": fallback.get("detected_vintage"),
        },
        reasoning=fallback["reasoning"],
        raw_metadata={"parsed_fallback": True},
    )


def encode_image_base64(image_bytes: bytes) -> str:
    """Encode image bytes to a base64 data URL."""
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"
