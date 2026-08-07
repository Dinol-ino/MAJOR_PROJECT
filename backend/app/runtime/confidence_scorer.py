from typing import List, Dict, Any
from app.runtime.hallucination_detector import HallucinationReport

class ConfidenceScorer:
    """
    Computes a 0.0 - 1.0 confidence score for the generated response based on:
    - Average chunk trust score
    - Retrieval hit verification
    - Hallucination signals
    """
    def score(self, answer: str, chunks: List[Dict[str, Any]], hallucination_report: HallucinationReport) -> float:
        if not chunks:
            return 0.1

        # Component 1: Average trust score of retrieved chunks (weight: 0.5)
        trust_scores = [c.get("trust_score", 0.5) for c in chunks if c.get("trust_score") is not None]
        avg_trust = (sum(trust_scores) / len(trust_scores)) if trust_scores else 0.5

        # Component 2: Retrieval presence bonus (weight: 0.3)
        retrieval_bonus = 0.3 if len(chunks) > 0 else 0.0

        # Component 3: Hallucination penalty (weight: 0.2)
        penalty = len(hallucination_report.signals) * 0.1
        hallucination_factor = max(0.0, 0.2 - penalty)

        final_score = (0.5 * avg_trust) + retrieval_bonus + hallucination_factor
        return round(min(1.0, max(0.0, final_score)), 2)
