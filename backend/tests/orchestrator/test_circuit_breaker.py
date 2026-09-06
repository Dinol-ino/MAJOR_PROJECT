import unittest
import time
from app.orchestrator.circuit_breaker import StepCircuitBreaker, CircuitState


class TestStepCircuitBreaker(unittest.TestCase):

    def setUp(self):
        self.cb = StepCircuitBreaker(failure_threshold=3, recovery_seconds=0.05)

    def test_initial_state_is_closed(self):
        self.assertTrue(self.cb.can_execute("TOOL_CALL"))
        self.assertEqual(self.cb.get_state("TOOL_CALL"), CircuitState.CLOSED)

    def test_consecutive_failures_trips_to_open(self):
        self.cb.record_failure("TOOL_CALL", reason="Timeout")
        self.assertEqual(self.cb.get_state("TOOL_CALL"), CircuitState.CLOSED)
        self.assertTrue(self.cb.can_execute("TOOL_CALL"))

        self.cb.record_failure("TOOL_CALL", reason="Timeout")
        self.assertEqual(self.cb.get_state("TOOL_CALL"), CircuitState.CLOSED)

        # 3rd failure trips the circuit
        tripped = self.cb.record_failure("TOOL_CALL", reason="Timeout")
        self.assertTrue(tripped)
        self.assertEqual(self.cb.get_state("TOOL_CALL"), CircuitState.OPEN)
        self.assertFalse(self.cb.can_execute("TOOL_CALL"))

    def test_cooldown_transitions_to_half_open_and_success_closes(self):
        # Trip circuit
        self.cb.record_failure("TOOL_CALL")
        self.cb.record_failure("TOOL_CALL")
        self.cb.record_failure("TOOL_CALL")
        self.assertEqual(self.cb.get_state("TOOL_CALL"), CircuitState.OPEN)

        # Wait for cooldown
        time.sleep(0.06)

        # Next check should allow trial execution (HALF_OPEN)
        self.assertTrue(self.cb.can_execute("TOOL_CALL"))
        self.assertEqual(self.cb.get_state("TOOL_CALL"), CircuitState.HALF_OPEN)

        # Success closes circuit
        self.cb.record_success("TOOL_CALL")
        self.assertEqual(self.cb.get_state("TOOL_CALL"), CircuitState.CLOSED)
        self.assertTrue(self.cb.can_execute("TOOL_CALL"))

    def test_step_isolation(self):
        # Tripping TOOL_CALL does not affect RETRIEVE
        self.cb.record_failure("TOOL_CALL")
        self.cb.record_failure("TOOL_CALL")
        self.cb.record_failure("TOOL_CALL")
        self.assertEqual(self.cb.get_state("TOOL_CALL"), CircuitState.OPEN)
        self.assertEqual(self.cb.get_state("RETRIEVE"), CircuitState.CLOSED)
        self.assertTrue(self.cb.can_execute("RETRIEVE"))


if __name__ == "__main__":
    unittest.main()
