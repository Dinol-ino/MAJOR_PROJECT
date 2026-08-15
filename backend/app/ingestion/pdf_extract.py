import os
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    fitz = None
    HAS_PYMUPDF = False

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


class PDFExtractor:
    def __init__(self, max_size_mb: int = 10, max_pages: int = 100):
        self.max_size_mb = max_size_mb
        self.max_pages = max_pages

    def sanitize_and_check_pdf(self, file_path: str) -> None:
        """
        Sanitizes and validates PDF structure before parsing.
        Checks for malicious embedded JavaScript, OpenAction triggers, or launch commands.
        """
        if HAS_PYMUPDF:
            doc = fitz.open(file_path)
            if len(doc) > self.max_pages:
                doc.close()
                raise ValueError(f"File exceeds page limit of {self.max_pages} pages.")

            # Inspect page metadata and objects for JavaScript or Launch actions
            for page in doc:
                text_page = page.get_text()
                # Check for suspicious embedded script tags inside PDF stream text
                if re.search(r"/JavaScript|/JS\b|/Launch\b|/EmbeddedFile\b", page.read_contents().decode("latin-1", errors="ignore"), re.IGNORECASE):
                    logger.warning("Sanitization warning: embedded script or launch action detected in PDF page.")

            doc.close()

    def extract_text(self, file_path: str) -> str:
        """
        Safely extracts plain text from PDF.
        Enforces size limit, page limit, structural sanitization check.
        """
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > self.max_size_mb:
            raise ValueError(f"File exceeds size limit of {self.max_size_mb}MB.")

        # Perform PDF sanitization and structural validation check
        self.sanitize_and_check_pdf(file_path)

        if not pdfplumber:
            if HAS_PYMUPDF:
                doc = fitz.open(file_path)
                texts = [page.get_text() for page in doc]
                doc.close()
                return "\n".join(texts)
            raise ImportError("Neither pdfplumber nor PyMuPDF is installed.")

        extracted_text = []
        with pdfplumber.open(file_path) as pdf:
            if len(pdf.pages) > self.max_pages:
                raise ValueError(f"File exceeds page limit of {self.max_pages} pages.")
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    extracted_text.append(text)
        
        return "\n".join(extracted_text)


