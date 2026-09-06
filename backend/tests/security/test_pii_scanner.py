import unittest
from app.security.pii_scanner import pii_scanner


class TestPIIScanner(unittest.TestCase):

    def test_redact_aadhaar(self):
        text = "Client's Aadhaar number is 5489 1234 8765 submitted for verification."
        redacted = pii_scanner.scan_and_redact(text)
        self.assertNotIn("5489 1234 8765", redacted)
        self.assertIn("<REDACTED_AADHAAR>", redacted)

    def test_redact_pan(self):
        text = "Income tax assessment for PAN ABCDE1234F under review."
        redacted = pii_scanner.scan_and_redact(text)
        self.assertNotIn("ABCDE1234F", redacted)
        self.assertIn("<REDACTED_PAN>", redacted)

    def test_redact_phone_and_email(self):
        text = "Contact counsel at advocate@legalchambers.in or +91 9876543210."
        redacted = pii_scanner.scan_and_redact(text)
        self.assertNotIn("advocate@legalchambers.in", redacted)
        self.assertNotIn("9876543210", redacted)
        self.assertIn("<REDACTED_EMAIL>", redacted)
        self.assertIn("<REDACTED_PHONE>", redacted)

    def test_contains_pii(self):
        self.assertTrue(pii_scanner.contains_pii("My PAN is ABCDE1234F"))
        self.assertFalse(pii_scanner.contains_pii("Section 302 IPC deals with murder."))


if __name__ == "__main__":
    unittest.main()
