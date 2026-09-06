import re
import hashlib
from typing import Dict, Any, Union, List

from app.security.pii_scanner import pii_scanner


class ObservabilityRedactor:
    """
    Confidentiality Redaction Engine for Observability (Phase 11).
    Guarantees:
    - Raw user prompts, document extracts, and sensitive legal text NEVER reach metrics or logs.
    - Captures ONLY structural telemetry: token lengths, character counts, SHA-256 hashes, categories.
    - PII is unconditionally scrubbed from log messages.
    """

    SENSITIVE_KEYS = {
        "prompt", "query", "raw_query", "content", "document_text", "text",
        "raw_answer", "answer", "input_payload", "output_payload", "context"
    }

    def sanitize_telemetry_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively processes a metrics/telemetry dictionary, replacing raw text
        fields with structural representations (length, SHA-256 hash).
        """
        sanitized: Dict[str, Any] = {}
        for k, v in payload.items():
            if k.lower() in self.SENSITIVE_KEYS and isinstance(v, str):
                sanitized[f"{k}_length"] = len(v)
                sanitized[f"{k}_hash"] = hashlib.sha256(v.encode("utf-8")).hexdigest()[:16]
            elif isinstance(v, dict):
                sanitized[k] = self.sanitize_telemetry_payload(v)
            elif isinstance(v, list):
                sanitized[k] = [
                    self.sanitize_telemetry_payload(item) if isinstance(item, dict)
                    else (hashlib.sha256(item.encode()).hexdigest()[:16] if isinstance(item, str) and len(item) > 100 else item)
                    for item in v
                ]
            else:
                sanitized[k] = v
        return sanitized

    def sanitize_log_message(self, message: str) -> str:
        """
        Redacts PII (Aadhaar, PAN, phone, email) from raw log strings.
        """
        if not message:
            return ""
        return pii_scanner.scan_and_redact(message)


observability_redactor = ObservabilityRedactor()
