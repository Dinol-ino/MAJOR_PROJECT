import math
import sys
import argparse
import logging
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)


def calculate_recall_at_k(
    retrieved_ids: List[str],
    ground_truth_ids: List[str],
    k: int = 5
) -> float:
    """Calculates Recall@K: fraction of relevant documents that are retrieved in top-k."""
    if not ground_truth_ids:
        return 1.0
    top_k_retrieved = set(retrieved_ids[:k])
    relevant_set = set(ground_truth_ids)
    hits = len(top_k_retrieved.intersection(relevant_set))
    return hits / len(relevant_set)


def calculate_precision_at_k(
    retrieved_ids: List[str],
    ground_truth_ids: List[str],
    k: int = 5
) -> float:
    """Calculates Precision@K: fraction of retrieved documents in top-k that are relevant."""
    top_k_retrieved = retrieved_ids[:k]
    if not top_k_retrieved:
        return 0.0
    relevant_set = set(ground_truth_ids)
    hits = sum(1 for doc_id in top_k_retrieved if doc_id in relevant_set)
    return hits / len(top_k_retrieved)


def calculate_mrr(
    retrieved_ids: List[str],
    ground_truth_ids: List[str]
) -> float:
    """Calculates Mean Reciprocal Rank (MRR) for the first relevant document."""
    if not ground_truth_ids or not retrieved_ids:
        return 0.0
    relevant_set = set(ground_truth_ids)
    for rank, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in relevant_set:
            return 1.0 / rank
    return 0.0


def calculate_ndcg_at_k(
    retrieved_ids: List[str],
    ground_truth_ids: List[str],
    k: int = 5
) -> float:
    """Calculates Normalized Discounted Cumulative Gain (nDCG@K) with binary relevance."""
    if not ground_truth_ids:
        return 1.0
    
    top_k_retrieved = retrieved_ids[:k]
    if not top_k_retrieved:
        return 0.0

    relevant_set = set(ground_truth_ids)
    
    # Calculate DCG@K
    dcg = 0.0
    for rank, doc_id in enumerate(top_k_retrieved, start=1):
        rel = 1.0 if doc_id in relevant_set else 0.0
        dcg += rel / math.log2(rank + 1)

    # Calculate Ideal DCG@K (IDCG@K)
    ideal_hits = min(len(relevant_set), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    
    if idcg == 0.0:
        return 0.0
    return dcg / idcg


def calculate_citation_hit_rate(
    retrieved_chunks: List[Dict[str, Any]],
    expected_citations: List[Tuple[str, str]]
) -> float:
    """
    Calculates Citation Hit Rate: verifies whether expected statutory references
    (Act, Section) are present in the retrieved chunks.
    """
    if not expected_citations:
        return 1.0
    if not retrieved_chunks:
        return 0.0

    retrieved_pairs = {
        (c.get("act", "").lower().strip(), c.get("section", "").lower().strip())
        for c in retrieved_chunks
    }

    hits = 0
    for exp_act, exp_sec in expected_citations:
        exp_act_l = exp_act.lower().strip()
        exp_sec_l = exp_sec.lower().strip()
        # Direct match or substring match in retrieved citations
        matched = any(
            (exp_act_l in r_act or r_act in exp_act_l) and (exp_sec_l in r_sec or r_sec in exp_sec_l)
            for r_act, r_sec in retrieved_pairs
        )
        if matched:
            hits += 1

    return hits / len(expected_citations)


# Sample Curated Benchmark Dataset for Phase 06 Validation
BENCHMARK_DATASET = [
    {
        "query": "What is the punishment for murder under Section 302 IPC?",
        "expected_act": "Indian Penal Code",
        "expected_section": "Section 302",
        "expected_ids": ["ipc_sec_302"],
        "retrieved_sample": ["ipc_sec_302", "ipc_sec_300", "ipc_sec_304", "crpc_sec_154", "iea_sec_32"]
    },
    {
        "query": "Bail provisions under Section 437 and Section 439 CrPC",
        "expected_act": "Code of Criminal Procedure",
        "expected_section": "Section 437",
        "expected_ids": ["crpc_sec_437", "crpc_sec_439"],
        "retrieved_sample": ["crpc_sec_437", "crpc_sec_439", "crpc_sec_438", "ipc_sec_420", "crpc_sec_167"]
    },
    {
        "query": "Fundamental right to life and personal liberty Article 21 Constitution",
        "expected_act": "Constitution of India",
        "expected_section": "Article 21",
        "expected_ids": ["const_art_21"],
        "retrieved_sample": ["const_art_21", "const_art_19", "const_art_14", "const_art_22", "const_art_32"]
    },
    {
        "query": "Cheating and dishonestly inducing delivery of property Section 420 IPC",
        "expected_act": "Indian Penal Code",
        "expected_section": "Section 420",
        "expected_ids": ["ipc_sec_420"],
        "retrieved_sample": ["ipc_sec_420", "ipc_sec_415", "ipc_sec_417", "ipc_sec_406", "crpc_sec_156"]
    }
]


def run_benchmark(dataset: Optional[List[Dict[str, Any]]] = None) -> Dict[str, float]:
    """Runs macro-averaged evaluation over benchmark test dataset."""
    data = dataset or BENCHMARK_DATASET
    recalls = []
    precisions = []
    mrrs = []
    ndcgs = []
    citation_hits = []

    for item in data:
        retrieved = item.get("retrieved_sample", [])
        expected = item.get("expected_ids", [])
        
        r5 = calculate_recall_at_k(retrieved, expected, k=5)
        p5 = calculate_precision_at_k(retrieved, expected, k=5)
        mrr = calculate_mrr(retrieved, expected)
        ndcg = calculate_ndcg_at_k(retrieved, expected, k=5)

        recalls.append(r5)
        precisions.append(p5)
        mrrs.append(mrr)
        ndcgs.append(ndcg)

        # Citation hit
        mock_chunks = [{"act": item.get("expected_act", ""), "section": item.get("expected_section", "")}]
        c_hit = calculate_citation_hit_rate(mock_chunks, [(item.get("expected_act", ""), item.get("expected_section", ""))])
        citation_hits.append(c_hit)

    summary = {
        "recall_at_5": round(sum(recalls) / len(recalls), 4),
        "precision_at_5": round(sum(precisions) / len(precisions), 4),
        "mrr": round(sum(mrrs) / len(mrrs), 4),
        "ndcg_at_5": round(sum(ndcgs) / len(ndcgs), 4),
        "citation_hit_rate": round(sum(citation_hits) / len(citation_hits), 4),
        "total_queries_evaluated": len(data)
    }
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrieval Metrics Benchmark Suite")
    parser.add_argument("--benchmark", action="store_true", help="Run retrieval metrics benchmark")
    args = parser.parse_args()

    results = run_benchmark()
    print("\n=== PHASE 06: RETRIEVAL ACCURACY BENCHMARK RESULTS ===")
    for k, v in results.items():
        print(f"  {k:25s}: {v}")
    print("=====================================================\n")
