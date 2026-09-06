import unittest
from unittest.mock import patch
from app.runtime.router import model_router
from app.config import settings


class TestModelRouter(unittest.TestCase):

    def test_security_classification_is_deterministic(self):
        decision = model_router.route_task("security_classification")
        self.assertEqual(decision["method"], "deterministic")
        self.assertIn("deterministic", decision["reason"].lower())

    def test_citation_verification_is_deterministic(self):
        decision = model_router.route_task("citation_verification")
        self.assertEqual(decision["method"], "deterministic")

    def test_intent_routing_uses_minimum_tier(self):
        decision = model_router.route_task("intent_routing")
        self.assertEqual(decision["tier"], "minimum")
        self.assertEqual(decision["method"], "llm")
        self.assertTrue(len(decision["model_name"]) > 0)

    def test_query_reformulation_uses_minimum_tier(self):
        decision = model_router.route_task("query_reformulation")
        self.assertEqual(decision["tier"], "minimum")

    def test_summarization_complexity_scaling(self):
        # Short text should use minimum tier
        short_decision = model_router.route_task("summarization", hardware_tier="standard", text_length=500)
        self.assertEqual(short_decision["tier"], "minimum")

        # Long text with standard hardware tier should scale to standard tier
        long_decision = model_router.route_task("summarization", hardware_tier="standard", text_length=6000)
        self.assertEqual(long_decision["tier"], "standard")

    def test_legal_reasoning_hardware_dependent(self):
        min_decision = model_router.route_task("legal_reasoning", hardware_tier="minimum")
        self.assertEqual(min_decision["tier"], "minimum")

        std_decision = model_router.route_task("legal_reasoning", hardware_tier="standard")
        self.assertEqual(std_decision["tier"], "standard")

        prem_decision = model_router.route_task("legal_reasoning", hardware_tier="premium")
        self.assertEqual(prem_decision["tier"], "premium")

    def test_router_bypass_when_disabled(self):
        with patch.object(settings.model, "routing_enabled", False):
            decision = model_router.route_task("legal_reasoning")
            self.assertEqual(decision["tier"], "fallback")
            self.assertEqual(decision["model_name"], settings.model.fallback_model)


if __name__ == "__main__":
    unittest.main()
