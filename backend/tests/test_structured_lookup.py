import pytest

from app.ingestion.statutory_corpus import index_statutory_corpus
from app.retrieval import structured_lookup as sl
from app.retrieval.bm25_index import tier1_bm25_index
from app.retrieval.tier1_law import Tier1LawRetrieval
from app.config import settings


@pytest.fixture(scope="module")
def corpus():
    index_statutory_corpus()
    return tier1_bm25_index


def test_parse_variants():
    assert sl.parse_references("Explain Section 138 of the Negotiable Instruments Act")[0][0] == "138"
    assert sl.parse_references("What is IPC 420?")[0] == ("420", "IPC")
    assert sl.parse_references("Section 420 IPC punishment")[0][0] == "420"
    assert sl.parse_references("what is cheating") == []


def test_same_number_resolves_to_the_named_act(corpus):
    ni = sl.lookup("Explain Section 138 of the Negotiable Instruments Act", corpus)
    assert ni and all("Negotiable" in c["act"] for c in ni)
    assert "Dishonour of cheque" in ni[0]["text"]
    ipc = sl.lookup("Section 138 of the Indian Penal Code", corpus)
    assert ipc and all("Penal" in c["act"] for c in ipc) and "soldier" in ipc[0]["text"]


def test_abbreviations(corpus):
    assert "Cheating" in sl.lookup("What is the punishment under Section 420 IPC?", corpus)[0]["text"]
    assert any("Criminal Procedure" in c["act"] for c in sl.lookup("Section 41 CrPC arrest without warrant", corpus))


def test_unknown_act_returns_nothing_not_a_different_act(corpus):
    assert sl.lookup("Section 138 of the Imaginary Statute Act", corpus) == []


def test_tier1_query_puts_exact_section_first(corpus):
    t1 = Tier1LawRetrieval(persist_dir=settings.CHROMA_PERSIST_DIR)
    r = t1.query("Explain Section 138 of the Negotiable Instruments Act", top_k=5)
    assert "Negotiable" in r[0]["act"] and r[0]["section"].upper().endswith("138")


def test_explicit_reference_drops_same_number_from_other_acts(corpus):
    t1 = Tier1LawRetrieval(persist_dir=settings.CHROMA_PERSIST_DIR)
    r = t1.query("Section 302 IPC", top_k=5)
    assert r[0]["act"] == "The Indian Penal Code"
    assert not [c for c in r if str(c["section"]).upper().replace("SECTION ", "") == "302" and "Penal" not in c["act"]]
