from typing import List, Dict, Any

class Tier1LawRetrieval:
    def __init__(self, persist_dir: str):
        self.persist_dir = persist_dir
        # ChromaDB setup placeholder

    def query(self, text: str, top_k: int = 3) -> List[Dict[str, Any]]:
        # Stub implementation returning a list of dicts with keys:
        # "act", "section", "text", "score"
        return [
            {
                "act": "IT Act",
                "section": "66",
                "text": "Section 66: Computer related offences. If any person, dishonestly or fraudulently, does any act referred to in section 43...",
                "score": 0.95
            }
        ]
