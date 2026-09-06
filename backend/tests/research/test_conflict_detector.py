import unittest
import time
from app.research.conflict_detector import conflict_detector, ConflictType, ConflictRecord
from app.research.provenance import (
    ProvenanceRecord,
    LegalEvidenceItem,
    compute_content_hash,
)


class TestConflictDetector(unittest.TestCase):

    def test_repeal_status_conflict_detected(self):
        # Local corpus says section is in force
        local_prov = ProvenanceRecord(
            source_id="ipc_309_loc",
            source_type="statutory_code",
            source_title="Indian Penal Code, 1860",
            jurisdiction="India / Union",
            act="Indian Penal Code",
            section="Section 309",
            document_version="Bare Act 2020",
            content_hash=compute_content_hash("Whoever attempts to commit suicide..."),
            trust_level="LOCAL_VERIFIED_CORPUS",
            retrieval_method="local_hybrid_bm25_vector"
        )
        local_item = LegalEvidenceItem(
            text="Section 309: Whoever attempts to commit suicide and does any act towards the commission...",
            provenance=local_prov
        )

        # Online source indicates section has been superseded / omitted / repealed
        online_prov = ProvenanceRecord(
            source_id="mhc_309_on",
            source_type="gazette_notification",
            source_title="Mental Healthcare Act Gazette",
            source_url="https://egazette.gov.in",
            jurisdiction="India / Union",
            act="Indian Penal Code",
            section="Section 309",
            document_version="Gazette Notification 2024",
            content_hash=compute_content_hash("Section 309 effectively omitted / repealed via Mental Healthcare Act Section 115"),
            trust_level="OFFICIAL_GAZETTE",
            retrieval_method="allowlisted_online_fetch"
        )
        online_item = LegalEvidenceItem(
            text="Section 309 IPC has been effectively repealed and omitted by Section 115 of the Mental Healthcare Act.",
            provenance=online_prov
        )

        conflicts = conflict_detector.detect_conflicts([local_item], [online_item])
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].conflict_type, ConflictType.STATUS_CONFLICT)
        self.assertIn("repealed or superseded", conflicts[0].description)

    def test_bns_replacement_conflict_detected(self):
        local_prov = ProvenanceRecord(
            source_id="ipc_420_loc",
            source_type="statutory_code",
            source_title="Indian Penal Code",
            jurisdiction="India / Union",
            act="Indian Penal Code",
            section="Section 420",
            document_version="Bare Act 2022",
            content_hash=compute_content_hash("Cheating and dishonestly inducing delivery of property"),
            trust_level="LOCAL_VERIFIED_CORPUS",
            retrieval_method="local_hybrid_bm25_vector"
        )
        local_item = LegalEvidenceItem(
            text="Section 420: Cheating and dishonestly inducing delivery of property.",
            provenance=local_prov
        )

        online_prov = ProvenanceRecord(
            source_id="bns_318_on",
            source_type="gazette_notification",
            source_title="Bharatiya Nyaya Sanhita Gazette",
            source_url="https://egazette.gov.in",
            jurisdiction="India / Union",
            act="Indian Penal Code",
            section="Section 420",
            document_version="BNS 2023 Gazette",
            content_hash=compute_content_hash("Bharatiya Nyaya Sanhita Section 318 replaces IPC Section 420"),
            trust_level="OFFICIAL_GAZETTE",
            retrieval_method="allowlisted_online_fetch"
        )
        online_item = LegalEvidenceItem(
            text="Under the Bharatiya Nyaya Sanhita (BNS), 2023, the offense of cheating is codified under Section 318.",
            provenance=online_prov
        )

        conflicts = conflict_detector.detect_conflicts([local_item], [online_item])
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].conflict_type, ConflictType.AMENDMENT_OVERWRITE)

    def test_consistent_provisions_produce_no_conflicts(self):
        local_prov = ProvenanceRecord(
            source_id="ipc_302_loc",
            source_type="statutory_code",
            source_title="Indian Penal Code",
            jurisdiction="India / Union",
            act="Indian Penal Code",
            section="Section 302",
            document_version="Bare Act",
            content_hash=compute_content_hash("Punishment for murder"),
            trust_level="LOCAL_VERIFIED_CORPUS",
            retrieval_method="local_hybrid_bm25_vector"
        )
        local_item = LegalEvidenceItem(text="Section 302: Punishment for murder.", provenance=local_prov)

        online_prov = ProvenanceRecord(
            source_id="ipc_302_on",
            source_type="statutory_code",
            source_title="Indian Penal Code",
            jurisdiction="India / Union",
            act="Indian Penal Code",
            section="Section 302",
            document_version="IndiaCode Portal",
            content_hash=compute_content_hash("Section 302: Punishment for murder is death or imprisonment for life."),
            trust_level="AUTHORITATIVE_PORTAL",
            retrieval_method="allowlisted_online_fetch"
        )
        online_item = LegalEvidenceItem(text="Section 302: Punishment for murder is death or imprisonment for life.", provenance=online_prov)

        conflicts = conflict_detector.detect_conflicts([local_item], [online_item])
        self.assertEqual(len(conflicts), 0)


if __name__ == "__main__":
    unittest.main()
