import os
from typing import Optional

# pdfplumber will be used for secure text extraction
try:
    import pdfplumber
except ImportError:
    pdfplumber = None

class PDFExtractor:
    def __init__(self, max_size_mb: int = 10, max_pages: int = 100):
        self.max_size_mb = max_size_mb
        self.max_pages = max_pages

    def extract_text(self, file_path: str) -> str:
        """
        Safely extracts plain text from PDF.
        Enforces size limit check.
        """
        # Validate file size
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > self.max_size_mb:
            raise ValueError(f"File exceeds size limit of {self.max_size_mb}MB.")

        if not pdfplumber:
            raise ImportError("pdfplumber is not installed/imported.")

        extracted_text = []
        with pdfplumber.open(file_path) as pdf:
            if len(pdf.pages) > self.max_pages:
                raise ValueError(f"File exceeds page limit of {self.max_pages} pages.")
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    extracted_text.append(text)
        
        return "\n".join(extracted_text)

