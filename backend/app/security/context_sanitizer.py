import re
import html
import logging
import unicodedata
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Patterns for embedded instructions across corpus, upload, and tool outputs
EMBEDDED_INSTRUCTION_PATTERNS = [
    # --- Existing patterns (Phase 07) ---
    re.compile(r"(?i)\bignore\s+(?:all\s+)?(?:previous|the|prior|earlier|past)?\s*instructions?\b"),
    re.compile(r"(?i)\bSYSTEM\s*:\s*ignore\b"),
    re.compile(r"(?i)\byou\s+are\s+now\s+(?:dan|jailbroken|unrestricted|developer\s+mode)\b"),
    re.compile(r"(?i)\b(?:reveal|output|print|show|dump|leak|disclose|display|repeat|expose)\s+(?:me\s+)?(?:the\s+|your\s+|all\s+|any\s+)?(?:system\s+prompt|secret\s+keys?|initial\s+prompt|hidden\s+prompt|api\s+keys?)\b"),
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


# Characters that render as nothing (or reorder text) and are used to split a keyword so a
# pattern no longer matches while a model still reads it ("ig\u200bnore previous ...").
# ZWNJ/ZWJ (U+200C/D) are meaningful in Indic scripts, so they are only dropped from the
# copy used for matching, never from text that turns out to be clean.
_INVISIBLE_ALWAYS = dict.fromkeys(map(ord, "\u200b\u200e\u200f\u2060\u2061\u2062\u2063\u2064\ufeff\u00ad\u180e"), None)
_INVISIBLE_ALWAYS.update(dict.fromkeys(range(0x202A, 0x202F), None))   # bidi embeddings/overrides
_INVISIBLE_ALWAYS.update(dict.fromkeys(range(0x2066, 0x206A), None))   # bidi isolates
_INVISIBLE_MATCH_ONLY = dict.fromkeys(map(ord, "\u200c\u200d"), None)
# Cyrillic / Greek letters that are visually identical to Latin ones.
_CONFUSABLES = str.maketrans({
    "\u0430": "a", "\u0435": "e", "\u043e": "o", "\u0440": "p", "\u0441": "c", "\u0443": "y",
    "\u0445": "x", "\u0456": "i", "\u0458": "j", "\u0455": "s", "\u04bb": "h", "\u0501": "d",
    "\u03bf": "o", "\u03b1": "a", "\u03b5": "e", "\u03bd": "v", "\u03b9": "i", "\u03c1": "p",
})


def _matching_form(text: str) -> str:
    """Canonical form used only to DETECT instructions: NFKC, no invisibles, confusables folded."""
    t = unicodedata.normalize("NFKC", text.translate(_INVISIBLE_ALWAYS))
    return t.translate(_INVISIBLE_MATCH_ONLY).translate(_CONFUSABLES)


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

        # 0. Evasion-resistant detection. If the canonical form of the text contains an
        #    embedded instruction (split with zero-width characters, written in fullwidth
        #    forms or with look-alike letters) the canonical form is what we sanitise and
        #    return, so the obfuscated original cannot reach the model. Clean text keeps its
        #    original characters (minus always-invisible ones).
        text = text.translate(_INVISIBLE_ALWAYS)
        canonical = _matching_form(text)
        if canonical != text and any(p.search(canonical) and not p.search(text) for p in EMBEDDED_INSTRUCTION_PATTERNS):
            logger.warning("Context Sanitizer detected an obfuscated embedded instruction in %s", source_type)
            text = canonical

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
            # Untrusted text must not be able to close or open our containers. Angle brackets are
            # neutralised (not stripped) so a "</data>" or "</retrieved_evidence>" inside a
            # document is shown to the model as inert text, never as structure.
            text_content = text_content.replace("<", "\u2039").replace(">", "\u203a")
            act = chunk.get("act", "Legal Provision")
            section = chunk.get("section", "General")
            
            # slug is what <citation_protocol> tells the model to copy into [^S:...].
            # It was never rendered, so the model invented one and the citation resolved
            # against nothing. Falls back to the act name when absent.
            slug = chunk.get("act_slug") or chunk.get("vault_doc_id") or act
            block = (
                f'<data slug="{html.escape(str(slug))}" act="{html.escape(str(act))}" '
                f'section="{html.escape(str(section))}">\n'
                f"{text_content}\n"
                f"</data>"
            )
            container_blocks.append(block)

        return "\n\n".join(container_blocks)


context_sanitizer = ContextSanitizer()
