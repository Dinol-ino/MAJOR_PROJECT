from typing import List, Dict, Any
from app.config import settings
from app.schemas import CitationSource

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
            key = (act.lower(), section.lower())

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
                )
            )

        return citations
