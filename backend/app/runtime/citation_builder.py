from typing import List, Dict, Any
from app.config import settings
from app.schemas import CitationSource

def classify_source_kind(doc_type) -> str:
    if doc_type in ("vault_document", "user_document"):
        return "user_document"
    if doc_type == "mcp_tool_result":
        return "external_source"
    return "statute"


def _as_int(value):
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


class CitationBuilder:
    """
    Builds ground-truth citation sources directly from retrieved chunks.
    Deduplicates by (Act, Section).
    """
    def build(self, chunks: List[Dict[str, Any]]) -> List[CitationSource]:
        seen = set()
        citations = []

        # Keep retrieval rank order; trust score only breaks ties (stable sort).
        sorted_chunks = sorted(chunks, key=lambda c: c.get("trust_score", 0.5), reverse=True)

        for chunk in sorted_chunks:
            meta = chunk.get("metadata") or {}
            act = chunk.get("act") or meta.get("act") or meta.get("filename") or "Unknown source"
            section = str(chunk.get("section") or meta.get("section") or "")
            page_start = _as_int(meta.get("page_start"))
            page_end = _as_int(meta.get("page_end"))
            # Two different passages of one document are distinct citations: key on the
            # document and page as well, so the second passage is not silently dropped.
            key = (act.lower(), section.lower(), meta.get("doc_id"), page_start)

            if key in seen:
                continue
            seen.add(key)

            raw_text = chunk.get("text", "")
            truncated_text = raw_text[:settings.CITATION_TEXT_MAX_CHARS] + ("..." if len(raw_text) > settings.CITATION_TEXT_MAX_CHARS else "")

            citations.append(
                CitationSource(
                    act=act,
                    section=section,
                    text=truncated_text,
                    similarity_score=chunk.get("similarity_score"),
                    trust_score=chunk.get("trust_score"),
                    freshness_score=chunk.get("freshness_score"),
                    injection_risk_score=chunk.get("injection_risk_score"),
                    confidence_score=None,
                    act_slug=meta.get("act_slug") or chunk.get("act_slug"),
                    doc_type=chunk.get("doc_type") or meta.get("doc_type"),
                    source_url=meta.get("source_url") or None,
                    document_version=meta.get("document_version") or None,
                    legal_status=meta.get("legal_status") or None,
                    verified_at=meta.get("verified_at") or None,
                    filename=meta.get("filename") or None,
                    retrieval_score=chunk.get("score"),
                    via=meta.get("via"),
                    source_kind=classify_source_kind(chunk.get("doc_type") or meta.get("doc_type")),
                    doc_id=meta.get("doc_id") or None,
                    page_start=page_start,
                    page_end=page_end if page_end is not None else page_start,
                )
            )

        return citations
