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
    _INTERNAL_SECTION_LABEL = re.compile(r"^\s*(?:chunk|page|part|para(?:graph)?|segment|clause\s+of)\b", re.IGNORECASE)

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

    def _normalize_section(self, s: str) -> str:
        """Normalises a section reference for comparison.

        Evidence chunks store "Section 43A" while the model emits "43A" or "s43A", so the
        plain normaliser compared "section43a" against "43a" and never matched - every
        citation resolved to nothing. Strips a leading section marker from BOTH sides.
        """
        raw = (s or "").strip()
        raw = re.sub(r"^\s*(?:section|sec|§|s)\.?\s*(?=\d)", "", raw, flags=re.IGNORECASE)
        return self._normalize_str(raw)

    def _has_real_section(self, s: str) -> bool:
        """True when a chunk label is a genuine statutory section reference.

        Vault and free-text chunks are labelled with internal positions ("Chunk 3",
        "Page 12") which carry no statutory meaning, so a citation whose section does
        not match them is not evidence of a hallucination. A real section label
        ("166", "43A", "Section 66") is comparable, so a mismatch against it IS a
        hallucination and must stay unresolved.
        """
        raw = (s or "").strip()
        if not raw:
            return False
        if self._INTERNAL_SECTION_LABEL.match(raw):
            return False
        return bool(re.search(r"\d", raw))

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
                norm_sec = self._normalize_section(sec_clean)

                # Two passes. A matching section is the strong signal. When the model's
                # section label differs from the chunk's - a vault chunk is labelled
                # "Chunk 1" while the document text says "Clause 1" - a slug or act match
                # still proves the claim came from that evidence chunk. Previously the
                # elif only ran when the model gave NO section, so a section mismatch left
                # the citation reported as pointing at nothing.
                for chunk in evidence:
                    chunk_sec = self._normalize_section(chunk.get("section", "") or chunk.get("section_no", ""))
                    if norm_sec and chunk_sec and norm_sec == chunk_sec:
                        resolved = True
                        matched_chunk_id = chunk.get("id") or chunk.get("chunk_id")
                        matched_doc_id = chunk.get("doc_id") or chunk.get("document_id")
                        matched_quote = chunk.get("text") or chunk.get("content")
                        if chunk.get("act"):
                            act_display = chunk.get("act")
                        break

                if not resolved and norm_act:
                    for chunk in evidence:
                        # If the model gave a section AND this chunk carries a genuine
                        # statutory section label, the first pass already compared them
                        # and they differed. Falling back to an act match here would
                        # validate a citation to a provision the evidence does not
                        # contain - exactly the hallucination this parser must catch.
                        if norm_sec and self._has_real_section(
                            chunk.get("section", "") or chunk.get("section_no", "")
                        ):
                            continue
                        chunk_act = self._normalize_str(chunk.get("act", "") or chunk.get("act_name", ""))
                        chunk_slug = self._normalize_str(chunk.get("act_slug", "") or "")
                        slug_hit = bool(chunk_slug) and norm_act == chunk_slug
                        act_hit = bool(chunk_act) and (norm_act in chunk_act or chunk_act in norm_act)
                        if slug_hit or act_hit:
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



_PROSE_SECTION = re.compile(r"(?i)\b(?:sections?|secs?\.?|s\.)\s*(\d+[A-Za-z]{0,3})\b")


def unsupported_section_mentions(answer: str, evidence_chunks) -> list:
    """Section numbers the answer names in prose that appear nowhere in the retrieved evidence.

    Citation tokens are verified separately; this catches a fluent "Section 999 provides..." that
    carries no token. A number counts as supported when it is the section label of an evidence
    chunk or is itself referenced ("section N") inside evidence text. Advisory: it feeds a visible
    caution, it does not block.
    """
    if not evidence_chunks:
        return []
    known = set()
    for c in evidence_chunks:
        label = str(c.get("section", "") or c.get("section_no", ""))
        m = re.search(r"(\d+[A-Za-z]{0,3})", label)
        if m and re.match(r"(?i)^\s*(?:section|sec|s|§)?\.?\s*\d", label):
            known.add(m.group(1).upper())
        for n in _PROSE_SECTION.findall(c.get("text", "") or ""):
            known.add(n.upper())
    seen, out = set(), []
    for n in _PROSE_SECTION.findall(answer or ""):
        n = n.upper()
        if n not in known and n not in seen:
            seen.add(n); out.append(n)
    return out

response_parser = ResponseParser()
