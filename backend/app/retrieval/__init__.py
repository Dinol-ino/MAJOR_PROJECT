"""
Retrieval Optimization & Hybrid RAG Package (Phase 06).
"""

from app.retrieval.tier1_law import Tier1LawRetrieval, get_shared_chroma_client
from app.retrieval.tier2_user import Tier2UserRetrieval
from app.retrieval.bm25_index import PersistentBM25Index, tier1_bm25_index
from app.retrieval.hybrid_rank import fuse_bm25_dense
from app.retrieval.pageindex import PageIndexBuilder
from app.retrieval.fusion_router import (
    FusionRouter,
    fusion_router,
    deduplicate_chunks,
    filter_superseded_provisions,
    calculate_jaccard_similarity
)
from app.retrieval.metrics import (
    calculate_recall_at_k,
    calculate_precision_at_k,
    calculate_mrr,
    calculate_ndcg_at_k,
    calculate_citation_hit_rate,
    run_benchmark
)

__all__ = [
    "Tier1LawRetrieval",
    "Tier2UserRetrieval",
    "get_shared_chroma_client",
    "PersistentBM25Index",
    "tier1_bm25_index",
    "fuse_bm25_dense",
    "PageIndexBuilder",
    "FusionRouter",
    "fusion_router",
    "deduplicate_chunks",
    "filter_superseded_provisions",
    "calculate_jaccard_similarity",
    "calculate_recall_at_k",
    "calculate_precision_at_k",
    "calculate_mrr",
    "calculate_ndcg_at_k",
    "calculate_citation_hit_rate",
    "run_benchmark",
]
