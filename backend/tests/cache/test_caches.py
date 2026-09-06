import unittest
import time
from app.cache import (
    BaseCache,
    l1_cache,
    l2_retrieval_cache,
    l3_embedding_cache,
    make_l1_process_key,
    make_l2_retrieval_key,
    make_l3_embedding_key,
)


class TestCaches(unittest.TestCase):

    def setUp(self):
        l1_cache.clear()
        l2_retrieval_cache.clear()
        l3_embedding_cache.clear()

    def test_base_cache_lru_eviction(self):
        cache = BaseCache(max_size=3, default_ttl_seconds=60)
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        cache.set("k3", "v3")

        # Access k1 to make k2 the least recently used
        self.assertEqual(cache.get("k1"), "v1")

        # Adding k4 should evict k2
        cache.set("k4", "v4")
        self.assertIsNone(cache.get("k2"))
        self.assertEqual(cache.get("k1"), "v1")
        self.assertEqual(cache.get("k3"), "v3")
        self.assertEqual(cache.get("k4"), "v4")

        metrics = cache.get_metrics()
        self.assertEqual(metrics["evictions"], 1)

    def test_base_cache_ttl_expiration(self):
        cache = BaseCache(max_size=10, default_ttl_seconds=1)
        cache.set("k_fast", "quick_value", ttl_seconds=1)
        self.assertEqual(cache.get("k_fast"), "quick_value")
        
        # Wait 1.1s for expiration
        time.sleep(1.1)
        self.assertIsNone(cache.get("k_fast"))

    def test_l1_process_cache_deduplication(self):
        session_id = "sess_l1_test"
        query = "What is Section 79 of IT Act?"

        self.assertIsNone(l1_cache.get_response(session_id, query))

        mock_response = {"answer": "Intermediary safe harbour clause.", "score": 0.98}
        l1_cache.set_response(session_id, query, mock_response)

        # Immediate repeat should hit L1
        hit = l1_cache.get_response(session_id, query)
        self.assertIsNotNone(hit)
        self.assertEqual(hit["answer"], mock_response["answer"])

    def test_l2_retrieval_caching_and_hit_rate(self):
        query = "Article 21 Right to Privacy"
        top_k = 3
        mock_results = [{"act": "Constitution", "section": "21", "text": "Protection of life and personal liberty"}]

        self.assertIsNone(l2_retrieval_cache.get_tier1_results(query, top_k))

        l2_retrieval_cache.set_tier1_results(query, top_k, mock_results)

        hit = l2_retrieval_cache.get_tier1_results(query, top_k)
        self.assertIsNotNone(hit)
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0]["section"], "21")

        metrics = l2_retrieval_cache.get_metrics()
        self.assertGreater(metrics["hits"], 0)
        self.assertGreater(metrics["hit_rate"], 0.0)

    def test_l3_embedding_caching(self):
        text = "Information Technology Act 2000"
        model_name = "BAAI/bge-small-en"
        mock_vec = [0.12, -0.45, 0.88, 0.05]

        self.assertIsNone(l3_embedding_cache.get_embedding(text, model_name))

        l3_embedding_cache.set_embedding(text, model_name, mock_vec)

        cached_vec = l3_embedding_cache.get_embedding(text, model_name)
        self.assertIsNotNone(cached_vec)
        self.assertEqual(cached_vec, mock_vec)


if __name__ == "__main__":
    unittest.main()
