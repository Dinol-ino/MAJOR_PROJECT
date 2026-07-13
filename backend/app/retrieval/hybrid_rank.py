from typing import List, Dict, Any

def fuse_bm25_dense(bm25_results: List[Dict[str, Any]], dense_results: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Reciprocal Rank Fusion (RRF) to merge BM25 search results and dense search results.
    Ranks items by scoring function: score = sum(1.0 / (k + rank_i))
    """
    k = 60
    rrf_scores = {}
    chunks_map = {}
    
    # Process BM25 results
    for rank, doc in enumerate(bm25_results):
        key = (doc["act"], doc["section"])
        rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank)
        if key not in chunks_map:
            chunks_map[key] = doc
            
    # Process Dense results
    for rank, doc in enumerate(dense_results):
        key = (doc["act"], doc["section"])
        rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank)
        if key not in chunks_map:
            chunks_map[key] = doc
            
    # Sort by score descending
    sorted_keys = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    
    # Build list of top_k results
    fused_results = []
    for key, score in sorted_keys[:top_k]:
        doc = chunks_map[key].copy()
        doc["score"] = score
        fused_results.append(doc)
        
    return fused_results

