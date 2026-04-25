"""Scoring engines for wine image candidate evaluation."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from rapidfuzz import fuzz


class Verdict(Enum):
    YES = "YES"
    NO = "NO"
    PARTIAL = "PARTIAL"
    UNCERTAIN = "UNCERTAIN"


@dataclass
class CandidateScore:
    """Score breakdown for a candidate image."""

    url: str
    overall_score: float = 0.0
    search_score: float = 0.0
    opencv_score: float = 0.0
    ocr_score: float = 0.0
    vlm_score: float = 0.0
    text_match_score: float = 0.0
    vintage_match_score: float = 0.0
    hard_fail: bool = False
    fail_reasons: List[str] = field(default_factory=list)
    details: Dict = field(default_factory=dict)


class BaseScorer:
    """Base class for scoring candidates."""

    def score(self, candidate_url: str, parsed_identity: dict, **kwargs) -> CandidateScore:
        raise NotImplementedError


class WeightedScorer(BaseScorer):
    """Weighted scoring engine combining multiple signals."""

    WEIGHTS = {
        "search_score": 0.10,
        "opencv_quality": 0.15,
        "text_match": 0.20,
        "vintage_match": 0.15,
        "ocr_confidence": 0.10,
        "vlm_verdict": 0.30,
    }

    def score(
        self,
        candidate_url: str,
        parsed_identity: dict,
        opencv_result: Optional[dict] = None,
        ocr_result: Optional[dict] = None,
        vlm_result: Optional[dict] = None,
        search_result: Optional[dict] = None,
    ) -> CandidateScore:
        score = CandidateScore(url=candidate_url)

        # Search authority score
        if search_result:
            score.search_score = search_result.get("score", 5.0) / 10.0

        # OpenCV quality score
        if opencv_result:
            opencv_pass = opencv_result.get("opencv_pass", False)
            if not opencv_pass:
                score.hard_fail = True
                score.fail_reasons.append(opencv_result.get("rejection_reason", "OpenCV fail"))
            else:
                # Bonus for good quality
                score.opencv_score = (
                    (1.0 if opencv_result.get("single_bottle") else 0.3)
                    + (0.3 if opencv_result.get("upright") else 0.0)
                    + (0.2 if opencv_result.get("label_visible") else 0.0)
                    + min(opencv_result.get("sharpness_score", 0) * 0.2, 0.2)
                ) / 1.7

        # Text match from OCR
        if ocr_result:
            score.ocr_score = ocr_result.get("confidence", 0.0)
            text = ocr_result.get("text", "").lower()
            score.text_match_score = self._calculate_text_match(text, parsed_identity)

        # Vintage match
        if ocr_result and parsed_identity.get("vintage"):
            score.vintage_match_score = (
                1.0 if parsed_identity["vintage"] in text else 0.0
            )

        # VLM verdict
        if vlm_result:
            verdict = vlm_result.get("verdict", "NO")
            confidence = vlm_result.get("confidence", 0.0)
            if verdict == "YES":
                score.vlm_score = confidence
            elif verdict == "PARTIAL":
                score.vlm_score = confidence * 0.5
            else:
                score.vlm_score = 0.0

            if verdict == "NO" and confidence > 0.7:
                score.hard_fail = True
                score.fail_reasons.append("VLM confident NO")

        # Calculate overall score
        if score.hard_fail:
            score.overall_score = 0.0
        else:
            score.overall_score = (
                self.WEIGHTS["search_score"] * score.search_score
                + self.WEIGHTS["opencv_quality"] * score.opencv_score
                + self.WEIGHTS["text_match"] * score.text_match_score
                + self.WEIGHTS["vintage_match"] * score.vintage_match_score
                + self.WEIGHTS["ocr_confidence"] * score.ocr_score
                + self.WEIGHTS["vlm_verdict"] * score.vlm_score
            )

        return score

    def _calculate_text_match(self, text: str, identity: dict) -> float:
        """Calculate fuzzy text match score between OCR text and expected identity."""
        if not text:
            return 0.0

        scores = []
        identity_fields = [
            identity.get("producer", ""),
            identity.get("appellation", ""),
            identity.get("vineyard_or_cuvee", ""),
            identity.get("normalized_wine_name", ""),
        ]

        for field in identity_fields:
            if field:
                score = fuzz.partial_ratio(text, field.lower()) / 100.0
                scores.append(score)

        return max(scores) if scores else 0.0


class VoterScorer(BaseScorer):
    """Voter scoring engine for ensemble decision making (vine2 style)."""

    def score(
        self,
        candidate_url: str,
        parsed_identity: dict,
        votes: Optional[List[dict]] = None,
        opencv_result: Optional[dict] = None,
        **kwargs,
    ) -> CandidateScore:
        """
        Score based on multiple voter signals.

        Votes is a list of dicts with keys: verifier (str), verdict (str), confidence (float)
        """
        score = CandidateScore(url=candidate_url)

        # Hard fail on OpenCV
        if opencv_result and not opencv_result.get("opencv_pass", True):
            score.hard_fail = True
            score.fail_reasons.append("OpenCV hard fail")
            score.overall_score = 0.0
            return score

        if not votes:
            score.overall_score = 0.0
            return score

        # Collect votes
        yes_votes = []
        no_votes = []
        partial_votes = []

        for vote in votes:
            verdict = vote.get("verdict", "NO")
            confidence = vote.get("confidence", 0.0)

            if verdict == "YES":
                yes_votes.append(confidence)
            elif verdict == "NO":
                no_votes.append(confidence)
            elif verdict == "PARTIAL":
                partial_votes.append(confidence)

        # Decision rules
        # Unanimous YES wins
        if yes_votes and not no_votes:
            score.vlm_score = sum(yes_votes) / len(yes_votes)
            score.overall_score = 0.7 + score.vlm_score * 0.3
        # Any confident NO with high confidence triggers hard fail
        elif any(c > 0.7 for c in no_votes):
            score.hard_fail = True
            score.fail_reasons.append("Confident NO vote")
            score.overall_score = 0.0
        # Split decisions: weight by confidence
        elif yes_votes:
            yes_avg = sum(yes_votes) / len(yes_votes) if yes_votes else 0
            no_avg = sum(no_votes) / len(no_votes) if no_votes else 0
            if yes_avg > no_avg:
                score.vlm_score = yes_avg
                score.overall_score = 0.5 + yes_avg * 0.3
            else:
                score.overall_score = 0.3
        else:
            score.overall_score = 0.0

        return score


class ConsensusScorer(BaseScorer):
    """Consensus scorer requiring multiple confirmations."""

    def score(
        self,
        candidate_url: str,
        parsed_identity: dict,
        votes: Optional[List[dict]] = None,
        **kwargs,
    ) -> CandidateScore:
        """
        Require consensus among multiple verifiers.
        """
        score = CandidateScore(url=candidate_url)

        if not votes or len(votes) < 2:
            score.overall_score = 0.0
            return score

        # Require majority YES for consensus
        yes_count = sum(1 for v in votes if v.get("verdict") == "YES")
        no_count = sum(1 for v in votes if v.get("verdict") == "NO")
        partial_count = len(votes) - yes_count - no_count

        if yes_count > len(votes) / 2:
            # Majority YES - calculate average confidence
            confidences = [
                v.get("confidence", 0.0) for v in votes if v.get("verdict") == "YES"
            ]
            score.vlm_score = sum(confidences) / len(confidences)
            score.overall_score = 0.6 + score.vlm_score * 0.4
        elif no_count >= len(votes) / 2:
            score.hard_fail = True
            score.fail_reasons.append("Consensus NO")
            score.overall_score = 0.0
        elif yes_count > 0 and partial_count > 0:
            # Mixed - weighted partial
            score.overall_score = 0.4
        else:
            score.overall_score = 0.0

        return score
