import unittest
from app.retrieval.hybrid_rank import fuse_bm25_dense

class TestRetrieval(unittest.TestCase):
    def test_rrf_fusion(self):
        bm25 = [
            {"act": "IT Act", "section": "66", "text": "Section 66 governs computer crimes.", "score": 10.5},
            {"act": "IT Act", "section": "43", "text": "Section 43 governs unauthorized access.", "score": 5.2}
        ]
        dense = [
            {"act": "IT Act", "section": "66", "text": "Section 66 governs computer crimes.", "score": 0.85},
            {"act": "IT Act", "section": "67", "text": "Section 67 governs publishing obscene material.", "score": 0.72}
        ]
        
        fused = fuse_bm25_dense(bm25, dense, top_k=2)
        
        self.assertEqual(len(fused), 2)
        # Section 66 should rank first since it appeared in both rankings
        self.assertEqual(fused[0]["section"], "66")

if __name__ == "__main__":
    unittest.main()
