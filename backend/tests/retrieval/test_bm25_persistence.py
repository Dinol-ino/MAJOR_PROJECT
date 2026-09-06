import os
import shutil
import tempfile
import unittest

from app.retrieval.bm25_index import PersistentBM25Index


class TestBM25Persistence(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.index = PersistentBM25Index(index_name="test_bm25", persist_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_add_and_search(self):
        self.index.add_document(
            doc_id="ipc_302",
            text="Punishment for murder whoever commits murder shall be punished with death or imprisonment for life.",
            metadata={"act": "Indian Penal Code", "section": "Section 302"}
        )
        self.index.add_document(
            doc_id="ipc_420",
            text="Cheating and dishonestly inducing delivery of property punishable with imprisonment up to seven years.",
            metadata={"act": "Indian Penal Code", "section": "Section 420"}
        )
        self.index.save()

        # Query for murder
        results = self.index.search("murder punishment life", top_k=2)
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0]["id"], "ipc_302")
        self.assertEqual(results[0]["section"], "Section 302")

    def test_persistence_across_instances(self):
        # Add documents and save
        self.index.add_documents_batch(
            doc_ids=["const_21", "crpc_154"],
            documents=[
                "No person shall be deprived of his life or personal liberty except according to procedure established by law.",
                "Information in cognizable cases first information report FIR police officer."
            ],
            metadatas=[
                {"act": "Constitution of India", "section": "Article 21"},
                {"act": "Code of Criminal Procedure", "section": "Section 154"}
            ]
        )

        # Create a new index instance pointing to the same directory
        reloaded_index = PersistentBM25Index(index_name="test_bm25", persist_dir=self.temp_dir)
        self.assertEqual(reloaded_index.count(), 2)

        results = reloaded_index.search("personal liberty", top_k=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "const_21")

    def test_delete_document(self):
        self.index.add_document("doc1", "Arbitration and conciliation act", {"act": "Arbitration"})
        self.assertEqual(self.index.count(), 1)
        
        deleted = self.index.delete_document("doc1")
        self.assertTrue(deleted)
        self.assertEqual(self.index.count(), 0)
        self.assertEqual(len(self.index.search("arbitration")), 0)


if __name__ == "__main__":
    unittest.main()
