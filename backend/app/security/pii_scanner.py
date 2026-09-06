import re
import logging
from typing import List, Dict, Any, Optional

from app.config import settings

logger = logging.getLogger(__name__)

# Fallback regex patterns for Indian and standard PII
AADHAAR_PATTERN = re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")
PAN_PATTERN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
PHONE_PATTERN = re.compile(r"\b(?:\+91[\s-]?)?[6789]\d{9}\b")
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

# Try loading Presidio engines
try:
    from presidio_analyzer import AnalyzerEngine
    from presidio_anonymizer import AnonymizerEngine
    _analyzer = AnalyzerEngine()
    _anonymizer = AnonymizerEngine()
    HAS_PRESIDIO = True
except Exception as e:
    logger.debug(f"Presidio engine not active ({e}); using regex PII scanner.")
    HAS_PRESIDIO = False


class PIIScanner:
    """
    Unconditional Ingestion-Time & Output Defense-in-Depth PII Scanner (Phase 07).
    Detects and redacts Aadhaar, PAN, phone numbers, email addresses, and personal entities.
    """

    def __init__(self, enabled: Optional[bool] = None):
        self.enabled = enabled if enabled is not None else settings.security.enable_pii_scanning

    def scan_and_redact(self, text: str) -> str:
        """
        Scans text and redacts sensitive PII entities unconditionally.
        """
        if not text or not self.enabled:
            return text

        redacted_text = text

        # 1. Presidio Analyzer & Anonymizer if available
        if HAS_PRESIDIO:
            try:
                entities = settings.security.pii_entities
                analyzer_results = _analyzer.analyze(text=redacted_text, entities=entities, language="en")
                if analyzer_results:
                    anonymized = _anonymizer.anonymize(text=redacted_text, analyzer_results=analyzer_results)
                    redacted_text = anonymized.text
            except Exception as err:
                logger.debug(f"Presidio scan error: {err}")

        # 2. Deterministic Indian PII regex patterns (defense in depth)
        redacted_text = AADHAAR_PATTERN.sub("<REDACTED_AADHAAR>", redacted_text)
        redacted_text = PAN_PATTERN.sub("<REDACTED_PAN>", redacted_text)
        redacted_text = PHONE_PATTERN.sub("<REDACTED_PHONE>", redacted_text)
        redacted_text = EMAIL_PATTERN.sub("<REDACTED_EMAIL>", redacted_text)

        # Normalize Presidio generic tags to canonical format
        redacted_text = redacted_text.replace("<EMAIL_ADDRESS>", "<REDACTED_EMAIL>")
        redacted_text = redacted_text.replace("<PHONE_NUMBER>", "<REDACTED_PHONE>")
        redacted_text = redacted_text.replace("<PERSON>", "<REDACTED_PERSON>")

        return redacted_text

    def contains_pii(self, text: str) -> bool:
        """Returns True if any unredacted PII patterns are found in the text."""
        if not text:
            return False
        if AADHAAR_PATTERN.search(text) or PAN_PATTERN.search(text) or EMAIL_PATTERN.search(text):
            return True
        return False


pii_scanner = PIIScanner()
