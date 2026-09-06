from typing import List, Dict, Any, Optional
from app.config import settings

def fuse_bm25_dense(
    bm25_results: List[Dict[str, Any]], 
    dense_results: List[Dict[str, Any]], 
    top_k: Optional[int] = None,
    k_constant: Optional[int] = None,
    min_score_threshold: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Reciprocal Rank Fusion (RRF) to merge BM25 search results and dense search results.
    Ranks items by scoring function: score = sum(1.0 / (k + rank_i))
    Filters out chunks with weak relevance or missing document content.
    """
    k = k_constant if k_constant is not None else settings.retrieval.rrf_k
    target_top_k = top_k if top_k is not None else settings.retrieval.top_k
    rrf_scores = {}
    chunks_map = {}
    
    # Process BM25 results
    for rank, doc in enumerate(bm25_results):
        key = (doc.get("act", "General"), doc.get("section", "General"), doc.get("text", "")[:50])
        rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank)
        if key not in chunks_map:
            chunks_map[key] = doc
            
    # Process Dense results (filter out negative/zero similarity if present)
    for rank, doc in enumerate(dense_results):
        dense_score = doc.get("score", 1.0)
        # If dense score is very low (< 0.2) and not in BM25, skip irrelevant chunk
        if dense_score < 0.20 and doc.get("act") not in [b.get("act") for b in bm25_results]:
            continue
        key = (doc.get("act", "General"), doc.get("section", "General"), doc.get("text", "")[:50])
        rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank)
        if key not in chunks_map:
            chunks_map[key] = doc
            
    # Sort by score descending
    sorted_keys = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    
    # Build list of top_k results
    fused_results = []
    for key, score in sorted_keys[:target_top_k]:
        doc = chunks_map[key].copy()
        doc["score"] = score
        if "doc_type" not in doc:
            doc["doc_type"] = doc.get("metadata", {}).get("doc_type", "statutory_law")
        fused_results.append(doc)
        
    return fused_results


