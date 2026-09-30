"""Deterministic "Section N of <Act>" resolution against the indexed statutory corpus.

Ranking (BM25 / dense) is the wrong tool for an exact reference: "Section 138 of the
Negotiable Instruments Act" must return that section, not whichever text scores highest, and
the same number exists in many Acts (IPC s.138 is about soldiers). The Act is resolved from
the query against the titles actually indexed; nothing here contains legal text.
"""
import re
from typing import Any, Dict, List, Optional, Tuple

# Abbreviations that cannot be derived from a title. Values are substrings of the normalised title.
_EXTRA_ALIASES = {
    "crpc": "criminal procedure", "cr.p.c": "criminal procedure", "cr pc": "criminal procedure",
    "ni act": "negotiable instruments", "n.i. act": "negotiable instruments",
    "it act": "information technology", "evidence act": "evidence", "contract act": "contract",
    "cpa": "consumer protection", "dpdp": "digital personal data", "dpdpa": "digital personal data",
    "cpc": "civil procedure", "companies act": "companies",
}
_STOP = {"the", "of", "and", "act", "code"}

_SEC = r"(?:sections?|secs?\.?|s\.|§)\s*(\d+[A-Za-z]{0,3})"
_ACT_PHRASE = r"([A-Za-z][A-Za-z.\s&]{1,80}?(?:Act|Code|Sanhita|Adhiniyam)(?:,?\s*\d{4})?|[A-Za-z][A-Za-z.]{1,8}(?:\s+Act)?)"
_AFTER = re.compile(_SEC + r"\s*(?:of|under|in|,|\()?\s*(?:the\s+)?" + _ACT_PHRASE, re.IGNORECASE)
_BEFORE = re.compile(r"\b([A-Za-z.]{2,8})\s*(?:,)?\s*" + _SEC, re.IGNORECASE)


_ABBR_NUM = re.compile(r"\b(ipc|bnss|bns|bsa|crpc|cpc|dpdpa?)\b\s*,?\s*(?:(?:sections?|secs?\.?|s\.)\s*)?(\d+[A-Za-z]{0,3})\b", re.IGNORECASE)


def _norm(s: str) -> str:
    s = re.sub(r",?\s*\d{4}\b", "", s.lower())
    s = re.sub(r"[^a-z. ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _initials(title: str) -> str:
    return "".join(w[0] for w in re.findall(r"[A-Za-z]+", re.sub(r",?\s*\d{4}", "", title)) if w.lower() not in ("the", "of", "and") and w[0].isupper() or (w.lower() == "of" and False))


def _act_matches(hint: str, act_title: str) -> bool:
    h = _norm(hint).replace(".", "").strip()
    if not h:
        return False
    t = _norm(act_title)
    if h in _EXTRA_ALIASES:
        return _EXTRA_ALIASES[h].replace(".", "") in t.replace(".", "")
    if h in _EXTRA_ALIASES.values() or h.replace(" act", "") in t:
        return True
    if _initials(act_title).lower() == h.replace(" ", ""):
        return True
    words = [w for w in h.split() if w not in _STOP]
    return bool(words) and all(w in t for w in words)


def parse_references(query: str) -> List[Tuple[str, Optional[str]]]:
    """[(section_number, act_hint_or_None)] in query order."""
    refs: List[Tuple[str, Optional[str]]] = []
    for m in _AFTER.finditer(query):
        refs.append((m.group(1).upper(), m.group(2).strip()))
    seen = {r[0] for r in refs}
    for m in re.finditer(_SEC, query, re.IGNORECASE):
        if m.group(1).upper() not in seen:
            refs.append((m.group(1).upper(), None))
    if not refs:
        m = _ABBR_NUM.search(query)
        if m:
            refs.append((m.group(2).upper(), m.group(1)))
    return refs


def lookup(query: str, index, limit: int = 6) -> List[Dict[str, Any]]:
    """Exact chunks for each explicit reference. Empty when the query names no section."""
    out: List[Dict[str, Any]] = []
    for number, hint in parse_references(query):
        matched = []
        for doc_id, text, meta in zip(index.doc_ids, index.documents, index.metadatas):
            if str(meta.get("section", "")).upper().replace("SECTION ", "").strip() != number:
                continue
            if hint and not _act_matches(hint, str(meta.get("act", ""))):
                continue
            matched.append({
                "act": meta.get("act", ""), "section": str(meta.get("section", number)), "text": text,
                "score": 1.0, "doc_type": "statutory_law", "retrieval_path": "structured_lookup",
                "metadata": meta,
            })
        # A hint that matched nothing means the Act is not in the corpus: return nothing rather than
        # a same-numbered section of a different Act.
        out.extend(matched)
    seen, unique = set(), []
    for c in out:
        k = (c["act"], c["section"], c["text"][:40])
        if k not in seen:
            seen.add(k); unique.append(c)
    return unique[:limit]
