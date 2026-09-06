import unittest
import tempfile
import shutil
import os
from app.retrieval.hybrid_rank import fuse_bm25_dense
from app.retrieval.pageindex import PageIndexBuilder
from app.ingestion.chunker import SectionAwareChunker
from app.ingestion.pdf_extract import PDFExtractor
from app.retrieval.tier1_law import Tier1LawRetrieval
from app.retrieval.tier2_user import Tier2UserRetrieval

class TestRetrieval(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        import gc
        gc.collect()
        shutil.rmtree(self.test_dir, ignore_errors=True)

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
        self.assertEqual(fused[0]["section"], "66")

    def test_page_index_builder(self):
        builder = PageIndexBuilder()
        sample_text = (
            "CHAPTER I - PRELIMINARY\n"
            "Section 1 Short title\n"
            "This Act may be called the IT Act.\n"
            "Section 2 Definitions\n"
            "In this Act, unless the context otherwise requires...\n"
            "CHAPTER II - OFFENCES\n"
            "Section 66 Computer crimes\n"
            "Any computer crime will be punished."
        )
        tree = builder.build_tree_from_text(sample_text)
        self.assertIn("Chapter I - PRELIMINARY", tree["chapters"])
        self.assertIn("Chapter II - OFFENCES", tree["chapters"])
        self.assertIn("1", tree["chapters"]["Chapter I - PRELIMINARY"]["sections"])
        self.assertIn("66", tree["chapters"]["Chapter II - OFFENCES"]["sections"])

        sections = builder.extract_section_headers(sample_text)
        self.assertEqual(len(sections), 3)
        self.assertEqual(sections[0]["section"], "1")
        self.assertIn("IT Act", sections[0]["text"])

    def test_section_aware_chunker(self):
        chunker = SectionAwareChunker(default_act_name="IT Act")
        sample_text = (
            "Section 66 Computer crimes\n"
            "Penalty details for computer offences."
        )
        chunks = chunker.chunk_document(sample_text)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["act"], "IT Act")
        self.assertEqual(chunks[0]["section"], "66")
        self.assertIn("Penalty details", chunks[0]["text"])

        # Fallback test for un-sectioned text
        fallback_text = "Some random text without any section headers. Just normal sentences. " * 30
        chunks_fallback = chunker.chunk_document(fallback_text)
        self.assertTrue(len(chunks_fallback) > 1)
        self.assertEqual(chunks_fallback[0]["section"], "Chunk 1")


    def test_pdf_extractor_limits(self):
        # Create a small dummy text file (pretending it's a PDF) to test size limit check
        temp_file = os.path.join(self.test_dir, "test.pdf")
        with open(temp_file, "w") as f:
            f.write("A" * 1024 * 1024 * 2) # 2 MB
            
        extractor = PDFExtractor(max_size_mb=1, max_pages=10)
        with self.assertRaises(ValueError) as ctx:
            extractor.extract_text(temp_file)
        self.assertIn("exceeds size limit", str(ctx.exception))

    def test_retrievers_integration(self):
        # Initialize retrievers using temporary directory for ChromaDB storage
        t1 = Tier1LawRetrieval(self.test_dir)
        t1.bm25_index.clear()
        t2 = Tier2UserRetrieval(self.test_dir)
        
        # Verify empty collections return empty lists
        self.assertEqual(t1.query("unauthorized access"), [])
        self.assertEqual(t2.query("session_1", "unauthorized access"), [])

        # Add mock documents via add_document to synchronize both Chroma and BM25
        t1.add_document("doc1", "Section 43: Unauthorized access to computer network is illegal.", {"act": "IT Act", "section": "43"})
        t1.add_document("doc2", "Section 66: Computer related offences penalty guidelines.", {"act": "IT Act", "section": "66"})

        results = t1.query("penalty guidelines", top_k=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["section"], "66")
        self.assertEqual(results[0]["act"], "IT Act")

        # Verify BM25 caching works on subsequent query call
        results_cached = t1.query("penalty guidelines", top_k=1)
        self.assertEqual(len(results_cached), 1)
        self.assertEqual(results_cached[0]["section"], "66")

        # Tier-2 User Uploads
        t2.add_documents("session_123", "contract.pdf", "Section 1 governs the payment agreement.\nSection 2 governs liability limits.")
        
        # Test query in same session
        res_user = t2.query("session_123", "liability limits", top_k=1)
        self.assertEqual(len(res_user), 1)
        self.assertEqual(res_user[0]["section"], "2")
        
        # Test query in different session (should be empty/isolated)
        res_diff_user = t2.query("session_abc", "liability limits", top_k=1)
        self.assertEqual(res_diff_user, [])

    def test_corpus_pipeline_diff(self):
        from app.ingestion.corpus_pipeline import CorpusPipeline
        pipeline = CorpusPipeline()
        doc_id = "statute_sec_66"
        initial_text = "Section 66 governs computer related offences with fine up to 5 lakh rupees."
        
        res1 = pipeline.process_and_verify(doc_id, initial_text)
        self.assertFalse(res1["has_diff"])
        self.assertFalse(res1["flagged_for_review"])

        # Re-processing unchanged text should produce no diff
        res2 = pipeline.process_and_verify(doc_id, initial_text)
        self.assertFalse(res2["has_diff"])

        # Processing modified text should produce exactly one flagged diff
        modified_text = "Section 66 governs computer related offences with fine up to 10 lakh rupees."
        res3 = pipeline.process_and_verify(doc_id, modified_text)
        self.assertTrue(res3["has_diff"])
        self.assertTrue(res3["flagged_for_review"])

if __name__ == "__main__":
    unittest.main()


