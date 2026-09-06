import time
import logging
from enum import Enum
from typing import Dict, Any, Optional
from app.config import settings

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "CLOSED"      # Normal operation: executions allowed
    OPEN = "OPEN"          # Tripped: step is temporarily disabled
    HALF_OPEN = "HALF_OPEN"# Trial recovery: single execution permitted to test health


class StepCircuitBreaker:
    """
    Circuit breaker keyed per step-type (Phase 09).
    If N consecutive failures occur for a step type (e.g. MCP tool calls or web scrapers),
    the step type is temporarily tripped to OPEN. The orchestrator can then safely degrade
    (e.g., fall back to local statutory retrieval only) rather than hanging or looping.
    """

    def __init__(
        self,
        failure_threshold: Optional[int] = None,
        recovery_seconds: Optional[float] = None
    ):
        self.failure_threshold = (
            failure_threshold
            if failure_threshold is not None
            else settings.orchestrator.circuit_breaker_failure_threshold
        )
        self.recovery_seconds = (
            recovery_seconds
            if recovery_seconds is not None
            else settings.orchestrator.circuit_breaker_recovery_seconds
        )
        # Structure per step_type: {state: CircuitState, failures: int, last_failure_time: float, trip_reason: str}
        self._states: Dict[str, Dict[str, Any]] = {}

    def _get_entry(self, step_type: str) -> Dict[str, Any]:
        if step_type not in self._states:
            self._states[step_type] = {
                "state": CircuitState.CLOSED,
                "consecutive_failures": 0,
                "last_failure_time": 0.0,
                "trip_reason": "",
            }
        return self._states[step_type]

    def can_execute(self, step_type: str) -> bool:
        """
        Evaluates whether an execution attempt for step_type is permitted.
        Returns True if CLOSED or if recovery cooldown has expired (transitioning to HALF_OPEN).
        Returns False if OPEN and cooldown is active.
        """
        entry = self._get_entry(step_type)
        state = entry["state"]

        if state == CircuitState.CLOSED:
            return True

        if state == CircuitState.OPEN:
            elapsed = time.time() - entry["last_failure_time"]
            if elapsed >= self.recovery_seconds:
                logger.info(
                    f"Circuit breaker for step '{step_type}' entering HALF_OPEN after {elapsed:.1f}s cooldown."
                )
                entry["state"] = CircuitState.HALF_OPEN
                return True
            logger.warning(
                f"Circuit breaker OPEN for step '{step_type}': execution blocked ({elapsed:.1f}s/{self.recovery_seconds}s cooldown). Reason: {entry.get('trip_reason')}"
            )
            return False

        if state == CircuitState.HALF_OPEN:
            return True

        return True

    def record_success(self, step_type: str) -> None:
        """Records a successful execution, resetting consecutive failures and closing circuit."""
        entry = self._get_entry(step_type)
        if entry["state"] != CircuitState.CLOSED:
            logger.info(f"Circuit breaker for step '{step_type}' recovered and CLOSED.")
        entry["state"] = CircuitState.CLOSED
        entry["consecutive_failures"] = 0
        entry["trip_reason"] = ""

    def record_failure(self, step_type: str, reason: str = "") -> bool:
        """
        Records a failed execution for step_type.
        Returns True if this failure tripped the circuit to OPEN, False otherwise.
        """
        entry = self._get_entry(step_type)
        entry["consecutive_failures"] += 1
        entry["last_failure_time"] = time.time()

        if entry["state"] == CircuitState.HALF_OPEN or entry["consecutive_failures"] >= self.failure_threshold:
            entry["state"] = CircuitState.OPEN
            entry["trip_reason"] = reason or f"Exceeded {self.failure_threshold} consecutive failures"
            logger.error(
                f"Circuit breaker TRIPPED to OPEN for step '{step_type}' after {entry['consecutive_failures']} consecutive failures. Cooldown: {self.recovery_seconds}s. Reason: {reason}"
            )
            return True

        return False

    def get_state(self, step_type: str) -> CircuitState:
        """Returns the current state for the given step type."""
        return self._get_entry(step_type)["state"]

    def reset(self, step_type: Optional[str] = None) -> None:
        """Manually resets circuit breaker state."""
        if step_type:
            if step_type in self._states:
                self._states[step_type] = {
                    "state": CircuitState.CLOSED,
                    "consecutive_failures": 0,
                    "last_failure_time": 0.0,
                    "trip_reason": "",
                }
        else:
            self._states.clear()

    def get_all_status(self) -> Dict[str, Any]:
        """Returns status of all tracked step types."""
        now = time.time()
        result = {}
        for step, entry in self._states.items():
            result[step] = {
                "state": entry["state"].value,
                "consecutive_failures": entry["consecutive_failures"],
                "last_failure_time": entry["last_failure_time"],
                "seconds_since_failure": round(now - entry["last_failure_time"], 1) if entry["last_failure_time"] > 0 else None,
                "trip_reason": entry["trip_reason"],
            }
        return result


circuit_breaker = StepCircuitBreaker()
