import unittest
import time
from app.research.provenance import (
    ProvenanceRecord,
    LegalEvidenceItem,
    validate_provenance_completeness,
    compute_content_hash,
    create_provenance_from_chunk,
)


class TestProvenanceCompleteness(unittest.TestCase):

    def test_complete_provenance_passes_validation(self):
        prov = ProvenanceRecord(
            source_id="ipc_sec_302",
            source_type="statutory_code",
            source_title="Indian Penal Code, 1860",
            source_url="https://indiacode.nic.in/handle/12345",
            jurisdiction="India / Union",
            act="Indian Penal Code",
            section="Section 302",
            document_version="Bare Act 2026",
            publication_date="1860-10-06",
            retrieval_timestamp=time.time(),
            content_hash=compute_content_hash("Whoever commits murder shall be punished with death..."),
            trust_level="OFFICIAL_GAZETTE",
            retrieval_method="local_hybrid_bm25_vector"
        )
        self.assertTrue(validate_provenance_completeness(prov))

    def test_missing_mandatory_field_raises_value_error(self):
        # Empty source_title
        prov = ProvenanceRecord(
            source_id="ipc_sec_302",
            source_type="statutory_code",
            source_title="", # Invalid
            jurisdiction="India / Union",
            act="Indian Penal Code",
            document_version="Bare Act 2026",
            content_hash=compute_content_hash("Some legal text"),
            trust_level="LOCAL_VERIFIED_CORPUS",
            retrieval_method="local_hybrid_bm25_vector"
        )
        with self.assertRaises(ValueError):
            validate_provenance_completeness(prov)

    def test_content_hash_deterministic(self):
        text = "Whoever causes death by doing an act with the intention of causing death..."
        h1 = compute_content_hash(text)
        h2 = compute_content_hash(text)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64) # SHA-256 hex string length

    def test_create_provenance_from_chunk(self):
        chunk = {
            "id": "ipc_sec_300_chunk_1",
            "text": "Except in the cases hereinafter excepted, culpable homicide is murder...",
            "act": "Indian Penal Code",
            "section": "Section 300",
            "metadata": {"jurisdiction": "India / Union", "version": "Bare Act 2026"}
        }
        prov = create_provenance_from_chunk(chunk)
        self.assertEqual(prov.source_id, "ipc_sec_300_chunk_1")
        self.assertEqual(prov.act, "Indian Penal Code")
        self.assertEqual(prov.section, "Section 300")
        self.assertEqual(prov.trust_level, "LOCAL_VERIFIED_CORPUS")
        self.assertTrue(validate_provenance_completeness(prov))


if __name__ == "__main__":
    unittest.main()
