import unittest
from unittest.mock import patch
from app.cache import l2_retrieval_cache
from app.config import settings


class TestCorpusInvalidation(unittest.TestCase):

    def setUp(self):
        l2_retrieval_cache.clear()

    def test_corpus_version_bump_invalidates_stale_l2_cache(self):
        query = "Bharatiya Nyaya Sanhita Section 69"
        top_k = 3
        v1_results = [{"act": "BNS", "section": "69", "text": "Sexual intercourse on false promise of marriage"}]

        # 1. Store under initial corpus version
        with patch.object(settings.performance, "corpus_version_hash", "v1.0.0_statutes_2026"):
            l2_retrieval_cache.set_tier1_results(query, top_k, v1_results)
            hit = l2_retrieval_cache.get_tier1_results(query, top_k)
            self.assertIsNotNone(hit)
            self.assertEqual(hit[0]["section"], "69")

        # 2. When corpus version is updated (e.g. re-ingestion in Stage 2/Phase 06 writes new version hash),
        # query with new corpus version MUST result in a cache miss
        with patch.object(settings.performance, "corpus_version_hash", "v1.1.0_statutes_amended_2026"):
            miss = l2_retrieval_cache.get_tier1_results(query, top_k)
            self.assertIsNone(miss, "Stale cache returned despite corpus version update!")


if __name__ == "__main__":
    unittest.main()
