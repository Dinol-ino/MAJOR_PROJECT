import os
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
        self._v4_prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "prompts",
            "legal_system_prompt_v4.md"
        )

    @property
    def system_prompt_template(self) -> str:
        return self._prompt_assembler.get_template()

    def get_v4_system_prompt(self) -> str:
        if os.path.exists(self._v4_prompt_path):
            with open(self._v4_prompt_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        return self.system_prompt_template

    def scan_and_anonymize_pii(self, text: str) -> str:
        if not self.enable_pii_scan:
            return text
        return pii_scanner.scan_and_redact(text)

    def anonymize(self, text: str) -> str:
        return self.scan_and_anonymize_pii(text)

    def strip_instruction_phrases(self, chunk_text: str) -> str:
        return context_sanitizer.sanitize_text(chunk_text, source_type="corpus")

    def build_prompt(
        self,
        question: str,
        retrieved_chunks: List[Dict[str, Any]],
        reasoning_effort: Optional[str] = "off"
    ) -> str:
        """
        Sanitizes retrieved chunks, redacts PII, wraps in <data> tags, and formats with System Prompt v4.
        Applies reasoning_effort modifier according to Spec 03.
        """
        sanitized_chunks = []
        for chunk in retrieved_chunks:
            item = chunk.copy()
            clean_text = self.strip_instruction_phrases(item.get("text", ""))
            item["text"] = self.scan_and_anonymize_pii(clean_text)
            sanitized_chunks.append(item)

        context_data = context_sanitizer.wrap_in_defensive_containers(sanitized_chunks, sanitize_first=False)
        safe_question = self.scan_and_anonymize_pii(question)

        v4_prompt = self.get_v4_system_prompt()

        effort_instruction = ""
        effort = (reasoning_effort or "off").lower()
        if effort == "off":
            effort_instruction = "\nDo not emit <deep_thinking> tags.\n"
        elif effort == "high":
            effort_instruction = "\nYou MUST emit <deep_thinking> reasoning before answering.\n"

        prompt = (
            f"{v4_prompt}\n{effort_instruction}\n\n"
            f"<retrieved_evidence>\n{context_data}\n</retrieved_evidence>\n\n"
            f"User Question: {safe_question}\nAnswer:"
        )
        return prompt
