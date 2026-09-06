import logging
from typing import List, Dict, Any, Tuple, Optional

from app.security.output_validator import output_validator, OutputValidator
from app.config import settings

logger = logging.getLogger(__name__)


class Layer3OutputGuard:
    """
    Layer 3 Output Guard (Phase 07 Bridge).
    Delegates to OutputValidator for deterministic grounding, citation verification,
    and schema validation.
    """

    def __init__(self, jaccard_threshold: Optional[float] = None):
        self.jaccard_threshold = jaccard_threshold if jaccard_threshold is not None else settings.GROUNDING_OVERLAP_THRESHOLD
        self.validator = OutputValidator(grounding_threshold=self.jaccard_threshold)
        self.last_clean_answer: str = ""

    def check_grounding(self, answer: str, retrieved_chunks: List[Dict[str, Any]]) -> bool:
        score = self.validator.compute_grounding_score(answer, retrieved_chunks)
        threshold = self.jaccard_threshold
        return score >= threshold

    def verify_citation_existence(self, answer: str, retrieved_chunks: List[Dict[str, Any]]) -> bool:
        is_ok, _ = self.validator.verify_citations_exist(answer, retrieved_chunks)
        return is_ok

    def validate(self, answer: str, retrieved_chunks: List[Dict[str, Any]], system_prompt: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Validates output against Layer 3 rules.
        Returns:
            (is_valid, error_reason)
        """
        result = self.validator.validate_output(
            answer=answer,
            retrieved_chunks=retrieved_chunks,
            system_prompt=system_prompt
        )
        self.last_clean_answer = result.answer
        return result.is_safe, result.notice
