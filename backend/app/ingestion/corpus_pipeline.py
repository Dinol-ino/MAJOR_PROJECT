import os
import hashlib
import logging
from typing import Dict, Any, Optional, List
from app.ingestion.pdf_extract import PDFExtractor
from app.defense.layer2_trusted_context import Layer2TrustedContext

logger = logging.getLogger(__name__)


class CorpusPipeline:
    def __init__(self, max_size_mb: int = 10, max_pages: int = 100):
        self.pdf_extractor = PDFExtractor(max_size_mb=max_size_mb, max_pages=max_pages)
        self.trusted_context = Layer2TrustedContext(enable_pii_scan=True)
        self._stored_hashes: Dict[str, str] = {}

    def compute_ingestion_hash(self, content_text: str) -> str:
        """Computes SHA-256 hash of normalized text for diff checking."""
        return hashlib.sha256(content_text.strip().encode("utf-8")).hexdigest()

    def process_and_verify(
        self, 
        doc_id: str, 
        raw_text: str, 
        jurisdiction: str = "India", 
        source_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Runs Stage 1 PDF sanitization & PII scanning, computes ingestion_hash,
        and flags diffs for review if content changed without silent overwrites.
        """
        # 1. PII Scan & Anonymize
        sanitized_text = self.trusted_context.scan_and_anonymize_pii(raw_text)

        # 2. Compute Ingestion Hash
        current_hash = self.compute_ingestion_hash(sanitized_text)

        # 3. Diff Check against stored version
        has_diff = False
        previous_hash = self._stored_hashes.get(doc_id)
        if previous_hash and previous_hash != current_hash:
            has_diff = True
            logger.warning(f"Corpus diff detected for {doc_id}! Previous: {previous_hash[:8]}, Current: {current_hash[:8]}. Flagged for review.")

        # Update stored hash
        self._stored_hashes[doc_id] = current_hash

        return {
            "document_id": doc_id,
            "source_url": source_url or "https://indiacode.nic.in",
            "jurisdiction": jurisdiction,
            "ingestion_hash": current_hash,
            "has_diff": has_diff,
            "flagged_for_review": has_diff,
            "sanitized_text": sanitized_text
        }
