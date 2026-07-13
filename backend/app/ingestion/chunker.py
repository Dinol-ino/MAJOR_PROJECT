from typing import List, Dict, Any, Optional
from app.retrieval.pageindex import PageIndexBuilder

class SectionAwareChunker:
    """
    Chunks document text by section headers, identifying sections like 'Section 66'
    and tagging each chunk with act/section metadata (PageIndex-style).
    """
    def __init__(self, default_act_name: str = "Document"):
        self.default_act_name = default_act_name
        self.builder = PageIndexBuilder()

    def chunk_document(self, text: str, act_name: Optional[str] = None) -> List[Dict[str, Any]]:
        act = act_name or self.default_act_name
        sections = self.builder.extract_section_headers(text)
        
        if not sections:
            # Fallback to character-based chunking with overlap
            chunk_size = 1000
            overlap = 200
            chunks = []
            text_len = len(text)
            start = 0
            chunk_idx = 1
            while start < text_len:
                end = min(start + chunk_size, text_len)
                chunk_text = text[start:end].strip()
                if chunk_text:
                    chunks.append({
                        "act": act,
                        "section": f"Chunk {chunk_idx}",
                        "text": chunk_text
                    })
                    chunk_idx += 1
                start += chunk_size - overlap
            return chunks if chunks else [{
                "act": act,
                "section": "General",
                "text": text.strip()
            }]
            
        chunks = []
        for sec in sections:
            chunks.append({
                "act": act,
                "section": sec["section"],
                "text": sec["text"]
            })
        return chunks

