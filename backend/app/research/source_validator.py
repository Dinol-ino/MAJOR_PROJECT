import logging
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from app.network.mode_enforcer import mode_enforcer, DisallowedDomainError
from app.security.context_sanitizer import context_sanitizer

logger = logging.getLogger(__name__)


class SourceValidator:
    """
    Validates fetched external legal sources before document extraction proceeds (Phase 10).
    Enforces domain allowlists, validates content-types, and sanitizes untrusted content.
    """

    ALLOWED_CONTENT_TYPES = [
        "text/html",
        "application/xhtml+xml",
        "application/json",
        "text/plain",
        "application/pdf",
    ]

    def validate_source(self, url: str, content_type: Optional[str] = None) -> bool:
        """
        Validates target URL against allowlist and checks MIME content type.
        """
        # Validate outbound URL via network mode enforcer
        mode_enforcer.validate_outbound_url(url)

        if content_type:
            clean_ct = content_type.split(";")[0].strip().lower()
            if clean_ct not in self.ALLOWED_CONTENT_TYPES:
                raise ValueError(
                    f"Unsupported content type '{clean_ct}' from '{url}'. "
                    f"Expected legal document formats: {self.ALLOWED_CONTENT_TYPES}"
                )

        return True

    def sanitize_fetched_content(self, raw_content: str, url: str) -> str:
        """
        Runs fetched untrusted web/gazette HTML or text through Phase 07 Context Sanitizer
        to strip prompt injections, script tags, and malicious payloads.
        """
        sanitized = context_sanitizer.sanitize_text(raw_content, source_type="mcp_result")
        return sanitized


source_validator = SourceValidator()
