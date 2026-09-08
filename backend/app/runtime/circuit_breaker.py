import time
import logging
from enum import Enum
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class FailureKind(str, Enum):
    CONNECT_ERROR = "connect_error"         # Daemon down or unreachable
    OOM_TIMEOUT = "oom_timeout"             # GPU/RAM OOM or inference timeout
    EMPTY_GENERATION = "empty_generation"   # Empty or whitespace-only generation
    MALFORMED_OUTPUT = "malformed_output"   # Output contract failure


class CircuitBreakerState(str, Enum):
    CLOSED = "CLOSED"         # Normal operation: local models receive requests
    OPEN = "OPEN"             # Tripped: local model blocked; route to cloud fallback
    HALF_OPEN = "HALF_OPEN"   # Cooldown elapsed: probing local model recovery


class CircuitBreaker:
    """
    Spec 02 — Per-Model Circuit Breaker State Machine.
    State Transitions:
      CLOSED --[3 consecutive {CONNECT_ERROR, OOM_TIMEOUT} within 120s]--> OPEN
      OPEN   --[60s cooldown elapsed]--> HALF_OPEN
      HALF_OPEN --[probe / generation succeeds]--> CLOSED
      HALF_OPEN --[probe / generation fails]--> OPEN
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        window_seconds: float = 120.0,
        cooldown_seconds: float = 60.0
    ):
        self.failure_threshold = failure_threshold
        self.window_seconds = window_seconds
        self.cooldown_seconds = cooldown_seconds

        # Per-model tracking: {model_name: {"state": CircuitBreakerState, "failures": [timestamps], "opened_at": float | None}}
        self._models: Dict[str, Dict[str, Any]] = {}

    def _get_entry(self, model: str) -> Dict[str, Any]:
        normalized = (model or "default").lower().strip()
        if normalized not in self._models:
            self._models[normalized] = {
                "state": CircuitBreakerState.CLOSED,
                "failures": [],
                "opened_at": None,
                "last_failure_reason": None,
                "last_failure_kind": None,
                "consecutive_failures": 0,
            }
        return self._models[normalized]

    def get_state(self, model: str) -> CircuitBreakerState:
        """
        Calculates active state for model, transitioning OPEN -> HALF_OPEN if cooldown elapsed.
        """
        entry = self._get_entry(model)
        now = time.time()

        if entry["state"] == CircuitBreakerState.OPEN:
            if entry["opened_at"] and (now - entry["opened_at"] >= self.cooldown_seconds):
                entry["state"] = CircuitBreakerState.HALF_OPEN
                logger.info(f"Circuit breaker for model '{model}' entered HALF_OPEN state (probing recovery).")
                return CircuitBreakerState.HALF_OPEN

        return entry["state"]

    def can_execute(self, model: str) -> bool:
        """
        Returns True if the local model is permitted to execute requests.
        Returns False if the circuit is actively OPEN.
        """
        state = self.get_state(model)
        return state in (CircuitBreakerState.CLOSED, CircuitBreakerState.HALF_OPEN)

    def record_success(self, model: str) -> None:
        """
        Resets failure counters and restores state to CLOSED.
        """
        entry = self._get_entry(model)
        old_state = entry["state"]
        entry["state"] = CircuitBreakerState.CLOSED
        entry["failures"] = []
        entry["consecutive_failures"] = 0
        entry["opened_at"] = None
        if old_state != CircuitBreakerState.CLOSED:
            logger.info(f"Circuit breaker for model '{model}' recovered and is now CLOSED.")

    def record_failure(
        self,
        model: str,
        kind: FailureKind = FailureKind.CONNECT_ERROR,
        reason: str = ""
    ) -> CircuitBreakerState:
        """
        Records failure event. If 3 consecutive CONNECT_ERROR or OOM_TIMEOUT within window, trips to OPEN.
        """
        entry = self._get_entry(model)
        now = time.time()

        entry["last_failure_kind"] = kind.value
        entry["last_failure_reason"] = reason or kind.value

        if entry["state"] == CircuitBreakerState.HALF_OPEN:
            # Failed while probing in HALF_OPEN -> immediately reopen
            entry["state"] = CircuitBreakerState.OPEN
            entry["opened_at"] = now
            logger.warning(f"Circuit breaker probe failed for model '{model}'. Reopened circuit.")
            return CircuitBreakerState.OPEN

        # Clean old failures outside window
        entry["failures"] = [ts for ts in entry["failures"] if now - ts <= self.window_seconds]
        
        # Only count severe infrastructure errors toward tripping breaker
        if kind in (FailureKind.CONNECT_ERROR, FailureKind.OOM_TIMEOUT):
            entry["failures"].append(now)
            entry["consecutive_failures"] += 1

            if len(entry["failures"]) >= self.failure_threshold:
                entry["state"] = CircuitBreakerState.OPEN
                entry["opened_at"] = now
                logger.error(
                    f"Circuit breaker TRIPPED to OPEN for model '{model}'! "
                    f"({len(entry['failures'])} severe failures within {self.window_seconds}s)."
                )

        return entry["state"]

    def reset(self, model: Optional[str] = None) -> None:
        """Resets breaker state for a specific model or all models."""
        if model:
            normalized = model.lower().strip()
            if normalized in self._models:
                del self._models[normalized]
        else:
            self._models.clear()

    def get_status(self) -> Dict[str, Any]:
        """
        Returns full circuit breaker telemetry for /runtime/status and UI.
        """
        now = time.time()
        summary = {}
        for m_name, entry in self._models.items():
            state = self.get_state(m_name)
            remaining_cooldown = 0.0
            if state == CircuitBreakerState.OPEN and entry["opened_at"]:
                remaining_cooldown = max(0.0, self.cooldown_seconds - (now - entry["opened_at"]))

            summary[m_name] = {
                "state": state.value,
                "consecutive_failures": entry["consecutive_failures"],
                "last_failure_kind": entry.get("last_failure_kind"),
                "last_failure_reason": entry.get("last_failure_reason"),
                "cooldown_remaining_seconds": round(remaining_cooldown, 1),
                "is_open": state == CircuitBreakerState.OPEN
            }
        return summary


circuit_breaker = CircuitBreaker()
