import unittest
from app.security.pdf_sanitizer import pdf_sanitizer, PDFSanitizer


class TestPDFSanitizer(unittest.TestCase):

    def setUp(self):
        self.sanitizer = PDFSanitizer(max_size_mb=5, max_pages=10)

    def test_invalid_header_rejection(self):
        fake_pdf = b"This is not a PDF file at all."
        is_valid, error = self.sanitizer.validate_pdf_bytes(fake_pdf)
        self.assertFalse(is_valid)
        self.assertIn("Missing %PDF magic identifier", error)

    def test_oversized_file_rejection(self):
        oversized = b"%PDF-1.4 " + (b"0" * (6 * 1024 * 1024))
        is_valid, error = self.sanitizer.validate_pdf_bytes(oversized)
        self.assertFalse(is_valid)
        self.assertIn("exceeds maximum allowed limit", error)

    def test_valid_pdf_header_passes(self):
        valid_header = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< >>\n%%EOF"
        is_valid, error = self.sanitizer.validate_pdf_bytes(valid_header)
        self.assertTrue(is_valid)
        self.assertIsNone(error)


if __name__ == "__main__":
    unittest.main()
