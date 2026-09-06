import unittest
from app.cache import (
    l1_cache,
    l2_retrieval_cache,
    make_l1_process_key,
    make_l2_retrieval_key,
)


class TestCacheIsolation(unittest.TestCase):

    def setUp(self):
        l1_cache.clear()
        l2_retrieval_cache.clear()

    def test_l1_cross_session_isolation(self):
        query = "Confidential Client Tax Summary"
        session_a = "session_client_alpha"
        session_b = "session_client_beta"

        # Key construction incorporates session_id
        key_a = make_l1_process_key(session_a, query)
        key_b = make_l1_process_key(session_b, query)
        self.assertNotEqual(key_a, key_b)

        # Set response for Session A
        l1_cache.set_response(session_a, query, {"answer": "Alpha confidential tax data."})

        # Session B querying the same text MUST NOT get Session A's cached response
        hit_b = l1_cache.get_response(session_b, query)
        self.assertIsNone(hit_b)

        # Session A querying the same text gets the cached response
        hit_a = l1_cache.get_response(session_a, query)
        self.assertIsNotNone(hit_a)
        self.assertEqual(hit_a["answer"], "Alpha confidential tax data.")

    def test_l2_cross_user_tier2_isolation(self):
        query = "Show undisclosed patent claim 3"
        user_a = "lawyer_firm_a"
        user_b = "lawyer_firm_b"
        session_a = "sess_patent_a"
        session_b = "sess_patent_b"
        top_k = 3

        # Key construction includes user_id and session_id
        key_a = make_l2_retrieval_key(
            query=query,
            top_k=top_k,
            corpus_version="v1.0.0",
            tier="tier2",
            user_id=user_a,
            session_id=session_a
        )
        key_b = make_l2_retrieval_key(
            query=query,
            top_k=top_k,
            corpus_version="v1.0.0",
            tier="tier2",
            user_id=user_b,
            session_id=session_b
        )
        self.assertNotEqual(key_a, key_b)

        # User A caches private document results
        mock_a_results = [{"act": "Patent A", "section": "3", "text": "Proprietary design specs"}]
        l2_retrieval_cache.set_tier2_results(
            query=query,
            top_k=top_k,
            user_id=user_a,
            session_id=session_a,
            results=mock_a_results
        )

        # User B querying exact same query MUST NOT hit User A's cache
        hit_b = l2_retrieval_cache.get_tier2_results(
            query=query,
            top_k=top_k,
            user_id=user_b,
            session_id=session_b
        )
        self.assertIsNone(hit_b)

        # User A gets their own cached results
        hit_a = l2_retrieval_cache.get_tier2_results(
            query=query,
            top_k=top_k,
            user_id=user_a,
            session_id=session_a
        )
        self.assertIsNotNone(hit_a)
        self.assertEqual(hit_a[0]["act"], "Patent A")


if __name__ == "__main__":
    unittest.main()
