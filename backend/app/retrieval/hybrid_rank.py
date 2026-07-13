from typing import List, Dict, Any

def fuse_bm25_dense(bm25_results: List[Dict[str, Any]], dense_results: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
    # Stubs for Reciprocal Rank Fusion (RRF) between rank_bm25 results and Chroma dense vector search results.
    # Combines results by score/rank, ensuring section matching gets highly rewarded.
    
    seen = {}
    # Combine lists
    for rank, res in enumerate(bm25_results):
        key = (res["act"], res["section"])
        seen[key] = seen.get(key, 0) + (1.0 / (60 + rank))
        
    for rank, res in enumerate(dense_results):
        key = (res["act"], res["section"])
        seen[key] = seen.get(key, 0) + (1.0 / (60 + rank))
        
    # Sort and return top_k
    sorted_keys = sorted(seen.items(), key=lambda x: x[1], reverse=True)[:top_k]
    
    # Re-map details (for stub just return bm25_results + dense_results)
    combined = []
    for (act, section), score in sorted_keys:
        # find in lists
        item = None
        for x in bm25_results + dense_results:
            if x["act"] == act and x["section"] == section:
                item = x.copy()
                item["score"] = score
                break
        if item:
            combined.append(item)
            
    return combined if combined else bm25_results
