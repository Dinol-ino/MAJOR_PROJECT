import re
from typing import List, Dict, Any

class SectionAwareChunker:
    """
    Chunks document text by section headers, identifying sections like 'Section 66'
    and tagging each chunk with act/section metadata (PageIndex-style).
    """
    def __init__(self, default_act_name: str = "Document"):
        self.default_act_name = default_act_name

    def chunk_document(self, text: str, act_name: Optional[str] = None) -> List[Dict[str, Any]]:
        act = act_name or self.default_act_name
        chunks = []
        
        # Simple section header split (e.g., 'Section 66' or 'Sec. 66' or 'CHAPTER IV')
        pattern = r"(?i)(?:Section|Sec\.)\s*(\d+[A-Z]*)"
        
        # Find all occurrences of Section headings
        splits = list(re.finditer(pattern, text))
        
        if not splits:
            # Fallback to single chunk
            return [{
                "act": act,
                "section": "General",
                "text": text.strip()
            }]
            
        for i, match in enumerate(splits):
            section_num = match.group(1)
            start_idx = match.start()
            end_idx = splits[i+1].start() if i + 1 < len(splits) else len(text)
            
            chunk_content = text[start_idx:end_idx].strip()
            chunks.append({
                "act": act,
                "section": section_num,
                "text": chunk_content
            })
            
        return chunks
from typing import Optional
