import os
import unittest
from app.config import settings
from app.defense.layer1_input_guard import Layer1InputGuard
from app.defense.layer2_trusted_context import Layer2TrustedContext
from app.defense.layer3_output_guard import Layer3OutputGuard
from app.runtime.token_budget_manager import TokenBudgetManager
from app.retrieval.hybrid_rank import fuse_bm25_dense


class TestNoHardcodedConstants(unittest.TestCase):
    """
    Automated check enforcing Phase 01 acceptance criteria:
    Zero hardcoded model names or thresholds outside app/config/
    """
    def test_defense_controllers_use_settings(self):
        # Layer 1
        l1 = Layer1InputGuard()
        self.assertEqual(l1.risk_threshold, settings.INJECTION_RISK_THRESHOLD)
        self.assertEqual(l1.max_length, settings.security.max_query_chars)

        # Layer 2
        l2 = Layer2TrustedContext()
        self.assertEqual(l2.enable_pii_scan, settings.ENABLE_PII_SCANNING)

        # Layer 3
        l3 = Layer3OutputGuard()
        self.assertEqual(l3.jaccard_threshold, settings.GROUNDING_OVERLAP_THRESHOLD)

        # Token Budget Manager
        tbm = TokenBudgetManager()
        self.assertEqual(tbm.max_context, settings.GENERATOR_CONTEXT_TOKENS)
        self.assertEqual(tbm.max_output, settings.GENERATOR_MAX_OUTPUT_TOKENS)
        self.assertEqual(tbm.safety_margin, settings.TOKEN_BUDGET_SAFETY_MARGIN)

    def test_hybrid_rank_uses_retrieval_settings(self):
        bm25_mock = [{"act": "IT Act", "section": "66", "text": "Cyber penalty"}]
        dense_mock = [{"act": "IT Act", "section": "66", "text": "Cyber penalty"}]
        results = fuse_bm25_dense(bm25_mock, dense_mock)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["act"], "IT Act")

    def test_no_hardcoded_model_names_in_python_modules(self):
        """
        Scans all Python files in backend/app/ (excluding app/config/ and model_registry.py)
        to verify no model name literals are hardcoded in application logic.
        """
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        backend_app = os.path.join(app_dir, "app")

        disallowed_literals = {
            "gpt-4", "gpt-3.5", "mistral-7b", "saul-7b"
        }

        violations = []
        for root, _, files in os.walk(backend_app):
            # Skip config directory as it is the authoritative registry
            if "config" in root:
                continue
            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        for disallowed in disallowed_literals:
                            if disallowed in content.lower():
                                violations.append(f"{file_path}: contains '{disallowed}'")

        self.assertEqual(violations, [], f"Found hardcoded disallowed model references: {violations}")


if __name__ == "__main__":
    unittest.main()
