import re
import logging
from typing import List, Dict, Any, Optional, Set, Tuple

from app.config import settings
from app.retrieval.hybrid_rank import fuse_bm25_dense
from app.retrieval.pageindex import PageIndexBuilder

logger = logging.getLogger(__name__)

# Statutory & structural regex anchors for deterministic classification
STRUCTURAL_PATTERNS = [
    re.compile(r"(?i)\b(?:section|sec\.|s\.)\s*\d+[a-z]*\b"),
    re.compile(r"(?i)\b(?:article|art\.)\s*\d+[a-z]*\b"),
    re.compile(r"(?i)\b(?:chapter|chap\.)\s+[ivxlcdm\d]+\b"),
    re.compile(r"(?i)\b(?:order|ord\.)\s+[ivxlcdm\d]+\s*(?:rule\s*\d+)?\b"),
    re.compile(r"(?i)\b(?:schedule|sched\.)\s+[ivxlcdm\d]+\b"),
    re.compile(r"(?i)\b(?:clause|sub-clause|sub-section)\s*\d+[a-z]*\b"),
]

SEMANTIC_BROAD_PATTERNS = [
    re.compile(r"(?i)\b(?:what\s+are\s+the\s+rights|procedure\s+for|how\s+to\s+apply|protections\s+for|grounds\s+for|difference\s+between)\b"),
    re.compile(r"(?i)\b(?:remedies\s+available|principles\s+of|jurisprudence|doctrine\s+of)\b"),
]


def calculate_jaccard_similarity(text1: str, text2: str) -> float:
    """Calculates word-token Jaccard similarity between two text snippets."""
    if not text1 or not text2:
        return 0.0
    tokens1: Set[str] = set(re.findall(r"\b\w+\b", text1.lower()))
    tokens2: Set[str] = set(re.findall(r"\b\w+\b", text2.lower()))
    if not tokens1 or not tokens2:
        return 0.0
    intersection = len(tokens1.intersection(tokens2))
    union = len(tokens1.union(tokens2))
    return intersection / union if union > 0 else 0.0


def deduplicate_chunks(
    chunks: List[Dict[str, Any]],
    similarity_threshold: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Deduplicates near-identical chunks (e.g. from bare act vs amendment cross-references).
    Keeps the higher scored chunk when similarity exceeds threshold.
    """
    threshold = similarity_threshold if similarity_threshold is not None else settings.retrieval.dedup_similarity_threshold
    deduped: List[Dict[str, Any]] = []

    for chunk in chunks:
        is_duplicate = False
        chunk_text = chunk.get("text", "")
        for existing in deduped:
            existing_text = existing.get("text", "")
            # Check exact match or high Jaccard overlap
            if chunk_text == existing_text:
                is_duplicate = True
                break
            if calculate_jaccard_similarity(chunk_text, existing_text) >= threshold:
                is_duplicate = True
                break
        
        if not is_duplicate:
            deduped.append(chunk)

    return deduped


def filter_superseded_provisions(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Excludes documents/chunks that have been flagged as superseded in metadata."""
    if not settings.retrieval.exclude_superseded:
        return chunks
    
    valid_chunks = []
    for chunk in chunks:
        meta = chunk.get("metadata", {})
        if not meta:
            # Check root dict if metadata fields are flat
            meta = chunk
        if meta.get("superseded_by") or meta.get("is_superseded"):
            logger.debug(f"Filtering superseded provision: {chunk.get('act')} {chunk.get('section')}")
            continue
        valid_chunks.append(chunk)
    return valid_chunks


class FusionRouter:
    """
    Retrieval Fusion Router (Phase 06).
    Classifies queries to route between:
    - `pageindex`: Structural navigation for specific statutory provisions (Act -> Chapter -> Section).
    - `hybrid`: Cross-corpus semantic retrieval (Dense + Persistent BM25 + RRF).
    - `both`: Multi-hop questions benefiting from structural precision and broad corpus context.
    """

    def __init__(self):
        self.pageindex_builder = PageIndexBuilder()

    def classify_query(self, query: str) -> str:
        """
        Deterministic heuristic classification:
        - structural: contains section, article, chapter numbers.
        - both: contains section number AND broad conceptual query terms.
        - semantic: standard natural language legal queries.
        """
        if not settings.retrieval.fusion_routing_enabled:
            return "hybrid"

        has_structural = any(pattern.search(query) for pattern in STRUCTURAL_PATTERNS)
        has_broad_semantic = any(pattern.search(query) for pattern in SEMANTIC_BROAD_PATTERNS)

        if has_structural and has_broad_semantic:
            return "both"
        elif has_structural:
            return "pageindex"
        else:
            return "hybrid"

    def execute_pageindex_lookup(
        self,
        query: str,
        corpus_documents: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Extracts structural target from query (e.g. 'Section 302') and looks up in PageIndex trees.
        """
        sec_match = re.search(r"(?i)\b(?:section|sec\.|s\.)\s*(\d+[a-z]*)\b", query)
        target_section = sec_match.group(1).upper() if sec_match else None

        if not target_section or not corpus_documents:
            return []

        results = []
        for doc in corpus_documents:
            text = doc.get("text", "")
            act_name = doc.get("act", "General Law")
            tree = self.pageindex_builder.build_tree_from_text(text)
            
            for chap_name, chap_data in tree.get("chapters", {}).items():
                sections = chap_data.get("sections", {})
                for sec_num, sec_content in sections.items():
                    if sec_num.upper() == target_section:
                        results.append({
                            "act": act_name,
                            "section": f"Section {sec_num}",
                            "chapter": chap_name,
                            "text": sec_content,
                            "score": 1.0,  # Exact structural anchor match
                            "retrieval_path": "pageindex",
                            "metadata": doc.get("metadata", {})
                        })
        return results

    def fuse_retrieval(
        self,
        query: str,
        hybrid_results: List[Dict[str, Any]],
        corpus_documents: Optional[List[Dict[str, Any]]] = None,
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Routes query, executes appropriate retrieval path, merges, deduplicates, and filters results.
        """
        k = top_k or settings.retrieval.top_k
        routing_path = self.classify_query(query)

        # Tag hybrid results with retrieval path
        tagged_hybrid = []
        for res in hybrid_results:
            item = res.copy()
            item["retrieval_path"] = "hybrid"
            tagged_hybrid.append(item)

        if routing_path == "pageindex":
            pageindex_hits = self.execute_pageindex_lookup(query, corpus_documents)
            if pageindex_hits:
                # Structural hits take precedence, fall back to hybrid if top_k not filled
                merged = pageindex_hits + [h for h in tagged_hybrid if h not in pageindex_hits]
            else:
                merged = tagged_hybrid
        elif routing_path == "both":
            pageindex_hits = self.execute_pageindex_lookup(query, corpus_documents)
            for hit in pageindex_hits:
                hit["retrieval_path"] = "both"
            for item in tagged_hybrid:
                item["retrieval_path"] = "both"
            merged = pageindex_hits + tagged_hybrid
        else:
            merged = tagged_hybrid

        # Apply superseded filtering
        filtered = filter_superseded_provisions(merged)

        # Apply near-identical deduplication
        deduped = deduplicate_chunks(filtered, similarity_threshold=settings.retrieval.dedup_similarity_threshold)

        return deduped[:k]


fusion_router = FusionRouter()
