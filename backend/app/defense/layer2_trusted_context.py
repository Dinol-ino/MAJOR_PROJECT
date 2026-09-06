import logging
from typing import List, Dict, Any, Optional

from app.security.context_sanitizer import context_sanitizer
from app.security.pii_scanner import pii_scanner
from app.prompts.assembler import prompt_assembler
from app.config import settings

logger = logging.getLogger(__name__)


class Layer2TrustedContext:
    """
    Layer 2 Trusted Context (Phase 07 Bridge).
    Delegates to ContextSanitizer and PIIScanner.
    """

    def __init__(self, enable_pii_scan: Optional[bool] = None):
        self.enable_pii_scan = enable_pii_scan if enable_pii_scan is not None else settings.security.enable_pii_scanning
        self._prompt_assembler = prompt_assembler

    @property
    def system_prompt_template(self) -> str:
        return self._prompt_assembler.get_template()

    def scan_and_anonymize_pii(self, text: str) -> str:
        if not self.enable_pii_scan:
            return text
        return pii_scanner.scan_and_redact(text)

    def anonymize(self, text: str) -> str:
        return self.scan_and_anonymize_pii(text)

    def strip_instruction_phrases(self, chunk_text: str) -> str:
        return context_sanitizer.sanitize_text(chunk_text, source_type="corpus")

    def build_prompt(self, question: str, retrieved_chunks: List[Dict[str, Any]]) -> str:
        """
        Sanitizes retrieved chunks, redacts PII, wraps in <data> tags, and formats with system prompt.
        """
        sanitized_chunks = []
        for chunk in retrieved_chunks:
            item = chunk.copy()
            clean_text = self.strip_instruction_phrases(item.get("text", ""))
            item["text"] = self.scan_and_anonymize_pii(clean_text)
            sanitized_chunks.append(item)

        context_data = context_sanitizer.wrap_in_defensive_containers(sanitized_chunks, sanitize_first=False)
        safe_question = self.scan_and_anonymize_pii(question)
        return self.system_prompt_template.format(context_data=context_data, question=safe_question)
