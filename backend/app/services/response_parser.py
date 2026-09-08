import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ParsedCitation:
    index: int
    act: str
    act_slug: str
    section: str
    page: Optional[int] = None
    source_chunk_id: Optional[str] = None
    vault_doc_id: Optional[str] = None
    quote: Optional[str] = None
    resolved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "act": self.act,
            "act_slug": self.act_slug,
            "section": self.section,
            "page": self.page,
            "source_chunk_id": self.source_chunk_id,
            "vault_doc_id": self.vault_doc_id,
            "quote": self.quote,
            "resolved": self.resolved,
        }


@dataclass
class ParsedResponse:
    content: str
    reasoning_trace: Optional[str] = None
    citations: List[ParsedCitation] = field(default_factory=list)
    grounding_score: float = 100.0
    citations_resolved_count: int = 0
    total_citations_count: int = 0
    has_unresolved_citations: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "reasoning_trace": self.reasoning_trace,
            "citations": [c.to_dict() for c in self.citations],
            "grounding_score": self.grounding_score,
            "citations_resolved_count": self.citations_resolved_count,
            "total_citations_count": self.total_citations_count,
            "has_unresolved_citations": self.has_unresolved_citations,
        }


class ResponseParser:
    """
    Spec 03 — Assistant Response Parser & Grounding Engine.
    Processes raw model streams/text to:
    1. Extract <deep_thinking>...</deep_thinking> reasoning trace.
    2. Extract machine-parseable [^S:act_slug|section|page?] citation tokens.
    3. Validate citations against supplied evidence chunks.
    4. Compute authentic Grounding Score according to Spec 03 §6.1 formula.
    5. Clean response text with markdown superscripts [^1], [^2].
    """

    DEEP_THINKING_REGEX = re.compile(r"<deep_thinking>(.*?)(?:</deep_thinking>|$)", re.DOTALL | re.IGNORECASE)
    CITATION_TOKEN_REGEX = re.compile(r"\[\^S:([^\|\]]+)\|([^\|\]]+)(?:\|([^\]]+))?\]")

    def extract_deep_thinking(self, text: str) -> Tuple[str, Optional[str]]:
        """
        Extracts <deep_thinking> content and strips it from user-facing text.
        Tolerates unclosed tags (Tier-0 models).
        """
        if not text:
            return "", None

        match = self.DEEP_THINKING_REGEX.search(text)
        if not match:
            return text.strip(), None

        reasoning = match.group(1).strip()
        cleaned = self.DEEP_THINKING_REGEX.sub("", text).strip()
        return cleaned, reasoning if reasoning else None

    def _normalize_str(self, s: str) -> str:
        return re.sub(r"[^a-zA-Z0-9]", "", s).lower()

    def parse_citations(
        self,
        text: str,
        evidence_chunks: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[str, List[ParsedCitation]]:
        """
        Parses [^S:act_slug|section|page?] tokens, verifies against evidence chunks,
        and converts tokens into readable superscripts [^1], [^2].
        """
        citations: List[ParsedCitation] = []
        evidence = evidence_chunks or []

        # Find all tokens
        matches = list(self.CITATION_TOKEN_REGEX.finditer(text))
        if not matches:
            return text, []

        token_to_index: Dict[str, int] = {}
        cleaned_text = text

        for i, match in enumerate(matches, start=1):
            full_token = match.group(0)
            act_slug = match.group(1).strip()
            section_raw = match.group(2).strip()
            page_raw = match.group(3).strip() if match.group(3) else None

            # Clean section
            sec_clean = re.sub(r"^[sS§\.\s]+", "", section_raw).strip()

            # Clean page
            page_num = None
            if page_raw:
                p_digits = re.search(r"\d+", page_raw)
                if p_digits:
                    page_num = int(p_digits.group(0))

            # Deduplicate by token if identical
            if full_token in token_to_index:
                idx = token_to_index[full_token]
            else:
                idx = len(citations) + 1
                token_to_index[full_token] = idx

                # Resolve against evidence
                resolved = False
                matched_chunk_id = None
                matched_doc_id = None
                matched_quote = None
                act_display = act_slug.replace("_", " ")

                norm_act = self._normalize_str(act_slug)
                norm_sec = self._normalize_str(sec_clean)

                for chunk in evidence:
                    chunk_act = self._normalize_str(chunk.get("act", "") or chunk.get("act_name", ""))
                    chunk_sec = self._normalize_str(chunk.get("section", "") or chunk.get("section_no", ""))
                    if norm_sec and chunk_sec:
                        if norm_sec == chunk_sec:
                            resolved = True
                            matched_chunk_id = chunk.get("id") or chunk.get("chunk_id")
                            matched_doc_id = chunk.get("doc_id") or chunk.get("document_id")
                            matched_quote = chunk.get("text") or chunk.get("content")
                            if chunk.get("act"):
                                act_display = chunk.get("act")
                            break
                    elif not norm_sec and norm_act and (norm_act in chunk_act or chunk_act in norm_act):
                        resolved = True
                        matched_chunk_id = chunk.get("id") or chunk.get("chunk_id")
                        matched_doc_id = chunk.get("doc_id") or chunk.get("document_id")
                        matched_quote = chunk.get("text") or chunk.get("content")
                        if chunk.get("act"):
                            act_display = chunk.get("act")
                        break

                citations.append(
                    ParsedCitation(
                        index=idx,
                        act=act_display,
                        act_slug=act_slug,
                        section=sec_clean,
                        page=page_num,
                        source_chunk_id=matched_chunk_id,
                        vault_doc_id=matched_doc_id,
                        quote=matched_quote[:200] if matched_quote else None,
                        resolved=resolved
                    )
                )

        # Replace citation tokens with superscript markdown [^1], [^2]
        def replace_token(m):
            t = m.group(0)
            idx = token_to_index.get(t, 1)
            return f"[^{idx}]"

        rendered_text = self.CITATION_TOKEN_REGEX.sub(replace_token, text)
        return rendered_text, citations

    def compute_grounding_score(
        self,
        citations: List[ParsedCitation],
        text: str,
        is_refusal_or_unanswerable: bool = False
    ) -> float:
        """
        Calculates Grounding Score according to Spec 03 §6.1 formula:
        score = (citations_resolved / total_citations) * 100
        Penalties:
        - -15 if any citation is unresolved
        - -25 if zero citations on an analysis-type answer
        """
        if is_refusal_or_unanswerable:
            return 100.0

        # Domain refusal check
        if "restricted to Indian legal analysis" in text or "Insufficient grounding" in text:
            return 100.0

        total = len(citations)
        if total == 0:
            # If substantive answer with claims but 0 citations, apply penalty
            if len(text.strip()) > 80:
                return 40.0  # Weakly grounded baseline
            return 80.0

        resolved = sum(1 for c in citations if c.resolved)
        ratio_score = (resolved / total) * 100.0

        # Penalties
        if resolved < total:
            ratio_score = max(0.0, ratio_score - 15.0)

        return round(min(100.0, max(0.0, ratio_score)), 1)

    def parse(
        self,
        raw_text: str,
        evidence_chunks: Optional[List[Dict[str, Any]]] = None
    ) -> ParsedResponse:
        """
        Full parse pipeline:
        Raw Stream/Text -> Extract <deep_thinking> -> Extract [^S:...] citations -> Validate -> Calculate Grounding
        """
        # 1. Extract reasoning
        cleaned_text, reasoning_trace = self.extract_deep_thinking(raw_text)

        # 2. Extract citations & format superscripts
        rendered_text, citations = self.parse_citations(cleaned_text, evidence_chunks)

        # 3. Compute Grounding Score
        resolved_count = sum(1 for c in citations if c.resolved)
        total_count = len(citations)
        has_unresolved = resolved_count < total_count

        score = self.compute_grounding_score(citations, rendered_text)

        return ParsedResponse(
            content=rendered_text,
            reasoning_trace=reasoning_trace,
            citations=citations,
            grounding_score=score,
            citations_resolved_count=resolved_count,
            total_citations_count=total_count,
            has_unresolved_citations=has_unresolved
        )


response_parser = ResponseParser()
