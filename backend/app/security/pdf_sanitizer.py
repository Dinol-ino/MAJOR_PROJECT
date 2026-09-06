import io
import re
import logging
from typing import Tuple, Optional, Dict, Any

from app.config import settings

logger = logging.getLogger(__name__)

# Suspicious/malicious PDF object keys
MALICIOUS_PDF_PATTERNS = [
    re.compile(b"/JavaScript\b"),
    re.compile(b"/JS\b"),
    re.compile(b"/Launch\b"),
    re.compile(b"/EmbeddedFiles\b"),
    re.compile(b"/AcroForm\b"),
]


class PDFSanitizer:
    """
    Ingestion-time PDF Security Validator & Sanitizer (Phase 07).
    Validates magic bytes, checks for malicious embedded executable objects/scripts,
    enforces page/size quotas, and extracts sanitized text.
    """

    def __init__(
        self,
        max_size_mb: Optional[int] = None,
        max_pages: Optional[int] = None
    ):
        self.max_size_bytes = (max_size_mb or settings.retrieval.max_file_size_mb) * 1024 * 1024
        self.max_pages = max_pages or settings.retrieval.max_file_pages

    def validate_pdf_bytes(self, pdf_bytes: bytes) -> Tuple[bool, Optional[str]]:
        """
        Validates raw PDF bytes before parsing:
        - Check size against max limit
        - Verify %PDF magic header
        - Check for suspicious embedded script objects (/JavaScript, /Launch)
        """
        if not pdf_bytes:
            return False, "Uploaded file is empty."

        if len(pdf_bytes) > self.max_size_bytes:
            return False, f"PDF file size ({len(pdf_bytes) / (1024*1024):.2f} MB) exceeds maximum allowed limit ({self.max_size_bytes / (1024*1024):.1f} MB)."

        # Check %PDF magic byte header in the first 1024 bytes
        if not pdf_bytes[:1024].startswith(b"%PDF"):
            if b"%PDF" not in pdf_bytes[:1024]:
                return False, "Invalid PDF header: Missing %PDF magic identifier."

        # Scan for active content exploits (Launch actions or embedded scripts)
        for pattern in MALICIOUS_PDF_PATTERNS:
            if pattern.search(pdf_bytes):
                logger.warning(f"Malicious or active PDF object detected: {pattern.pattern}")
                # We flag as suspicious but proceed to sanitize on extraction

        return True, None

    def extract_clean_text(self, pdf_bytes: bytes) -> Tuple[str, Dict[str, Any]]:
        """
        Extracts plain text safely using PyMuPDF while ignoring active forms/scripts.
        Enforces page limits.
        """
        is_valid, error = self.validate_pdf_bytes(pdf_bytes)
        if not is_valid:
            raise ValueError(f"PDF Validation Failed: {error}")

        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            total_pages = len(doc)

            if total_pages > self.max_pages:
                doc.close()
                raise ValueError(f"PDF page count ({total_pages}) exceeds maximum allowed limit of {self.max_pages} pages.")

            extracted_text = []
            for page_num in range(total_pages):
                page = doc.load_page(page_num)
                text = page.get_text("text")
                extracted_text.append(text)

            doc.close()
            full_text = "\n\n".join(extracted_text)
            metadata = {
                "total_pages": total_pages,
                "size_bytes": len(pdf_bytes),
                "is_sanitized": True
            }
            return full_text, metadata

        except Exception as exc:
            logger.error(f"Error during PDF text extraction: {exc}")
            raise


pdf_sanitizer = PDFSanitizer()
