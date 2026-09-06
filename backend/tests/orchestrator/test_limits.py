import unittest
import time
from app.orchestrator.limits import (
    ExecutionBudget,
    StepLimitExceeded,
    ToolCallLimitExceeded,
    TokenLimitExceeded,
    TimeLimitExceeded,
    DocLimitExceeded,
    NetworkLimitExceeded,
    RetryBudgetExceeded,
)


class TestOrchestratorLimits(unittest.TestCase):

    def test_step_limit_breach(self):
        budget = ExecutionBudget(max_steps=3)
        budget.record_step() # 1
        budget.record_step() # 2
        budget.record_step() # 3
        with self.assertRaises(StepLimitExceeded):
            budget.record_step() # 4 -> raises

    def test_tool_call_limit_breach(self):
        budget = ExecutionBudget(max_tool_calls=2)
        budget.record_tool_call() # 1
        budget.record_tool_call() # 2
        with self.assertRaises(ToolCallLimitExceeded):
            budget.record_tool_call() # 3 -> raises

    def test_token_limit_breach(self):
        budget = ExecutionBudget(max_tokens=1000)
        budget.record_tokens(600)
        with self.assertRaises(TokenLimitExceeded):
            budget.record_tokens(500) # 1100 -> raises

    def test_doc_limit_breach(self):
        budget = ExecutionBudget(max_retrieved_docs=5)
        budget.record_docs(4)
        with self.assertRaises(DocLimitExceeded):
            budget.record_docs(3) # 7 -> raises

    def test_network_limit_breach(self):
        budget = ExecutionBudget(max_network_requests=2)
        budget.record_network(2)
        with self.assertRaises(NetworkLimitExceeded):
            budget.record_network(1) # 3 -> raises

    def test_retry_budget_breach(self):
        budget = ExecutionBudget(retry_budget=1)
        budget.record_retry() # 1
        with self.assertRaises(RetryBudgetExceeded):
            budget.record_retry() # 2 -> raises

    def test_time_limit_breach(self):
        budget = ExecutionBudget(max_execution_time_seconds=0.01)
        time.sleep(0.02)
        with self.assertRaises(TimeLimitExceeded):
            budget.check_time()

    def test_budget_snapshot(self):
        budget = ExecutionBudget(max_steps=5, max_tokens=2000)
        budget.record_step()
        budget.record_tokens(350)
        snap = budget.snapshot()
        self.assertEqual(snap["steps_taken"], 1)
        self.assertEqual(snap["max_steps"], 5)
        self.assertEqual(snap["tokens_used"], 350)
        self.assertIn("elapsed_seconds", snap)


if __name__ == "__main__":
    unittest.main()
