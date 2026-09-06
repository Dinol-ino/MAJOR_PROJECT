import unittest
from app.mcp.policy_engine import policy_engine, PolicyDecision


class TestMCPPolicyEngine(unittest.TestCase):

    def test_authorized_offline_tool_passes_in_offline_mode(self):
        decision = policy_engine.evaluate(
            tool_name="local_statute_search",
            current_mode="OFFLINE",
            call_count_in_request=0
        )
        self.assertTrue(decision.is_allowed)
        self.assertEqual(decision.category, "LOCAL_RETRIEVAL")
        self.assertEqual(decision.required_mode, "OFFLINE")

    def test_online_required_tool_blocked_in_offline_mode(self):
        decision = policy_engine.evaluate(
            tool_name="live_statute_checker",
            current_mode="OFFLINE",
            call_count_in_request=0
        )
        self.assertFalse(decision.is_allowed)
        self.assertEqual(decision.category, "CURRENT_LAW")
        self.assertIn("requires ONLINE mode", decision.reason)

    def test_online_required_tool_passes_in_online_mode(self):
        decision = policy_engine.evaluate(
            tool_name="live_statute_checker",
            current_mode="ONLINE",
            call_count_in_request=0
        )
        self.assertTrue(decision.is_allowed)
        self.assertEqual(decision.category, "CURRENT_LAW")

    def test_unauthorized_tool_call_is_rejected(self):
        decision = policy_engine.evaluate(
            tool_name="arbitrary_unauthorized_tool",
            current_mode="OFFLINE",
            call_count_in_request=0
        )
        self.assertFalse(decision.is_allowed)
        self.assertEqual(decision.category, "UNAUTHORIZED")
        self.assertIn("not in the authorized MCP permission allowlist", decision.reason)

    def test_server_denied_tool_is_rejected(self):
        decision = policy_engine.evaluate(
            tool_name="delete_project",
            current_mode="OFFLINE",
            call_count_in_request=0
        )
        self.assertFalse(decision.is_allowed)
        self.assertIn("explicitly denied", decision.reason)

    def test_request_call_budget_quota_exceeded(self):
        # local_statute_search allows 10 calls
        decision = policy_engine.evaluate(
            tool_name="local_statute_search",
            current_mode="OFFLINE",
            call_count_in_request=10
        )
        self.assertFalse(decision.is_allowed)
        self.assertIn("quota exceeded", decision.reason)


if __name__ == "__main__":
    unittest.main()
