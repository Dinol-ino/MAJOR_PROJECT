import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.citation_graph_service import (
    citation_graph_service,
    DERIVATION_CORPUS_STRUCTURE,
    DERIVATION_TEXT_EXTRACTION,
    DERIVATION_CURATED_LEGAL_RELATIONSHIP,
    DERIVATION_MCP_CASE_LAW_LOOKUP,
    DERIVATION_LLM_SUGGESTED_UNVERIFIED,
    DERIVATION_USER_DOCUMENT_REFERENCE,
    VALID_DERIVATION_METHODS
)
from app.db.engine import get_sync_session
from app.db.models import Statute, StatuteSection, CitationEdge
from app.services.statute_sync import statute_sync_service

client = TestClient(app)


@pytest.fixture(autouse=True)
def seed_statutes_and_graph():
    statute_sync_service.auto_seed_if_empty()
    yield


def test_statute_catalog_coverage_honesty():
    """Task 5.4.1: Statute Library section counts must reflect actually indexed sections vs nominal total."""
    response = client.get("/statutes/catalog")
    assert response.status_code == 200
    data = response.json()
    assert "catalog" in data
    assert data["total_acts"] >= 10

    for item in data["catalog"]:
        assert "nominal_sections_count" in item
        assert "indexed_sections_count" in item
        assert "coverage_display" in item
        assert isinstance(item["indexed_sections_count"], int)
        assert isinstance(item["nominal_sections_count"], int)
        assert item["indexed_sections_count"] <= item["nominal_sections_count"] or item["nominal_sections_count"] > 0

    companies_act = next((s for s in data["catalog"] if "companies" in s["slug"]), None)
    if companies_act:
        assert companies_act["nominal_sections_count"] == 470
        assert companies_act["indexed_sections_count"] >= 3
        assert "sections indexed" in companies_act["coverage_display"]


def test_citation_graph_derivation_methods_and_backend():
    """Task 5.2.1 & 5.2.2: Every graph edge must have an explicit valid derivation_method."""
    response = client.get("/statutes/graph?scope=global")
    assert response.status_code == 200
    data = response.json()

    assert "nodes" in data
    assert "links" in data
    assert "backend_used" in data
    assert data["backend_used"] in ["memgraph", "in_process_sqlite", "in_process_postgres"]

    assert len(data["links"]) > 0
    for link in data["links"]:
        assert "derivation_method" in link
        assert link["derivation_method"] in VALID_DERIVATION_METHODS
        assert "relation" in link
        assert "source" in link
        assert "target" in link

    precedent_links = [l for l in data["links"] if l["derivation_method"] == DERIVATION_MCP_CASE_LAW_LOOKUP]
    assert len(precedent_links) > 0


def test_graph_growth_from_chat_citation():
    """Task 5.3.1: A chat citation for a previously-absent section creates a new graph node and increments cited_in_conversations."""
    conv_id = f"test_growth_conv_{uuid.uuid4().hex[:8]}"
    msg_id = f"test_msg_{uuid.uuid4().hex[:8]}"
    test_sec_num = f"999_{uuid.uuid4().hex[:4]}"

    citations = [
        {
            "act": "Information Technology Act, 2000",
            "act_slug": "it_act_2000",
            "section": test_sec_num,
            "heading": "Special Quantum Cyber Encryption Offence",
            "raw_text": "Whoever uses unauthorized quantum keys shall be punished with imprisonment up to five years and fine."
        }
    ]

    edges_added = citation_graph_service.record_citations(
        conversation_id=conv_id,
        message_id=msg_id,
        citations=citations
    )
    assert edges_added >= 2

    graph_res = citation_graph_service.get_graph(scope="conversation", conversation_id=conv_id)
    assert graph_res["empty_state"] is False
    assert len(graph_res["nodes"]) >= 2

    sec_node = next((n for n in graph_res["nodes"] if f"section:it_act_2000:{test_sec_num}" in n["id"]), None)
    assert sec_node is not None
    assert sec_node["cited_in_conversations"] >= 1
    assert sec_node["label"] == f"Section {test_sec_num}"

    pen_edge = next((l for l in graph_res["links"] if l["relation"] == "penalizes_with"), None)
    assert pen_edge is not None
    assert pen_edge["derivation_method"] == DERIVATION_TEXT_EXTRACTION


def test_user_document_reference_edge_distinction():
    """Task 5.3.2: Citations from user uploaded matter are tagged with derivation_method=user_document_reference."""
    conv_id = f"test_user_doc_conv_{uuid.uuid4().hex[:8]}"
    doc_id = f"doc_{uuid.uuid4().hex[:8]}"

    citations = [
        {
            "act": "Indian Contract Act, 1872",
            "act_slug": "contract_act_1872",
            "section": "73",
            "heading": "Compensation for loss or damage"
        }
    ]

    edges_added = citation_graph_service.record_citations(
        conversation_id=conv_id,
        message_id=doc_id,
        citations=citations,
        is_user_document=True
    )
    assert edges_added >= 2

    graph_res = citation_graph_service.get_graph(scope="conversation", conversation_id=conv_id)
    user_edges = [l for l in graph_res["links"] if l["derivation_method"] == DERIVATION_USER_DOCUMENT_REFERENCE]
    assert len(user_edges) > 0
    assert user_edges[0]["is_user_document"] is True


def test_co_citation_unverified_tagging():
    """Task 5.2.1: Inter-section co-citations generated by LLM reasoning are tagged llm_suggested_unverified."""
    conv_id = f"test_cocite_conv_{uuid.uuid4().hex[:8]}"
    msg_id = f"test_msg_{uuid.uuid4().hex[:8]}"

    citations = [
        {"act_slug": "it_act_2000", "section": "66", "act": "Information Technology Act, 2000"},
        {"act_slug": "companies_act_2013", "section": "166", "act": "Companies Act, 2013"}
    ]

    citation_graph_service.record_citations(
        conversation_id=conv_id,
        message_id=msg_id,
        citations=citations
    )

    graph_res = citation_graph_service.get_graph(scope="conversation", conversation_id=conv_id)
    cocite_edge = next((l for l in graph_res["links"] if l["relation"] == "co_cited_in_claim"), None)
    assert cocite_edge is not None
    assert cocite_edge["derivation_method"] == DERIVATION_LLM_SUGGESTED_UNVERIFIED
    assert cocite_edge["is_unverified"] is True


def test_graph_node_neighborhood_expansion():
    """Verify expand_node endpoint returns typed links and derivation methods."""
    res = client.post("/statutes/graph/expand", json={"node_id": "section:it_act_2000:66", "depth": 1})
    assert res.status_code == 200
    data = res.json()
    assert "nodes" in data
    assert "links" in data
    if data["links"]:
        for l in data["links"]:
            assert "derivation_method" in l
