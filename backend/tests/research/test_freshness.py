import unittest
import time
from app.research.freshness import freshness_detector, FreshnessResult


class TestFreshnessDetector(unittest.TestCase):

    def test_query_with_freshness_keywords_triggers_flag(self):
        res: FreshnessResult = freshness_detector.detect("What is the latest amendment to Section 302 IPC in 2024?")
        self.assertTrue(res.requires_freshness)
        self.assertEqual(res.recommended_source_category, "CURRENT_LAW")
        self.assertEqual(res.target_statute_hint, "Indian Penal Code, 1860")

    def test_query_about_bns_replacement(self):
        res: FreshnessResult = freshness_detector.detect("Is IPC replaced by BNS 2023?")
        self.assertTrue(res.requires_freshness)
        self.assertIn("Bharatiya Nyaya Sanhita", res.target_statute_hint or "")

    def test_settled_statutory_query_does_not_trigger_freshness(self):
        res: FreshnessResult = freshness_detector.detect("What are the elements of theft under Section 378?")
        self.assertFalse(res.requires_freshness)

    def test_stale_corpus_metadata_triggers_freshness(self):
        # Metadata verified 200 days ago (> 90 days threshold)
        old_timestamp = time.time() - (200 * 86400)
        stale_meta = [
            {"act": "Indian Penal Code", "section": "Section 302", "last_verified_at": old_timestamp}
        ]
        res: FreshnessResult = freshness_detector.detect(
            query="Explain punishment for murder under Section 302",
            local_metadata=stale_meta
        )
        self.assertTrue(res.requires_freshness)
        self.assertIn("last verified", res.reason)

    def test_superseded_metadata_flag_triggers_freshness(self):
        superseded_meta = [
            {"act": "Indian Penal Code", "is_superseded": True, "superseded_by": "Bharatiya Nyaya Sanhita, 2023"}
        ]
        res: FreshnessResult = freshness_detector.detect(
            query="Define criminal conspiracy",
            local_metadata=superseded_meta
        )
        self.assertTrue(res.requires_freshness)
        self.assertIn("superseded", res.reason)


if __name__ == "__main__":
    unittest.main()
