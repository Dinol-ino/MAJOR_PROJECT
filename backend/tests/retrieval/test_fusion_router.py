import unittest
from unittest.mock import patch
from app.retrieval.fusion_router import fusion_router, FusionRouter
from app.config import settings


class TestFusionRouter(unittest.TestCase):

    def test_classify_structural_queries(self):
        self.assertEqual(fusion_router.classify_query("What does Section 302 IPC say?"), "pageindex")
        self.assertEqual(fusion_router.classify_query("Explain Sec. 420 of the Penal Code"), "pageindex")
        self.assertEqual(fusion_router.classify_query("Protection under Article 21"), "pageindex")
        self.assertEqual(fusion_router.classify_query("Procedure under Chapter IV"), "pageindex")
        self.assertEqual(fusion_router.classify_query("Injunction under Order 39 Rule 1 CPC"), "pageindex")

    def test_classify_semantic_queries(self):
        self.assertEqual(fusion_router.classify_query("tenant rights when facing unfair eviction"), "hybrid")
        self.assertEqual(fusion_router.classify_query("bail conditions in economic fraud matters"), "hybrid")
        self.assertEqual(fusion_router.classify_query("how to file a consumer complaint for defective goods"), "hybrid")

    def test_classify_multi_hop_both_queries(self):
        self.assertEqual(
            fusion_router.classify_query("What are the rights and grounds for bail under Section 437 CrPC?"),
            "both"
        )
        self.assertEqual(
            fusion_router.classify_query("Explain the difference between Section 299 and Section 300 jurisprudence"),
            "both"
        )

    def test_fusion_router_disabled_fallback(self):
        with patch.object(settings.retrieval, "fusion_routing_enabled", False):
            self.assertEqual(fusion_router.classify_query("Section 302 IPC"), "hybrid")

    def test_execute_pageindex_lookup(self):
        corpus = [
            {
                "act": "Indian Penal Code",
                "text": "CHAPTER XVI\nOF OFFENCES AFFECTING THE HUMAN BODY\nSection 300 Murder\nExcept in the cases hereinafter excepted culpable homicide is murder.\nSection 302 Punishment for murder\nWhoever commits murder shall be punished with death or imprisonment for life."
            }
        ]
        results = fusion_router.execute_pageindex_lookup("What is Section 302?", corpus_documents=corpus)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["act"], "Indian Penal Code")
        self.assertEqual(results[0]["section"], "Section 302")
        self.assertIn("Whoever commits murder", results[0]["text"])
        self.assertEqual(results[0]["retrieval_path"], "pageindex")


if __name__ == "__main__":
    unittest.main()
