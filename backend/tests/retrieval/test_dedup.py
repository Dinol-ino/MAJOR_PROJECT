import unittest
from app.retrieval.fusion_router import deduplicate_chunks, calculate_jaccard_similarity


class TestChunkDeduplication(unittest.TestCase):

    def test_jaccard_similarity(self):
        text_a = "Whoever commits murder shall be punished with death or imprisonment for life"
        text_b = "Whoever commits murder shall be punished with death or imprisonment for life and fine"
        sim = calculate_jaccard_similarity(text_a, text_b)
        self.assertGreater(sim, 0.8)

    def test_deduplicate_identical_chunks(self):
        chunks = [
            {"act": "IPC", "section": "302", "text": "Punishment for murder shall be death or life imprisonment.", "score": 0.95},
            {"act": "IPC Amendment", "section": "302", "text": "Punishment for murder shall be death or life imprisonment.", "score": 0.90},
            {"act": "CrPC", "section": "154", "text": "Information in cognizable cases shall be reduced to writing.", "score": 0.85},
        ]
        deduped = deduplicate_chunks(chunks, similarity_threshold=0.85)
        self.assertEqual(len(deduped), 2)
        self.assertEqual(deduped[0]["act"], "IPC")
        self.assertEqual(deduped[1]["act"], "CrPC")

    def test_deduplicate_near_identical_chunks(self):
        chunks = [
            {"act": "Bare Act", "section": "420", "text": "Cheating and dishonestly inducing delivery of property punishable with 7 years imprisonment.", "score": 0.9},
            {"act": "Annotated Act", "section": "420", "text": "Cheating and dishonestly inducing delivery of property punishable with seven years imprisonment.", "score": 0.8},
        ]
        deduped = deduplicate_chunks(chunks, similarity_threshold=0.80)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["act"], "Bare Act")


if __name__ == "__main__":
    unittest.main()
