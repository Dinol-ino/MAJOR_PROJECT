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

        # Sort by trust_score descending if available
        sorted_chunks = sorted(chunks, key=lambda c: c.get("trust_score", 0.5), reverse=True)

        for chunk in sorted_chunks:
            act = chunk.get("act", "General Law")
            section = chunk.get("section", "General")
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
                    confidence_score=chunk.get("confidence_score")
                )
            )

        return citations
