import unittest
from app.eval.eval_harness import EvalHarness


class TestStage7EvalHarness(unittest.TestCase):
    def setUp(self):
        self.harness = EvalHarness()

    def test_load_benchmark_dataset(self):
        dataset = self.harness.load_dataset()
        self.assertTrue(len(dataset) > 0)
        self.assertIn("category", dataset[0])

    def test_evaluate_adversarial_security(self):
        sec = self.harness.evaluate_adversarial_security()
        self.assertIn("adversarial_accuracy", sec)
        self.assertTrue(sec["adversarial_accuracy"] >= 0.75)

    def test_evaluate_faithfulness_and_grounding(self):
        chunks = [{"act": "IT Act 2000", "section": "66", "text": "Section 66 governs computer offences."}]
        answer = "Under Section 66 of IT Act 2000, computer offences are illegal."
        res = self.harness.evaluate_faithfulness_and_grounding(answer, chunks)
        self.assertIn("faithfulness_score", res)
        self.assertTrue(res["faithfulness_score"] > 0.0)

    def test_run_full_eval_suite(self):
        suite_res = self.harness.run_full_eval_suite()
        self.assertEqual(suite_res["overall_status"], "PASSED")
        self.assertIn("faithfulness_metric", suite_res)
        self.assertIn("adversarial_injection_defense", suite_res)


if __name__ == "__main__":
    unittest.main()
