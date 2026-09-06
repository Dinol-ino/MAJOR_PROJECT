import unittest
from app.observability.redaction import observability_redactor


class TestObservabilityRedaction(unittest.TestCase):

    def test_sanitize_telemetry_payload_strips_sensitive_text(self):
        raw_payload = {
            "request_id": "req_12345",
            "prompt": "Tell me about Section 302 and secret confidential clause.",
            "document_text": "Confidential internal legal memo with sensitive client data.",
            "total_duration_ms": 120.5,
            "metadata": {
                "query": "Is Aadhaar number 2345-6789-0123 valid?",
                "tokens": 45
            }
        }

        sanitized = observability_redactor.sanitize_telemetry_payload(raw_payload)

        # Raw prompt and document_text must NOT exist in output
        self.assertNotIn("prompt", sanitized)
        self.assertNotIn("document_text", sanitized)
        self.assertIn("prompt_length", sanitized)
        self.assertIn("prompt_hash", sanitized)
        self.assertIn("document_text_length", sanitized)
        self.assertIn("document_text_hash", sanitized)

        # Nested query sanitized
        self.assertNotIn("query", sanitized["metadata"])
        self.assertIn("query_length", sanitized["metadata"])
        self.assertIn("query_hash", sanitized["metadata"])

        # Non-sensitive keys preserved
        self.assertEqual(sanitized["request_id"], "req_12345")
        self.assertEqual(sanitized["total_duration_ms"], 120.5)

    def test_sanitize_log_message_redacts_pii(self):
        msg = "User requested lookup with Aadhaar 2345-6789-0123 and PAN ABCDE1234F."
        clean = observability_redactor.sanitize_log_message(msg)
        self.assertNotIn("2345-6789-0123", clean)
        self.assertNotIn("ABCDE1234F", clean)
        self.assertIn("REDACTED", clean)


if __name__ == "__main__":
    unittest.main()
