import logging
from typing import Tuple, Optional, Dict, Any
from app.security.injection_gate import InjectionGate, injection_gate
from app.config import settings

logger = logging.getLogger(__name__)


class Layer1InputGuard:
    """
    Layer 1 Input Guard (Phase 07 Bridge).
    Delegates to the hard-gate InjectionGate validator.
    """

    def __init__(self, max_length: Optional[int] = None, risk_threshold: Optional[float] = None):
        self.max_length = max_length if max_length is not None else settings.security.max_query_chars
        self.risk_threshold = risk_threshold if risk_threshold is not None else settings.INJECTION_RISK_THRESHOLD
        self.gate = InjectionGate(max_length=self.max_length, risk_threshold=self.risk_threshold)

    def get_query_hash(self, message: str) -> str:
        return self.gate.compute_query_hash(message)

    def validate_with_score(self, message: str) -> Tuple[bool, Optional[str], float, str]:
        return self.gate.evaluate_query(message)

    def validate(self, message: str) -> Tuple[bool, Optional[str]]:
        return self.gate.validate(message)
