from typing import List, Dict, Any, Tuple
from app.config import settings

class TokenBudgetManager:
    """
    Manages context token limits dynamically to prevent model context overflow.
    Truncates lowest trust score chunks first.
    """
    def __init__(self, context_limit: int = 4096, max_output_tokens: int = 1024):
        self.max_context = context_limit
        self.safety_margin = settings.TOKEN_BUDGET_SAFETY_MARGIN
        self.max_output = max_output_tokens
        self.available_prompt_tokens = max(512, self.max_context - self.max_output - self.safety_margin)

    def fit_chunks(self, base_prompt_tokens: int, chunks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
        budget_remaining = self.available_prompt_tokens - base_prompt_tokens
        
        if budget_remaining <= 0 or not chunks:
            # Always preserve at least 1 chunk if possible
            return (chunks[:1] if chunks else []), max(0, len(chunks) - 1)

        # Sort chunks by trust score descending
        sorted_chunks = sorted(chunks, key=lambda c: c.get("trust_score", 0.5), reverse=True)
        
        fitted = []
        truncated_count = 0
        used_tokens = 0

        for chunk in sorted_chunks:
            chunk_text = chunk.get("text", "")
            chunk_tokens = len(chunk_text) // 4
            
            if used_tokens + chunk_tokens <= budget_remaining:
                fitted.append(chunk)
                used_tokens += chunk_tokens
            else:
                truncated_count += 1

        # Keep original order for fitted chunks
        fitted_ids = {id(c) for c in fitted}
        final_chunks = [c for c in chunks if id(c) in fitted_ids]
        
        if not final_chunks and chunks:
            final_chunks = chunks[:1]
            truncated_count = len(chunks) - 1

        return final_chunks, truncated_count
