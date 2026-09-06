import re
import html
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Patterns for embedded instructions across corpus, upload, and tool outputs
EMBEDDED_INSTRUCTION_PATTERNS = [
    # --- Existing patterns (Phase 07) ---
    re.compile(r"(?i)\bignore\s+(?:all\s+)?(?:previous|the|prior|earlier|past)?\s*instructions?\b"),
    re.compile(r"(?i)\bSYSTEM\s*:\s*ignore\b"),
    re.compile(r"(?i)\byou\s+are\s+now\s+(?:dan|jailbroken|unrestricted|developer\s+mode)\b"),
    re.compile(r"(?i)\b(?:reveal|output|print|show|dump)\s+(?:system\s+prompt|secret\s+key|initial\s+prompt)\b"),
    re.compile(r"(?i)\bforget\s+(?:everything|all\s+rules|your\s+instructions)\b"),
    re.compile(r"(?i)\brespond\s+only\s+with\s+(?:the\s+following|'yes'|'no'|pwned)\b"),
    re.compile(r"(?i)<\s*/?\s*(?:system|instruction|prompt|secret)\s*>"),
    re.compile(r"(?i)\[\s*/?\s*(?:system|inst|sys)\s*\]"),
    re.compile(r"(?i)<<\s*sys\s*>>"),

    # --- Phase 12 additions: ADMIN/OVERRIDE/AI-DIRECTIVE in tool/retrieved content ---
    re.compile(r"(?i)\bADMIN\s*(?:INSTRUCTION|OVERRIDE|COMMAND|DIRECTIVE)\b"),
    re.compile(r"(?i)\bSECURITY\s+BYPASS\s+TOKEN\b"),
    re.compile(r"(?i)\bAI[\s_-]?(?:OVERRIDE|DIRECTIVE|COMMAND)\b"),
    re.compile(r"(?i)\b(?:new|updated?)\s+system\s+directive\b"),
    re.compile(r"(?i)\bNOTE\s+TO\s+(?:AI|MODEL|SYSTEM)\s*[:\-]"),
    re.compile(r"(?i)\b(?:authorized|official)\s+backdoor\b"),
    re.compile(r"(?i)\bALL\s+RESTRICTIONS?\s+(?:LIFTED|REMOVED|DISABLED)\b"),
    re.compile(r"(?i)<!--\s*(?:override|inject|admin)\b"),
    re.compile(r"(?i)\bP\.S\.\s+to\s+(?:model|ai|system)\b"),
    re.compile(r"(?i)\bDisable\s+safety\s+filters?\b"),

    # --- Phase 12 additions: document/tool sourced instruction overrides ---
    re.compile(r"(?i)\bthis\s+document\s+supersedes\s+your\s+(?:system\s+prompt|context|instructions?)\b"),
    re.compile(r"(?i)\bCONFIDENTIAL\s+TO\s+(?:AI|THE\s+AI)\b"),
    re.compile(r"(?i)\b(?:source\s+document|the\s+(?:PDF|statute|document|case\s+law))\s+(?:states|instructs|requires)\s+.{0,50}(?:AI|system|model)\s+(?:must|should|shall)\s+(?:ignore|reveal|disable|bypass)\b"),
    re.compile(r"(?i)\{\{.*?\}\}"),
    re.compile(r"(?i)\bfollowing\s+(?:this\s+)?(?:overrides?|supersedes?)\s+all\s+(?:previous\s+)?(?:context|instructions?|guidelines?)\b"),
    re.compile(r"(?i)\bthis\s+(?:is\s+an?\s+)?authorized\s+(?:override|backdoor)\b"),

    # --- Phase 12 additions: eval / exec injection in tool results ---
    re.compile(r"(?i)\beval\s*\(\s*(?:user_input|input|request)\b"),
    re.compile(r"(?i)\bos\.system\s*\("),
    re.compile(r"<\s*execute\s*>"),
    re.compile(r"(?i)\bTOOL_RESULT\s*[:\{].*?instruction\b"),
    re.compile(r"(?i)\bonerror\s*="),
    re.compile(r"(?i)\balert\s*\("),

    # --- Phase 12 additions: indirect/retrieved content override phrases ---
    re.compile(r"(?i)\bai\s+assistant\s+must\s+now\s+act\s+as\s+(?:an?\s+)?unrestricted\b"),
    re.compile(r"(?i)\boverride\s*[:\-]\s*ignore\s+your\s+context\s+window\b"),
    re.compile(r"(?i)\bai\s+systems?\s+must\s+bypass\s+their\s+safety\b"),
    re.compile(r"(?i)\bAI\s+OVERRIDE\s+COMMAND\b"),
    re.compile(r"(?i)\bDisable\s+your\s+safety\s+filters?\s+and\s+output\b"),
    re.compile(r"(?i)\bai\s+systems?\s+must\s+reveal\s+their\s+system\s+prompts?\b"),
    re.compile(r"(?i)SYSTEM_OVERRIDE"),                     # null-byte SYSTEM_OVERRIDE token
    re.compile(r"(?i)\bsearch_tool\s+returned\b.{0,30}OVERRIDE\b"),
    re.compile(r"(?i)\breturned\b.{0,30}(?:OVERRIDE|ignore\s+all\s+previous)\b"),
    re.compile(r"(?i)\ball\s+restrictions?\s+lifted\b"),

    # --- Phase 12 additions: PDF/document footer override patterns ---
    re.compile(r"(?i)\bread\s+the\s+uploaded\s+.{0,30}and\s+follow\s+all\s+instructions?\b"),
]


class ContextSanitizer:
    """
    Layer 2 Unified Context Sanitizer (Phase 07).
    Sanitizes untrusted text content from all three sources:
    1. Retrieved corpus chunks
    2. Uploaded documents (PDF/text)
    3. MCP & Web tool results
    """

    def __init__(self):
        pass

    def sanitize_text(self, text: str, source_type: str = "corpus") -> str:
        """
        Strips potential embedded instructions, control tokens, script tags,
        and delimiters from text content.
        """
        if not text:
            return ""

        # 1. Strip script tags specifically
        clean_text = re.sub(
            r"(?i)<\s*script\b[^>]*>.*?<\s*/\s*script\s*>",
            "[STRIPPED_SCRIPT]",
            text,
            flags=re.DOTALL
        )

        # 2. Strip active HTML elements and tags with handlers
        clean_text = re.sub(
            r"(?i)<\s*(?:img|iframe|object|embed|svg|style|b|a|div|span)\b[^>]*>.*?<\s*/\s*(?:img|iframe|object|embed|svg|style|b|a|div|span)\s*>",
            "[STRIPPED_HTML_ELEMENT]",
            clean_text,
            flags=re.DOTALL
        )
        clean_text = re.sub(
            r"(?i)<\s*(?:img|iframe|object|embed|svg|style|link|meta)\b[^>]*\/?>",
            "[STRIPPED_HTML_ELEMENT]",
            clean_text
        )


        # 2. Strip prompt injections & control tokens
        for pattern in EMBEDDED_INSTRUCTION_PATTERNS:
            if pattern.search(clean_text):
                logger.warning(f"Context Sanitizer stripped embedded pattern ({pattern.pattern[:30]}...) from {source_type}")
                clean_text = pattern.sub("[STRIPPED_UNTRUSTED_INSTRUCTION]", clean_text)

        return clean_text.strip()


    def sanitize_chunks(
        self,
        chunks: List[Dict[str, Any]],
        source_type: str = "retrieved_corpus"
    ) -> List[Dict[str, Any]]:
        """Sanitizes a list of document chunks."""
        sanitized = []
        for chunk in chunks:
            item = chunk.copy()
            raw_text = item.get("text", "")
            item["text"] = self.sanitize_text(raw_text, source_type=source_type)
            sanitized.append(item)
        return sanitized

    def wrap_in_defensive_containers(
        self,
        chunks: List[Dict[str, Any]],
        sanitize_first: bool = True
    ) -> str:
        """
        Wraps chunks in strict <data act="..." section="..."> containers for safe prompt construction.
        """
        container_blocks = []
        for chunk in chunks:
            raw_text = chunk.get("text", "")
            text_content = self.sanitize_text(raw_text, source_type="corpus") if sanitize_first else raw_text
            act = chunk.get("act", "Legal Provision")
            section = chunk.get("section", "General")
            
            block = (
                f'<data act="{html.escape(str(act))}" section="{html.escape(str(section))}">\n'
                f"{text_content}\n"
                f"</data>"
            )
            container_blocks.append(block)

        return "\n\n".join(container_blocks)


context_sanitizer = ContextSanitizer()
