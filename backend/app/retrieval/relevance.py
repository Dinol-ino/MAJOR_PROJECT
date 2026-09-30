"""
Query-to-evidence relevance gate.

Ranking functions (BM25+, RRF) always return the "best" chunks even when none of them is
relevant: BM25Plus gives every document a positive score. Sending those chunks to the model
teaches it to answer from unrelated text and produces a citation for a passage that never
supported the answer. This module decides whether a chunk actually shares subject matter
with the query, so an off-topic question ends in an honest "not found in your documents"
instead of a confident answer built on irrelevant pages.

Deliberately lexical and deterministic (no model, no network): it is auditable and works
when no embedding model is installed.
"""
import math
import re
from typing import Iterable, List, Set

from app.retrieval.bm25_index import default_tokenizer

_SUFFIXES = ("ations", "ation", "ions", "ion", "ings", "ing", "ors", "or", "ed", "es", "s")

# "Summarise this document" style requests carry no topical terms by design.
_DOCUMENT_LEVEL = re.compile(
    r"(?i)\b(summar(?:y|ise|ize)|overview|key\s+(?:points|facts|issues|takeaways)|"
    r"what\s+is\s+(?:this|the)\s+(?:document|case|file|judg(?:e)?ment|contract|agreement)\s+about|"
    r"outline|gist|tl;?dr|main\s+(?:points|issues|arguments))\b"
)


def stem(token: str) -> str:
    t = token.lower()
    for suffix in _SUFFIXES:
        if len(t) - len(suffix) >= 4 and t.endswith(suffix):
            t = t[: -len(suffix)]
            break
    return t[:5]


def content_stems(text: str) -> Set[str]:
    return {stem(t) for t in default_tokenizer(text or "") if len(t) >= 3}


def is_document_level_query(query: str) -> bool:
    return bool(_DOCUMENT_LEVEL.search(query or ""))


def term_coverage(query_stems: Set[str], text: str) -> float:
    if not query_stems:
        return 0.0
    return len(query_stems & content_stems(text)) / len(query_stems)


def required_matches(n_terms: int, min_coverage: float) -> int:
    return max(1, math.ceil(n_terms * min_coverage))


def weighted_coverage(query_stems: Set[str], text_stems: Set[str], df: dict, n_docs: int) -> float:
    """Share of the query's *information* present in the text.

    Each term is weighted by inverse document frequency in the corpus being searched. A term
    that appears nowhere in the corpus (e.g. "France" in a set of contracts) carries the
    maximum weight, so missing it sinks the score, while a term found in most passages
    (e.g. "company" in the Companies Act) adds little. Plain term counting cannot make that
    distinction: "capital of France" would match any passage containing "capital".
    """
    def idf(s: str) -> float:
        return math.log((n_docs + 1) / (df.get(s, 0) + 0.5))

    total = sum(idf(s) for s in query_stems)
    if total <= 0:
        return 0.0
    return sum(idf(s) for s in query_stems & text_stems) / total


def supports_query(query: str, text: str, min_coverage: float = 0.34, stats=None) -> bool:
    """True when the chunk shares enough distinctive query terms to be evidence for it.

    ``stats`` is (df, n_docs) from the searched index; without it a plain term-count is used.
    """
    q = content_stems(query)
    if not q:
        return False
    t = content_stems(text)
    if stats is not None and stats[1] > 0:
        return weighted_coverage(q, t, stats[0], stats[1]) >= min_coverage
    return len(q & t) >= required_matches(len(q), min_coverage)


def filter_supported(query: str, chunks: Iterable[dict], min_coverage: float = 0.34, stats=None) -> List[dict]:
    return [c for c in chunks if supports_query(query, c.get("text", ""), min_coverage, stats)]
