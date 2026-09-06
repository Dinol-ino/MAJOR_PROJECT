import unittest
from app.retrieval.metrics import (
    calculate_recall_at_k,
    calculate_precision_at_k,
    calculate_mrr,
    calculate_ndcg_at_k,
    calculate_citation_hit_rate,
    run_benchmark
)


class TestRetrievalMetrics(unittest.TestCase):

    def test_recall_at_k(self):
        retrieved = ["doc1", "doc2", "doc3", "doc4", "doc5"]
        ground_truth = ["doc2", "doc5", "doc9"]
        
        # In top 3: only doc2 is present (1/3)
        r3 = calculate_recall_at_k(retrieved, ground_truth, k=3)
        self.assertAlmostEqual(r3, 1.0 / 3.0)

        # In top 5: doc2 and doc5 are present (2/3)
        r5 = calculate_recall_at_k(retrieved, ground_truth, k=5)
        self.assertAlmostEqual(r5, 2.0 / 3.0)

    def test_precision_at_k(self):
        retrieved = ["doc1", "doc2", "doc3", "doc4", "doc5"]
        ground_truth = ["doc2", "doc4"]

        # In top 5: doc2 and doc4 are present (2/5 = 0.4)
        p5 = calculate_precision_at_k(retrieved, ground_truth, k=5)
        self.assertEqual(p5, 0.4)

    def test_mrr(self):
        # First relevant doc is at rank 2 -> MRR = 1/2 = 0.5
        retrieved = ["doc1", "doc2", "doc3"]
        ground_truth = ["doc2", "doc3"]
        self.assertEqual(calculate_mrr(retrieved, ground_truth), 0.5)

        # First relevant doc is at rank 1 -> MRR = 1.0
        retrieved = ["doc2", "doc1", "doc3"]
        self.assertEqual(calculate_mrr(retrieved, ground_truth), 1.0)

    def test_ndcg_at_k(self):
        retrieved = ["doc1", "doc2", "doc3"]
        ground_truth = ["doc1", "doc2"]
        ndcg = calculate_ndcg_at_k(retrieved, ground_truth, k=3)
        self.assertEqual(ndcg, 1.0)  # Perfect ordering of relevant docs

    def test_citation_hit_rate(self):
        retrieved_chunks = [
            {"act": "Indian Penal Code", "section": "Section 302", "text": "..."},
            {"act": "Code of Criminal Procedure", "section": "Section 154", "text": "..."}
        ]
        expected = [
            ("Indian Penal Code", "Section 302"),
            ("Code of Criminal Procedure", "Section 154")
        ]
        hit_rate = calculate_citation_hit_rate(retrieved_chunks, expected)
        self.assertEqual(hit_rate, 1.0)

    def test_run_benchmark(self):
        summary = run_benchmark()
        self.assertIn("recall_at_5", summary)
        self.assertIn("precision_at_5", summary)
        self.assertIn("mrr", summary)
        self.assertIn("ndcg_at_5", summary)
        self.assertIn("citation_hit_rate", summary)
        self.assertGreater(summary["recall_at_5"], 0.8)


if __name__ == "__main__":
    unittest.main()
