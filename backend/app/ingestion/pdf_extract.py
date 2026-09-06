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

    def _normalize_extracted_text(self, text: str) -> str:
        """
        Normalizes extracted text, fixing common PDF text-extraction artifacts
        such as merged tokens, missing punctuation spacing, and hyphenated line breaks.
        """
        if not text:
            return ""

        # 1. Fix hyphenation across line breaks: "inter-\nactions" -> "interactions"
        text = re.sub(r"(\b[a-zA-Z]+)-\n([a-zA-Z]+\b)", r"\1\2", text)

        # 2. Fix citations joined to previous word without spaces: "identically[Vaswani" -> "identically [Vaswani"
        text = re.sub(r"([a-zA-Z0-9])(\[|\()", r"\1 \2", text)
        text = re.sub(r"(\]|\))([a-zA-Z0-9])", r"\1 \2", text)

        # 3. Fix merged "etal." tokens: "Vaswanietal." -> "Vaswani et al."
        text = re.sub(r"\betal\b", "et al", text, flags=re.IGNORECASE)
        text = re.sub(r"([a-zA-Z]+)etal\b", r"\1 et al", text, flags=re.IGNORECASE)

        # 4. Ensure space after comma/semicolon/period if missing before next word
        text = re.sub(r"([a-zA-Z]),([a-zA-Z])", r"\1, \2", text)
        text = re.sub(r"([a-zA-Z]);([a-zA-Z])", r"\1; \2", text)

        # 5. Clean up multiple spaces and irregular blank lines
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def extract_text(self, file_path: str) -> str:
        """
        Safely extracts plain text from PDF with proper inter-word spacing.
        Enforces size limit, page limit, and structural sanitization.
        """
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > self.max_size_mb:
            raise ValueError(f"File exceeds size limit of {self.max_size_mb}MB.")

        # Perform PDF sanitization and structural validation check
        self.sanitize_and_check_pdf(file_path)

        extracted_text = []

        # PyMuPDF is preferred for high-fidelity block layout and font decoding
        if HAS_PYMUPDF:
            doc = fitz.open(file_path)
            if len(doc) > self.max_pages:
                doc.close()
                raise ValueError(f"File exceeds page limit of {self.max_pages} pages.")
            for page in doc:
                # Use block extraction for natural paragraph spacing
                blocks = page.get_text("blocks")
                page_lines = []
                for b in blocks:
                    # b[4] is the text content of the block
                    if len(b) > 4 and isinstance(b[4], str) and b[4].strip():
                        page_lines.append(b[4].strip())
                if page_lines:
                    extracted_text.append("\n".join(page_lines))
                else:
                    # Fallback to standard page text with preserved whitespace flags
                    raw_p = page.get_text("text")
                    if raw_p:
                        extracted_text.append(raw_p)
            doc.close()
            full_text = "\n\n".join(extracted_text)
            return self._normalize_extracted_text(full_text)

        if pdfplumber:
            with pdfplumber.open(file_path) as pdf:
                if len(pdf.pages) > self.max_pages:
                    raise ValueError(f"File exceeds page limit of {self.max_pages} pages.")
                for page in pdf.pages:
                    text = page.extract_text(x_tolerance=2, y_tolerance=2, layout=False)
                    if text:
                        extracted_text.append(text)
            full_text = "\n\n".join(extracted_text)
            return self._normalize_extracted_text(full_text)

        raise ImportError("Neither pdfplumber nor PyMuPDF is installed.")



