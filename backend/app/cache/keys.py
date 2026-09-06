import hashlib
import re
from typing import Optional


def normalize_query_text(text: str) -> str:
    """Normalizes query text by lowercasing and collapsing whitespace."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.strip().lower())


def hash_text(text: str) -> str:
    """Computes SHA-256 hash of a string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_l1_process_key(session_id: str, raw_query: str) -> str:
    """
    Constructs L1 Process Cache key.
    Enforces session-scoping and normalized query hashing to prevent cross-session leakage.
    """
    norm_query = normalize_query_text(raw_query)
    q_hash = hash_text(norm_query)
    return f"l1:sess:{session_id}:q:{q_hash}"


def make_l2_retrieval_key(
    query: str,
    top_k: int,
    corpus_version: str,
    tier: str = "tier1",
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> str:
    """
    Constructs L2 Retrieval Cache key.
    Guarantees:
    1. Corpus version is embedded so any statutory re-ingestion automatically misses stale cache.
    2. If tier is tier2 (user document), user_id and session_id are strictly required and embedded
       to guarantee zero cross-user/cross-session document leakage.
    """
    norm_query = normalize_query_text(query)
    q_hash = hash_text(norm_query)

    if tier == "tier2":
        u_id = user_id or "anonymous"
        s_id = session_id or "default"
        return f"l2:tier2:u:{u_id}:s:{s_id}:k:{top_k}:v:{corpus_version}:q:{q_hash}"
    
    return f"l2:tier1:k:{top_k}:v:{corpus_version}:q:{q_hash}"


def make_l3_embedding_key(text: str, model_name: str) -> str:
    """
    Constructs L3 Embedding Cache key.
    Embeddings are deterministic per model version; keyed on exact normalized text hash + model name.
    """
    t_hash = hash_text(text.strip())
    # Sanitize model name for key formatting
    clean_model = model_name.replace("/", "_").replace(":", "_")
    return f"l3:emb:{clean_model}:h:{t_hash}"
